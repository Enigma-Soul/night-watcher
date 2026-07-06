"""night-watcher 入口（根下唯一 .py 文件）。

启动顺序：
    Config.load + logger.setup
    → QApplication 早建（供 QMessageBox）并设窗口图标
    → adapter_loader.scan（id 重复/为空 → 弹窗退出）
    → 实例化 {id: cls(config.adapter_config(id))}
    → active 失效则回退第一个并写回
    → App.run()
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from libs.adapter_loader import DuplicateAdapterIdError, EmptyAdapterIdError, scan
from libs.config import Config
from libs.logger import get as get_logger
from libs.logger import setup as setup_logger
from libs.ui.app import App


def _resource_path(name: str) -> str:
    """解析资源绝对路径：打包后取 ``sys._MEIPASS``，开发态取源码根目录。"""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent
    return str(Path(base) / name)


def main():
    # Windows 任务栏按 AppUserModelID 分组进程；显式设置避免归到 python.exe 默认图标
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EnigmaSoul.NightWatcher")

    config = Config("config.json")
    config.load()
    setup_logger("log.log")
    log = get_logger()
    log.info("night-watcher 启动")

    qt_app = QApplication(sys.argv)  # 早建，供 QMessageBox
    qt_app.setWindowIcon(QIcon(_resource_path("icon.png")))

    try:
        classes = scan("adapter")
    except (DuplicateAdapterIdError, EmptyAdapterIdError, ImportError) as e:
        QMessageBox.critical(None, "启动失败", str(e))
        sys.exit(1)

    if not classes:
        QMessageBox.critical(None, "启动失败", "未发现任何 adapter，请放入 adapter/*.py")
        sys.exit(1)

    instances = {cls.id: cls(config.adapter_config(cls.id)) for cls in classes}

    active = config.gui().get("active_adapter", "")
    if active not in instances:
        active = next(iter(instances))
        config.set_active_adapter(active)

    app = App(config, instances, active)
    log.info("活跃数据源: {}", active)
    app.run()


if __name__ == "__main__":
    main()
