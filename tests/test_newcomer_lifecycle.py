"""tests/test_newcomer_lifecycle.py — 新人生命周期纯函数单元测试。

覆盖：
  - get_status_label: 状态标签查找
  - STATUS_FLOW: 状态流完整性
  - DEFAULT_RULES: 默认规则数据完整性
"""
from __future__ import annotations

import pytest

from services.newcomer_lifecycle import (
    DEFAULT_RULES,
    STATUS_FLOW,
    STATUS_LABELS,
    get_status_label,
)


# ═══════════════════════════════════════════════════════════════
#  STATUS_FLOW / STATUS_LABELS 数据完整性
# ═══════════════════════════════════════════════════════════════


class TestStatusConstants:
    """状态常量的完整性和一致性。"""

    def test_status_flow_not_empty(self):
        assert len(STATUS_FLOW) >= 5

    def test_status_flow_order(self):
        """状态流顺序应该是 pending → internal → external → formal → graduated"""
        assert STATUS_FLOW[0] == "pending"
        assert "internal_training" in STATUS_FLOW
        assert "external_training" in STATUS_FLOW
        assert "graduated" in STATUS_FLOW

    def test_all_flow_states_have_labels(self):
        """STATUS_FLOW 中的每个状态在 STATUS_LABELS 中都有对应标签。"""
        for status in STATUS_FLOW:
            assert status in STATUS_LABELS, f"状态 '{status}' 缺少 label 定义"

    def test_label_tuple_structure(self):
        """每个标签都是 (text, color, bg_color) 三元组。"""
        for status, label in STATUS_LABELS.items():
            assert isinstance(label, tuple), f"状态 '{status}' 的 label 不是 tuple"
            assert len(label) == 3, f"状态 '{status}' 的 label 长度不是 3"
            text, color, bg = label
            assert isinstance(text, str) and len(text) > 0
            assert color.startswith("#")
            assert bg.startswith("#")


# ═══════════════════════════════════════════════════════════════
#  get_status_label
# ═══════════════════════════════════════════════════════════════


class TestGetStatusLabel:
    """状态标签查找函数。"""

    def test_known_status(self):
        text, color, bg = get_status_label("pending")
        assert "待开始" in text
        assert color.startswith("#")

    def test_graduated(self):
        text, _, _ = get_status_label("graduated")
        assert "毕业" in text

    def test_training_compat(self):
        """兼容旧的 'training' 状态。"""
        text, _, _ = get_status_label("training")
        assert "培训" in text

    def test_unknown_status(self):
        """未知状态返回默认值。"""
        text, color, bg = get_status_label("nonexistent_status")
        assert text == "未知"
        assert color.startswith("#")

    def test_internal_training(self):
        text, _, _ = get_status_label("internal_training")
        assert "内检" in text

    def test_external_training(self):
        text, _, _ = get_status_label("external_training")
        assert "外检" in text

    def test_exited(self):
        text, _, _ = get_status_label("exited")
        assert "退出" in text


# ═══════════════════════════════════════════════════════════════
#  DEFAULT_RULES
# ═══════════════════════════════════════════════════════════════


class TestDefaultRules:
    """默认晋级规则的数据完整性。"""

    def test_rules_not_empty(self):
        assert len(DEFAULT_RULES) >= 2

    def test_rule_required_fields(self):
        """每条规则都包含必要字段。"""
        required = {"rule_code", "rule_name", "from_status", "to_status",
                     "metric", "compare_op", "threshold", "consecutive_days",
                     "min_qa_cnt", "description"}
        for rule in DEFAULT_RULES:
            missing = required - set(rule.keys())
            assert not missing, f"规则 '{rule.get('rule_code')}' 缺少字段: {missing}"

    def test_internal_to_external_rule(self):
        """内检→外检规则的参数正确。"""
        rule = next(r for r in DEFAULT_RULES if r["rule_code"] == "INTERNAL_TO_EXTERNAL")
        assert rule["from_status"] == "internal_training"
        assert rule["to_status"] == "external_training"
        assert rule["threshold"] == 90.0
        assert rule["consecutive_days"] == 3

    def test_external_to_formal_rule(self):
        """外检→正式上线规则的参数正确。"""
        rule = next(r for r in DEFAULT_RULES if r["rule_code"] == "EXTERNAL_TO_FORMAL")
        assert rule["from_status"] == "external_training"
        assert rule["to_status"] == "graduated"
        assert rule["threshold"] == 98.0
        assert rule["consecutive_days"] == 3

    def test_from_status_in_flow(self):
        """所有规则的 from_status 都在状态流中。"""
        for rule in DEFAULT_RULES:
            assert rule["from_status"] in STATUS_FLOW, \
                f"规则 '{rule['rule_code']}' 的 from_status '{rule['from_status']}' 不在 STATUS_FLOW 中"

    def test_to_status_in_flow_or_graduated(self):
        """所有规则的 to_status 都在状态流中或是 graduated/exited。"""
        valid = set(STATUS_FLOW) | {"graduated", "exited"}
        for rule in DEFAULT_RULES:
            assert rule["to_status"] in valid, \
                f"规则 '{rule['rule_code']}' 的 to_status '{rule['to_status']}' 不是有效状态"

    def test_thresholds_reasonable(self):
        """阈值范围在 0-100 之间。"""
        for rule in DEFAULT_RULES:
            assert 0 <= rule["threshold"] <= 100, \
                f"规则 '{rule['rule_code']}' 的阈值 {rule['threshold']} 超出合理范围"

    def test_consecutive_days_positive(self):
        """连续天数为正整数。"""
        for rule in DEFAULT_RULES:
            assert rule["consecutive_days"] > 0

    def test_min_qa_cnt_positive(self):
        """最低质检量为正整数。"""
        for rule in DEFAULT_RULES:
            assert rule["min_qa_cnt"] > 0
