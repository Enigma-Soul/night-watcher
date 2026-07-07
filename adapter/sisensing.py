"""硅基动感 (SiBionics / Sisensing) adapter。

从硅基 API 拉取关注者血糖数据，转成内部统一格式（``sgv`` 为 mg/dL int）。
关注者模式，返回全量历史（约 14 天，每 5 分钟一点）。token 需抓包获取
（见 ``docs/sisensing-api.md``）。

硅基服务器时间戳与客户端时钟存在偏差，故本 adapter 在基类固定轮询之上
覆盖一套自适应调度（``discovery → wait → probing → steady``）校准时差：
启动后短轮询发现首个新点 → 等 ~290s → 1s 探测窗口捕获下一个新点 →
算出 offset 进入 steady，按 ``服务器新点时刻 + offset + 5s`` 对齐拉取。

本 adapter 仅拉取不上传——上传 NightScout 非本项目核心功能，若日后需要可
由本 adapter 自行扩展，不影响主程序。
"""

from __future__ import annotations

import json
import os
import time

import requests

from libs.base_adapter import BaseAdapter, FetchError

# mmol/L → mg/dL
_MMOLL_TO_MGDL = 18.018

# 硅基 s 值 → Nightscout 方向名（硅基仅 -2..2，无 Double）
_S_TO_DIRECTION = {
    -2: "SingleDown",
    -1: "FortyFiveDown",
    0: "Flat",
    1: "FortyFiveUp",
    2: "SingleUp",
}

# 服务器区域 → URL
_URLS = {
    "CN": "https://api.sisensing.com/follow/app/follow/myself/glucose/details/devices",
    "EU": "https://cgm-ce.sisensing.com/user/app/follow/sharer",  # 未验证，保留
}


