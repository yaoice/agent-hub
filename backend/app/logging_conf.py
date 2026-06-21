# -*- coding: utf-8 -*-
"""统一日志初始化：按 LOG_LEVEL 配置应用日志输出。

应用内统一使用 `logging.getLogger(__name__)`（名称以 "app." 开头），
本模块为 "app" 父 logger 配置独立 handler，保证日志始终以统一格式输出，
不依赖 uvicorn 是否已配置 root logger。
"""
from __future__ import annotations

import logging

from .config import settings

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging() -> None:
    """初始化应用日志（幂等）。LOG_LEVEL 非法时回退 INFO。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, str(settings.log_level).upper(), logging.INFO)

    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        app_logger.addHandler(handler)
    # 自带 handler，避免再向 root 传播导致重复打印
    app_logger.propagate = False

    _CONFIGURED = True
