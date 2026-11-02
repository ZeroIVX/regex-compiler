# Regex Compiler · v2（重构优化版）

> 从正则表达式到最小化确定有限自动机的完整编译器。
> 本版为**重构优化后**的实现，与 [`v1`](../v1/) 对照可观察架构演进。

一个用纯 Python 标准库实现的正则表达式编译器，覆盖了从**词法分析**到**DFA 最小化**的
全部编译阶段，并提供命令行工具、Web 图形界面与自动机可视化能力。

**运行时零第三方依赖**，仅需 Python 3.10+。

> 本仓库同时保留 [`v1`](../v1/)（初版实现）作为对照。
> 两版的差异分析见 [`docs/VERSION_COMPARISON.md`](../docs/VERSION_COMPARISON.md)，
> 架构设计见 [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)。

---

## 目录

- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [编译流水线](#编译流水线)
- [算法说明](#算法说明)
- [命令行用法](#命令行用法)
- [Web 图形界面](#web-图形界面)
- [测试](#测试)
- [设计要点](#设计要点)

---

## 核心特性

| 能力 | 说明 |
|---|---|
| **完整编译流水线** | 词法分析 → 语法分析 → Thompson NFA → 子集构造 DFA → Hopcroft 最小化 |
| **支持的语法** | 字面字符、`.`、`[a-z]`、`[^a-z]`、`( )`、`\|`、`*`、`+`、`?`、`\` 转义 |
| **三种匹配模式** | `match`（完全匹配）、`search`（搜索）、`findall`（查找全部） |
| **语义对齐 Python `re`** | 与标准库 `re` 逐一对拍验证，行为完全一致 |
| **自动机可视化** | NFA / DFA / 最小 DFA 导出为 SVG 与 draw.io XML |
| **Web 图形界面** | 零依赖的多线程 HTTP 服务，浏览器中实时查看编译结果 |
| **命令行工具** | 匹配、AST 打印、流水线统计、批量导出 |
| **113 个测试用例** | 单元测试 + 与 `re` 的差分对拍测试 |

---

## 快速开始

### 一键启动（推荐）

| 系统 | 操作 |
|---|---|
| **Windows** | 双击 `启动.bat` |
| **Linux / macOS** | `./启动.sh` |

脚本会自动检测 Python 环境、启动 Web 服务并打开浏览器；
若默认端口 `8080` 被占用，会自动顺延到下一个可用端口。
按 `Ctrl+C` 停止服务。

需要功能菜单或其它能力时：

```bash
python start.py --menu          # 功能菜单（Web / 演示 / 测试 / 导出 / 交互）
python start.py --demo          # 命令行跑一遍经典示例
python start.py --test          # 运行全部测试
python start.py --export "a+"   # 导出该模式的自动机可视化
python start.py --port 9000     # 指定端口
python start.py --no-browser    # 不自动打开浏览器
```

### 命令行方式

```bash
# 查看编译流水线统计
python -m regex_compiler -p "(a|b)*abb" -i

# 运行全部测试
python run_tests.py

# 直接启动 Web 图形界面
python -m regex_compiler --serve
# 浏览器访问 http://127.0.0.1:8080
```

作为库使用：

```python
from regex_compiler import RegexMatcher

matcher = RegexMatcher(r"(a|b)*abb")

matcher.match("ababb")        # True  —— 完全匹配
matcher.search("xxababb")     # (2, 7) —— 搜索第一个匹配
matcher.findall("ababbababb") # [(0, 10, 'ababbababb')] —— 全部匹配（最长匹配语义）
matcher.print_info()          # 流水线统计信息
```

---

## 项目结构

```
启动.bat / 启动.sh          # 一键启动器（双击即用）
start.py                    # 跨平台启动器：Web / 菜单 / 演示 / 测试 / 导出
run_tests.py                # 测试入口

regex_compiler/
├── __init__.py              # 公共 API 出口
├── __main__.py              # python -m regex_compiler 入口
├── errors.py                # 统一异常体系
├── charset.py               # 字符类语义与不相交字母表划分
├── cli.py                   # 命令行接口
├── frontend/                # ── 编译器前端 ──
│   ├── lexer.py             #    词法分析：字符串 → Token 流
│   ├── parser.py            #    语法分析：Token 流 → AST
│   └── ast_nodes.py         #    AST 节点定义
├── backend/                 # ── 编译器后端 ──
│   ├── nfa.py               #    Thompson 构造：AST → ε-NFA
│   ├── dfa.py               #    子集构造：ε-NFA → DFA
│   └── minimize.py          #    Hopcroft 最小化：DFA → 最小 DFA
├── core/                    # ── 核心 ──
│   └── matcher.py           #    编译流水线与匹配引擎
├── visualization/           # ── 可视化 ──
│   ├── layout.py            #    通用图结构与布局算法
│   ├── svg.py               #    SVG 渲染
│   └── drawio.py            #    draw.io XML 导出
└── web/                     # ── Web 界面 ──
    ├── server.py            #    多线程 HTTP 服务
    └── gui.html             #    前端页面（零依赖原生 HTML/CSS/JS）

tests/                       # 113 个测试用例
├── test_lexer.py            #   词法分析
├── test_parser.py           #   语法分析
├── test_nfa.py              #   NFA 构造
├── test_dfa.py              #   DFA 构造与最小化
├── test_integration.py      #   匹配器集成测试
└── test_differential.py     #   与 Python re 的差分对拍
```

分层依据编译器经典架构：**前端**（frontend）负责把字符流变成语法树，
**后端**（backend）负责把语法树变成机器，**核心**（core）负责串联流水线，
**可视化**与 **Web** 是面向用户的输出层。

---

## 编译流水线

```
   正则表达式
       │
       │  Lexer ──── 逐字符扫描，识别元字符与字符类
       ▼
   Token 流
       │
       │  Parser ─── 递归下降，按上下文无关文法建树
       ▼
   AST ──── build_alphabet ──▶ Alphabet（互不相交字符块）
       │                              │
       │  Thompson 构造                │
       ▼                              ▼
   ε-NFA ──── 子集构造 ────▶ DFA ──── Hopcroft 最小化 ────▶ 最小 DFA
                                                              │
                                                              ▼
                                                     match / search / findall
```

---

## 算法说明

### 1. 词法分析

逐字符扫描，识别 `CHAR`、`CHARCLASS`、`LPAREN`、`RPAREN`、`STAR`、`PLUS`、
`QUESTION`、`PIPE`、`DOT` 八类记号。支持 `\x` 转义与 `[a-z]`、`[^a-z]` 字符类
（含范围、否定、转义字符）。

### 2. 语法分析（递归下降）

依据 LL(1) 文法：

```
Expr     → Concat ('|' Concat)*
Concat   → Postfix+
Postfix  → Atom ('*' | '+' | '?')*
Atom     → CHAR | CHARCLASS | '.' | '(' Expr ')'
```

优先级自低到高：选择 `|` < 连接 < 后缀 `* + ?`。

### 3. NFA 构造（Thompson 算法，O(n)）

为每种运算符定义固定的 NFA 子图模式，递归地把 AST 转换为 ε-NFA：

| 运算符 | 子图模式 |
|---|---|
| 字面字符 `a` | `start --a--> accept` |
| 连接 `AB` | `A.accept --ε--> B.start` |
| 选择 `A\|B` | 新 start ε-分叉至两侧，两侧 ε-汇聚到新 accept |
| 闭包 `A*` | 新 start 可跳过或进入 A，A 可自环或退出 |
| 正闭包 `A+` | 等价于 `A·A*`，至少匹配一次 |
| 可选 `A?` | 新 start 可跳过或进入 A |

### 4. DFA 构造（子集构造法）

DFA 的每个状态对应一组 NFA 状态的**子集**。从起始状态的 ε-闭包出发，
用 BFS 遍历所有可达子集，对每个字符块计算 `move` 后取 ε-闭包得到后继子集。

### 5. DFA 最小化（Hopcroft 算法，O(k·n·log n)）

1. **补全 DFA**：加入死状态，使转移函数成为全函数 —— 这是 Hopcroft 正确性的前提，
   否则「无转移」与「转移到非终态」会被误判为两种行为。
2. **初始划分** `P = {F, Q\F}`（终态集 / 非终态集）。
3. **反复精炼**：从工作队列取出划分块 `A`，对每个符号计算原像
   `X = {q | δ(q,a) ∈ A}`，用 `X` 切分所有划分块。
4. **小半边入队优化**：切分后只把较小的子块加入工作队列，保证复杂度。
5. **重建与剪枝**：映射为最小 DFA，删除从起始状态不可达的状态。

实现中维护**反向转移表**（逆像索引），使原像计算无需扫描全图。

---

## 命令行用法

```bash
# 查看编译流水线统计
python -m regex_compiler -p "(a|b)*abb" -i

# 完全匹配并显示模拟步骤
python -m regex_compiler -p "a+" -m "aaa"

# 搜索 / 查找全部
python -m regex_compiler -p "ab" -s "xxabyy"
python -m regex_compiler -p "ab" -f "ababab"

# 打印抽象语法树
python -m regex_compiler -p "a(b|c)*d" --ast

# 导出可视化文件（SVG + draw.io）
python -m regex_compiler -p "(a|b)*abb" -v -o output

# 交互模式
python -m regex_compiler --interactive

# 启动 Web 界面
python -m regex_compiler --serve --port 8080
```

---

## Web 图形界面

```bash
python -m regex_compiler --serve
```

浏览器访问 `http://127.0.0.1:8080`，左侧输入正则表达式与测试串，
右侧可切换查看 **NFA / DFA / 最小 DFA** 三种自动机的状态转移图，
下方实时显示 DFA 模拟轨迹。

后端基于标准库 `ThreadingHTTPServer`，无任何 Web 框架依赖。

| 端点 | 说明 |
|---|---|
| `GET /` | 图形界面页面 |
| `GET /api/info` | 编译流水线统计与 Token 列表 |
| `GET /api/match` | 匹配结果、search/findall 区间、模拟轨迹 |
| `GET /api/visualize` | 自动机 SVG（`type=nfa\|dfa\|mindfa`） |
| `GET /api/ast` | AST 文本形式 |
| `GET /api/tokens` | Token 列表 |

---

## 测试

```bash
python run_tests.py     # 标准库 unittest，零依赖
pytest                  # 若已安装 pytest
```

```
Ran 113 tests in 0.027s

OK
```

其中 `tests/test_differential.py` 是本项目最有价值的测试资产 ——
它把本实现与 Python 标准库 `re` 模块逐一对拍：

- **完整匹配** —— 与 `re.fullmatch()` 对比
- **搜索匹配** —— 与 `re.search()` 对比匹配区间
- **全部匹配** —— 与 `re.finditer()` 对比区间序列
- **穷举对拍** —— 在 `ab` 上枚举所有长度 ≤ 3 的字符串做全量比对

这保证了本实现的语义与工业级正则引擎严格一致，而不只是「大致能用」。

---

## 设计要点

### 字符类的不相交划分

DFA 要求「给定输入字符，转移唯一确定」。如果直接以单个字符为转移标签，
`a|[a-z]` 这类模式会在同一状态上产生两条可同时匹配的转移，破坏确定性。

本项目的做法是构造**互不相交的字符块**：

1. 模式中的每种字符条件抽象为 `CharClass`（精确集合 / 取反集合）；
2. 收集模式显式提及的字符作为分界字符，其余归入 REST 块；
3. 以「被哪些字符类包含」为签名分组 —— 同组字符在任意字符类上的归属完全一致；
4. 仅被覆盖的块进入 DFA 字母表。

这样 `.` 与 `[^a-z]` 的语义得以完整保留，同时 DFA 保持真正的确定性。

### 字符类在 NFA 中不展开

`[a-z]` 在 NFA 中只产生**一条**转移边（而非展开成 26 个状态），
语义交由字母表划分处理。这让 NFA 规模与模式长度线性相关，
而非与字符类大小相关。

### 统一异常体系

所有编译期错误继承自 `RegexCompilerError`，并细分为 `LexerError`、
`ParserError`、`BuildError`，均携带出错位置，便于定位。

---

## 环境

- Python 3.10+（开发环境：Python 3.13）
- 运行时依赖：**无**
- 开发依赖：`pytest`、`mypy`、`ruff`（通过 `pip install -e ".[dev]"` 安装）

## 许可

MIT