class SisensingAdapter(BaseAdapter):
    id = "sisensing"
    name = "硅基动感"
    poll_interval_seconds = 300  # 硅基每 5 分钟一帧

    def __init__(self, adapter_config: dict | None = None):
        super().__init__(adapter_config)
        # 自适应调度状态
        self._phase = "discovery"  # discovery | wait | probing | steady
        self._last_latest: int = 0  # 最新数据点时间戳(ms)
        self._offset: float = 0.0  # 服务器-客户端时差(秒)
        self._wait_until: float = 0.0  # wait 到期时间(客户端秒)
        self._probe_deadline: float = 0.0  # probing 截止时间(客户端秒)
        self._load_offset()  # 已校准则直接进 steady

    def is_configured(self) -> bool:
        return bool(self.config.get("ss_token"))

    def fetch(self) -> list[dict]:
        return self._parse(self._request())

    def _request(self) -> dict:
        token = self.config.get("ss_token", "")
        if not token:
            raise FetchError("硅基 ss_token 未配置", adapter_id=self.id)
        region = str(self.config.get("ss_region", "CN")).upper()
        url = _URLS.get(region, _URLS["CN"])
        headers = {
            "Authorization": f"Bearer {token}",  # 文档要求 Bearer，参考项目漏了
            "User-Agent": "night-watcher",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = int(self.config.get("timeout", 10))
        retries = max(1, int(self.config.get("retries", 3)))
        # CN 区端点直连，绕过系统代理（Clash 会把 CN 域名绕到境外节点并偶发停滞）
        sess = requests.Session()
        sess.trust_env = False
        last_err: Exception | None = None
        for _ in range(retries):
            try:
                r = sess.get(url, headers=headers, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as e:
                last_err = e
        raise FetchError(f"硅基请求失败: {last_err}", adapter_id=self.id)

    def _parse(self, raw: dict) -> list[dict]:
        """解析硅基响应 → entries。纯函数，可离线用 test.json 测试。"""
        if not isinstance(raw, dict):
            raise FetchError("硅基响应非对象", adapter_id=self.id)
        code = raw.get("code")
        if code != 200:
            raise FetchError(f"硅基返回 code={code} msg={raw.get('msg')}", adapter_id=self.id)

        data = raw.get("data") or {}
        gdl = data.get("glucoseDataList", [])
        # 参考项目见过 gdl 为 dict 的情况，统一包成 list
        if isinstance(gdl, dict):
            gdl = [gdl]
        if not isinstance(gdl, list):
            raise FetchError("硅基 glucoseDataList 格式异常", adapter_id=self.id)

        # 设备选择：取 glucoseInfos 非空且 latestGlucoseTime 最大的设备
        # （跳过过期/空设备，避免 test.json 里 glucoseInfos=[] 的设备噪声）
        candidates = [d for d in gdl if isinstance(d, dict) and d.get("glucoseInfos")]
        if not candidates:
            return []
        device = max(candidates, key=lambda d: _to_int(d.get("latestGlucoseTime")))

        entries: list[dict] = []
        for p in device.get("glucoseInfos", []):
            if not isinstance(p, dict):
                continue
            try:
                date = int(p["t"])
                sgv = round(float(p["v"]) * _MMOLL_TO_MGDL)
            except (KeyError, TypeError, ValueError):
                continue
            direction = _S_TO_DIRECTION.get(_to_int(p.get("s")), "None")
            entries.append({"date": date, "sgv": sgv, "direction": direction})
        return entries

    # ---- 自适应拉取调度（服务器-客户端时差校准）----

    def note_fetch_result(self, entries: list[dict]):
        """每次成功拉取后调用，更新自适应状态机。"""
        if not entries:
            return
        now = time.time()
        latest = max(e["date"] for e in entries)

        # 首次调用：用服务器数据设基线
        if self._last_latest == 0:
            self._last_latest = latest
            return

        is_new = latest > self._last_latest
        self._last_latest = latest

        if not is_new:
            return

        if self._phase == "discovery":
            # ① 发现第一个新数据点 → 进入 290s 等待
            self._phase = "wait"
            self._wait_until = now + 290

        elif self._phase == "probing":
            # ④ 探测窗口内捕获新数据 → 得 offset，立即退出并持久化
            self._offset = now - latest / 1000.0
            self._phase = "steady"
            self._persist_offset()

        # steady：offset 已锁定，无需操作

    def next_poll_delay_sec(self) -> int:
        """返回建议的下次拉取延迟(秒)。"""
        now = time.time()

        # probing 超时 → 回 wait，重新走 ③④
        if self._phase == "probing" and now > self._probe_deadline:
            self._phase = "wait"
            self._wait_until = now + 290

        if self._phase == "discovery":
            return 20  # ② 每 20s 一次，至多等 300s

        if self._phase == "wait":
            if now >= self._wait_until:
                self._phase = "probing"
                self._probe_deadline = now + 10  # ④ 含请求共 10s，间隔 1s
                return 1
            return max(1, int(self._wait_until - now))

        if self._phase == "probing":
            return 1

        if self._phase == "steady":
            next_server = self._last_latest / 1000.0 + self.poll_interval_seconds
            next_client = next_server + self._offset + 5
            return max(30, int(next_client - now))

        return 60

    # ---- 缓存与持久化（带时差校准元数据）----

    def save_cache(self, entries: list[dict]):
        """保存 entries 与自适应元数据到 ``data/<id>.json``。"""
        path = self._cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "entries": entries,
                    "offset": self._offset,
                    "phase": self._phase,
                    "last_latest": self._last_latest,
                },
                f,
                ensure_ascii=False,
            )

    def _persist_offset(self):
        """将 offset 写回已存在的缓存文件（不重写 entries，防 crash 丢失）。"""
        path = self._cache_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data["offset"] = self._offset
            data["phase"] = self._phase
            data["last_latest"] = self._last_latest
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except (OSError, json.JSONDecodeError):
            pass

    def _load_offset(self):
        """从缓存文件恢复自适应元数据；已校准直接进 steady。"""
        path = self._cache_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("phase") == "steady" and d.get("offset"):
                self._offset = float(d["offset"])
                self._phase = "steady"
                self._last_latest = int(d.get("last_latest", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            pass


def _to_int(v) -> int:
    """安全转 int（容忍字符串数字与 None→0）。"""
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return 0
