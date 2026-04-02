from pathlib import Path

import streamlit as st

from services.dashboard_service import DashboardService


st.set_page_config(page_title="质培运营看板", page_icon="🧭", layout="wide")

# Hero 区域
st.markdown("""
<div style="margin-bottom: 1.5rem; padding: 1.5rem; background: #ffffff; border-radius: 1rem; border-left: 4px solid #2e7d32; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #1a1a1a;">🧭 质培运营看板</h1>
    </div>
    <div style="font-size: 0.9rem; color: #4b5563; line-height: 1.6;">
        项目骨架 · 数据库初始化 · 快速启动
    </div>
</div>
""", unsafe_allow_html=True)

service = DashboardService()
schema_path = Path(__file__).resolve().parent / "storage" / "schema.sql"
db_path = Path(service.db_path).resolve()

# 移除旧标题（已整合到 Hero 区域）

col1, col2, col3 = st.columns(3)
col1.metric("数据库路径", str(db_path.name))
col2.metric("Schema 文件", schema_path.name)
col3.metric("当前状态", "等待导入真实 fact 数据")

with st.container(border=True):
    st.markdown("### 你现在可以直接做的事")
    st.markdown(
        """
1. 点击下方按钮初始化 schema，或直接运行 `python3 jobs/refresh_warehouse.py`。  
2. 用 `python3 jobs/import_fact_data.py --qa-file /你的文件.xlsx` 导入质检明细。  
3. 运行 `streamlit run app.py`，再进入 `pages/01_首页.py` 看真实页面。  
        """
    )

cols = st.columns([1, 1, 2])
if cols[0].button("初始化 Schema", use_container_width=True):
    service.ensure_schema()
    st.success(f"已执行 schema：{schema_path}")

if cols[1].button("检查是否已有数据", use_container_width=True):
    if service.has_any_data():
        st.success("数据库中已存在 fact 数据，可以直接进入首页页面。")
    else:
        st.warning("当前还没有 fact 数据，页面能打开，但会提示先导入明细。")

with st.container(border=True):
    st.markdown("### 项目结构")
    st.code(
        """
app.py
storage/
  ├── schema.sql
  └── repository.py
services/
  └── dashboard_service.py
pages/
  └── 01_首页.py
        """.strip(),
        language="text",
    )

with st.expander("为什么我建议先做这套结构", expanded=True):
    st.markdown(
        """
- `storage/schema.sql`：把事实层 / 汇总层 / 预警层一次定住。  
- `storage/repository.py`：负责所有 TiDB 查询，避免 SQL 散在页面里。  
- `services/dashboard_service.py`：负责组装“日 / 周 / 月 + 下探”页面数据。  
- `pages/01_首页.py`：直接体现看板交互，不再停留在静态 demo。  
        """
    )

st.info("下一步最值钱的是：拿一份真实质检明细先跑导入，再看首页是不是已经能出真指标。")
