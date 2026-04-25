"""tests/test_error_boundary.py — utils/error_boundary.py 单元测试。

覆盖：
  - _SectionBoundary 上下文管理器的异常捕获行为
"""
from __future__ import annotations

import pytest

from utils.error_boundary import _SectionBoundary


class TestSectionBoundary:
    """区块级错误边界的核心逻辑（不依赖 Streamlit 运行时）。"""

    def test_no_exception(self):
        """无异常时正常通过。"""
        boundary = _SectionBoundary("测试区块")
        with boundary:
            x = 1 + 1
        assert x == 2

    def test_keyboard_interrupt_not_caught(self):
        """KeyboardInterrupt 不应被捕获。"""
        boundary = _SectionBoundary("测试区块")
        with pytest.raises(KeyboardInterrupt):
            with boundary:
                raise KeyboardInterrupt()

    def test_system_exit_not_caught(self):
        """SystemExit 不应被捕获。"""
        boundary = _SectionBoundary("测试区块")
        with pytest.raises(SystemExit):
            with boundary:
                raise SystemExit(1)

    def test_label_stored(self):
        """标签正确存储。"""
        boundary = _SectionBoundary("趋势图")
        assert boundary.label == "趋势图"
