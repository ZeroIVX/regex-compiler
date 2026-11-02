"""Web 图形界面 —— 基于标准库的多线程 HTTP 服务。"""

from __future__ import annotations

from .server import RegexAPIHandler, serve

__all__ = ["RegexAPIHandler", "serve"]
