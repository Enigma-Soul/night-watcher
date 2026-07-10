"""血糖曲线：QPainter 画近 N 小时折线 + 高/低虚线。

替代旧 ``DotWidget`` 的散点（其依赖旧 SGV 的 spacing 推算，已弃用）。
entries 为 ``[{"date","sgv","direction"}, ...]``，sgv 为 mg/dL。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from libs import i18n


class ChartView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self._entries: list[dict] = []
        self._low = 72
        self._high = 180
        self._max_sgv = 270
        self._range_ms = 6 * 3600 * 1000
        self._line_color = QColor(100, 150, 250)
        self._high_line_color = QColor(250, 150, 100)
        self._low_line_color = QColor(150, 250, 100)
        self._line_width = 2
        self._dot_visible = False
        self._dot_size = 3
        self._low_zone_color = QColor(235, 87, 87)
        self._normal_zone_color = QColor(109, 174, 129)
        self._high_zone_color = QColor(242, 201, 76)

    def set_data(self, entries: list[dict], low: int, high: int, max_sgv: int, range_hours: int):
        self._entries = entries
        self._low = low
        self._high = high
        self._max_sgv = max(max_sgv, 1)
        self._range_ms = max(range_hours, 1) * 3600 * 1000
        self.update()

    def set_theme(self, chart):
        """应用图表主题（线色/线宽/散点）。*chart* 为 ``libs.theme.ChartTheme``。"""
        self._line_color = QColor(chart.line_color)
        self._high_line_color = QColor(chart.high_line_color)
        self._low_line_color = QColor(chart.low_line_color)
        self._low_zone_color = QColor(chart.low_zone_color)
        self._normal_zone_color = QColor(chart.normal_zone_color)
        self._high_zone_color = QColor(chart.high_zone_color)
        self._line_width = chart.line_width
        self._dot_visible = chart.dot_visible
        self._dot_size = chart.dot_size
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if not self._entries:
            p.setPen(QColor(150, 150, 150))
            p.drawText(self.rect(), Qt.AlignCenter, i18n.t("common.no_data"))
            return

        now = self._entries[-1]["date"]
        start = now - self._range_ms

        def y(sgv: float) -> float:
            return h - sgv / self._max_sgv * h

        # 高/低虚线
        for val, color in [(self._high, self._high_line_color), (self._low, self._low_line_color)]:
            p.setPen(QPen(color, 1, Qt.DashLine))
            yy = int(y(val))
            p.drawLine(0, yy, w, yy)

        # 收集可见数据点（像素坐标 + sgv 值）
        visible: list[tuple[float, float, int]] = []
        for e in self._entries:
            if e["date"] < start:
                continue
            px = (e["date"] - start) / self._range_ms * w
            py = y(e["sgv"])
            visible.append((px, py, e["sgv"]))

        if not visible:
            return

        # 按血糖区间给每个线段着色
        for i in range(1, len(visible)):
            x1, y1, _sgv1 = visible[i - 1]
            x2, y2, sgv2 = visible[i]
            if sgv2 > self._high:
                sc = self._high_zone_color
            elif sgv2 < self._low:
                sc = self._low_zone_color
            else:
                sc = self._normal_zone_color
            p.setPen(QPen(sc, self._line_width))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # 散点（同样按区间着色）
        if self._dot_visible:
            for px, py, sgv in visible:
                if sgv > self._high:
                    sc = self._high_zone_color
                elif sgv < self._low:
                    sc = self._low_zone_color
                else:
                    sc = self._normal_zone_color
                p.setBrush(sc)
                p.setPen(QPen(sc, 1))
                p.drawEllipse(
                    int(px - self._dot_size // 2),
                    int(py - self._dot_size // 2),
                    self._dot_size,
                    self._dot_size,
                )
