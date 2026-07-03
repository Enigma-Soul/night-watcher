"""adapter 自动扫描：启动时扫描 ``adapter/`` 目录，收集 BaseAdapter 子类。

加载规则：
- 文件名以 ``_`` 开头跳过（同时排除 ``__init__`` 与 ``_disabled`` 等）；
- 其余 ``.py`` 全部 import，收集**本模块内定义**的 ``BaseAdapter`` 子类；
- ``id`` 为空或重复 → 抛错（main 捕获后弹窗退出）；
- import 失败不静默，上抛 ``ImportError``（修正旧 ``except: pass``）。

adapter 文件须用绝对导入：``from libs.base_adapter import BaseAdapter``。
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from .base_adapter import BaseAdapter


class DuplicateAdapterIdError(Exception):
    """两个 adapter 类的 id 相同。"""

    def __init__(self, id: str, file_a: str, file_b: str):
        super().__init__(f"adapter id 重复: {id!r} (出现于 {file_a} 与 {file_b})")
        self.id = id
        self.file_a = file_a
        self.file_b = file_b


class EmptyAdapterIdError(Exception):
    """adapter 子类未覆盖 id。"""

    def __init__(self, file: str):
        super().__init__(f"adapter 未设置 id: {file}")
        self.file = file


def scan(package: str = "adapter") -> list[type[BaseAdapter]]:
    """扫描 ``package`` 下的 ``.py``，返回 BaseAdapter 子类列表（未实例化）。"""
    pkg = importlib.import_module(package)
    found: list[type[BaseAdapter]] = []
    for _finder, modname, _ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_"):
            continue  # __init__ 与用户写的 _xxx.py 都跳过
        mod = importlib.import_module(f"{package}.{modname}")
        for _name, cls in inspect.getmembers(mod, inspect.isclass):
            if not _is_adapter_subclass(cls, mod):
                continue
            if not cls.id:
                raise EmptyAdapterIdError(getattr(mod, "__file__", modname))
            found.append(cls)

    # id 去重检测
    seen: dict[str, str] = {}
    for cls in found:
        prev = seen.get(cls.id)
        if prev is not None:
            raise DuplicateAdapterIdError(cls.id, prev, _cls_file(cls))
        seen[cls.id] = _cls_file(cls)
    return found


def _is_adapter_subclass(cls: Any, mod: Any) -> bool:
    """是否为定义在 ``mod`` 内的 BaseAdapter 子类（排除被 import 带进来的基类）。"""
    return (
        issubclass(cls, BaseAdapter)
        and cls is not BaseAdapter
        and cls.__module__ == mod.__name__
    )


def _cls_file(cls: type) -> str:
    mod = inspect.getmodule(cls)
    return getattr(mod, "__file__", cls.__module__)
