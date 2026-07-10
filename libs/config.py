"""全局配置读写：``config.json`` 只存配置不存数据。

数据（历史血糖 entries）走 ``libs.cache.Cache``。配置损坏时备份为
``config.json.bad`` 并写默认配置，避免阻断启动。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# 内部血糖统一 mg/dL；low/high/max 默认值取 mg/dL
DEFAULT_CONFIG: dict = {
    "gui": {
        "low_line": 72,
        "high_line": 180,
        "max": 270,
        "color_scheme": 0,  # 已由 theme 体系取代，保留仅为向后兼容
        "theme": "default",
        "unit": "mmol/L",  # "mmol/L" | "mg/dL"，仅影响显示
        "time_range": 6,  # 1/6/12/24 小时
        "language": "auto",  # "auto"(按系统区域) | "zh-cn" | "en"
        "active_adapter": "sisensing",
    },
    "adapter": {
        "sisensing": {
            "ss_token": "",
            "ss_region": "CN",
            "timeout": 10,
            "retries": 3,
        },
        "nightscout": {"ns_url": "", "api_secret": "", "count": 288},
    },
}


class Config:
    """``config.json`` 的读写封装。"""

    def __init__(self, path: str | Path = "config.json"):
        self.path = Path(path)
        self._data: dict = {}

    def load(self) -> dict:
        """读取配置；文件缺失或损坏则写默认（损坏先备份 .bad）。"""
        if not self.path.exists():
            self._data = _deep_copy(DEFAULT_CONFIG)
            self.save()
            return self._data
        try:
            with self.path.open("r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, OSError):
            _backup(self.path)
            self._data = _deep_copy(DEFAULT_CONFIG)
            self.save()
        # 合并默认键，补齐缺失字段（兼容旧/手改配置）
        self._data = _merge_defaults(self._data, DEFAULT_CONFIG)
        return self._data

    def save(self) -> None:
        """原子写：先写 ``.tmp`` 再 ``os.replace``。"""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self) -> dict:
        return self._data

    def gui(self) -> dict:
        return self._data.setdefault("gui", {})

    def adapters(self) -> dict:
        return self._data.setdefault("adapter", {})

    def adapter_config(self, adapter_id: str) -> dict:
        """某 adapter 的配置 dict，缺则空 dict（不抛 KeyError）。"""
        cfg = self.adapters().get(adapter_id)
        return cfg if isinstance(cfg, dict) else {}

    def update_gui(self, partial: dict) -> None:
        self.gui().update(partial)
        self.save()

    def update_adapter(self, adapter_id: str, partial: dict) -> None:
        self.adapters().setdefault(adapter_id, {}).update(partial)
        self.save()

    def set_active_adapter(self, adapter_id: str) -> None:
        self.gui()["active_adapter"] = adapter_id
        self.save()


def _deep_copy(d: dict) -> dict:
    return json.loads(json.dumps(d))


def _merge_defaults(actual: dict, defaults: dict) -> dict:
    """递归合并：默认键打底，actual 覆盖（补齐缺失字段，保留用户值）。"""
    result: dict = _deep_copy(defaults)
    for k, v in actual.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge_defaults(v, result[k])
        else:
            result[k] = v
    return result


def _backup(path: Path) -> None:
    bad = path.with_suffix(path.suffix + ".bad")
    try:
        os.replace(path, bad)
    except OSError:
        pass
