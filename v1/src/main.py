"""主入口 —— CLI 命令行接口和交互模式"""

import sys
import os

from .lexer import lex, LexerError
from .parser import parse, print_ast, ParserError
from .nfa import ThompsonBuilder
from .dfa import build_dfa, simulate_dfa
from .minimize import minimize_dfa
from .matcher import RegexMatcher
from .visualizer import (
    render_nfa_svg, render_dfa_svg, render_min_dfa_svg, render_drawio_xml,
)


def _ensure_output_dir(path: str) -> str:
    """确保输出目录存在并返回路径"""
    out_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    return path


def cmd_info(matcher: RegexMatcher) -> None:
    """打印编译器流水线信息"""
    print(matcher.print_info())


def cmd_ast(pattern: str) -> None:
    """打印 AST 树"""
    ast = parse(pattern)
    print(f"Pattern: {pattern}")
    print("=" * 40)
    print(print_ast(ast))


def cmd_match(matcher: RegexMatcher, text: str) -> None:
    """执行完全匹配"""
    result = matcher.match(text)
    steps = matcher.simulate(text)
    print(f"Pattern: {matcher.pattern}")
    print(f"Input:   {text!r}")
    print(f"Match:   {'ACCEPT' if result else 'REJECT'}")
    print()
    print("Simulation steps:")
    for step in steps:
        if step.get("error"):
            print(f"  [{step['pos']}] '{step['char']}' -> ERROR (no transition)")
        else:
            status = "+" if step["accepted"] else ""
            print(f"  [{step['pos']}] '{step['char']}' -> State {step['to_state']} {status}")


def cmd_search(matcher: RegexMatcher, text: str) -> None:
    """执行搜索匹配"""
    result = matcher.search(text)
    print(f"Pattern: {matcher.pattern}")
    print(f"Input:   {text!r}")
    if result:
        start, end = result
        print(f"Found:   [{start}:{end}] = {text[start:end]!r}")
    else:
        print("No match found.")


def cmd_findall(matcher: RegexMatcher, text: str) -> None:
    """找到所有匹配"""
    results = matcher.findall(text)
    print(f"Pattern: {matcher.pattern}")
    print(f"Input:   {text!r}")
    print(f"Matches: {len(results)}")
    for start, end, substr in results:
        print(f"  [{start}:{end}] = {substr!r}")


def cmd_visualize(matcher: RegexMatcher, out_dir: str = "output") -> None:
    """生成所有可视化输出"""
    os.makedirs(out_dir, exist_ok=True)

    nfa_path = os.path.join(out_dir, "nfa.svg")
    dfa_path = os.path.join(out_dir, "dfa.svg")
    min_dfa_path = os.path.join(out_dir, "minimal_dfa.svg")
    drawio_path = os.path.join(out_dir, "automata.drawio")

    render_nfa_svg(matcher.nfa, nfa_path)
    print(f"NFA SVG:  {nfa_path}")

    render_dfa_svg(matcher.dfa, dfa_path)
    print(f"DFA SVG:  {dfa_path}")

    render_min_dfa_svg(matcher.min_dfa, min_dfa_path)
    print(f"Min DFA:  {min_dfa_path}")

    xml = render_drawio_xml(matcher.nfa, matcher.dfa, matcher.min_dfa, drawio_path)
    print(f"DrawIO:   {drawio_path}")


def interactive_mode():
    """交互模式"""
    print("=" * 50)
    print("  正则表达式编译器 - 交互模式")
    print("=" * 50)
    print()
    print("支持运算符: | * + ? () . [a-z]")
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
        if pattern.lower() in ('quit', 'exit'):
            break

        try:
            matcher = RegexMatcher(pattern)
            print(matcher.print_info())
            print()

            while True:
                try:
                    test_str = input("Test string: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not test_str:
                    # 显示可视化
                    cmd_visualize(matcher, "output")
                    print()
                    break

                if test_str.lower() in ('quit', 'exit', 'next'):
                    break

                result = matcher.match(test_str)
                print(f"  Match: {'ACCEPT' if result else 'REJECT'}")

                search_result = matcher.search(test_str)
                if search_result:
                    s, e = search_result
                    print(f"  Search: [{s}:{e}] = {test_str[s:e]!r}")

                print()

        except (LexerError, ParserError, ValueError) as e:
            print(f"Error: {e}")
            print()

    print("Goodbye!")


def main():
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="正则表达式编译器 —— Regex → NFA → DFA → MinDFA 完整流水线",
    )
    parser.add_argument("--pattern", "-p", type=str, help="正则表达式")
    parser.add_argument("--match", "-m", type=str, help="完全匹配测试字符串")
    parser.add_argument("--search", "-s", type=str, help="搜索匹配测试字符串")
    parser.add_argument("--findall", "-f", type=str, help="查找所有匹配")
    parser.add_argument("--ast", "-a", action="store_true", help="打印 AST")
    parser.add_argument("--info", "-i", action="store_true", help="打印流水线信息")
    parser.add_argument("--visualize", "-v", action="store_true", help="生成可视化输出")
    parser.add_argument("--output", "-o", type=str, default="output", help="输出目录 (默认: output)")
    parser.add_argument("--interactive", "-I", action="store_true", help="交互模式")

    args = parser.parse_args()

    # 交互模式
    if args.interactive:
        interactive_mode()
        return

    # 必须提供 pattern
    if not args.pattern:
        parser.print_help()
        print("\nTip: 使用 --interactive 进入交互模式")
        return

    try:
        matcher = RegexMatcher(args.pattern)
    except (LexerError, ParserError) as e:
        print(f"Error parsing pattern: {e}")
        sys.exit(1)

    # 执行各种命令
    any_cmd = False

    if args.info:
        cmd_info(matcher)
        any_cmd = True

    if args.ast:
        if any_cmd:
            print()
        cmd_ast(args.pattern)
        any_cmd = True

    if args.match:
        if any_cmd:
            print()
        cmd_match(matcher, args.match)
        any_cmd = True

    if args.search:
        if any_cmd:
            print()
        cmd_search(matcher, args.search)
        any_cmd = True

    if args.findall:
        if any_cmd:
            print()
        cmd_findall(matcher, args.findall)
        any_cmd = True

    if args.visualize:
        if any_cmd:
            print()
        cmd_visualize(matcher, args.output)
        any_cmd = True

    if not any_cmd:
        # 默认：显示信息和可视化
        cmd_info(matcher)
        print()
        cmd_visualize(matcher, args.output)


if __name__ == "__main__":
    main()
