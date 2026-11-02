"""命令行接口 —— 提供模式匹配与可视化的命令行入口。

用法示例::

    python -m regex_compiler -p "(a|b)*abb" -m "ababb"
    python -m regex_compiler -p "a(b|c)*d" --ast --info
    python -m regex_compiler -p "a+" -v -o output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.matcher import RegexMatcher
from .errors import RegexCompilerError
from .frontend.parser import print_ast
from .visualization import (
    render_dfa_svg,
    render_drawio_xml,
    render_min_dfa_svg,
    render_nfa_svg,
)

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="regex_compiler",
        description="正则表达式编译器 —— Regex → NFA → DFA → MinDFA 完整流水线",
    )
    parser.add_argument("--pattern", "-p", type=str, help="正则表达式")
    parser.add_argument("--match", "-m", type=str, help="完全匹配测试字符串")
    parser.add_argument("--search", "-s", type=str, help="搜索匹配测试字符串")
    parser.add_argument("--findall", "-f", type=str, help="查找所有匹配")
    parser.add_argument("--ast", "-a", action="store_true", help="打印 AST")
    parser.add_argument("--info", "-i", action="store_true", help="打印流水线信息")
    parser.add_argument("--visualize", "-v", action="store_true", help="生成可视化输出")
    parser.add_argument("--output", "-o", type=str, default="output", help="输出目录")
    parser.add_argument("--interactive", "-I", action="store_true", help="交互模式")
    parser.add_argument(
        "--serve", action="store_true", help="启动 Web 图形界面服务器"
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=8080, help="服务器监听端口")
    return parser


def _print_match(matcher: RegexMatcher, text: str) -> None:
    """执行并展示完全匹配。"""
    result = matcher.match(text)
    print(f"Pattern: {matcher.pattern}")
    print(f"Input:   {text!r}")
    print(f"Match:   {'ACCEPT' if result else 'REJECT'}")
    print()
    print("Simulation steps:")
    for step in matcher.simulate(text):
        if step.get("error"):
            print(f"  [{step['pos']}] '{step['char']}' -> ERROR (no transition)")
        else:
            marker = "+" if step["accepted"] else ""
            print(f"  [{step['pos']}] '{step['char']}' -> State {step['to_state']} {marker}")


def _print_search(matcher: RegexMatcher, text: str) -> None:
    """执行并展示搜索匹配。"""
    result = matcher.search(text)
    print(f"Pattern: {matcher.pattern}")
    print(f"Input:   {text!r}")
    if result:
        start, end = result
        print(f"Found:   [{start}:{end}] = {text[start:end]!r}")
    else:
        print("No match found.")


def _print_findall(matcher: RegexMatcher, text: str) -> None:
    """执行并展示全部匹配。"""
    results = matcher.findall(text)
    print(f"Pattern: {matcher.pattern}")
    print(f"Input:   {text!r}")
    print(f"Matches: {len(results)}")
    for start, end, substring in results:
        print(f"  [{start}:{end}] = {substring!r}")


def _export_visualizations(matcher: RegexMatcher, out_dir: str) -> None:
    """生成全部可视化输出文件。"""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    outputs = [
        ("nfa.svg", render_nfa_svg(matcher.nfa)),
        ("dfa.svg", render_dfa_svg(matcher.dfa)),
        ("minimal_dfa.svg", render_min_dfa_svg(matcher.min_dfa)),
    ]
    for filename, content in outputs:
        path = directory / filename
        path.write_text(content, encoding="utf-8")
        print(f"  {filename:<20} -> {path}")

    drawio_path = directory / "automata.drawio"
    drawio_path.write_text(
        render_drawio_xml(matcher.nfa, matcher.dfa, matcher.min_dfa),
        encoding="utf-8",
    )
    print(f"  {'automata.drawio':<20} -> {drawio_path}")


def _interactive_mode() -> None:
    """交互模式：输入模式与测试串，实时反馈匹配结果。"""
    print("=" * 52)
    print("  正则表达式编译器 — 交互模式")
    print("=" * 52)
    print()
    print("支持运算符: | * + ? () . [a-z] [^a-z]")
    print("输入 'quit' 或 'exit' 退出")
    print()

    while True:
        try:
            pattern = input("Pattern: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not pattern:
            continue
        if pattern.lower() in ("quit", "exit"):
            break

        try:
            matcher = RegexMatcher(pattern)
        except RegexCompilerError as error:
            print(f"Error: {error}")
            print()
            continue

        print()
        print(matcher.print_info())
        print()

        while True:
            try:
                test_str = input("Test string: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not test_str:
                _export_visualizations(matcher, "output")
                print()
                break

            if test_str.lower() in ("quit", "exit", "next"):
                break

            print(f"  Match:  {'ACCEPT' if matcher.match(test_str) else 'REJECT'}")
            search_result = matcher.search(test_str)
            if search_result:
                start, end = search_result
                print(f"  Search: [{start}:{end}] = {test_str[start:end]!r}")
            print()

    print("Goodbye!")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口，返回进程退出码。"""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.interactive:
        _interactive_mode()
        return 0

    if args.serve:
        from .web.server import serve

        serve(host=args.host, port=args.port)
        return 0

    if not args.pattern:
        parser.print_help()
        print("\n提示: 使用 --interactive 进入交互模式，或 --serve 启动 Web 界面")
        return 0

    try:
        matcher = RegexMatcher(args.pattern)
    except RegexCompilerError as error:
        print(f"Error parsing pattern: {error}")
        return 1

    executed = False

    if args.info:
        print(matcher.print_info())
        executed = True

    if args.ast:
        if executed:
            print()
        print(f"Pattern: {args.pattern}")
        print("=" * 40)
        print(print_ast(matcher.ast))
        executed = True

    if args.match is not None:
        if executed:
            print()
        _print_match(matcher, args.match)
        executed = True

    if args.search is not None:
        if executed:
            print()
        _print_search(matcher, args.search)
        executed = True

    if args.findall is not None:
        if executed:
            print()
        _print_findall(matcher, args.findall)
        executed = True

    if args.visualize:
        if executed:
            print()
        _export_visualizations(matcher, args.output)
        executed = True

    if not executed:
        print(matcher.print_info())
        print()
        _export_visualizations(matcher, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
