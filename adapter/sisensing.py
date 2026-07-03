"""硅基动感 (SiBionics / Sisensing) adapter。

从硅基 API 拉取关注者血糖数据，转成内部统一格式（``sgv`` 为 mg/dL int）。
关注者模式，返回全量历史（约 14 天，每 5 分钟一点）。token 需抓包获取
（见 ``docs/sisensing-api.md``）。

本 adapter 仅拉取不上传——上传 NightScout 非本项目核心功能，若日后需要可
由本 adapter 自行扩展，不影响主程序。
"""
from __future__ import annotations

import json

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

    def is_configured(self) -> bool:
        return bool(self.config.get("ss_token")) or bool(self.config.get("mock_file"))

    def fetch(self) -> list[dict]:
        # 离线冒烟：mock_file 指向本地 json，走完整解析链路，无需 token
        mock = self.config.get("mock_file")
        if mock:
            try:
                with open(mock, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                raise FetchError(f"读取 mock_file 失败: {e}", adapter_id=self.id)
            return self._parse(raw)
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


def _to_int(v) -> int:
    """安全转 int（容忍字符串数字与 None→0）。"""
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return 0
