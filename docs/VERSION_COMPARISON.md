# 版本对比

本文对比 `v1`（初版实现）与 `v2`（重构优化版）在架构、算法、工程质量上的差异，
所有规模数据均为实测结果。

---

## 概览

| 维度 | v1 | v2 |
|---|---|---|
| 定位 | 初版实现，保留原始结构 | 重构优化版，面向长期维护 |
| 目录结构 | 平铺 `src/` | 分层包 `regex_compiler/` |
| 字符类实现 | 字符集展开 | 不相交字母表划分 |
| 最小化算法 | 划分精炼（Moore 式） | Hopcroft（工作队列 + 反向转移表） |
| 异常体系 | 各阶段独立异常 | 统一基类 + 位置信息 |
| 类型注解 | 部分 | 全覆盖 |
| 测试规模 | 87 个 | 113 个 |
| 测试策略 | 单元测试 | 单元测试 + 与 `re` 差分对拍 |
| 工程化配置 | 无 | `pyproject.toml`、CLI 入口、包数据声明 |
| Web 端口 | 固定 8080 | 自动顺延 |
| 非 ASCII 支持 | 不支持 | 支持 |

---

## 一、目录结构

### v1：平铺式

```
v1/src/
├── lexer.py      parser.py     ast_nodes.py
├── nfa.py        dfa.py        minimize.py
├── matcher.py    visualizer.py server.py
├── main.py       gui.html
```

11 个模块平铺在同一层。优点是初学时一眼看完；缺点是模块间的**层次关系不可见** ——
`minimize` 依赖 `dfa`、`dfa` 依赖 `nfa` 这条依赖链只能靠阅读源码推断。

### v2：分层包

```
v2/regex_compiler/
├── errors.py        charset.py
├── frontend/        lexer.py  parser.py  ast_nodes.py
├── backend/         nfa.py  dfa.py  minimize.py
├── core/            matcher.py
├── visualization/   layout.py  svg.py  drawio.py
├── web/             server.py  gui.html
└── cli.py
```

**目录即架构文档**。`frontend` / `backend` 的划分直接对应编译器的经典结构，
`charset.py` 置于顶层是因为它被前后端共同依赖，放在任一侧都会造成反向依赖。

`visualizer.py`（v1 中 565 行）在 v2 中被拆为三个模块：
`layout.py` 负责图结构与布局，`svg.py` 负责矢量渲染，`drawio.py` 负责 XML 导出。
拆分依据是「**变换**与**输出**分离」—— 三种自动机共用同一套布局算法，
只是渲染配色不同。

---

## 二、字符类实现（核心差异）

### v1：字符集展开

`.` 与 `[^a-z]` 在构造 NFA 时被展开为逐字符的选择子图。需要一个有限全集作为基准：

```python
UNIVERSE = 可打印 ASCII (0x20–0x7E) ∪ {'\t', '\n', '\r'}   # 98 个字符
```

**优点**：实现直观，NFA 构造逻辑无需改动。
**代价**：状态数随字符集大小线性膨胀；全集之外的字符无法匹配。

### v2：不相交字母表划分

把字符类按「被哪些类包含」的签名分组，形成互不相交的字符块，
作为 DFA 的单个转移标签。字符类在 NFA 中**只占一条边**，不展开。

**优点**：规模与模式长度相关，与字符集大小无关；天然支持全集外字符（REST 块）。
**代价**：需要在 NFA 构造前先算一次字母表，概念上更复杂。

### 实测规模对比

| 模式 | v1 NFA | v1 DFA | v1 MinDFA | v2 NFA | v2 DFA | v2 MinDFA |
|---|---:|---:|---:|---:|---:|---:|
| `a` | 2 | 2 | 2 | 2 | 2 | 2 |
| `a\|b` | 6 | 3 | 2 | 6 | 3 | 2 |
| `(a\|b)*abb` | 14 | 5 | 4 | 14 | 5 | 4 |
| `a(b\|c)*d` | 12 | 5 | 3 | 12 | 5 | 3 |
| `a+b+c+` | 12 | 4 | 4 | 12 | 4 | 4 |
| `[a-z]` | **102** | **27** | 2 | **2** | **2** | 2 |
| `[^a-z]` | **286** | **73** | 2 | **2** | **2** | 2 |
| `.` | **386** | **98** | 2 | **2** | **2** | 2 |
| `a.b` | **390** | **100** | 4 | **6** | **4** | 4 |

