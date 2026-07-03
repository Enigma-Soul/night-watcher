"""血糖数据存储：扁平 ``list[dict]``，按 date 去重，不联网。

彻底弃用旧 ``library/SGV.py`` 的 spacing 分组压缩——其
``merge_from_source``（用 ``len(keys()[-1])`` 字符串长度算 spacing，无意义）、
``get_zipped_from_source``（循环从 0 起错位）、``get_a_value``（对 list 调
``.keys()`` 必抛 AttributeError）均有 bug。

内部约定：``sgv`` 恒为 int mg/dL；``direction`` 为 NS 方向名字符串；
``date`` 为 unix 毫秒。
"""
from __future__ import annotations

from typing import Iterable


class SGV:
    """血糖 entries 容器。"""

    def __init__(self, entries: list[dict] | None = None):
        self._by_date: dict[int, dict] = {}
        if entries:
            self.merge(entries)

    def merge(self, new_entries: Iterable[dict]) -> int:
        """按 date 去重合并（new 覆盖 old）。返回新增/更新条数。

        非法条目（缺 date 或 date 不可转 int）直接跳过，不抛异常。
        """
        n = 0
        for e in new_entries:
            try:
                date = int(e["date"])
            except (KeyError, TypeError, ValueError):
                continue
            entry = {
                "date": date,
                "sgv": int(e.get("sgv", 0)),
                "direction": e.get("direction") or "None",
            }
            if date not in self._by_date:
                n += 1
            self._by_date[date] = entry
        return n

    def latest(self) -> dict | None:
        """date 最大的条目；空则 None。"""
        if not self._by_date:
            return None
        return max(self._by_date.values(), key=lambda e: e["date"])

    def nth_last(self, n: int = 1) -> dict | None:
        """倒数第 n 条（n=1 即 latest）。越界返回 None。"""
        items = self.all()
        if n < 1 or n > len(items):
            return None
        return items[-n]

    def in_range(self, start_ms: int, end_ms: int) -> list[dict]:
        """返回 [start, end] 内的 entries，按 date 升序。"""
        return [e for e in self.all() if start_ms <= e["date"] <= end_ms]

    def last_n(self, n: int) -> list[dict]:
        items = self.all()
        return items[-n:] if n > 0 else []

    def all(self) -> list[dict]:
        """全部 entries 的副本，按 date 升序。"""
        return sorted(self._by_date.values(), key=lambda e: e["date"])

    def clear(self) -> None:
        self._by_date.clear()

    def tir(self, low: int, high: int, start_ms: int, end_ms: int) -> tuple[float, float, float]:
        """目标范围 (high%, range%, low%)。空窗口返回 (0, 0, 0)。"""
        window = self.in_range(start_ms, end_ms)
        total = len(window)
        if total == 0:
            return (0.0, 0.0, 0.0)
        hi = sum(1 for e in window if e["sgv"] > high)
        lo = sum(1 for e in window if e["sgv"] < low)
        mid = total - hi - lo
        return (hi / total * 100, mid / total * 100, lo / total * 100)

    def __len__(self) -> int:
        return len(self._by_date)
