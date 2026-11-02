"""AST 节点定义 —— 正则表达式的抽象语法树节点类型"""

from abc import ABC
from dataclasses import dataclass


class ASTNode(ABC):
    """AST 节点基类"""
    pass


@dataclass
class CharNode(ASTNode):
    """单个字符匹配节点，如 a"""
    char: str

    def __repr__(self):
        return f"Char({self.char!r})"


@dataclass
class DotNode(ASTNode):
    """通配符节点，匹配任意字符 ."""

    def __repr__(self):
        return "Dot"


@dataclass
class ConcatNode(ASTNode):
    """连接节点，如 ab"""
    left: ASTNode
    right: ASTNode

    def __repr__(self):
        return f"Concat({self.left!r}, {self.right!r})"


@dataclass
class UnionNode(ASTNode):
    """选择节点，如 a|b"""
    left: ASTNode
    right: ASTNode

    def __repr__(self):
        return f"Union({self.left!r}, {self.right!r})"


@dataclass
class StarNode(ASTNode):
    """闭包节点，如 a*"""
    child: ASTNode

    def __repr__(self):
        return f"Star({self.child!r})"


@dataclass
class PlusNode(ASTNode):
    """正闭包节点，如 a+"""
    child: ASTNode

    def __repr__(self):
        return f"Plus({self.child!r})"


@dataclass
class QuestionNode(ASTNode):
    """可选节点，如 a?"""
    child: ASTNode

    def __repr__(self):
        return f"Question({self.child!r})"


@dataclass
class CharClassNode(ASTNode):
    """字符类节点，如 [a-z0-9]

    chars 已经是展开后的具体字符集：取反形式在词法阶段就展开为
    「全集减去被排除字符」，因此这里不再保留 negated 标志。
    """
    chars: frozenset[str]

    def __repr__(self):
        return f"CharClass({{{''.join(sorted(self.chars))}}})"
