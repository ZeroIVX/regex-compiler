# Regex Compiler

从正则表达式到最小化确定有限自动机的完整编译器实现 —— 覆盖词法分析、语法分析、
NFA 构造、DFA 构造与 DFA 最小化的全部编译阶段，并附带自动机可视化与 Web 交互界面。

仓库保留两个版本的完整源码，用于呈现同一项目从**初版实现**到**架构重构**的演进过程。

**运行时零第三方依赖，仅需 Python 3.10+。**

---

## 两版源码

| 版本 | 定位 | 目录结构 | 字符类实现 | 最小化算法 | 测试 |
|---|---|---|---|---|---|
| **v1** | 初版实现 | 平铺 `src/` | 字符集展开 | 划分精炼（Moore 式） | 87 |
| **v2** | 重构优化版 | 分层包 | 不相交字母表划分 | Hopcroft | 113 |

> **如何选择**：实际使用与二次开发请选 **v2**；v1 保留为「重构前」的对照样本，
> 便于观察架构演进的具体差异。

### 核心差异一览

| 维度 | v1 | v2 |
|---|---|---|
| 包结构 | `src/lexer.py` 等平铺 | `regex_compiler/frontend/`、`backend/`、`core/` 分层 |
| 通配符 `.` 的 NFA 规模 | 386 个状态 | 2 个状态 |
| `[^a-z]` 的 NFA 规模 | 286 个状态 | 2 个状态 |
| 非 ASCII 字符支持 | 不支持（`. ` 无法匹配中文） | 支持 |
| 异常体系 | 各阶段独立异常 | 统一基类 + 位置信息 |
| 工程化 | 无 | `pyproject.toml`、类型注解、CLI 入口、包数据声明 |
| 测试策略 | 单元测试 | 单元测试 + 与 Python `re` 的差分对拍 |
| Web 端口 | 固定 8080 | 自动顺延 |

完整对比（含复杂度推导与代码量数据）见 [`docs/VERSION_COMPARISON.md`](docs/VERSION_COMPARISON.md)。

---

## 快速开始

### v2（推荐）

```bash
cd v2
```

| 系统 | 操作 |
|---|---|
| **Windows** | 双击 `启动.bat` |
| **Linux / macOS** | `./启动.sh` |

脚本自动检测 Python、启动 Web 服务并打开浏览器，端口占用时自动顺延。

```bash
python start.py --menu           # 功能菜单
python start.py --demo           # 命令行演示
python start.py --test           # 运行全部测试
python start.py --export "a+"    # 导出自动机可视化
```

命令行方式：

```bash
cd v2
python -m regex_compiler -p "(a|b)*abb" -i     # 流水线统计
python -m regex_compiler -p "a+" -m "aaa"      # 完全匹配
python -m regex_compiler -p "a(b|c)*d" --ast   # 打印 AST
python -m regex_compiler -p "a+" -v -o output  # 导出 SVG 与 draw.io
```

### v1（对照版）

```bash
cd v1
python start.py            # 启动 Web 界面（固定 8080 端口）
python start.py --demo     # 命令行演示
python start.py --test     # 运行全部测试
```

---

## 仓库结构

```
regex-compiler/
├── README.md                    # 本文件：仓库总览
├── LICENSE                      # MIT
├── .gitignore
├── .gitattributes               # 换行符规范化
│
├── v1/                          # 初版实现
│   ├── README.md                # 版本说明、已知局限
│   ├── start.py                 # 一键启动器
│   ├── 启动.bat / 启动.sh
│   ├── run_tests.py
│   ├── architecture.drawio      # 架构图（draw.io 源码）
│   ├── src/                     # 平铺源码
│   └── tests/                   # 87 个测试
│
├── v2/                          # 重构优化版
│   ├── README.md
│   ├── pyproject.toml
│   ├── start.py
│   ├── 启动.bat / 启动.sh
│   ├── run_tests.py
│   ├── architecture.drawio
│   ├── regex_compiler/          # 分层包
│   │   ├── frontend/            #   词法 / 语法 / AST
│   │   ├── backend/             #   NFA / DFA / 最小化
│   │   ├── core/                #   流水线与匹配引擎
│   │   ├── visualization/       #   SVG / draw.io
│   │   └── web/                 #   HTTP 服务与页面
│   └── tests/                   # 113 个测试
│
├── docs/                        # 跨版本文档
│   ├── ARCHITECTURE.md          # 架构设计
│   ├── VERSION_COMPARISON.md    # 版本对比
│   └── DESIGN_NOTES.md          # 设计与算法说明
│
└── assets/
    └── architecture-v2.drawio   # v2 架构图（draw.io 源码）
```

---

## 技术要点

### 编译流水线

```
正则表达式 → Token 流 → AST → ε-NFA → DFA → 最小 DFA → 匹配结果
             Lexer    Parser  Thompson  子集构造  最小化
```

### 算法与复杂度

| 阶段 | 算法 | 复杂度 |
|---|---|---|
| 词法分析 | 逐字符扫描 | `O(n)` |
| 语法分析 | LL(1) 递归下降 | `O(n)` |
| NFA 构造 | Thompson | `O(n)` |
| DFA 构造 | 子集构造 | `O(2^m · k)` 最坏 |
| DFA 最小化 | v1：Moore 划分精炼 / v2：Hopcroft | `O(n²·k)` / `O(k·n·log n)` |
| 匹配 | DFA 模拟 | `O(m)`（`m` 为输入长度） |

### 两处关键设计

**1. 字符类的不相交字母表划分（v2）**

DFA 要求「给定输入字符，转移唯一确定」。若以单字符作转移标签，
`a|[a-z]` 会在同一状态产生两条可命中的转移，破坏确定性。
v2 将字符类按「被哪些字符类包含」的签名分组，形成互不相交的字符块，
既保证确定性，又让 NFA 规模与模式长度线性相关。

v1 采用字符集展开：把 `.` 与 `[^...]` 直接展开为逐字符的选择子图。
实现直观，但状态数随字符集大小急剧膨胀，且无法覆盖全集外字符。

**2. 与工业级引擎的语义对齐（v2）**

v2 的测试包含一组**差分对拍**用例，把本实现与 Python 标准库 `re` 逐项比对
（完全匹配、搜索、全部匹配），并在短字符串上做穷举验证。
这保证了语义与工业级正则引擎严格一致，而非「大致可用」。

---

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 分层架构、数据流、模块职责、设计权衡 |
| [`docs/VERSION_COMPARISON.md`](docs/VERSION_COMPARISON.md) | 两版逐项对比、性能数据、迁移建议 |
| [`docs/DESIGN_NOTES.md`](docs/DESIGN_NOTES.md) | 文法推导、算法细节、测试设计、已知局限 |

各版本另有独立的 `README.md`，描述该版本的具体用法与局限。

---

## 环境要求

- Python 3.10 及以上
- 运行时依赖：无
- 开发依赖（可选，仅 v2）：`pytest`、`mypy`、`ruff`

```bash
cd v2
pip install -e ".[dev]"
```

---

## 许可

[MIT License](LICENSE)

---

<div align="right">Zero</div>
