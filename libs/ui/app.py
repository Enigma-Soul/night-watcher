"""App：接线 Config/Cache/SGV/adapter/QTimer/QThreadPool。

``fetch`` 在子线程跑（``QRunnable``），完成后经 ``Signal`` 回主线程做
``merge``/``save``/``update_ui``，避免阻塞 UI（修正旧 ``Thread + sleep`` 模式
在 QTimer 槽里同步请求会冻死悬浮窗的问题）。
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from libs.base_adapter import BaseAdapter, FetchError
from libs.cache import Cache
from libs.config import Config
from libs.logger import get as get_logger
from libs.sgv import SGV
from libs.theme import load_theme

from .float_widget import FloatWidget
from .info_panel import InfoPanel
from .settings_dialog import SettingsDialog

_MGDL_PER_MMOLL = 18.018

# Nightscout 方向 → 箭头（覆盖全 7 种 + None/未知 → →）
_DIRECTION_ARROW = {
    "DoubleUp": "↑↑",
    "SingleUp": "↑",
    "FortyFiveUp": "↗",
    "Flat": "→",
    "FortyFiveDown": "↘",
    "SingleDown": "↓",
    "DoubleDown": "↓↓",
}


def _compute_interval(entries: list[dict]) -> int | None:
    """根据数据点时间间隔众数计算实际拉取间隔(ms)。

    若无足够数据点(>=2)或有效间隔，返回 None。
    """
    if len(entries) < 2:
        return None
    sorted_entries = sorted(entries, key=lambda e: e["date"])
    diffs = []
    for i in range(1, len(sorted_entries)):
        d = sorted_entries[i]["date"] - sorted_entries[i - 1]["date"]
        if 60_000 <= d <= 3_600_000:  # 1 分钟 ~ 1 小时，排除异常间隔
            diffs.append(d)
    if not diffs:
        return None
    rounded = [round(d / 1000) * 1000 for d in diffs]
    return Counter(rounded).most_common(1)[0][0]


class _FetchSignals(QObject):
    # (adapter_id, entries|None, error|None)
    done = Signal(str, object, object)


class _FetchWorker(QRunnable):
    """子线程跑 adapter.fetch()，避免阻塞 UI 主线程。"""

    def __init__(self, adapter: BaseAdapter):
        super().__init__()
        self._adapter = adapter
        self.signals = _FetchSignals()

    def run(self):
        try:
            entries = self._adapter.fetch()
            self.signals.done.emit(self._adapter.id, entries, None)
        except FetchError as e:
            self.signals.done.emit(self._adapter.id, None, e)
        except Exception as e:  # 兜底：非 FetchError 也归一
            self.signals.done.emit(
                self._adapter.id, None, FetchError(str(e), adapter_id=self._adapter.id))


class App:
    def __init__(self, config: Config, cache: Cache,
                 adapters: dict[str, BaseAdapter], active_id: str):
        self.config = config
        self.cache = cache
        self.adapters = adapters
        self.active_id = active_id
        self.sgv = SGV(cache.load(active_id))
        self._offline = not adapters[active_id].is_configured()

        # 主题
        self.theme = load_theme(self.config.gui().get("theme", "default"))

        self.widget = FloatWidget()
        self.panel = InfoPanel()
        self.widget.apply_theme(self.theme.main)
        self.panel.apply_theme(self.theme.panel, self.theme.chart, self.theme.tir)

        self.pool = QThreadPool.globalInstance()
        self._sched_timer = QTimer()
        self._sched_timer.setSingleShot(True)
        self._sched_timer.timeout.connect(self.refresh)
        self._fetching = False

        sources = [(aid, a.display_name()) for aid, a in adapters.items()]
        self.widget.set_sources(sources)
        self.widget.on_toggle_panel = self._toggle_panel
        self.widget.on_open_settings = self.open_settings
        self.widget.on_select_source = self.switch_source
        self.widget.on_refresh = self.refresh
        self.widget.on_moved = self._position_panel
        self.panel.range_changed.connect(self._on_range_changed)

    def run(self):
        self.widget.show()
        self.update_ui()
        self.refresh()  # 启动后立即拉一次（成功后 _schedule_next 调度下次）
        QApplication.instance().exec()

    # ---- 拉取 ----

    def refresh(self):
        if self._fetching:
            return
        self._sched_timer.stop()  # 取消排队中的定时器
        adapter = self.adapters.get(self.active_id)
        if not adapter or not adapter.is_configured():
            self._offline = True
            self.update_ui()
            return
        self._fetching = True
        worker = _FetchWorker(adapter)
        worker.signals.done.connect(self._on_fetch_result)
        self.pool.start(worker)

    @Slot(str, object, object)
    def _on_fetch_result(self, aid: str, entries, error):
        self._fetching = False
        if aid != self.active_id:
            return  # 切源后丢弃过期结果
        if error is not None:
            get_logger().warning("adapter %s 拉取失败: %s", aid, error)
            self._offline = True
            self.update_ui()
            self._sched_timer.start(60_000)  # 失败后 1 分钟重试
            return
        if entries:
            self.sgv.merge(entries)
            self.cache.save(aid, self.sgv.all())
        self._offline = False
        self.update_ui()
        self._schedule_next()

    # ---- 调度 ----

    def _schedule_next(self):
        """根据最新数据点时间和间隔众数计算下一次拉取时间。"""
        adapter = self.adapters.get(self.active_id)
        poll_sec = adapter.poll_interval_seconds if adapter else 300
        interval_ms = _compute_interval(self.sgv.all()) or (poll_sec * 1000)
        latest = self.sgv.latest()
        now_ms = int(datetime.now().timestamp() * 1000)
        if latest:
            expected = latest["date"] + interval_ms + 5000  # +5s 缓冲
            delay_ms = expected - now_ms
        else:
            delay_ms = 0
        # 下限 30s（防止 stale 数据导致 tight loop），上限 3 倍间隔
        delay_ms = max(30_000, min(delay_ms, interval_ms * 3))
        self._sched_timer.start(int(delay_ms))

    # ---- 切源 / 设置 ----

    def switch_source(self, aid: str):
        if aid not in self.adapters or aid == self.active_id:
            return
        self._sched_timer.stop()
        self.active_id = aid
        self.config.set_active_adapter(aid)
        self.sgv = SGV(self.cache.load(aid))
        self._offline = not self.adapters[aid].is_configured()
        self.update_ui()
        self.refresh()

    def _on_range_changed(self, hours: int):
        self.config.update_gui({"time_range": hours})
        self.update_ui()

    def open_settings(self):
        dlg = SettingsDialog(
            self.config.gui(),
            self.config.adapters(),
            [(aid, a.display_name()) for aid, a in self.adapters.items()],
            self.widget,
        )
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    def _on_settings_changed(self, data: dict):
        self.config.update_gui(data.get("gui", {}))
        for aid, cfg in data.get("adapter", {}).items():
            self.config.update_adapter(aid, cfg)
            if aid in self.adapters:
                self.adapters[aid].config = self.config.adapter_config(aid)
        new_active = data.get("gui", {}).get("active_adapter", self.active_id)
        if new_active in self.adapters and new_active != self.active_id:
            self.switch_source(new_active)
        else:
            new_theme_name = data.get("gui", {}).get("theme")
            if new_theme_name and new_theme_name != self.config.gui().get("theme"):
                self.theme = load_theme(new_theme_name)
                self.widget.apply_theme(self.theme.main)
                self.panel.apply_theme(self.theme.panel, self.theme.chart, self.theme.tir)
            self._offline = not self.adapters[self.active_id].is_configured()
            self.update_ui()
            self.refresh()

    # ---- UI ----

    def _toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide()
        else:
            self.panel.show()
            self._position_panel()

    def _position_panel(self):
        self.panel.set_position_near(self.widget.x(), self.widget.y())

    def update_ui(self):
        gui = self.config.gui()
        unit = gui.get("unit", "mmol/L")
        low = int(gui.get("low_line", 72))
        high = int(gui.get("high_line", 180))
        max_sgv = int(gui.get("max", 270))
        hours = int(gui.get("time_range", 6))

        latest = self.sgv.latest()
        if latest is None:
            value_text, arrow, time_ago = "--", "→", "无数据"
        else:
            value_text = self._format_value(latest["sgv"], unit)
            arrow = _DIRECTION_ARROW.get(latest.get("direction"), "→")
            time_ago = self._time_ago(latest["date"])

        now_ms = int(datetime.now().timestamp() * 1000)
        start_ms = now_ms - hours * 3600 * 1000
        chart_entries = self.sgv.in_range(start_ms, now_ms)
        tir = self.sgv.tir(low, high, start_ms, now_ms)

        self.widget.set_value(value_text, arrow, offline=self._offline)
        self._position_panel()
        self.panel.update_data(value_text, arrow, time_ago, self._offline,
                               chart_entries, low, high, max_sgv, hours, tir)

    @staticmethod
    def _format_value(sgv: int, unit: str) -> str:
        if unit == "mmol/L":
            return f"{sgv / _MGDL_PER_MMOLL:.1f}"
        return f"{int(sgv)}"

    @staticmethod
    def _time_ago(date_ms: int) -> str:
        now_ms = int(datetime.now().timestamp() * 1000)
        diff = (now_ms - date_ms) // 60000
        if diff < 1:
            return "刚刚"
        if diff < 60:
            return f"{diff} 分钟前"
        return f"{diff // 60} 小时前"
