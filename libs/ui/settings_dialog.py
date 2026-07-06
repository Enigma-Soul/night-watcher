"""设置对话框：gui 设置 + 数据源选择 + 当前 adapter 配置编辑。

发 ``settings_changed(dict)``，结构 ``{"gui": {...}, "adapter": {id: {...}}}``，
App 收到后写回 Config 并按需刷新。警报线/最大值按当前 unit 输入，保存时
统一转回 mg/dL 内部存储（修正旧代码 unit 语义反转 bug）。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
)

from libs.theme import scan_themes

_MGDL_PER_MMOLL = 18.018
_TIME_OPTIONS = [1, 6, 12, 24]

# 各 adapter 需在设置里编辑的配置键（key 含 token/secret 时密码模式）
_ADAPTER_FIELDS = {
    "sisensing": ["ss_token", "ss_region", "timeout", "retries"],
    "nightscout": ["ns_url", "api_secret", "count"],
}

# 整型字段：保存时转 int，避免 config 存成字符串（adapter 的 int() 兜底之外再加一道）
_INT_FIELDS = {"timeout", "retries", "count"}


class SettingsDialog(QDialog):
    settings_changed = Signal(dict)

    def __init__(
        self, gui: dict, adapter_configs: dict, adapter_sources: list[tuple[str, str]], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(440, 520)
        self._gui = dict(gui)
        self._adapter_configs = {k: dict(v) for k, v in adapter_configs.items()}
        self._sources = adapter_sources
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        is_mmol = self._gui.get("unit", "mmol/L") == "mmol/L"
        self._low_edit = QLineEdit(self._fmt(self._gui.get("low_line", 72), is_mmol))
        self._high_edit = QLineEdit(self._fmt(self._gui.get("high_line", 180), is_mmol))
        self._max_edit = QLineEdit(self._fmt(self._gui.get("max", 270), is_mmol))

        self._theme_combo = QComboBox()
        available = scan_themes()
        self._theme_combo.addItems(available)
        current = self._gui.get("theme", "default")
        if current in available:
            self._theme_combo.setCurrentText(current)
        elif "default" in available:
            self._theme_combo.setCurrentText("default")

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["mmol/L", "mg/dL"])
        self._unit_combo.setCurrentText(self._gui.get("unit", "mmol/L"))

        self._time_combo = QComboBox()
        self._time_combo.addItems(["1 小时", "6 小时", "12 小时", "24 小时"])
        hours = int(self._gui.get("time_range", 6))
        self._time_combo.setCurrentIndex(
            _TIME_OPTIONS.index(hours) if hours in _TIME_OPTIONS else 1
        )

        self._source_combo = QComboBox()
        for aid, name in self._sources:
            self._source_combo.addItem(name, aid)
        active = self._gui.get("active_adapter", "")
        for i in range(self._source_combo.count()):
            if self._source_combo.itemData(i) == active:
                self._source_combo.setCurrentIndex(i)
                break

        form.addRow("低警报线:", self._low_edit)
        form.addRow("高警报线:", self._high_edit)
        form.addRow("框内最大值:", self._max_edit)
        form.addRow("主题:", self._theme_combo)
        form.addRow("血糖单位:", self._unit_combo)
        form.addRow("时间范围:", self._time_combo)
        form.addRow("数据源:", self._source_combo)
        layout.addLayout(form)

        self._adapter_refs: dict[str, dict[str, QLineEdit]] = {}
        for aid, name in self._sources:
            box = QGroupBox(f"{name} ({aid})")
            bform = QFormLayout(box)
            refs: dict[str, QLineEdit] = {}
            for key in _ADAPTER_FIELDS.get(aid, []):
                le = QLineEdit(str(self._adapter_configs.get(aid, {}).get(key, "")))
                if "token" in key or "secret" in key:
                    le.setEchoMode(QLineEdit.Password)
                bform.addRow(f"{key}:", le)
                refs[key] = le
            self._adapter_refs[aid] = refs
            layout.addWidget(box)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._apply)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @staticmethod
    def _fmt(mgdl: float, is_mmol: bool) -> str:
        return f"{mgdl / _MGDL_PER_MMOLL:.1f}" if is_mmol else f"{int(mgdl)}"

    def _apply(self):
        is_mmol = self._unit_combo.currentText() == "mmol/L"
        try:
            low = float(self._low_edit.text())
            high = float(self._high_edit.text())
            mx = float(self._max_edit.text())
            if is_mmol:
                low, high, mx = low * _MGDL_PER_MMOLL, high * _MGDL_PER_MMOLL, mx * _MGDL_PER_MMOLL
        except ValueError:
            return  # 输入非法，不关闭
        gui = {
            "low_line": low,
            "high_line": high,
            "max": mx,
            "theme": self._theme_combo.currentText(),
            "unit": self._unit_combo.currentText(),
            "time_range": _TIME_OPTIONS[self._time_combo.currentIndex()],
            "active_adapter": self._source_combo.currentData(),
        }
        adapter = {}
        for aid, refs in self._adapter_refs.items():
            cfg = {}
            for k, le in refs.items():
                if k in _INT_FIELDS:
                    s = le.text().strip()
                    if s == "":
                        continue  # 留空则不覆盖，沿用 config 现值
                    try:
                        cfg[k] = int(s)
                    except ValueError:
                        return  # 非整数，不关闭（与 low/high/max 校验一致）
                else:
                    cfg[k] = le.text()
            adapter[aid] = cfg
        self.settings_changed.emit({"gui": gui, "adapter": adapter})
        self.accept()
