"""核心模块 —— 编译流水线与匹配引擎。"""

from __future__ import annotations

from .matcher import CompileResult, RegexMatcher, compile_pattern

__all__ = ["CompileResult", "RegexMatcher", "compile_pattern"]
