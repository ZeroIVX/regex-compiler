"""正则表达式编译器 —— 从正则表达式到最小化 DFA 的完整实现。

本包实现了《编译原理》课程中自动机理论的核心内容：

- **词法分析**：把正则表达式切分为 Token 流
- **语法分析**：递归下降法构造抽象语法树
- **NFA 构造**：Thompson 算法，O(n) 时间
- **DFA 构造**：子集构造法
- **DFA 最小化**：Hopcroft 算法，O(k·n·log n)

对外只暴露稳定的公共 API，模块内部的组织可以自由演进。

Example:
    >>> from regex_compiler import RegexMatcher
    >>> RegexMatcher(r"(a|b)*abb").match("ababb")
    True
"""

from __future__ import annotations

from .charset import Alphabet, CharBlock, CharClass, build_alphabet
from .core.matcher import CompileResult, RegexMatcher, compile_pattern
from .errors import (
    BuildError,
    LexerError,
    ParserError,
    RegexCompilerError,
)

__version__ = "2.0.0"

__all__ = [
    "Alphabet",
    "BuildError",
    "CharBlock",
    "CharClass",
    "CompileResult",
    "LexerError",
    "ParserError",
    "RegexCompilerError",
    "RegexMatcher",
    "__version__",
    "build_alphabet",
    "compile_pattern",
]
