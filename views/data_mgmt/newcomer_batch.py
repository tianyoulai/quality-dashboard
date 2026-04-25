"""数据管理 - 新人批次管理 Tab。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from views.data_mgmt._shared import repo


def render_newcomer_batch_tab():
    """渲染「新人批次管理」Tab 内容。"""
    st.markdown("### 📋 新人批次 / 姓名管理")
    st.caption("管理新人名单（dim_newcomer_batch）。支持上传 Excel/CSV 批量导入新人名单，也可以手动添加。")

    nc_mgmt_tab = st.radio(
        "操作方式",
        ["📥 批量上传", "✏️ 手动添加", "📊 当前名单", "🗑️ 清空名单"],
        horizontal=True, key="nc_mgmt_mode",
    )

    if nc_mgmt_tab == "📥 批量上传":
        _render_batch_upload()
    elif nc_mgmt_tab == "✏️ 手动添加":
        _render_manual_add()
    elif nc_mgmt_tab == "📊 当前名单":
        _render_member_list()
    elif nc_mgmt_tab == "🗑️ 清空名单":
        _render_clear_list()


def _render_batch_upload():
    """批量上传新人名单。"""
    st.markdown("""
    **上传格式说明**（Excel 或 CSV 文件）：

    | 列名 | 必填 | 说明 |
    |---|---|---|
    | `reviewer_name` 或 `姓名` | ✅ | 审核人核心姓名（如"刘崇阳"） |
    | `batch_name` 或 `批次` | ✅ | 批次名称（如"0408批"） |
    | `team_name` 或 `基地` | ❌ | 所在基地/团队（如"白龙湖"） |
    | `reviewer_alias` 或 `全名` | ❌ | 全名（如"云雀联营-刘崇阳"），不填则自动生成 |
    | `join_date` 或 `入职日期` | ❌ | 入职日期（YYYY-MM-DD），不填则默认今天 |
    | `team_leader` 或 `组长` | ❌ | 团队组长 |
    | `delivery_pm` 或 `交付PM` | ❌ | 交付PM |
    | `mentor_name` 或 `导师` | ❌ | 导师姓名 |
    | `owner` 或 `质培owner` | ❌ | 质培负责人 |
    """)

    nc_batch_file = st.file_uploader(
        "选择新人名单文件",
        type=["xlsx", "xls", "csv"],
        key="nc_batch_uploader",
    )

    nc_import_mode = st.radio(
        "导入模式",
        ["追加（保留已有数据）", "覆盖（先清空再导入）"],
        horizontal=True, key="nc_import_mode",
    )

    if nc_batch_file and st.button("📥 导入新人名单", key="import_nc_batch"):
        try:
            # 读取文件
            if nc_batch_file.name.endswith(".csv"):
                try:
                    batch_df = pd.read_csv(nc_batch_file, dtype=str)
                except UnicodeDecodeError:
                    nc_batch_file.seek(0)
                    batch_df = pd.read_csv(nc_batch_file, encoding="gb18030", dtype=str)
            else:
                batch_df = pd.read_excel(nc_batch_file, dtype=str)

            st.write(f"读取到 {len(batch_df)} 行数据")
            st.dataframe(batch_df.head(5))

            # 列名映射
            col_map = {
                "姓名": "reviewer_name", "名字": "reviewer_name", "审核人": "reviewer_name",
                "批次": "batch_name", "批次名": "batch_name",
                "基地": "team_name", "团队": "team_name", "队伍": "team_name",
                "全名": "reviewer_alias", "别名": "reviewer_alias",
                "入职日期": "join_date", "日期": "join_date",
                "组长": "team_leader", "带教": "team_leader",
                "交付PM": "delivery_pm", "PM": "delivery_pm",
                "导师": "mentor_name",
                "质培owner": "owner", "owner": "owner",
            }
            batch_df = batch_df.rename(columns={k: v for k, v in col_map.items() if k in batch_df.columns})

            # 验证必填列
            if "reviewer_name" not in batch_df.columns:
                st.error("❌ 缺少必填列：`reviewer_name` 或 `姓名`")
            elif "batch_name" not in batch_df.columns:
                st.error("❌ 缺少必填列：`batch_name` 或 `批次`")
            else:
                _process_batch_import(batch_df, nc_import_mode)
        except Exception as e:
            st.error(f"导入失败：{e}")


def _process_batch_import(batch_df: pd.DataFrame, nc_import_mode: str):
    """处理批量导入的业务逻辑。"""
    # 自动补全
    if "reviewer_alias" not in batch_df.columns:
        batch_df["reviewer_alias"] = batch_df["reviewer_name"].apply(
            lambda x: f"云雀联营-{x}" if x and not str(x).startswith("云雀联营-") else x
        )
    if "join_date" not in batch_df.columns:
        batch_df["join_date"] = str(date.today())
    if "team_name" not in batch_df.columns:
        batch_df["team_name"] = batch_df["batch_name"].apply(
            lambda x: "黑虎泉" if "黑虎泉" in str(x) else ("青龙河" if "青龙河" in str(x) else ("白龙湖" if "白龙湖" in str(x) else "未分组"))
        )

    for col in ["team_leader", "delivery_pm", "mentor_name", "owner"]:
        if col not in batch_df.columns:
            batch_df[col] = ""

    # 覆盖模式：先清空
    if nc_import_mode == "覆盖（先清空再导入）":
        repo.execute("TRUNCATE TABLE dim_newcomer_batch")
        st.warning("已清空旧数据")

    # 逐行插入
    inserted, skipped = 0, 0
    seen_keys: set[tuple[str, str]] = set()
    for _, row in batch_df.iterrows():
        name = str(row["reviewer_name"]).strip()
        batch = str(row["batch_name"]).strip()
        if not name or not batch or name == "nan" or batch == "nan":
            skipped += 1
            continue

        dedup_key = (batch, name)
        if dedup_key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(dedup_key)

        if nc_import_mode != "覆盖（先清空再导入）":
            existing = repo.fetch_one(
                "SELECT COUNT(*) AS cnt FROM dim_newcomer_batch WHERE reviewer_name = %s AND batch_name = %s",
                [name, batch]
            )
            if existing and existing["cnt"] > 0:
                skipped += 1
                continue

        repo.execute("""
            INSERT IGNORE INTO dim_newcomer_batch
            (batch_name, reviewer_name, reviewer_alias, team_name, join_date,
             team_leader, delivery_pm, mentor_name, owner, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """, [
            batch, name,
            str(row.get("reviewer_alias", f"云雀联营-{name}")).strip(),
            str(row.get("team_name", "未分组")).strip(),
            str(row.get("join_date", str(date.today()))).strip(),
            str(row.get("team_leader", "")).strip(),
            str(row.get("delivery_pm", "")).strip(),
            str(row.get("mentor_name", "")).strip(),
            str(row.get("owner", "")).strip(),
        ])
        inserted += 1

    st.success(f"✅ 导入完成！新增 {inserted} 人，跳过 {skipped} 人（已存在或无效行）")
    st.cache_data.clear()


def _render_manual_add():
    """手动添加新人。"""
    st.markdown("#### 手动添加新人")
    with st.form("add_newcomer_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("姓名 *", placeholder="如：刘崇阳")
            new_batch = st.text_input("批次 *", placeholder="如：0408批")
            new_team = st.text_input("基地", placeholder="如：白龙湖")
        with col2:
            new_join_date = st.date_input("入职日期", value=date.today())
            new_leader = st.text_input("组长", placeholder="可选")
            new_mentor = st.text_input("导师", placeholder="可选")

        submitted = st.form_submit_button("➕ 添加")
        if submitted:
            if not new_name or not new_batch:
                st.error("姓名和批次为必填项")
            else:
                new_alias = f"云雀联营-{new_name}" if not new_name.startswith("云雀联营-") else new_name
                team = new_team or (
                    "黑虎泉" if "黑虎泉" in new_batch else (
                        "青龙河" if "青龙河" in new_batch else (
                            "白龙湖" if "白龙湖" in new_batch else "未分组"
                        )
                    )
                )
                existing = repo.fetch_one(
                    "SELECT COUNT(*) AS cnt FROM dim_newcomer_batch WHERE reviewer_name = %s AND batch_name = %s",
                    [new_name, new_batch]
                )
                if existing and existing["cnt"] > 0:
                    st.warning(f"{new_name} 在 {new_batch} 中已存在")
                else:
                    repo.execute("""
                        INSERT INTO dim_newcomer_batch
                        (batch_name, reviewer_name, reviewer_alias, team_name, join_date,
                         team_leader, mentor_name, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                    """, [new_batch, new_name, new_alias, team, new_join_date, new_leader or "", new_mentor or ""])
                    st.success(f"✅ 已添加 {new_name} 到 {new_batch}")
                    st.cache_data.clear()


def _render_member_list():
    """查看当前名单。"""
    st.markdown("#### 当前新人名单")
    try:
        all_members = repo.fetch_df("""
            SELECT batch_name, reviewer_name, reviewer_alias, team_name, join_date,
                   team_leader, delivery_pm, mentor_name, owner, status
            FROM dim_newcomer_batch
            ORDER BY batch_name, team_name, reviewer_name
        """)
        if all_members is not None and not all_members.empty:
            st.info(f"共 {len(all_members)} 人，{all_members['batch_name'].nunique()} 个批次")

            batch_filter = st.multiselect(
                "筛选批次",
                options=sorted(all_members["batch_name"].unique().tolist()),
                key="nc_batch_filter",
            )
            if batch_filter:
                all_members = all_members[all_members["batch_name"].isin(batch_filter)]

            st.dataframe(all_members, use_container_width=True, height=400)

            csv_data = all_members.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 导出 CSV", data=csv_data,
                file_name=f"newcomer_list_{date.today():%Y%m%d}.csv",
                mime="text/csv",
            )
        else:
            st.info("暂无新人名单数据")
    except Exception as e:
        st.error(f"查询失败：{e}")


def _render_clear_list():
    """清空名单。"""
    st.markdown("#### ⚠️ 清空新人名单")
    st.error("此操作将删除 dim_newcomer_batch 中的所有数据，不可逆！")
    try:
        cnt = repo.fetch_one("SELECT COUNT(*) AS cnt FROM dim_newcomer_batch")
        st.info(f"当前共 {cnt['cnt']} 条新人名单记录")
    except Exception:
        pass

    if st.checkbox("我确认要清空所有新人名单", key="nc_batch_clear_confirm"):
        confirm_text = st.text_input(
            "请输入 DELETE 确认", key="nc_batch_clear_text", placeholder="输入 DELETE",
        )
        if st.button("🗑️ 清空名单", key="nc_batch_clear", disabled=(confirm_text != "DELETE")):
            repo.execute("TRUNCATE TABLE dim_newcomer_batch")
            st.success("新人名单已清空！")
            st.cache_data.clear()
