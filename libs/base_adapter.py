"""adapter 抽象基类：数据源转接头契约。

每个 adapter 文件（``adapter/*.py``）定义一个 ``BaseAdapter`` 子类，类属性
``id`` 为唯一标识。**仅 adapter 做网络请求**；``fetch`` 返回统一格式 entries，
去重/排序交给 ``SGV.merge``。
"""

from __future__ import annotations

import json
import os
import time


class FetchError(Exception):
    """adapter fetch 失败（网络/认证/解析）。"""

    def __init__(self, message: str, *, adapter_id: str = ""):
        super().__init__(message)
        self.adapter_id = adapter_id


class BaseAdapter:
    """所有数据源 adapter 的基类。"""

    id: str = ""  # 子类必须覆盖，唯一标识
    name: str = ""  # 子类必须覆盖，UI 显示名
    poll_interval_seconds: int = 300  # 数据拉取间隔（秒），子类按实际覆盖

    def __init__(self, adapter_config: dict | None = None):
        self.config: dict = adapter_config or {}
        # 自适应调度状态
        self._phase = "discovery"  # discovery | wait | probing | steady
        self._last_latest: int = 0  # 最新数据点时间戳(ms)
        self._offset: float = 0.0  # 服务器-客户端时差(秒)
        self._wait_until: float = 0.0  # wait 到期时间(客户端秒)
        self._probe_deadline: float = 0.0  # probing 截止时间(客户端秒)
        self._load_offset()

    def fetch(self) -> list[dict]:
        """拉取并返回 entries：``[{"date":int_ms,"sgv":int_mgdl,"direction":str}]``。

        失败应抛 ``FetchError``。不要在此去重/排序（交给 ``SGV.merge``）。
        """
        raise NotImplementedError

    def is_configured(self) -> bool:
        """是否具备最小可用配置（token/url 齐全）。子类按需覆盖。"""
        return True

    def display_name(self) -> str:
        return self.name or self.id

    # ---- 自适应拉取调度 ----

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

    # ---- 缓存与持久化 ----

    def _cache_dir(self) -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, "..", "data")

    def _cache_path(self) -> str:
        return os.path.join(self._cache_dir(), f"{self.id}.json")

    def load_cached_entries(self) -> list[dict]:
        """读取 ``data/<id>.json`` 返回缓存的 entries；无文件/损坏返回 []。"""
        path = self._cache_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("entries", [])
        except (OSError, json.JSONDecodeError):
            return []

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
