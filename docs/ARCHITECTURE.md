# 架构设计

本文说明 `regex-compiler` 的整体架构、模块划分与关键设计权衡。
架构图源码见 [`assets/architecture-v2.drawio`](../assets/architecture-v2.drawio)，
可直接用 [draw.io](https://app.diagrams.net/) 打开编辑。

---

## 设计目标

| 目标 | 说明 |
|---|---|
| **阶段可分离** | 编译各阶段职责单一，任一阶段可单独替换或测试 |
| **零运行时依赖** | 仅用 Python 标准库，降低部署与复现成本 |
| **可观测** | 每个阶段的中间产物（Token / AST / NFA / DFA）均可访问与可视化 |
| **可验证** | 语义与工业级引擎对齐，而非「大致可用」 |

---

## 分层结构

```
                    ┌─────────────────────────────┐
                    │        用户入口层            │
                    │  cli.py   web/   start.py   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │          核心层              │
                    │      core/matcher.py         │
                    │   编译流水线 · 匹配引擎       │
                    └───────┬──────────────┬───────┘
                            │              │
          ┌─────────────────▼───┐      ┌───▼─────────────────┐
          │      前端 frontend   │      │   后端 backend      │
          │  lexer → parser     │      │  nfa → dfa → min    │
          │  → ast_nodes        │      │                     │
          └─────────────────────┘      └─────────────────────┘
                            │              │
                    ┌───────▼──────────────▼───────┐
                    │        charset.py            │
                    │  字符类语义 · 不相交字母表    │
                    └──────────────────────────────┘

                    ┌──────────────────────────────┐
                    │     可视化 visualization      │
                    │   layout → svg / drawio      │
                    └──────────────────────────────┘
```

### 为什么这样分层

**前端 / 后端** 的划分来自编译器的经典结构：前端把**字符流**变成**语法树**，
后端把**语法树**变成**可执行机器**。这条界线是稳定的 —— 若要支持新的语法糖，
只动前端；若要更换自动机构造算法，只动后端。

**`charset.py` 独立于前后端**，因为它同时被两处使用：前端需要它表达字符类语义，
后端需要它把字符类划分成互不相交的字母表。放在任何一侧都会造成反向依赖。

**`core/` 只做编排**，不实现算法。它把各阶段串成流水线，并对外暴露
`match` / `search` / `findall` 三种匹配语义。这样「算法」与「用例」解耦 ——
更换匹配策略只需改核心层，不影响自动机实现。

**可视化与 Web 是输出层**，只读不写编译产物，因此可以自由增删而不影响内核。

---

## 模块职责

### 前端 `regex_compiler/frontend/`

| 模块 | 职责 | 关键类型 |
|---|---|---|
| `lexer.py` | 逐字符扫描，产出 Token 流 | `Token`、`TokenType`、`Lexer` |
| `ast_nodes.py` | AST 节点定义（不可变 dataclass） | `CharNode`、`UnionNode` 等 8 种 |
| `parser.py` | LL(1) 递归下降，构造 AST | `Parser`、`print_ast` |

词法分析负责的第一件事是把**字符类**归一化：`[^a-z]` 与 `[a-z]` 在词法层就被
转为带取反标志的 `CharClass` 对象，后续阶段不必再关心方括号语法。

### 后端 `regex_compiler/backend/`

| 模块 | 职责 | 关键类型 |
|---|---|---|
| `nfa.py` | Thompson 构造，AST → ε-NFA | `NFAState`、`NFA`、`ThompsonBuilder` |
| `dfa.py` | 子集构造，ε-NFA → DFA | `DFAState`、`DFA`、`build_dfa` |
| `minimize.py` | Hopcroft 最小化，DFA → 最小 DFA | `MinDFAState`、`MinDFA` |

三个模块严格单向依赖：`minimize` 依赖 `dfa`，`dfa` 依赖 `nfa`，反向无依赖。

### 核心 `regex_compiler/core/`

`matcher.py` 中的 `compile_pattern()` 是唯一的流水线编排点，返回 `CompileResult`
（含 Token、AST、字母表、NFA、DFA、最小 DFA 六项产物），
`RegexMatcher` 在此之上提供面向用户的匹配接口。

### 其他

| 模块 | 职责 |
|---|---|
| `charset.py` | 字符类语义、字符块划分、`Alphabet` 抽象 |
| `errors.py` | 统一异常体系（`RegexCompilerError` 及三个子类） |
| `visualization/` | 通用图结构 → SVG / draw.io XML 渲染 |
| `web/` | 标准库 `ThreadingHTTPServer` + 原生前端页面 |
| `cli.py` | argparse 命令行接口 |

---

## 数据流

一次编译的完整数据流：

```
pattern: str
   │
   │ lex()
   ▼
list[Token]                     ── 记号序列，携带位置信息用于报错
   │
   │ parse_tokens()
   ▼
ASTNode                         ── 不可变语法树，可用模式匹配分派
   │
   │ collect_charsets() → build_alphabet()
   ▼
Alphabet                        ── 互不相交的字符块，DFA 的真实字母表
   │
   │ ThompsonBuilder.build()
   ▼
NFA                             ── 转移标签为 CharClass，而非具体字符
   │
   │ build_dfa(nfa, alphabet)
   ▼
DFA                             ── 转移标签为字符块 id，严格确定
   │
   │ minimize_dfa(dfa)
   ▼
MinDFA                          ── 状态数最少，语义等价
   │
   ▼
match / search / findall
```

**关键点**：`Alphabet` 在 NFA 之前就已确定。这是因为 NFA 的转移边以 `CharClass`
为标签，而 DFA 需要把这些标签映射到互不相交的字符块上。先算字母表，
能让 DFA 构造阶段直接遍历字符块，无需在构造过程中反复判断重叠。

---

## 字符类的处理：本项目最核心的设计

### 问题

DFA 的定义要求：给定输入字符，转移唯一确定。如果直接把「单字符」当作转移标签，
下面的模式会破坏确定性：

```
a|[a-z]
```

同一个状态上存在 `a` 和 `a-z` 两条边，输入 `a` 时两条边都可命中 —— 这不是 DFA。

### 解法：不相交字符块划分

1. 收集模式中所有字符类 `C₁ … Cₘ`
2. 取所有被显式提及的字符，加上一个「REST」代表未提及字符
3. 以「该字符被哪些字符类包含」为**签名**分组
4. 同签名的字符合并为一个**字符块**，作为 DFA 的单个转移标签

因为同块字符在**任意**字符类上的归属完全一致，所以对任一块而言，
「哪些边可命中」是唯一确定的 —— 确定性得到保证。

### 一个例子

模式 `a|[a-z]`：

| 字符 | 被哪些类包含 | 所属块 |
|---|---|---|
| `a` | `{a}` 和 `[a-z]` | 块 0 |
| `b`…`z` | `{a-z}` | 块 1 |
| 其他 | 无 | 块 2（未被覆盖，不进入字母表） |

DFA 从起始状态出发：块 0 → 终态，块 1 → 终态，块 2 无转移。
输入 `a` 只可能落在块 0，因此转移唯一。

### 与「字符集展开」方案的对比

初版（v1）采用另一种思路：把 `.` 与 `[^a-z]` 直接展开成逐字符的选择子图。

| 模式 | 展开方案 NFA 状态数 | 划分方案 NFA 状态数 |
|---|---|---|
| `.` | 386 | 2 |
| `[^a-z]` | 286 | 2 |
| `[a-z]` | 102 | 2 |

展开方案的规模与**字符集大小**成正比；划分方案的规模与**模式长度**成正比。
详细数据见 [`VERSION_COMPARISON.md`](VERSION_COMPARISON.md)。

---

## 错误处理

统一的异常层次：

```
RegexCompilerError
├── LexerError      词法错误（携带 position）
├── ParserError     语法错误（携带 position）
└── BuildError      自动机构造错误
```

设计考虑：编译器报错的价值取决于定位精度。因此词法与语法错误都强制携带
字符偏移量，Web 接口会把它原样透传给前端，命令行则直接展示给用户。

调用方既可按阶段精确捕获，也可一次性兜底 `RegexCompilerError`。

---

## 可视化子系统

三种自动机（NFA / DFA / 最小 DFA）结构相似，但原实现为每种各写了一遍渲染逻辑，
存在大量重复。当前设计先统一抽象为**通用图结构**：

```
AutomatonGraph = { nodes: [GraphNode], edges: [GraphEdge] }
```

再由单一渲染管线 `render_graph(graph, theme)` 输出，三者只差配色方案。
新增自动机类型时只需实现一个 `xxx_to_graph()` 转换函数。

输出支持两种格式：

- **SVG**：直接嵌入网页，`viewBox` 自适应缩放
- **draw.io XML**：可在 draw.io 中打开继续编辑，包含三个 diagram 页

---

## 扩展点

| 想做的事 | 需要改动的位置 |
|---|---|
| 新增语法（如 `{n,m}` 量词） | `lexer.py` 加记号 → `ast_nodes.py` 加节点 → `nfa.py` 加构造 |
| 更换最小化算法 | 只需替换 `minimize.py`，接口保持 `DFA → MinDFA` |
| 新增输出格式 | `visualization/` 下加渲染器，复用 `AutomatonGraph` |
| 接入新的前端框架 | `web/gui.html` 替换，API 契约不变 |
| 支持 Unicode 全文匹配 | `charset.py` 的 `_pick_unmentioned` 与 REST 块逻辑已就绪，主要工作在校验与测试 |

---

<div align="right">Zero</div>
