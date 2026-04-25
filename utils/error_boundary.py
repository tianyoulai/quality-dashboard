"""全局错误边界 — 捕获页面级别未处理异常，优雅展示错误信息。

每个页面在入口处调用 `with page_error_boundary("页面名"):` 即可获得统一的异常兜底。
避免白屏 / 报错堆栈直接暴露给用户。
"""
from __future__ import annotations

import traceback
from contextlib import contextmanager

import streamlit as st


@contextmanager
def page_error_boundary(page_name: str = "页面"):
    """页面级错误边界上下文管理器。

    用法::

        with page_error_boundary("总览"):
            # 页面全部逻辑
            ...

    未处理的异常会被捕获并展示为友好的错误面板，而不是让整个页面崩溃白屏。
    """
    try:
        yield
    except st.runtime.scriptrunner.StopException:
        # st.stop() 抛出的异常，正常中断，不应被捕获
        raise
    except Exception as exc:
        _render_error_panel(page_name, exc)


def safe_section(label: str):
    """区块级错误边界上下文管理器。

    用法::

        with safe_section("趋势图"):
            # 渲染逻辑
            ...

    捕获区块内异常，只影响当前区块，不会导致整个页面崩溃。
    """
    return _SectionBoundary(label)


class _SectionBoundary:
    """区块级错误边界（实现为上下文管理器）。"""

    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        # st.stop() 不应被捕获
        if issubclass(exc_type, (SystemExit, KeyboardInterrupt)):
            return False
        try:
            if issubclass(exc_type, st.runtime.scriptrunner.StopException):
                return False
        except AttributeError:
            pass

        st.warning(
            f"⚠️ 「{self.label}」模块加载异常，其他模块不受影响。\n\n"
            f"**错误信息**：`{exc_val}`",
            icon="⚠️",
        )
        with st.expander("🔍 查看详细错误信息", expanded=False):
            st.code(traceback.format_exc(), language="text")
        return True  # 吞掉异常，继续执行后续代码


def _render_error_panel(page_name: str, exc: Exception) -> None:
    """渲染友好的错误面板。"""
    st.error(
        f"😵 **{page_name}**加载时遇到问题，请稍后刷新重试。\n\n"
        f"如果问题持续存在，请联系管理员。",
        icon="🚨",
    )
    with st.expander("🔍 查看详细错误信息（供技术排查）", expanded=False):
        st.code(traceback.format_exc(), language="text")

    # 提供便捷操作
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 刷新页面", key="err_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if st.button("🗑️ 清除缓存", key="err_clear_cache", use_container_width=True):
            st.cache_data.clear()
            st.success("缓存已清除，请刷新页面。")
    with col3:
        st.button("🏠 返回首页", key="err_home", use_container_width=True, on_click=lambda: st.switch_page("pages/01_总览.py"))
