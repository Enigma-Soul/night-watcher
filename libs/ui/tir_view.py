"""TIR 展示：High/Range/Low 三段进度条 + 百分比文字。

弃用旧 ``PieChart`` 饼图，简化为进度条，更直观。
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class TirView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = {"High": "#F2C94C", "Range": "#6DAE81", "Low": "#EB5757"}
        self._bars: dict[str, QProgressBar] = {}
        self._labels: dict[str, QLabel] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for key in ("High", "Range", "Low"):
            row = QHBoxLayout()
            lbl = QLabel(f"{key}: 0%")
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
        for key, val in (("High", high), ("Range", range_), ("Low", low)):
            self._bars[key].setValue(int(val))
            self._labels[key].setText(f"{key}: {val:.1f}%")

    def set_theme(self, tir):
        """应用 TIR 主题颜色。*tir* 为 ``libs.theme.TirTheme``。"""
        self._colors = {"High": tir.high_color, "Range": tir.range_color, "Low": tir.low_color}
        for key, bar in self._bars.items():
            c = self._colors[key]
            bar.setStyleSheet(
                f"QProgressBar {{background: rgba(255,255,255,0.2); border-radius:3px;}}"
                f"QProgressBar::chunk {{background-color:{c}; border-radius:3px;}}"
            )
