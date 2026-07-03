"""主题系统：加载 themes/*.toml 并转为类型化 Theme 对象。

设计：
- Theme 是嵌套 dataclass 树，每个子 widget 取自己那一段。
- DEFAULT_THEME_DICT 定义所有键的默认值；用户 .toml 文件只需写要覆盖的键。
- load_theme(name) 深拷贝默认值，与 TOML 递归合并，转为 Theme 返回。
- scan_themes() 扫描 themes/ 目录用于设置对话框。
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# ---- 子主题 dataclass ----


@dataclass
class MainTheme:
    """主悬浮窗主题。"""

    background: str = "#1E1E2E"
    opacity: float = 0.85
    text_color: str = "#FFFFFF"
    offline_color: str = "#FFAA00"
    border_color: str = "#646464"


@dataclass
class PanelTheme:
    """信息面板主题。"""

    background: str = "#1E1E2E"
    opacity: float = 0.86
    text_color: str = "#FFFFFF"
    border_color: str = "#506080"
    border_radius: int = 10


@dataclass
class ChartTheme:
    """折线/散点图主题。"""

    line_color: str = "#6496FA"
    high_line_color: str = "#FA9664"
    low_line_color: str = "#96FA64"
    line_width: int = 2
    dot_visible: bool = True
    dot_size: int = 3
    low_zone_color: str = "#EB5757"
    normal_zone_color: str = "#6DAE81"
    high_zone_color: str = "#F2C94C"


@dataclass
class TirTheme:
    """TIR 进度条主题。"""

    high_color: str = "#F2C94C"
    range_color: str = "#6DAE81"
    low_color: str = "#EB5757"


@dataclass
class Theme:
    """总主题：聚合四个子主题。"""

    main: MainTheme = field(default_factory=MainTheme)
    panel: PanelTheme = field(default_factory=PanelTheme)
    chart: ChartTheme = field(default_factory=ChartTheme)
    tir: TirTheme = field(default_factory=TirTheme)


# ---- 默认值与合并 ----

DEFAULT_THEME_DICT: dict = {
    "main": {
        "background": "#1E1E2E",
        "opacity": 0.85,
        "text_color": "#FFFFFF",
        "offline_color": "#FFAA00",
        "border_color": "#646464",
    },
    "panel": {
        "background": "#1E1E2E",
        "opacity": 0.86,
        "text_color": "#FFFFFF",
        "border_color": "#506080",
        "border_radius": 10,
    },
    "chart": {
        "line_color": "#6496FA",
        "high_line_color": "#FA9664",
        "low_line_color": "#96FA64",
        "line_width": 2,
        "dot_visible": True,
        "dot_size": 3,
        "low_zone_color": "#EB5757",
        "normal_zone_color": "#6DAE81",
        "high_zone_color": "#F2C94C",
    },
    "tir": {
        "high_color": "#F2C94C",
        "range_color": "#6DAE81",
        "low_color": "#EB5757",
    },
}

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并 *override* 到 *base*（原地修改 base，同时返回 base）。"""
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _dict_to_theme(d: dict) -> Theme:
    return Theme(
        main=MainTheme(**d.get("main", {})),
        panel=PanelTheme(**d.get("panel", {})),
        chart=ChartTheme(**d.get("chart", {})),
        tir=TirTheme(**d.get("tir", {})),
    )


# ---- 公开 API ----


def load_theme(name: str) -> Theme:
    """加载 ``themes/{name}.toml``，缺失则以默认值补足；文件不存在退回到默认主题。"""
    merged = copy.deepcopy(DEFAULT_THEME_DICT)
    path = THEMES_DIR / f"{name}.toml"
    if path.exists():
        with open(path, "rb") as f:
            user = tomllib.load(f)
        _deep_merge(merged, user)
    return _dict_to_theme(merged)


def scan_themes() -> list[str]:
    """扫描 ``themes/`` 目录，返回可用主题名列表（用于设置对话框）。"""
    if not THEMES_DIR.exists():
        return ["default"]
    names = [p.stem for p in sorted(THEMES_DIR.glob("*.toml"))]
    return names if names else ["default"]
