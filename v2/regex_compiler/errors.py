"""统一异常体系。

编译器各阶段的错误全部继承自 :class:`RegexCompilerError`，
调用方既可以按阶段精确捕获，也可以一次性兜底处理。
"""

from __future__ import annotations


class RegexCompilerError(Exception):
    """正则表达式编译器的基础异常。"""


class LexerError(RegexCompilerError):
    """词法分析错误：无法识别的字符、未闭合的字符类等。"""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"词法错误 (位置 {position}): {message}")
        self.position = position
        self.raw_message = message


class ParserError(RegexCompilerError):
    """语法分析错误：违反文法规则、括号不配对等。"""

    def __init__(self, message: str, position: int | None = None) -> None:
        if position is None:
            super().__init__(f"语法错误: {message}")
        else:
            super().__init__(f"语法错误 (位置 {position}): {message}")
        self.position = position
        self.raw_message = message


class BuildError(RegexCompilerError):
    """自动机构造错误：AST 无法构造出合法的自动机等。"""
