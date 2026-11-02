#!/usr/bin/env python3
"""正则表达式编译器 v1 —— 一键启动器。

v1 为初版实现，保留平铺式 ``src/`` 目录结构与字符集展开方案，
用于与 v2 做架构对比。功能已修复至正确，但存在已知局限，
详见同目录 README.md 的「已知局限」一节。

用法::

    python start.py                  # 启动 Web 界面（默认）
    python start.py --menu           # 功能菜单
    python start.py --demo           # 命令行演示
    python start.py --test           # 运行全部测试
    python start.py --interactive    # 交互模式
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

DEFAULT_PORT = 8080

BANNER = """
==============================================================
   正则表达式编译器  v1  (初版实现)
   Regex -> NFA -> DFA -> MinDFA
==============================================================
"""


def _port_in_use(port: int) -> bool:
    """检测端口是否已被占用。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return True
        return False


def _open_browser_later(url: str, delay: float = 1.0) -> None:
    """延迟打开浏览器。"""

    def _open() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:  # pragma: no cover
            print(f"  未能自动打开浏览器，请手动访问: {url}")

    threading.Thread(target=_open, daemon=True).start()


def launch_web() -> int:
    """启动 Web 图形界面（v1 固定使用 8080 端口）。"""
    print(BANNER)
    if _port_in_use(DEFAULT_PORT):
        print(f"  [错误] 端口 {DEFAULT_PORT} 已被占用。")
        print("         请先关闭占用该端口的程序；")
        print("         若需要端口自动顺延，请改用 v2 版本。")
        return 1

    url = f"http://localhost:{DEFAULT_PORT}"
    print(f"  访问地址: {url}")
    print("  按 Ctrl+C 停止服务")
    print()

    _open_browser_later(url)
    from src.server import main as serve_main

    serve_main()
    return 0


DEMO_PATTERNS = [
    ("(a|b)*abb", ["abb", "aabb", "ababb", "aba"]),
    ("a(b|c)*d", ["ad", "abcd", "abc"]),
    (".", ["x", "", "\n"]),
    ("[^a-z]", ["5", "a"]),
    ("a+", ["", "a", "aaa"]),
]


def run_demo() -> int:
    """在命令行跑一遍经典示例。"""
    from src.matcher import RegexMatcher

    print(BANNER)
    print("  编译流水线演示（v1 字符集展开方案）\n")

    for index, (pattern, texts) in enumerate(DEMO_PATTERNS, start=1):
        matcher = RegexMatcher(pattern)
        print(f"  [{index}] 模式 {pattern}")
        print(f"      NFA 状态  : {len(matcher.nfa.states)}")
        print(f"      DFA 状态  : {len(matcher.dfa.states)}")
        print(f"      最小化后  : {len(matcher.min_dfa.states)}")
        print("      匹配测试  :")
        for text in texts:
            accepted = matcher.match(text)
            marker = "✓" if accepted else "✗"
            verdict = "ACCEPT" if accepted else "REJECT"
            print(f"        {marker} {text!r:<12} {verdict}")
        print()

    print("  说明: `.` 与 `[^...]` 通过展开字符集实现，")
    print("        因此 NFA 状态数会随字符集大小显著膨胀。\n")
    return 0


def run_tests() -> int:
    """运行全部测试。"""
    print(BANNER)
    import run_tests as runner

    return runner.main()


def run_interactive() -> int:
    """进入命令行交互模式。"""
    from src.main import interactive_mode

    print(BANNER)
    interactive_mode()
    return 0


MENU = """
  请选择功能：

    1) 启动 Web 图形界面（自动打开浏览器）
    2) 命令行演示
    3) 运行全部测试
    4) 命令行交互模式
    0) 退出
"""


def interactive_menu() -> int:
    """功能菜单。"""
    print(BANNER)
    while True:
        print(MENU)
        try:
            choice = input("  请输入编号 [0-4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice in ("0", "q", "quit", "exit"):
            print("\n  再见！\n")
            return 0
        if choice == "1":
            return launch_web()
        if choice == "2":
            run_demo()
        elif choice == "3":
            run_tests()
        elif choice == "4":
            return run_interactive()
        else:
            print("  [提示] 无效的编号，请重新输入\n")


def main(argv: list[str] | None = None) -> int:
    """解析参数并分派。"""
    parser = argparse.ArgumentParser(
        prog="start.py", description="正则表达式编译器 v1 —— 一键启动器"
    )
    parser.add_argument("--menu", "-m", action="store_true", help="显示功能菜单")
    parser.add_argument("--serve", action="store_true", help="启动 Web 界面（默认）")
    parser.add_argument("--demo", action="store_true", help="命令行演示")
    parser.add_argument("--test", action="store_true", help="运行全部测试")
    parser.add_argument("--interactive", "-I", action="store_true", help="交互模式")
    args = parser.parse_args(argv)

    if args.test:
        return run_tests()
    if args.demo:
        return run_demo()
    if args.interactive:
        return run_interactive()
    if args.menu:
        return interactive_menu()
    return launch_web()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  已取消。")
        sys.exit(130)