**结论**：

1. 不含通配符与字符类的模式，两版规模**完全一致** —— 说明差异只来自字符类处理方式。
2. 含通配符的模式，v1 的 NFA 规模是 v2 的 **193 倍**（386 vs 2）。
3. v1 的 DFA 状态也多得多（98 vs 2），因为每个具体字符都要单独成一条转移。
4. 最小化后两版都收敛到 2 个状态 —— 说明**最小化本身是正确的**，
   差异纯粹来自构造阶段的中间规模。

### 语义差异

```python
# v1
RegexMatcher(".").match("中")   # False  ← 全集外字符无法匹配

# v2
RegexMatcher(".").match("中")   # True
```

v2 的 REST 块代表「所有未被模式显式提及的字符」，天然覆盖任意字符，
因此不存在这个限制。

---

## 三、最小化算法

### v1：划分精炼（Moore 式）

每轮精炼都重新扫描全部状态并计算签名：

```python
while True:
    changed, state_to_part, partitions = _partition_refine(...)
    if not changed:
        break
```

复杂度约 `O(n²·k)`（`n` 为状态数，`k` 为字母表大小）。功能正确，常数偏大。

### v2：Hopcroft

关键改进有两点：

**1. 先用死状态补全 DFA**

Hopcroft 的正确性前提是转移函数为全函数。若直接对部分 DFA 做划分，
「没有转移」与「转移到非终态」会被误判为两种不同行为，导致状态无法合并。

v2 在最小化前先补上死状态（sink），最小化后再剪除不可达状态 —— 这样
`a*` 这类模式仍能得到 1 个状态的结果，不会被死状态污染。

**2. 工作队列 + 反向转移表**

```
while worklist:
    A = worklist.pop()
    for each symbol a:
        X = {q | δ(q,a) ∈ A}        # 通过反向转移表求原像，无需扫描全图
        for each block Y split by X:
            分裂 Y，只把较小的半边入队      # Hopcroft 的关键优化
```

复杂度 `O(k·n·log n)`。

### 对比小结

| 项 | v1 | v2 |
|---|---|---|
| 算法 | Moore 式划分精炼 | Hopcroft |
| 复杂度 | `O(n²·k)` | `O(k·n·log n)` |
| 死状态处理 | 未显式处理 | 先补全再剪枝 |
| 原像计算 | 每轮全量扫描 | 反向转移表索引 |

小规模模式下两者结果一致、耗时差异不明显。引入 Hopcroft 的价值在于
**算法正确性与复杂度上界**，而非当前的性能收益。

---

## 四、异常体系

### v1：各阶段独立

```python
class LexerError(Exception): ...
class ParserError(Exception): ...
```

调用方若要统一处理，只能写 `except (LexerError, ParserError, ValueError)`。

### v2：统一基类 + 定位

```python
RegexCompilerError
├── LexerError      # 携带 position
├── ParserError     # 携带 position
└── BuildError
```

调用方既可精确捕获某个阶段，也可一次性兜底。所有错误都带字符偏移量，
Web 接口原样透传，前端直接展示给用户。

---

## 五、测试策略

| 项 | v1 | v2 |
|---|---|---|
| 用例数 | 87 | 113 |
| 框架 | 自研 runner | `unittest`（同时兼容 pytest） |
| 覆盖范围 | 各阶段单元测试 | 各阶段单元测试 + 集成测试 |
| 语义验证 | 人工编写预期值 | **与 Python `re` 差分对拍** |

### v2 的差分对拍

`tests/test_differential.py` 把本实现与标准库 `re` 逐项比对：

| 用例 | 比对对象 |
|---|---|
| `test_full_match_equivalence` | `re.fullmatch()` |
| `test_search_equivalence` | `re.search()` 的匹配区间 |
| `test_findall_equivalence` | `re.finditer()` 的区间序列 |
| `test_exhaustive_short_strings` | 在 `ab` 上穷举长度 ≤ 3 的全部字符串 |

