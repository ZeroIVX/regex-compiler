"""简易测试运行器 —— 直接运行所有测试，无需 pytest 安装"""

import sys
import os
import traceback

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_lexer import TestLexer, TestLexerErrors
from tests.test_parser import TestParser, TestParserErrors
from tests.test_nfa import TestThompson
from tests.test_dfa import TestDFAConstruction, TestMinimize
from tests.test_integration import (
    TestRegexMatcher, TestSearch, TestFindAll, TestEdgeCases, TestPipelineInfo
)
from tests.test_regression import (
    TestWildcard, TestNegatedClass, TestPlusClosure, TestKnownLimitation
)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def run_test_class(cls) -> tuple[int, int, list[str]]:
    """运行一个测试类中的所有 test_ 方法"""
    passed = 0
    failed = 0
    failures = []

    instance = cls()
    test_methods = sorted(
        [name for name in dir(cls) if name.startswith("test_")],
    )

    for method_name in test_methods:
        method = getattr(instance, method_name)
        test_name = f"{cls.__name__}.{method_name}"
        try:
            method()
            passed += 1
            print(f"  {GREEN}PASS{RESET} {test_name}")
        except AssertionError as e:
            failed += 1
            failures.append(f"{test_name}: {e}")
            print(f"  {RED}FAIL{RESET} {test_name} - {e}")
        except Exception as e:
            failed += 1
            failures.append(f"{test_name}: {e}")
            print(f"  {RED}ERROR{RESET} {test_name} - {e}")

    return passed, failed, failures


def main():
    test_classes = [
        TestLexer,
        TestLexerErrors,
        TestParser,
        TestParserErrors,
        TestThompson,
        TestDFAConstruction,
        TestMinimize,
        TestRegexMatcher,
        TestSearch,
        TestFindAll,
        TestEdgeCases,
        TestPipelineInfo,
        TestWildcard,
        TestNegatedClass,
        TestPlusClosure,
        TestKnownLimitation,
    ]

    total_passed = 0
    total_failed = 0
    all_failures = []

    for cls in test_classes:
        print(f"\n{YELLOW}{cls.__name__}{RESET}")
        p, f, fails = run_test_class(cls)
        total_passed += p
        total_failed += f
        all_failures.extend(fails)

    print(f"\n{'=' * 60}")
    print(f"Total: {total_passed + total_failed} tests")
    print(f"  {GREEN}Passed: {total_passed}{RESET}")
    if total_failed > 0:
        print(f"  {RED}Failed: {total_failed}{RESET}")
        for fail in all_failures:
            print(f"    {fail}")
    else:
        print(f"  {GREEN}All tests passed!{RESET}")
    print(f"{'=' * 60}")

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
