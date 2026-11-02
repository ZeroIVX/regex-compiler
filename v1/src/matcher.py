"""匹配器 —— 基于最小化 DFA 进行正则匹配

提供三种匹配模式：
- match: 完全匹配（整个字符串是否被正则接受）
- search: 搜索匹配（找到第一个匹配子串）
- findall: 找到所有匹配子串
"""

from __future__ import annotations
from .lexer import lex, TokenType
from .parser import parse
from .nfa import ThompsonBuilder, NFA
from .dfa import build_dfa, DFA, simulate_dfa
from .minimize import minimize_dfa, MinDFA


class RegexMatcher:
    """正则表达式匹配器 —— 完整的编译流水线"""

    def __init__(self, pattern: str):
        self.pattern = pattern

        # 词法分析
        tokens = lex(pattern)
        self._tokens = tokens

        # 语法分析
        self._ast = parse(pattern)

        # NFA 构造
        builder = ThompsonBuilder()
        self._nfa = builder.build(self._ast)

        # DFA 构造
        self._dfa = build_dfa(self._nfa)

        # 最小化
        self._min_dfa = minimize_dfa(self._dfa)

        # 匹配时使用的字母表
        self._alphabet = self._nfa.alphabet

    # ---- 公开接口 ----

    def match(self, text: str) -> bool:
        """完全匹配：检查整个字符串是否被正则接受"""
        return self._match_full(text, self._min_dfa)

    def search(self, text: str) -> tuple[int, int] | None:
        """搜索：返回第一个匹配子串的 (start, end)，找不到返回 None"""
        if not text:
            if self.match(""):
                return (0, 0)
            return None
        return self._search_impl(text, self._min_dfa)

    def findall(self, text: str) -> list[tuple[int, int, str]]:
        """找到所有匹配，返回 [(start, end, substring), ...]"""
        results: list[tuple[int, int, str]] = []
        pos = 0
        text_len = len(text)
        while pos < text_len:
            result = self._search_impl(text, self._min_dfa, start=pos)
            if result is None:
                break
            start, end = result
            if start == end:
                # 空匹配，前进一个字符避免死循环
                results.append((start, end, ""))
                pos = end + 1
            else:
                results.append((start, end, text[start:end]))
                pos = end
        return results

    # ---- 访问器 ----

    @property
    def ast(self):
        return self._ast

    @property
    def nfa(self) -> NFA:
        return self._nfa

    @property
    def dfa(self) -> DFA:
        return self._dfa

    @property
    def min_dfa(self) -> MinDFA:
        return self._min_dfa

    # ---- 内部实现 ----

    def _match_full(self, text: str, min_dfa: MinDFA) -> bool:
        """完全匹配"""
        current = min_dfa.start
        for ch in text:
            if ch in current.transitions:
                current = current.transitions[ch]
            else:
                return False
        return current.is_final

    def _search_impl(self, text: str, min_dfa: MinDFA,
                     start: int = 0) -> tuple[int, int] | None:
        """在 text[start:] 中搜索第一个匹配"""
        text_len = len(text)
        for i in range(start, text_len):
            current = min_dfa.start
            if current.is_final:
                return (i, i)

            for j in range(i, text_len):
                ch = text[j]
                if ch in current.transitions:
                    current = current.transitions[ch]
                    if current.is_final:
                        return (i, j + 1)
                else:
                    break

            # 检查是否在当前位置有匹配
            # (上面循环中已处理)

        return None

    def simulate(self, text: str):
        """返回模拟的详细步骤（用于可视化）"""
        current = self._min_dfa.start
        steps: list[dict] = []

        steps.append({
            "pos": 0,
            "char": "",
            "from_state": -1,
            "to_state": current.id,
            "accepted": current.is_final,
        })

        for i, ch in enumerate(text):
            from_state = current.id
            if ch in current.transitions:
                current = current.transitions[ch]
                steps.append({
                    "pos": i + 1,
                    "char": ch,
                    "from_state": from_state,
                    "to_state": current.id,
                    "accepted": current.is_final,
                })
            else:
                steps.append({
                    "pos": i + 1,
                    "char": ch,
                    "from_state": from_state,
                    "to_state": -1,
                    "accepted": False,
                    "error": True,
                })
                return steps

        return steps

    def print_info(self) -> str:
        """打印编译器流水线信息"""
        lines = [
            f"Pattern: {self.pattern}",
            f"Tokens: {len(self._tokens)}",
            f"NFA States: {len(self._nfa.states)}",
            f"DFA States: {len(self._dfa.states)}",
            f"Min DFA States: {len(self._min_dfa.states)}",
            f"Alphabet: {sorted(self._alphabet)}",
            f"Compression: {len(self._dfa.states)} -> {len(self._min_dfa.states)} states "
            f"({100 * (1 - len(self._min_dfa.states) / max(1, len(self._dfa.states))):.1f}% reduction)",
        ]
        return "\n".join(lines)
