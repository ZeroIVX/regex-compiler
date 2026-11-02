# Regex Compiler · v1（初版实现）

> 正则表达式编译器的第一版实现，保留最初的设计与目录结构。
> 用于与 [`v2`](../v2/) 做架构与工程质量的对照。

本版本使用**平铺式 `src/` 目录**、**字符集展开**方案实现通配符与取反字符类，
最小化采用**划分精炼（Moore 式）**。功能已修复至正确，可作为独立项目运行。

---

## 目录

- [功能概览](#功能概览)
- [快速开始](#快速开始)
- [目录结构](#目录结构)
- [编译流水线](#编译流水线)
- [算法说明](#算法说明)
- [已知局限](#已知局限)
- [测试](#测试)
- [与 v2 的关系](#与-v2-的关系)

---

## 功能概览

| 能力 | 说明 |
|---|---|
| 编译流水线 | 词法分析 → 递归下降语法分析 → Thompson NFA → 子集构造 DFA → DFA 最小化 |
| 支持的语法 | 字面字符、`.`、`[a-z]`、`[^a-z]`、`( )`、`\|`、`*`、`+`、`?`、`\` 转义 |
| 匹配模式 | `match`（完全匹配）、`search`（搜索）、`findall`（查找全部） |
| 可视化 | NFA / DFA / 最小 DFA 导出为 SVG 与 draw.io XML |
| Web 界面 | 纯标准库多线程 HTTP 服务 + 原生 HTML/CSS/JS 页面 |
| 命令行 | 匹配、AST 打印、流水线统计、批量导出 |

运行时**零第三方依赖**，仅需 Python 3.10+。

---

## 快速开始

### 一键启动

| 系统 | 操作 |
|---|---|
| **Windows** | 双击 `启动.bat` |
| **Linux / macOS** | `./启动.sh` |

默认启动 Web 界面并打开浏览器（v1 固定使用 `8080` 端口）。

```bash
python start.py --menu          # 功能菜单
python start.py --demo          # 命令行演示
python start.py --test          # 运行全部测试
python start.py --interactive   # 交互模式
```

### 作为库使用

```python
import sys
sys.path.insert(0, "v1")

from src.matcher import RegexMatcher

matcher = RegexMatcher(r"(a|b)*abb")
matcher.match("ababb")      # True
matcher.search("xxababb")   # (2, 7)
matcher.findall("abab")
```

### 原有命令行入口

```bash
python -m src.main -p "(a|b)*abb" -i     # 流水线统计
python -m src.main -p "a+" -m "aaa"      # 完全匹配
python -m src.main -p "a(b|c)*d" --ast   # 打印 AST
python -m src.main -p "(a|b)*abb" -v     # 导出可视化
```

---

## 目录结构

```
v1/
├── 启动.bat / 启动.sh      # 一键启动脚本
├── start.py                # 启动器：Web / 菜单 / 演示 / 测试 / 交互
├── run_tests.py            # 测试运行器
├── src/                    # 全部源码平铺在同一层
│   ├── __init__.py
│   ├── lexer.py            # 词法分析
│   ├── parser.py           # 递归下降语法分析
│   ├── ast_nodes.py        # AST 节点
│   ├── nfa.py              # Thompson 构造
│   ├── dfa.py              # 子集构造
│   ├── minimize.py         # 划分精炼（Moore 式）
│   ├── matcher.py          # 编译流水线与匹配引擎
│   ├── visualizer.py       # SVG 与 draw.io 导出
│   ├── server.py           # Web 服务
│   ├── main.py             # 命令行入口
│   └── gui.html            # 前端页面
└── tests/                  # 87 个测试用例
    ├── test_lexer.py
    ├── test_parser.py
    ├── test_nfa.py
    ├── test_dfa.py
    ├── test_integration.py
    └── test_regression.py  # 修复项的回归测试
```

---

## 编译流水线

```
正则表达式
    │ Lexer          逐字符扫描，识别元字符与字符类
    ▼
Token 流
    │ Parser         递归下降，构造 AST
    ▼
AST
    │ Thompson       构造 ε-NFA
    ▼
ε-NFA
    │ 子集构造       确定化为 DFA
    ▼
DFA
    │ 划分精炼       合并等价状态
    ▼
最小 DFA  ──►  match / search / findall
```

---

## 算法说明

### 词法分析与语法分析

词法分析逐字符扫描，产出 `CHAR`、`CHARCLASS`、`LPAREN`、`RPAREN`、`STAR`、
`PLUS`、`QUESTION`、`PIPE`、`DOT`、`EOF` 等记号。

语法分析采用 LL(1) 递归下降：

```
Expr     → Concat ('|' Concat)*
Concat   → Postfix+
Postfix  → Atom ('*' | '+' | '?')*
Atom     → CHAR | CHARCLASS | '.' | '(' Expr ')'
```

### NFA 构造（Thompson）

为每种运算符定义固定的子图模式，递归地把 AST 转换为 ε-NFA：

| 运算符 | 子图模式 |
|---|---|
| 字面字符 `a` | `start --a--> accept` |
| 连接 `AB` | `A.accept --ε--> B.start` |
| 选择 `A\|B` | 新 start 分叉，两侧 ε-汇聚到新 accept |
| 闭包 `A*` | 新 start 可跳过或进入 A，A 可自环或退出 |
| 正闭包 `A+` | 等价于 `A·A*` |
| 可选 `A?` | 新 start 可跳过或进入 A |

### DFA 构造（子集构造）

以 ε-闭包为起点做 BFS，每个 DFA 状态对应一组 NFA 状态的子集。

### DFA 最小化（划分精炼 / Moore 式）

1. 初始划分 `P = {F, Q-F}`（终态集 / 非终态集）
2. 反复按「对每个符号转移到哪个组」切分各组，直到划分稳定
3. 每个划分块映射为一个最小 DFA 状态，重建转移关系

每一轮都重新扫描全部状态，最坏复杂度约 `O(n²·k)`。
功能上与 Hopcroft 等价，但常数更大。

---

## 已知局限

这些局限是本版本的**设计取舍**，也正是 v2 改进的出发点。

### 1. 字符全集限定为 ASCII

`.` 与 `[^...]` 通过展开具体字符实现，需要一个有限全集作为基准：

```python
UNIVERSE = 可打印 ASCII (0x20–0x7E) ∪ {'\t', '\n', '\r'}   # 共 98 个字符
```

后果：全集之外的字符（例如中文）**不会被 `.` 匹配**。

```python
RegexMatcher(".").match("x")   # True
RegexMatcher(".").match("中")  # False  ← 局限
```

### 2. 状态数随字符集大小膨胀

字符类在 NFA 中被展开为逐字符的选择子图，状态数急剧上升：

| 模式 | v1 NFA 状态数 | v2 NFA 状态数 |
|---|---|---|
| `a` | 2 | 2 |
| `.` | **386** | **2** |
| `a.b` | **390** | **8** |
| `[^a-z]` | **286** | **2** |
| `(a\|b)*abb` | 14 | 14 |

不含通配符与字符类的模式（如 `(a|b)*abb`）两版规模一致。

### 3. 最小化为 Moore 式而非 Hopcroft

划分精炼每轮全量扫描，复杂度 `O(n²·k)`；v2 采用带工作队列与反向转移表的
Hopcroft 算法，达到 `O(k·n·log n)`。小规模模式下差异不明显，
该差异主要体现在算法实现质量上。

### 4. 不支持锚点与量词区间

不支持 `^` `$` 锚点、`{n,m}` 区间量词、反向引用等扩展语法。

### 5. Web 端口固定

服务固定监听 `8080`，被占用时需手动释放；v2 支持端口自动顺延。

---

## 测试

```bash
python run_tests.py
```

```
Total: 87 tests
  Passed: 87
  All tests passed!
```

其中 `tests/test_regression.py` 专门覆盖本版修复的三项语义缺陷：

- `.` 通配符此前因字母表未收录而完全失效
- `[^...]` 取反字符类此前语义反转（等价于正向类）
- `a+` 正闭包构造函数复用同一片段，导致状态冗余

---

## 与 v2 的关系

| 维度 | v1（本版） | v2 |
|---|---|---|
| 目录结构 | 平铺 `src/` | 分层包 `regex_compiler/` |
| 字符类实现 | 字符集展开 | 不相交字母表划分 |
| 最小化算法 | 划分精炼（Moore 式） | Hopcroft（工作队列 + 反向转移表） |
| 测试规模 | 87 个 | 113 个（含与 `re` 的差分对拍） |
| 工程化 | 无 | `pyproject.toml`、类型注解、统一异常、CLI 入口 |
| 端口处理 | 固定 8080 | 自动顺延 |

完整对比见 [`docs/VERSION_COMPARISON.md`](../docs/VERSION_COMPARISON.md)。

**建议用途**：v1 适合作为「重构前」的对照样本，观察架构演进；
实际使用与二次开发请选用 v2。

---

## 环境

- Python 3.10+
- 运行时依赖：无

## 许可

MIT

---

<div align="right">Zero</div>
