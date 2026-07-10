"""桌面悬浮窗：120×60 无边框置顶半透明圆角，显示血糖值 + 趋势箭头。

左键短按切换 InfoPanel，拖拽移动；右键菜单（设置 / 数据源子菜单 / 退出）。
全新重写，不沿用旧 ``library/gui/MainPanel.py`` 代码。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QWidget

from libs import i18n
from libs.theme import MainTheme


class FloatWidget(QWidget):
    """桌面悬浮主窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(120, 60)

        self._drag_pos: QPoint | None = None
        self._press_pos: QPoint | None = None

        self._mt = MainTheme()  # 默认主题，由 App.apply_theme 覆盖

        # 由 App 注入的回调
        self.on_toggle_panel = lambda: None
        self.on_open_settings = lambda: None
        self.on_select_source = lambda aid: None
        self.on_refresh = lambda: None  # 右键 → 强制刷新
        self.on_moved = lambda: None  # 拖动时通知重定位面板
        self.sources: list[tuple[str, str]] = []  # [(adapter_id, display_name)]

        self.label = QLabel("-- →", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Arial", 18))
        self.label.setGeometry(0, 0, 120, 60)
        self.label.setStyleSheet("color: white;")

    def set_value(self, text: str, arrow: str, offline: bool = False):
        color = self._mt.offline_color if offline else self._mt.text_color
        self.label.setText(f"{text} {arrow}")
        self.label.setStyleSheet(f"color: {color};")

    def apply_theme(self, mt):
        """应用主窗主题。*mt* 为 ``libs.theme.MainTheme``。"""
        self._mt = mt
        self.update()

    def set_sources(self, sources: list[tuple[str, str]]):
        self.sources = sources

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            self._press_pos = event.position().toPoint()
        elif event.button() == Qt.RightButton:
            self._exec_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint()
            self.on_moved()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._press_pos is not None:
            moved = event.position().toPoint() - self._press_pos
            if moved.manhattanLength() < 10:  # 短按切换面板
                self.on_toggle_panel()
            self._drag_pos = None
            self._press_pos = None

    def _exec_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: rgba(50,50,50,220); border:1px solid #444; color:white; }"
            "QMenu::item { padding:5px 25px; }"
            "QMenu::item:selected { background: rgba(80,80,80,200); }"
        )
        menu.addAction(i18n.t("menu.refresh"), self.on_refresh)
        menu.addSeparator()
        menu.addAction(i18n.t("menu.settings"), self.on_open_settings)
        if self.sources:
            sub = menu.addMenu(i18n.t("menu.data_source"))
            for aid, name in self.sources:
                act = QAction(name, sub)
                act.triggered.connect(lambda checked=False, a=aid: self.on_select_source(a))  # noqa: B023
                sub.addAction(act)
        menu.addSeparator()
        menu.addAction(i18n.t("menu.quit"), QApplication.quit)
        menu.exec(pos)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 8, 8)
        mt = self._mt
        bg = QColor(mt.background)
        bg.setAlphaF(mt.opacity)
        p.setPen(QPen(QColor(mt.border_color), 1))
        p.setBrush(QBrush(bg))
        p.drawPath(path)
