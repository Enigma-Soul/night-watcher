"""night-watcher 入口（根下唯一 .py 文件）。

启动顺序：
    QApplication 早建（供 QMessageBox）
    → Config.load + logger.setup
    → adapter_loader.scan（id 重复/为空 → 弹窗退出）
    → 实例化 {id: cls(config.adapter_config(id))}
    → active 失效则回退第一个并写回
    → App.run()
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from libs.adapter_loader import EmptyAdapterIdError, DuplicateAdapterIdError, scan
from libs.cache import Cache
from libs.config import Config
from libs.logger import get as get_logger
from libs.logger import setup as setup_logger
from libs.ui.app import App


def main():
    config = Config("config.json")
    config.load()
    setup_logger("log.log")
    log = get_logger()
    log.info("night-watcher 启动")

    app_qt = QApplication(sys.argv)  # 早建，供 QMessageBox

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

    cache = Cache("cache.json")
    app = App(config, cache, instances, active)
    log.info("活跃数据源: %s", active)
    app.run()


if __name__ == "__main__":
    main()
