"""历史 entries 缓存：``cache.json`` 按 adapter id 分区，原子写。

与 ``config.json`` 分离——配置走 Config，历史血糖数据走本模块。
启动时先 ``load(active_id)`` 填充 SGV，adapter fetch 后 ``save``。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_VERSION_KEY = "__version__"
_VERSION = 1


class Cache:
    """``cache.json`` 按 adapter id 分区的读写。"""

    def __init__(self, path: str | Path = "cache.json"):
        self.path = Path(path)

    def _read_all(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            # 损坏当作空，避免阻断启动
            return {}

    def load(self, adapter_id: str) -> list[dict]:
        """读取某 adapter 的 entries；缺/损坏返回 []。"""
        entries = self._read_all().get(adapter_id, [])
        return entries if isinstance(entries, list) else []

    def has(self, adapter_id: str) -> bool:
        return adapter_id in self._read_all()

    def save(self, adapter_id: str, entries: list[dict]) -> None:
        """原子写整文件，只更新对应分区，不动其他 adapter。"""
        data = self._read_all()
        data[_VERSION_KEY] = _VERSION
        data[adapter_id] = entries
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, self.path)
