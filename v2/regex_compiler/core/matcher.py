"""匹配引擎 —— 驱动完整编译流水线并执行匹配。

流水线：

.. code-block:: text

    正则表达式
        │  Lexer      词法分析
        ▼
    Token 流
        │  Parser     递归下降语法分析
        ▼
    AST
        │  build_alphabet  字符类不相交划分
        ▼
    Alphabet
        │  Thompson   NFA 构造
        ▼
    ε-NFA
        │  Subset Construction  子集构造
        ▼
    DFA
        │  Hopcroft   DFA 最小化
        ▼
    MinDFA  ──►  match / search / findall
"""

from __future__ import annotations

from dataclasses import dataclass

from ..backend.dfa import DFA, build_dfa
from ..backend.minimize import MinDFA, minimize_dfa
from ..backend.nfa import NFA, ThompsonBuilder
from ..charset import Alphabet, build_alphabet
from ..frontend.ast_nodes import ASTNode, collect_charsets
from ..frontend.lexer import Token, lex
from ..frontend.parser import parse_tokens


@dataclass
class CompileResult:
    """一次编译的全部产物。"""

    pattern: str
    tokens: list[Token]
    ast: ASTNode
    alphabet: Alphabet
    nfa: NFA
    dfa: DFA
    min_dfa: MinDFA


class RegexMatcher:
    """正则表达式匹配器 —— 封装完整编译流水线。

    典型用法::

        matcher = RegexMatcher(r"(a|b)*abb")
        matcher.match("ababb")      # True
        matcher.search("xxababb")   # (2, 7)
        matcher.findall("ababbababb")
    """

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        result = compile_pattern(pattern)
        self._tokens = result.tokens
        self._ast = result.ast
        self._alphabet = result.alphabet
        self._nfa = result.nfa
        self._dfa = result.dfa
        self._min_dfa = result.min_dfa

    # ---- 公开接口 ----

    def match(self, text: str) -> bool:
        """完全匹配：检查整个字符串是否被正则接受。"""
        return self._match_full(text)

    def search(self, text: str) -> tuple[int, int] | None:
        """搜索匹配：返回第一个匹配子串的 ``(start, end)``，找不到返回 ``None``。"""
        if not text:
            return (0, 0) if self.match("") else None
        return self._search_impl(text, 0)

    def findall(self, text: str) -> list[tuple[int, int, str]]:
        """查找所有不重叠的匹配，返回 ``[(start, end, substring), ...]``。"""
        results: list[tuple[int, int, str]] = []
        pos = 0
        text_len = len(text)

        while pos <= text_len:
            result = self._search_impl(text, pos)
            if result is None:
                break
            start, end = result
            results.append((start, end, text[start:end]))
            # 空匹配时前进一位，避免死循环
            pos = end + 1 if start == end else end

        return results

    # ---- 访问器 ----

    @property
    def tokens(self) -> list[Token]:
        """Token 流。"""
        return self._tokens

    @property
    def ast(self) -> ASTNode:
        """抽象语法树。"""
        return self._ast

    @property
    def alphabet(self) -> Alphabet:
        """不相交字母表。"""
        return self._alphabet

    @property
    def nfa(self) -> NFA:
        """ε-NFA。"""
        return self._nfa

    @property
    def dfa(self) -> DFA:
        """子集构造得到的 DFA。"""
        return self._dfa

    @property
    def min_dfa(self) -> MinDFA:
        """最小化 DFA。"""
        return self._min_dfa

    # ---- 内部实现 ----

    def _match_full(self, text: str) -> bool:
        """完全匹配：在最小 DFA 上跑完整个字符串。"""
        current = self._min_dfa.start
        for ch in text:
            block_id = self._alphabet.block_of(ch)
            if block_id is None or block_id not in current.transitions:
                return False
            current = current.transitions[block_id]
        return current.is_final

    def _search_impl(self, text: str, start: int) -> tuple[int, int] | None:
        """在 ``text[start:]`` 中查找第一个匹配。

        逐个起点尝试在最小 DFA 上前进，记录沿途最远的接受位置 ——
        这保证了「最左最长」的匹配语义（与 POSIX 正则一致）。
        """
        text_len = len(text)
        for i in range(start, text_len):
            current = self._min_dfa.start
            last_accept = i if current.is_final else -1

            for j in range(i, text_len):
                block_id = self._alphabet.block_of(text[j])
                if block_id is None or block_id not in current.transitions:
                    break
                current = current.transitions[block_id]
                if current.is_final:
                    last_accept = j + 1

            if last_accept != -1:
                return (i, last_accept)

        # 空串位置上的匹配（模式可匹配空串）
        if start <= text_len and self._min_dfa.start.is_final:
            return (text_len, text_len)
        return None

    def simulate(self, text: str) -> list[dict]:
        """返回匹配过程的详细步骤，用于可视化。"""
        current = self._min_dfa.start
        steps: list[dict] = [
            {
                "pos": 0,
                "char": "",
                "from_state": -1,
                "to_state": current.id,
                "accepted": current.is_final,
            }
        ]

        for i, ch in enumerate(text):
            from_state = current.id
            block_id = self._alphabet.block_of(ch)
            if block_id is not None and block_id in current.transitions:
                current = current.transitions[block_id]
                steps.append(
                    {
                        "pos": i + 1,
                        "char": ch,
                        "from_state": from_state,
                        "to_state": current.id,
                        "accepted": current.is_final,
                    }
                )
            else:
                steps.append(
                    {
                        "pos": i + 1,
                        "char": ch,
                        "from_state": from_state,
                        "to_state": -1,
                        "accepted": False,
                        "error": True,
                    }
                )
                return steps

        return steps

    def print_info(self) -> str:
        """返回编译流水线的统计信息。"""
        dfa_count = len(self._dfa.states)
        min_count = len(self._min_dfa.states)
        reduction = 100 * (1 - min_count / max(1, dfa_count))
        return "\n".join(
            [
                f"Pattern: {self.pattern}",
                f"Tokens: {len(self._tokens)}",
                f"Alphabet Blocks: {len(self._alphabet.covered_ids)}"
                f" ({', '.join(self._alphabet.label_of(i) for i in self._alphabet.covered_ids)})",
                f"NFA States: {len(self._nfa.states)}",
                f"DFA States: {dfa_count}",
                f"Min DFA States: {min_count}",
                f"Compression: {dfa_count} -> {min_count} states ({reduction:.1f}% reduction)",
            ]
        )


def compile_pattern(pattern: str) -> CompileResult:
    """执行完整编译流水线，返回各阶段产物。"""
    tokens = lex(pattern)

    meaningful = [t for t in tokens if t.type.name != "EOF"]
    if meaningful:
        ast = parse_tokens(tokens)
    else:
        from ..frontend.ast_nodes import CharNode

        ast = CharNode("")

    alphabet = build_alphabet(collect_charsets(ast))

    nfa = ThompsonBuilder().build(ast)
    dfa = build_dfa(nfa, alphabet)
    min_dfa = minimize_dfa(dfa)

    return CompileResult(
        pattern=pattern,
        tokens=meaningful,
        ast=ast,
        alphabet=alphabet,
        nfa=nfa,
        dfa=dfa,
        min_dfa=min_dfa,
    )


__all__ = ["CompileResult", "RegexMatcher", "compile_pattern"]
