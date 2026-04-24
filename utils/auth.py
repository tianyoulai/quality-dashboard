"""轻量级访问控制模块。

Streamlit Cloud 不支持完整的 RBAC，使用密码保护关键页面。
角色划分：
- admin: 可访问数据管理、告警规则、数据清除
- viewer: 可访问总览、内检、明细、新人追踪（默认角色）

使用方式：
  from utils.auth import require_role
  require_role("admin")  # 需要管理员权限的页面调用
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

_SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.json"


def _load_auth_config() -> dict:
    """加载认证配置。"""
    if _SETTINGS_PATH.exists():
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
        return settings.get("auth", {})
    return {}


def _is_auth_enabled() -> bool:
    """检查是否启用了访问控制。"""
    cfg = _load_auth_config()
    return cfg.get("enabled", False)


def _check_password(password: str) -> str | None:
    """检查密码，返回角色名或 None。"""
    cfg = _load_auth_config()
    users = cfg.get("users", {})
    for username, user_cfg in users.items():
        if user_cfg.get("password") == password:
            return user_cfg.get("role", "viewer")
    # 兼容简单模式
    admin_pwd = cfg.get("admin_password", "")
    if admin_pwd and password == admin_pwd:
        return "admin"
    return None


def get_current_role() -> str:
    """获取当前用户角色。未登录返回 'viewer'。"""
    if not _is_auth_enabled():
        return "admin"  # 未启用认证时默认管理员
    return st.session_state.get("user_role", "viewer")


def is_admin() -> bool:
    """检查当前用户是否是管理员。"""
    return get_current_role() == "admin"


def require_role(role: str = "admin") -> None:
    """要求特定角色才能继续。不满足时显示密码输入框。

    Args:
        role: 要求的最低角色。'admin' 或 'viewer'。
    """
    if not _is_auth_enabled():
        return  # 未启用认证，直接通过

    current = get_current_role()
    if role == "viewer":
        return  # viewer 角色无需认证
    if current == "admin":
        return  # 已是管理员

    # 显示密码输入框
    st.markdown("---")
    st.warning("🔐 此页面需要管理员权限")
    with st.form("admin_auth_form"):
        pwd = st.text_input("管理员密码", type="password", placeholder="请输入管理员密码")
        submitted = st.form_submit_button("🔓 验证", use_container_width=True)
        if submitted:
            result_role = _check_password(pwd)
            if result_role == "admin":
                st.session_state["user_role"] = "admin"
                st.success("✅ 验证通过")
                st.rerun()
            else:
                st.error("❌ 密码错误")
    st.stop()


def render_admin_badge() -> None:
    """在侧边栏显示当前角色标识。"""
    if not _is_auth_enabled():
        return
    role = get_current_role()
    badge = "🔑 管理员" if role == "admin" else "👀 观察者"
    st.sidebar.markdown(f"""
    <div style="text-align:center; padding: 0.25rem; margin-bottom: 0.5rem;">
        <span style="background: {'#DCFCE7' if role == 'admin' else '#F3F4F6'}; 
                     padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.75rem;
                     color: {'#166534' if role == 'admin' else '#6B7280'};">
            {badge}
        </span>
    </div>
    """, unsafe_allow_html=True)

    if role == "admin":
        if st.sidebar.button("🔒 退出管理模式", key="logout_admin", use_container_width=True):
            st.session_state["user_role"] = "viewer"
            st.rerun()
