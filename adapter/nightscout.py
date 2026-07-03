"""NightScout 源 adapter。

数据本身就是 NightScout 协议（``entries.json``），但因 URL 不同仍需独立
adapter（见用户约定）。仅拉取，``sgv`` 已是 mg/dL，直通。
"""
from __future__ import annotations

import requests

from libs.base_adapter import BaseAdapter, FetchError


class NightscoutAdapter(BaseAdapter):
    id = "nightscout"
    name = "NightScout"
    poll_interval_seconds = 300  # NightScout 一般也是 5 分钟

    def is_configured(self) -> bool:
        return bool(self.config.get("ns_url"))

    def fetch(self) -> list[dict]:
        ns_url = self.config.get("ns_url", "").rstrip("/")
        if not ns_url:
            raise FetchError("NightScout ns_url 未配置", adapter_id=self.id)
        url = f"{ns_url}/api/v1/entries.json"
        headers = {"Accept": "application/json"}
        secret = self.config.get("api_secret", "")
        if secret:
            headers["api-secret"] = secret
        params = {"count": int(self.config.get("count", 288))}
        timeout = int(self.config.get("timeout", 10))
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            raw = r.json()
        except (requests.RequestException, ValueError) as e:
            raise FetchError(f"NightScout 请求失败: {e}", adapter_id=self.id)
        if not isinstance(raw, list):
            raise FetchError("NightScout 响应非数组", adapter_id=self.id)

        entries: list[dict] = []
        for e in raw:
            if not isinstance(e, dict):
                continue
            # 只取 sgv 类型（跳过 mbgl/cal 等其他条目）
            if e.get("type") and e["type"] != "sgv":
                continue
            try:
                date = int(e["date"])
                sgv = int(e["sgv"])
            except (KeyError, TypeError, ValueError):
                continue
            direction = e.get("direction") or "None"
            entries.append({"date": date, "sgv": sgv, "direction": direction})
        return entries