覆盖 33 个模式 × 27 个测试串。设计意图是：**语义正确性不应依赖人工编写的预期值**，
而应以工业级引擎为基准。这项测试在开发过程中实际发现了多处边界偏差
（空匹配位置、最长匹配语义等）。

---

## 六、工程化

| 项 | v1 | v2 |
|---|---|---|
| 包元数据 | 无 | `pyproject.toml`（名称、版本、分类器、依赖） |
| 开发依赖声明 | 无 | `[project.optional-dependencies] dev` |
| CLI 入口 | 无（仅 `python -m src.main`） | `regex-compiler` 命令 |
| 类型注解 | 部分函数 | 全覆盖，含 `mypy` 配置 |
| 代码规范 | 无 | `ruff` 配置 |
| 包数据声明 | 无 | `gui.html` 随包发布 |
| 测试入口 | 自研 runner | `unittest` 标准发现 + `run_tests.py` 兼容 |

v2 可 `pip install -e .` 安装为可导入的包，v1 只能通过 `sys.path` 注入使用。

---

## 七、Web 与启动

| 项 | v1 | v2 |
|---|---|---|
| 服务实现 | 手写 `process_request` 覆盖 | 标准库 `ThreadingHTTPServer` |
| 端口占用 | 固定 8080，占用即失败 | 自动顺延，最多试 20 个 |
| GUI 的 search/findall | 均退化为完全匹配 | 三种模式各自独立计算 |
| 启动脚本 | 有 | 有（同等能力） |

v1 的 `ThreadingHTTPServer` 是手工重写的：覆盖 `process_request` 并复制了
标准库的处理逻辑。v2 改用标准库自带的 `ThreadingHTTPServer`，
减少约 25 行重复代码，也避免了与标准库实现漂移的风险。

v1 的 GUI 存在一处交互缺陷：三个按钮（Match / Search / FindAll）都会传
`mode` 参数，但服务端忽略该参数，导致三者行为完全相同。v2 中服务端按 `mode`
分别计算，该缺陷已修复；v1 也已同步修复以保持可用。

---

## 八、代码量

| 项 | v1 | v2 | 变化 |
|---|---:|---:|---|
| 核心代码 | 2358 行 | 3068 行 | +30% |
| 测试代码 | 646 行 | 979 行 | +52% |

v2 代码量更大，主要来自：

- 完整的类型注解与 docstring
- `charset.py` 的字母表划分逻辑（约 200 行）
- Hopcroft 的反向转移表与工作队列（约 80 行）
- 分层带来的 `__init__.py` 导出声明

代码量增加换取了可维护性与正确性保障，属于有意识的取舍。

---

## 九、迁移建议

### 用 v2 的场景

- 实际使用本工具做正则匹配
- 需要匹配非 ASCII 字符
- 作为库集成到其他项目
- 二次开发、扩展语法

### 用 v1 的场景

- 学习编译器分阶段实现，希望一眼看到全部模块
- 对照理解「字符集展开」与「字母表划分」两种方案的差异
- 研究重构前后的代码演进

### 从 v1 迁移到 v2 的注意点

| 变化 | 迁移动作 |
|---|---|
| 包名 `src` → `regex_compiler` | 改导入路径 |
| `CharClassNode(chars, negated)` → `CharClassNode(charset)` | 取反语义在 `CharClass` 内部表达 |
| `DFA.transitions` 键从 `str` → 字符块 id | 通过 `alphabet.block_of(ch)` 转换 |
| `nfa_move(states, symbol, dot_allowed)` → 去掉 `dot_allowed` | 字母表已包含全部有效符号 |
| 异常类型 | 统一继承 `RegexCompilerError` |

---

## 十、结论

两个版本功能等价、语义一致（v2 覆盖更广），差异集中在**内部构造方式**与
**工程质量**：

- **v1** 用最直接的方式实现功能，代价是中间规模膨胀与结构耦合
- **v2** 引入抽象（字符块、统一图结构、分层包），换取规模可控与长期可维护

这类重构的收益在功能上不可见，但在**扩展成本**上差异明显：
v2 新增一种输出格式只需加一个渲染器，v1 则需要动 565 行的 `visualizer.py`。

---

<div align="right">Zero</div>
