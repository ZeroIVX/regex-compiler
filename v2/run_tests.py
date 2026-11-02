"""测试运行入口。

无需安装任何第三方库，直接运行::

    python run_tests.py

也可以用 pytest 运行（需先 ``pip install -e ".[dev]"``）::

    pytest
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 确保项目根目录在 sys.path 中，保证可以直接运行本脚本
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    """发现并运行全部测试用例。"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(ROOT / "tests"), top_level_dir=str(ROOT))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
