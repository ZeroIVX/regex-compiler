"""字符类语义与 **不相交字母表划分**。

为什么需要「不相交划分」
------------------------
DFA 的定义要求：给定输入字符，转移是唯一确定的。
如果直接把「单个字符」当作转移标签，像 ``a|[a-z]`` 这样的模式会在同一个
状态上产生两条可同时匹配的转移，破坏确定性 —— 这也是原实现中 ``.``
通配符与 ``[^...]`` 取反字符类语义失效的根因。

本模块的做法
------------
1. 模式中的每一种字符条件用 :class:`CharClass` 描述（精确集合 / 取反集合）；
2. 收集模式里显式提及过的字符作为 *分界字符*，其余字符统一归入 REST 块；
3. 以「该字符被哪些 CharClass 包含」作为签名对字符分组 ——
   同组字符在任意字符类上的归属完全一致，因此可合并为单个 DFA 转移标签；
4. 只有被至少一个字符类覆盖的块才进入 DFA 字母表，未覆盖的块天然拒绝。

这样既完整保留了 ``.`` 与 ``[^a-z]`` 的语义，又让 DFA 保持真正的确定性。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

NEWLINE = "\n"


@dataclass(frozen=True)
class CharClass:
    """一个字符类。

    Attributes:
        chars: 精确语义下为「允许的字符」；取反语义下为「被排除的字符」。
        negated: 是否取反。取反时匹配所有 *不在* ``chars`` 中的字符。
    """

    chars: frozenset[str]
    negated: bool = False

    def contains(self, ch: str) -> bool:
        """判断字符 ``ch`` 是否属于本字符类。"""
        return (ch in self.chars) != self.negated

    def label(self) -> str:
        """人类可读的描述，用于可视化输出。"""
        if self.negated:
            if not self.chars:
                return "任意字符"
            return "任意字符(除" + format_ranges(self.chars) + ")"
        return format_ranges(self.chars)


def dot_class() -> CharClass:
    """``.`` 通配符：匹配除换行外的任意字符（与 Python ``re`` 语义一致）。"""
    return CharClass(frozenset({NEWLINE}), negated=True)


def literal_class(ch: str) -> CharClass:
    """单个字面字符。"""
    return CharClass(frozenset({ch}))


def format_ranges(chars: Iterable[str]) -> str:
    """把字符集合压缩成 ``a-z,0-9`` 形式的紧凑描述。"""
    items = sorted(chars)
    if not items:
        return "(空)"

    parts: list[str] = []
    start = prev = items[0]
    for ch in items[1:]:
        if ord(ch) == ord(prev) + 1:
            prev = ch
            continue
        parts.append(start if start == prev else f"{start}-{prev}")
        start = prev = ch
    parts.append(start if start == prev else f"{start}-{prev}")
    return ",".join(parts)


@dataclass(frozen=True)
class CharBlock:
    """一个互不相交的字符块，是 DFA 的一个转移标签。"""

    id: int
    sample: str              # 代表字符，用于与 CharClass 做包含判定
    members: frozenset[str]  # 块内被模式提及的字符
    is_rest: bool            # 是否代表「未被模式提及」的字符
    label: str

    def __repr__(self) -> str:
        return f"CharBlock(id={self.id}, label={self.label!r})"


class Alphabet:
    """互不相交的字符块集合，构成 DFA 的字母表。"""

    def __init__(
        self,
        blocks: Sequence[CharBlock],
        char_to_block: dict[str, int],
        rest_block: int | None,
        covered: Sequence[int],
    ) -> None:
        self._blocks = tuple(blocks)
        self._char_to_block = char_to_block
        self._rest_block = rest_block
        self._covered = tuple(covered)

    @property
    def blocks(self) -> tuple[CharBlock, ...]:
        """所有字符块（含未被覆盖的）。"""
        return self._blocks

    @property
    def covered_ids(self) -> tuple[int, ...]:
        """被至少一个字符类覆盖的块 id —— 这些才构成 DFA 的转移标签。"""
        return self._covered

    @property
    def covered_blocks(self) -> tuple[CharBlock, ...]:
        """被覆盖的字符块。"""
        return tuple(self._blocks[i] for i in self._covered)

    def block_of(self, ch: str) -> int | None:
        """返回字符 ``ch`` 所属的块 id；若无对应块返回 ``None``。"""
        if ch in self._char_to_block:
            return self._char_to_block[ch]
        return self._rest_block

    def block(self, block_id: int) -> CharBlock:
        """按 id 取字符块。"""
        return self._blocks[block_id]

    def label_of(self, block_id: int) -> str:
        """按 id 取字符块的可读描述。"""
        return self._blocks[block_id].label

    def __repr__(self) -> str:
        return (
            f"Alphabet(blocks={len(self._blocks)}, covered={len(self._covered)}, "
            f"labels={[b.label for b in self.covered_blocks]})"
        )


def _pick_unmentioned(mentioned: set[str]) -> str:
    """挑一个未被模式提及的字符作为 REST 块的代表。"""
    for code in range(0xE000, 0xF8FF):  # 私有使用区，几乎不会与用户模式冲突
        ch = chr(code)
        if ch not in mentioned:
            return ch
    return "\uffff"


def build_alphabet(classes: Sequence[CharClass]) -> Alphabet:
    """依据模式中出现的字符类构造互不相交的字母表。

    Args:
        classes: 模式中出现的全部字符类（可重复，重复不影响结果）。

    Returns:
        :class:`Alphabet` 实例。
    """
    unique: list[CharClass] = []
    seen: set[CharClass] = set()
    for cl in classes:
        if cl not in seen:
            seen.add(cl)
            unique.append(cl)

    mentioned: set[str] = set()
    for cl in unique:
        mentioned |= cl.chars

    # 按「被哪些字符类包含」的签名分组
    groups: dict[frozenset[int], set[str]] = {}
    for ch in sorted(mentioned):
        signature = frozenset(i for i, cl in enumerate(unique) if cl.contains(ch))
        groups.setdefault(signature, set()).add(ch)

    # 未被提及的字符共享同一个签名
    rest_sample = _pick_unmentioned(mentioned)
    rest_signature = frozenset(i for i, cl in enumerate(unique) if cl.contains(rest_sample))
    groups.setdefault(rest_signature, set()).add(rest_sample)

    blocks: list[CharBlock] = []
    char_to_block: dict[str, int] = {}
    rest_block: int | None = None

    for block_id, (_signature, members) in enumerate(sorted(groups.items(), key=lambda kv: min(kv[1]))):
        is_rest = rest_sample in members
        mentioned_members = frozenset(m for m in members if m != rest_sample)
        sample = rest_sample if is_rest else min(members)

        covering = [cl for cl in unique if cl.contains(sample)]
        exact_covering = [cl for cl in covering if not cl.negated]
        if exact_covering:
            label = format_ranges(mentioned_members)
        elif is_rest:
            excluded: set[str] = set()
            for cl in covering:
                excluded |= cl.chars
            label = "其他字符" if not excluded else f"其他字符(除{format_ranges(excluded)})"
        else:
            label = format_ranges(mentioned_members)

        block = CharBlock(
            id=block_id,
            sample=sample,
            members=mentioned_members,
            is_rest=is_rest,
            label=label,
        )
        blocks.append(block)
        if is_rest:
            rest_block = block_id
        for ch in mentioned_members:
            char_to_block[ch] = block_id

    # 仅被覆盖的块进入 DFA 字母表
    covered = [
        block.id
        for block in blocks
        if any(cl.contains(block.sample) for cl in unique)
    ]

    return Alphabet(blocks, char_to_block, rest_block, covered)
