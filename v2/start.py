#!/usr/bin/env python3
"""正则表达式编译器 —— 一键启动器。

直接双击 ``启动.bat``（Windows）或 ``./启动.sh``（Linux/macOS）即可启动
Web 图形界面并自动打开浏览器。

也可以单独调用本脚本获得更多能力::

    python start.py                  # 启动 Web 界面（默认）
    python start.py --menu           # 显示功能菜单
    python start.py --demo           # 命令行跑一遍经典示例
    python start.py --test           # 运行全部测试
    python start.py --export PATTERN # 导出该模式的自动机可视化
    python start.py --port 9000      # 指定端口
    python start.py --no-browser     # 不自动打开浏览器
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
MAX_PORT_PROBE = 20

BANNER = r"""
==============================================================
   正则表达式编译器   Regex Compiler
   Regex -> Lexer -> Parser -> NFA -> DFA -> MinDFA
==============================================================
"""


# ============================================================
# 工具函数
# ============================================================

def _find_free_port(host: str, preferred: int) -> tuple[int, bool]:
    """从 ``preferred`` 起找一个可用端口。

    Returns:
        ``(端口号, 是否发生了顺延)``
    """
    for offset in range(MAX_PORT_PROBE):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port, offset > 0
    raise RuntimeError(f"端口 {preferred}~{preferred + MAX_PORT_PROBE - 1} 均被占用")


def _open_browser_later(url: str, delay: float = 1.0) -> None:
    """延迟一小会儿再打开浏览器，给服务器留出启动时间。"""

    def _open() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover - 环境相关
            print(f"  未能自动打开浏览器，请手动访问: {url}")

    threading.Thread(target=_open, daemon=True).start()


# ============================================================
# 各功能实现
# ============================================================

def launch_web(host: str, port: int, open_browser: bool = True) -> int:
    """启动 Web 图形界面。"""
    from regex_compiler.web.server import serve

    actual_port, shifted = _find_free_port(host, port)
    url = f"http://{host}:{actual_port}"

    print(BANNER)
    if shifted:
        print(f"  [提示] 端口 {port} 已被占用，改用 {actual_port}")
    print(f"  访问地址: {url}")
    print("  按 Ctrl+C 停止服务")
    print()

    if open_browser:
        _open_browser_later(url)

    try:
        serve(host=host, port=actual_port, quiet=True)
    except OSError as error:
        print(f"  [错误] 无法启动服务器: {error}")
        return 1
    return 0


DEMO_PATTERNS: list[tuple[str, list[str]]] = [
    (r"(a|b)*abb", ["abb", "aabb", "ababb", "aba", "abba"]),
    (r"a(b|c)*d", ["ad", "abcd", "acd", "abc"]),
    (r"a+b+c+", ["abc", "aaabbbccc", "cba"]),
    (r"[a-z]+[0-9]", ["abc1", "ABC1", "abc"]),
    (r"colou?r", ["color", "colour", "colouur"]),
    (r".", ["x", "", "\n"]),
    (r"[^a-z]", ["5", "A", "a"]),
]


def run_demo() -> int:
    """在命令行跑一遍经典示例，展示完整编译流水线。"""
    from regex_compiler import RegexMatcher

    print(BANNER)
    print("  编译流水线演示\n")

    for index, (pattern, texts) in enumerate(DEMO_PATTERNS, start=1):
        matcher = RegexMatcher(pattern)
        nfa_count = len(matcher.nfa.states)
        dfa_count = len(matcher.dfa.states)
        min_count = len(matcher.min_dfa.states)
        reduction = 100 * (1 - min_count / max(1, dfa_count))
        alphabet = ", ".join(
            matcher.alphabet.label_of(block_id)
            for block_id in matcher.alphabet.covered_ids
        )

        print(f"  [{index}] 模式 {pattern}")
        print(f"      词法记号  : {len(matcher.tokens)}")
        print(f"      字母表    : {alphabet}")
        print(f"      NFA 状态  : {nfa_count}")
        print(f"      DFA 状态  : {dfa_count}")
        print(f"      最小化后  : {min_count}  (压缩 {reduction:.1f}%)")
        print("      匹配测试  :")
        for text in texts:
            accepted = matcher.match(text)
            marker = "✓" if accepted else "✗"
            verdict = "ACCEPT" if accepted else "REJECT"
            print(f"        {marker} {text!r:<12} {verdict}")
        print()

    print("  提示: 用 --menu 进入功能菜单，或 --serve 打开图形界面\n")
    return 0


def run_tests() -> int:
    """运行全部测试用例。"""
    import unittest

    print(BANNER)
    print("  运行测试套件\n")

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=1).run(suite)

    print()
    if result.wasSuccessful():
        print(f"  ✓ 全部 {result.testsRun} 个测试通过\n")
        return 0
    print(f"  ✗ 存在失败用例（共 {result.testsRun} 个）\n")
    return 1


def export_visualizations(pattern: str, out_dir: str = "output") -> int:
    """导出指定模式的自动机可视化文件。"""
    from regex_compiler.visualization import (
        render_dfa_svg,
        render_drawio_xml,
        render_min_dfa_svg,
        render_nfa_svg,
    )
    from regex_compiler import RegexMatcher
    from regex_compiler.errors import RegexCompilerError

    print(BANNER)
    print(f"  导出可视化: {pattern}\n")

    try:
        matcher = RegexMatcher(pattern)
    except RegexCompilerError as error:
        print(f"  [错误] 模式无法编译: {error}\n")
        return 1

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    files = [
        ("nfa.svg", render_nfa_svg(matcher.nfa)),
        ("dfa.svg", render_dfa_svg(matcher.dfa)),
        ("minimal_dfa.svg", render_min_dfa_svg(matcher.min_dfa)),
        (
            "automata.drawio",
            render_drawio_xml(matcher.nfa, matcher.dfa, matcher.min_dfa),
        ),
    ]

    for filename, content in files:
        path = directory / filename
        path.write_text(content, encoding="utf-8")
        print(f"  ✓ {filename:<20} {path}")

    print()
    return 0


def run_interactive() -> int:
    """进入命令行交互模式。"""
    from regex_compiler.cli import _interactive_mode

    print(BANNER)
    _interactive_mode()
    return 0


# ============================================================
# 菜单
# ============================================================

MENU = """
  请选择功能：

    1) 启动 Web 图形界面（自动打开浏览器）
    2) 命令行演示（跑一遍经典示例）
    3) 运行全部测试
    4) 导出自动机可视化（SVG + draw.io）
    5) 命令行交互模式
    0) 退出
