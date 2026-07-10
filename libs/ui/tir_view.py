"""TIR 展示：High/Range/Low 三段进度条 + 百分比文字。

弃用旧 ``PieChart`` 饼图，简化为进度条，更直观。标签文案走 i18n，
内部仅用小写键（high/range/low）索引颜色与控件，显示时再翻译。
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from libs import i18n

# 内部顺序键 -> i18n 键（显示文案随语言切换）
_KEYS = ("high", "range", "low")


class TirView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = {"high": "#F2C94C", "range": "#6DAE81", "low": "#EB5757"}
        self._bars: dict[str, QProgressBar] = {}
        self._labels: dict[str, QLabel] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for key in _KEYS:
            row = QHBoxLayout()
            lbl = QLabel(f"{i18n.t(f'tir.{key}')}: 0%")
            lbl.setStyleSheet("color: white; font-size: 12px;")
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            c = self._colors[key]
            bar.setStyleSheet(
                f"QProgressBar {{background: rgba(255,255,255,0.2); border-radius: 3px;}}"
                f"QProgressBar::chunk {{background-color: {c}; border-radius: 3px;}}"
            )
            row.addWidget(lbl)
            row.addWidget(bar)
            layout.addLayout(row)
            self._bars[key] = bar
            self._labels[key] = lbl

    def set_values(self, high: float, range_: float, low: float):
        for key, val in (("high", high), ("range", range_), ("low", low)):
            self._bars[key].setValue(int(val))
            self._labels[key].setText(f"{i18n.t(f'tir.{key}')}: {val:.1f}%")

    def set_theme(self, tir):
        """应用 TIR 主题颜色。*tir* 为 ``libs.theme.TirTheme``。"""
        self._colors = {"high": tir.high_color, "range": tir.range_color, "low": tir.low_color}
        for key, bar in self._bars.items():
            c = self._colors[key]
            bar.setStyleSheet(
                f"QProgressBar {{background: rgba(255,255,255,0.2); border-radius:3px;}}"
                f"QProgressBar::chunk {{background-color:{c}; border-radius:3px;}}"
            )
