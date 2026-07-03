"""loguru 日志方案：彩色终端 + 文件落地 + 线程安全。

应用启动时调用 setup(path) 完成配置；get() 返回全局 loguru logger。
loguru 的 format 用 ``{}`` 而非 stdlib ``%s`` —— 调用侧统一。
"""

from __future__ import annotations

import sys

from loguru import logger

FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<cyan>{level: <7}</cyan> | <level>{message}</level>"
)

_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {message}"


def setup(path: str = "log.log"):
    """初始化输出：stderr 彩色 + 路径文件落地。重复调用仅首次生效。"""
    if getattr(logger, "_night_watcher_configured", False):
        return
    logger._night_watcher_configured = True

    logger.remove()
    logger.add(
        sys.stderr,
        format=FORMAT,
        level="DEBUG",
        colorize=True,
    )
    logger.add(
        path,
        format=_FILE_FORMAT,
        level="DEBUG",
        rotation="1 MB",
        retention="7 days",
        encoding="utf-8",
    )


def get():
    """返回全局 loguru logger。"""
    return logger