"""


def interactive_menu(host: str, port: int) -> int:
    """显示功能菜单，循环直到用户退出。"""
    print(BANNER)

    while True:
        print(MENU)
        try:
            choice = input("  请输入编号 [0-5]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice in ("0", "q", "quit", "exit"):
            print("\n  再见！\n")
            return 0

        if choice == "1":
            return launch_web(host, port, open_browser=True)

        if choice == "2":
            run_demo()
        elif choice == "3":
            run_tests()
        elif choice == "4":
            try:
                pattern = input("  请输入正则表达式（默认 (a|b)*abb）: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            export_visualizations(pattern or r"(a|b)*abb")
        elif choice == "5":
            run_interactive()
            return 0
        else:
            print("  [提示] 无效的编号，请重新输入\n")


# ============================================================
# 入口
# ============================================================

def main(argv: list[str] | None = None) -> int:
    """解析参数并分派到对应功能。"""
    parser = argparse.ArgumentParser(
        prog="start.py",
        description="正则表达式编译器 —— 一键启动器",
    )
    parser.add_argument("--menu", "-m", action="store_true", help="显示功能菜单")
    parser.add_argument(
        "--serve", action="store_true", help="启动 Web 图形界面（默认行为）"
    )
    parser.add_argument("--demo", action="store_true", help="命令行演示")
    parser.add_argument("--test", action="store_true", help="运行全部测试")
    parser.add_argument("--export", metavar="PATTERN", help="导出该模式的自动机可视化")
    parser.add_argument("--interactive", "-I", action="store_true", help="命令行交互模式")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--output", "-o", default="output", help="可视化输出目录")

    args = parser.parse_args(argv)

    if args.test:
        return run_tests()
    if args.demo:
        return run_demo()
    if args.export:
        return export_visualizations(args.export, args.output)
    if args.interactive:
        return run_interactive()
    if args.menu:
        return interactive_menu(args.host, args.port)

    # 默认：启动 Web 图形界面
    return launch_web(args.host, args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  已取消。")
        sys.exit(130)
