"""硅基动感 (SiBionics / Sisensing) adapter。

从硅基 API 拉取关注者血糖数据，转成内部统一格式（``sgv`` 为 mg/dL int）。
关注者模式，返回全量历史（约 14 天，每 5 分钟一点）。token 需抓包获取
（见 ``docs/sisensing-api.md``）。

硅基每 300s 产出一帧、网格固定，故本 adapter 在基类固定轮询之上覆盖一套
自适应调度（``discovery → steady``）：discovery 每 20s 轮询锁定首个新点的
客户端时刻 → steady 按 ``上次新点时刻 + 300 + 3s`` 预测下次拉取，并以服务器
跨步推进锚点（容忍漏帧、无逐轮漂移）。调度不依赖时差校准；但服务器时间戳与
客户端时钟有偏差，故另观测 ``client−server`` 时差（``_clock_offset_sec``）仅
用于显示"最后更新"补偿。

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

# 自适应调度常量
_DISCOVERY_POLL_SEC = 20  # discovery 轮询间隔(300s 网格内必检到新点)
_FETCH_DELAY_SEC = 3  # 预判新点到达后额外等待的拉取延迟
_MIN_DELAY_SEC = 5  # 下次拉取最小间隔(重试下限,防抖)
_STEADY_MISS_RESET = 10  # steady 连续未见新点达此数 → 回 discovery 重新锁定


class SisensingAdapter(BaseAdapter):
    id = "sisensing"
    name = "硅基动感"
    poll_interval_seconds = 300  # 硅基每 5 分钟一帧

    def __init__(self, adapter_config: dict | None = None):
        super().__init__(adapter_config)
        # 自适应调度状态：discovery(找首个新点) → steady(按 300s 网格预测)
        self._phase = "discovery"
        self._last_latest: int = 0  # 最新数据点时间戳(ms)
        self._last_new_client_time: float = 0.0  # 上次见到新点的客户端时刻(秒)
        self._misses: int = 0  # steady 连续未见新点次数
        self._clock_offset_sec: float = 0.0  # 时钟偏差(秒，client−server)，仅显示补偿
        self._load_state()  # 已锁定网格则直接进 steady

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

    # ---- 自适应拉取调度（按 300s 网格预测，无时差校准）----

    def note_fetch_result(self, entries: list[dict]):
        """每次成功拉取后调用，更新自适应状态机。

        硅基每 300s 产出一帧、网格固定。discovery 短轮询锁定首个新点的客户端
        时刻；steady 据此预测下一帧时刻（+3s 拉取），并按服务器实际跨步推进
        锚点（容忍漏帧、无逐轮漂移）。连续多次未见新点则回 discovery 重新锁定。
        """
        if not entries:
            return
        now = time.time()
        latest = max(e["date"] for e in entries)

        # 首次：仅记基线，进入 discovery 等待首个新点
        if self._last_latest == 0:
            self._last_latest = latest
            self._phase = "discovery"
            return

        is_new = latest > self._last_latest
        prev_latest = self._last_latest
        self._last_latest = latest

        if not is_new:
            # 新点未到（预测偏早或服务器延迟）→ 计数，超限回 discovery
            self._misses += 1
            if self._phase == "steady" and self._misses >= _STEADY_MISS_RESET:
                self._phase = "discovery"
                self._last_new_client_time = 0.0
            return

        # 见到新点
        self._misses = 0
        # 记录时钟偏差(client−server 时间戳)，仅用于显示"最后更新"补偿；
        # steady 阶段 +3s 拉新鲜点，此值稳定，补偿后≈距上次拉取(即距数据产出)
        self._clock_offset_sec = now - latest / 1000.0
        if self._phase == "discovery":
            # 锁定网格：记录客户端时刻（含 ≤20s 检测滞后）
            self._last_new_client_time = now
            self._phase = "steady"
        else:
            # steady：按服务器跨步推进锚点（整 300s 倍数，容忍漏帧且无漂移）
            steps = max(1, round((latest - prev_latest) / 1000 / self.poll_interval_seconds))
            self._last_new_client_time += steps * self.poll_interval_seconds
        self._persist_state()

    def next_poll_delay_sec(self) -> int:
        """返回建议的下次拉取延迟(秒)。"""
        if self._phase == "discovery":
            return _DISCOVERY_POLL_SEC
        # steady：下次拉取 = 上次新点客户端时刻 + 300 + 3s 延迟
        now = time.time()
        delay = (self._last_new_client_time + self.poll_interval_seconds + _FETCH_DELAY_SEC) - now
        return max(_MIN_DELAY_SEC, int(delay))

    # ---- 缓存与持久化（带调度元数据）----

    def save_cache(self, entries: list[dict]):
        """保存 entries 与自适应元数据到 ``data/<id>.json``。"""
        path = self._cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "entries": entries,
                    "phase": self._phase,
                    "last_latest": self._last_latest,
                    "last_new_client_time": self._last_new_client_time,
                    "clock_offset_sec": self._clock_offset_sec,
                },
                f,
                ensure_ascii=False,
            )

    def _persist_state(self):
        """将调度元数据写回已存在的缓存文件（不重写 entries，防 crash 丢失）。"""
        path = self._cache_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data["phase"] = self._phase
            data["last_latest"] = self._last_latest
            data["last_new_client_time"] = self._last_new_client_time
            data["clock_offset_sec"] = self._clock_offset_sec
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except (OSError, json.JSONDecodeError):
            pass

    def _load_state(self):
        """从缓存恢复调度元数据；已锁定网格(有客户端时刻)则直接进 steady。

        旧版基于 offset 的缓存无 ``last_new_client_time``，视为未锁定 → 回
        discovery 重新校准（offset 不可靠，见 git history）。
        """
        path = self._cache_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self._last_latest = int(d.get("last_latest", 0))
            self._clock_offset_sec = float(d.get("clock_offset_sec", 0.0))
            t = float(d.get("last_new_client_time", 0.0))
            if d.get("phase") == "steady" and t > 0:
                self._phase = "steady"
                self._last_new_client_time = t
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            pass


def _to_int(v) -> int:
    """安全转 int（容忍字符串数字与 None→0）。"""
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return 0
