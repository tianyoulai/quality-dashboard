"""tests/test_error_boundary.py — utils/error_boundary.py 单元测试。

覆盖：
  - _SectionBoundary 上下文管理器的异常捕获行为
  - run_safe 函数的异常处理和返回值
  - guard 装饰器的异常拦截
"""
from __future__ import annotations

import pytest

from utils.error_boundary import _SectionBoundary, run_safe, guard


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


class TestRunSafe:
    """run_safe 函数的核心逻辑测试。"""

    def test_normal_return(self):
        """正常函数调用返回正确结果。"""
        result = run_safe("测试", lambda x: x * 2, 5)
        assert result == 10

    def test_exception_returns_default(self):
        """异常时返回默认值 None。"""
        def bad_fn():
            raise ValueError("测试错误")
        result = run_safe("测试", bad_fn)
        assert result is None

    def test_exception_returns_custom_default(self):
        """异常时返回自定义默认值。"""
        def bad_fn():
            raise RuntimeError("boom")
        result = run_safe("测试", bad_fn, default=[])
        assert result == []

    def test_kwargs_passed(self):
        """关键字参数正确传递。"""
        def fn(a, b=10):
            return a + b
        result = run_safe("测试", fn, 5, b=20)
        assert result == 25

    def test_keyboard_interrupt_not_caught(self):
        """KeyboardInterrupt 不应被捕获。"""
        def bad_fn():
            raise KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            run_safe("测试", bad_fn)

    def test_system_exit_not_caught(self):
        """SystemExit 不应被捕获。"""
        def bad_fn():
            raise SystemExit(1)
        with pytest.raises(SystemExit):
            run_safe("测试", bad_fn)


class TestGuard:
    """guard 装饰器测试。"""

    def test_decorated_normal(self):
        """装饰器不影响正常函数。"""
        @guard("测试")
        def add(a, b):
            return a + b
        assert add(3, 4) == 7

    def test_decorated_exception_returns_none(self):
        """装饰器捕获异常返回 None。"""
        @guard("测试")
        def crash():
            raise ValueError("crash")
        result = crash()
        assert result is None

    def test_preserves_function_name(self):
        """装饰器保留原函数名。"""
        @guard("测试")
        def my_function():
            pass
        assert my_function.__name__ == "my_function"
