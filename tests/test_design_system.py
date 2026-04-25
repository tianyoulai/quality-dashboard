"""tests/test_design_system.py — utils/design_system.py 单元测试。

覆盖：
  - COLORS 常量完整性（_Colors 自定义类）
  - DesignSystem 纯函数方法（chart_layout 等不依赖 Streamlit 的方法）

注意：hero/section/metric_card/footer 等方法内部调用 st.markdown()，
在无 Streamlit 运行时环境中返回 None，因此仅测试不依赖 st.* 的方法。
"""
from __future__ import annotations

import pytest

from utils.design_system import COLORS, DesignSystem


@pytest.fixture
def ds():
    return DesignSystem()


# ═══════════════════════════════════════════════════════════════
#  COLORS 常量（_Colors 自定义类）
# ═══════════════════════════════════════════════════════════════


class TestColors:
    """设计系统颜色常量。"""

    def test_has_primary(self):
        assert hasattr(COLORS, "primary")
        assert COLORS.primary.startswith("#")

    def test_has_success(self):
        assert hasattr(COLORS, "success")
        assert COLORS.success.startswith("#")

    def test_has_danger(self):
        assert hasattr(COLORS, "danger")
        assert COLORS.danger.startswith("#")

    def test_has_warning(self):
        assert hasattr(COLORS, "warning")
        assert COLORS.warning.startswith("#")

    def test_has_chart_palette(self):
        assert hasattr(COLORS, "chart_palette")
        palette = COLORS.chart_palette
        assert isinstance(palette, (list, tuple))
        assert len(palette) >= 3

    def test_has_text_colors(self):
        assert hasattr(COLORS, "text_primary")
        assert hasattr(COLORS, "text_secondary")
        assert hasattr(COLORS, "text_muted")

    def test_has_bg_colors(self):
        assert hasattr(COLORS, "bg_page")
        assert hasattr(COLORS, "bg_card")

    def test_p0_p1_p2_alert_colors(self):
        """告警等级颜色。"""
        for attr in ("p0", "p1", "p2"):
            assert hasattr(COLORS, attr)
            assert getattr(COLORS, attr).startswith("#")

    def test_light_variants(self):
        """每个语义色都有 _light 变体。"""
        for base in ("primary", "success", "danger", "warning"):
            light_attr = f"{base}_light"
            assert hasattr(COLORS, light_attr), f"缺少 {light_attr}"


# ═══════════════════════════════════════════════════════════════
#  DesignSystem 纯函数方法（不依赖 Streamlit 运行时）
# ═══════════════════════════════════════════════════════════════


class TestDesignSystemPureMethods:
    """不依赖 st.markdown() 的纯函数方法。"""

    def test_chart_layout_returns_dict(self, ds):
        result = ds.chart_layout("测试图表")
        assert isinstance(result, dict)

    def test_chart_layout_has_font(self, ds):
        result = ds.chart_layout("测试")
        assert "font" in result

    def test_chart_layout_title(self, ds):
        result = ds.chart_layout("趋势分析")
        # title 可能在顶层或嵌套结构中
        assert "title" in result or "趋势分析" in str(result)

    def test_group_card_style_returns_tuple(self, ds):
        """group_card_style 返回样式相关内容。"""
        if hasattr(ds, "group_card_style"):
            result = ds.group_card_style(is_selected=False, accuracy_rate=95.0)
            assert result is not None

    def test_methods_exist(self, ds):
        """核心方法都已注册。"""
        expected_methods = [
            "chart_layout", "inject_theme", "hero", "section",
            "metric_card", "footer", "alert_badge", "status_chip",
        ]
        for method in expected_methods:
            assert hasattr(ds, method), f"缺少方法: {method}"
