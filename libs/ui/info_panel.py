"""信息面板：展开后显示数值+趋势+最后更新+时间范围按钮+曲线+TIR。

``Qt.Tool | Frameless | StaysOnTop``。由 FloatWidget 短按切换显示/隐藏。
全新重写，不沿用旧 ``library/gui/InfoPanel.py`` 代码。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .chart_view import ChartView
from .tir_view import TirView
from libs.theme import PanelTheme, ChartTheme, TirTheme


class InfoPanel(QWidget):
    range_changed = Signal(int)  # 1/6/12/24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(260, 280)

        self._pt = PanelTheme()  # 默认主题，由 apply_theme 覆盖
        self._ct = ChartTheme()
        self._tt = TirTheme()

        self._value_label = QLabel("-- →")
        self._value_label.setStyleSheet("font-size: 18px; color: white;")
        self._time_label = QLabel("--")
        self._time_label.setStyleSheet("font-size: 12px; color: #DDD;")

        self._chart = ChartView()
        self._tir = TirView()
        self._build()
        self._apply_panel_style()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(self._value_label)
        top.addStretch()
        top.addWidget(self._time_label)
        root.addLayout(top)

        btns = QHBoxLayout()
        for text, hours in [("1h", 1), ("6h", 6), ("12h", 12), ("1d", 24)]:
            b = QPushButton(text)
            b.setFixedHeight(22)
            b.setStyleSheet(
                "QPushButton {background:transparent; color:#DDD; border:none; font-size:12px;}"
                "QPushButton:hover {color:white; background:rgba(255,255,255,0.1);}"
            )
            b.clicked.connect(lambda checked=False, h=hours: self.range_changed.emit(h))  # noqa: B023
            btns.addWidget(b)
        root.addLayout(btns)

        root.addWidget(self._chart)
        root.addWidget(self._tir)

    def _apply_panel_style(self):
        """根据当前面板主题更新 label 颜色。"""
        self._value_label.setStyleSheet(
            f"font-size:18px; color:{self._pt.text_color};")
        self._time_label.setStyleSheet(
            f"font-size:12px; color:{self._pt.text_color};")

    def paintEvent(self, event):
        """手绘圆角半透明背景（WA_TranslucentBackground + stylesheet 不可靠）。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), self._pt.border_radius, self._pt.border_radius)
        bg = QColor(self._pt.background)
        bg.setAlphaF(self._pt.opacity)
        p.setPen(QPen(QColor(self._pt.border_color), 1))
        p.setBrush(QBrush(bg))
        p.drawPath(path)

    def set_position_near(self, anchor_x: int, anchor_y: int):
        self.move(anchor_x + (120 - self.width()) // 2, anchor_y + 60 + 5)

    def apply_theme(self, pt, ct, tt):
        """应用面板/图表/TIR 主题。"""
        self._pt = pt
        self._ct = ct
        self._tt = tt
        self._chart.set_theme(ct)
        self._tir.set_theme(tt)
        self._apply_panel_style()
        self.update()

    def update_data(self, value_text: str, arrow: str, time_ago: str, offline: bool,
                    chart_entries: list[dict], low: int, high: int, max_sgv: int,
                    range_hours: int, tir: tuple[float, float, float]):
        color_str = "#FFAA00" if offline else self._pt.text_color
        self._value_label.setStyleSheet(f"font-size:18px; color:{color_str};")
        self._value_label.setText(f"{value_text} {arrow}")
        self._time_label.setText(time_ago)
        self._chart.set_data(chart_entries, low, high, max_sgv, range_hours)
        self._tir.set_values(tir[0], tir[1], tir[2])
