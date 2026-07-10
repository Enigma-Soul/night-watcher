"""i18n：TOML 翻译表加载 + 运行时取词。

语言选择由 ``gui.language`` 配置项驱动：``"auto"`` 时按系统区域检测
（``zh*`` -> ``zh-cn``，其余 -> ``en``），否则用指定值。翻译表置于
``i18n/{lang}.toml``，打包后随 ``_MEIPASS`` 一并发布。

取词用点分键（如 ``"menu.refresh"``），支持 ``{name}`` 占位符格式化。
缺词容错：当前语言表未命中时回退到 ``en`` 翻译；两者均缺才返回键名本身，
便于发现漏译而不至于向用户裸露键名。
"""

from __future__ import annotations

import locale
import sys
import tomllib
import warnings
from pathlib import Path

_FALLBACK_LANG = "zh-cn"
_EN = "en"


def _resource_dir() -> Path:
    """i18n 目录：打包态取 ``sys._MEIPASS``，开发态取源码根下 ``i18n/``。"""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent
    return Path(base) / "i18n"


def available_languages() -> list[str]:
    """扫描 ``i18n/`` 下可用语言代码（文件名去 ``.toml``）；目录缺失回退默认。"""
    d = _resource_dir()
    if not d.is_dir():
        return [_FALLBACK_LANG]
    return sorted(p.stem for p in d.glob("*.toml")) or [_FALLBACK_LANG]


def detect_locale() -> str:
    """按系统区域推断语言：``zh*`` -> ``zh-cn``，其余 -> ``en``，失败回退 ``en``。"""
    try:
        # getdefaultlocale 在 3.12 起弃用但仍可用；静默其 DeprecationWarning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            loc = locale.getdefaultlocale()[0] or ""
    except Exception:
        loc = ""
    return "zh-cn" if loc.lower().startswith("zh") else "en"


def resolve_language(pref: str) -> str:
    """将用户偏好（可为 ``auto``/空）解析为具体语言代码，非法值回退默认。"""
    pref = (pref or "").strip().lower()
    if pref in ("", "auto"):
        pref = detect_locale()
    avail = available_languages()
    return pref if pref in avail else (avail[0] if avail else _FALLBACK_LANG)


def _load_table(lang: str) -> dict:
    """读取某语言 TOML 为 dict；文件缺失返回空 dict。"""
    path = _resource_dir() / f"{lang}.toml"
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _lookup(table: dict, key: str) -> str | None:
    """按点分键取字符串；任一层缺失或非字符串返回 None。"""
    cur: object = table
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur if isinstance(cur, str) else None


class Translator:
    """单语言翻译器：按点分键取词，支持 ``{name}`` 占位符格式化。"""

    def __init__(self):
        self._lang = _FALLBACK_LANG
        self._table: dict = {}
        self._fallback_table: dict = {}
        self.load(_FALLBACK_LANG)

    def load(self, lang: str) -> None:
        """加载指定语言表；语言非法或缺文件则用空表，缺词时回退 en。"""
        resolved = resolve_language(lang)
        self._table = _load_table(resolved)
        self._fallback_table = _load_table(_EN)
        self._lang = resolved

    @property
    def lang(self) -> str:
        return self._lang

    def t(self, key: str, **fmt) -> str:
        # 当前语言未命中 -> 回退 en -> 仍缺则返回键名，便于发现漏译
        text = _lookup(self._table, key)
        if text is None:
            text = _lookup(self._fallback_table, key)
        if text is None:
            return key
        return text.format(**fmt) if fmt else text


_tr = Translator()


def set_lang(pref: str) -> str:
    """设置当前语言（``pref`` 可为 ``auto``/``zh-cn``/``en``），返回实际加载的语言。"""
    resolved = resolve_language(pref)
    if resolved != _tr.lang:
        _tr.load(resolved)
    return _tr.lang


def lang() -> str:
    return _tr.lang


def t(key: str, **fmt) -> str:
    return _tr.t(key, **fmt)
