"""adapter 抽象基类：数据源转接头契约。

每个 adapter 文件（``adapter/*.py``）定义一个 ``BaseAdapter`` 子类，类属性
``id`` 为唯一标识。**仅 adapter 做网络请求**；``fetch`` 返回统一格式 entries，
去重/排序交给 ``SGV.merge``。
"""
from __future__ import annotations


class FetchError(Exception):
    """adapter fetch 失败（网络/认证/解析）。"""

    def __init__(self, message: str, *, adapter_id: str = ""):
        super().__init__(message)
        self.adapter_id = adapter_id


class BaseAdapter:
    """所有数据源 adapter 的基类。"""

    id: str = ""    # 子类必须覆盖，唯一标识
    name: str = ""  # 子类必须覆盖，UI 显示名
    poll_interval_seconds: int = 300  # 数据拉取间隔（秒），子类按实际覆盖

    def __init__(self, adapter_config: dict | None = None):
        self.config: dict = adapter_config or {}

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
