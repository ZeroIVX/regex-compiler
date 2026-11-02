"""抽象语法树节点定义。

AST 采用不可变 dataclass，配合 Python 3.10+ 的结构化模式匹配
（``match`` / ``case``）可以在编译器后端优雅地分派。
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from ..charset import CharClass, dot_class


class ASTNode(ABC):
    """AST 节点基类。"""


@dataclass(frozen=True)
class CharNode(ASTNode):
    """单个字面字符，如 ``a``。"""

    char: str

    def __repr__(self) -> str:
        return f"Char({self.char!r})"


@dataclass(frozen=True)
class DotNode(ASTNode):
    """通配符节点 ``.``，匹配除换行外的任意字符。"""

    def __repr__(self) -> str:
        return "Dot"


@dataclass(frozen=True)
class CharClassNode(ASTNode):
    """字符类节点，如 ``[a-z0-9]`` 或取反形式 ``[^a-z]``。"""

    charset: CharClass

    def __repr__(self) -> str:
        return f"CharClass({self.charset.label()})"


@dataclass(frozen=True)
class ConcatNode(ASTNode):
    """连接节点，如 ``ab``。"""

    left: ASTNode
    right: ASTNode

    def __repr__(self) -> str:
        return f"Concat({self.left!r}, {self.right!r})"


@dataclass(frozen=True)
class UnionNode(ASTNode):
    """选择节点，如 ``a|b``。"""

    left: ASTNode
    right: ASTNode

    def __repr__(self) -> str:
        return f"Union({self.left!r}, {self.right!r})"


@dataclass(frozen=True)
class StarNode(ASTNode):
    """闭包节点，如 ``a*``。"""

    child: ASTNode

    def __repr__(self) -> str:
        return f"Star({self.child!r})"


@dataclass(frozen=True)
class PlusNode(ASTNode):
    """正闭包节点，如 ``a+``。"""

    child: ASTNode

    def __repr__(self) -> str:
        return f"Plus({self.child!r})"


@dataclass(frozen=True)
class QuestionNode(ASTNode):
    """可选节点，如 ``a?``。"""

    child: ASTNode

    def __repr__(self) -> str:
        return f"Question({self.child!r})"


def collect_charsets(node: ASTNode) -> list[CharClass]:
    """收集 AST 中出现的全部字符类，供字母表划分使用。

    结果的顺序与 AST 的遍历顺序一致，因此同一模式总是得到同一份字母表。
    """
    result: list[CharClass] = []
    match node:
        case CharNode(char):
            result.append(CharClass(frozenset({char})))
        case DotNode():
            result.append(dot_class())
        case CharClassNode(charset):
            result.append(charset)
        case ConcatNode(left, right) | UnionNode(left, right):
            result.extend(collect_charsets(left))
            result.extend(collect_charsets(right))
        case StarNode(child) | PlusNode(child) | QuestionNode(child):
            result.extend(collect_charsets(child))
        case _:
            pass
    return result
