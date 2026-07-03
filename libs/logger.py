"""日志封装：基于 stdlib logging，文件 + 控制台双输出。

弃用旧 ``library/gui/module.py::log`` 的"未设 path 即 sys.exit(1)"暴政——
此处文件不可写时仅降级为控制台输出，不阻断启动。
"""
from __future__ import annotations

import logging
from pathlib import Path

_LOGGER_NAME = "night_watcher"
_configured = False


def setup(path: str | Path = "log.log", level: int = logging.INFO) -> logging.Logger:
    """配置 handler，返回 logger。重复调用安全（仅首次生效）。"""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%y/%m/%d %H:%M:%S")

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    try:
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        # 文件不可写（只读目录等）时不阻断启动
        pass

    _configured = True
    return logger


def get() -> logging.Logger:
    """返回 logger（未 setup 时也能用，输出到已挂载的 handler）。"""
    return logging.getLogger(_LOGGER_NAME)
