"""adapter 抽象基类：数据源转接头契约。

每个 adapter 文件（``adapter/*.py``）定义一个 ``BaseAdapter`` 子类，类属性
``id`` 为唯一标识。**仅 adapter 做网络请求**；``fetch`` 返回统一格式 entries，
去重/排序交给 ``SGV.merge``。

默认调度为固定间隔轮询（``poll_interval_seconds``）；产出时间固定的数据源
（如硅基，每 300s 一帧）在子类覆盖 ``note_fetch_result`` / ``next_poll_delay_sec``
实现自适应预测调度（见 ``adapter/sisensing.py``）。
"""

from __future__ import annotations

import json
import os


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
        # 调度阶段标识，供日志/调试；自适应子类会覆盖为 discovery/steady
        self._phase: str = "fixed"
        # 服务器-客户端时钟偏差(秒，client−server)，仅用于显示"最后更新"补偿；
        # 默认 0 即无补偿（本地/同区源），存在时差的子类（如硅基）按观测更新
        self._clock_offset_sec: float = 0.0

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

    # ---- 调度（默认固定间隔；需时差校准的子类覆盖）----

    def note_fetch_result(self, entries: list[dict]):
        """成功拉取后钩子；默认无操作（固定间隔调度无需维护状态）。"""
        return

    def next_poll_delay_sec(self) -> int:
        """返回建议的下次拉取延迟(秒)；默认固定间隔。"""
        return self.poll_interval_seconds

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
        """保存 entries 到 ``data/<id>.json``。"""
        path = self._cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"entries": entries}, f, ensure_ascii=False)
