"""数据管理页：上传质检 Excel / 申诉 CSV，一键刷新数仓和告警。"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.audit import log_action
from views.data_mgmt import (
    preview_file_rows,
    get_upload_history,
    check_file_exists,
    compute_file_hash_from_bytes,
    compute_file_hash_chunked,
    PROJECT_ROOT,
    repo,
    render_freshness_panel,
    render_health_check,
)

from utils.styles import inject_global_css
inject_global_css()

# 权限控制（可通过 config/settings.json 启用）
from utils.auth import require_role, render_admin_badge
render_admin_badge()
require_role("admin")

# Hero 区域
st.markdown("""
<div style="margin-bottom: 1.5rem; padding: 1.5rem; background: #ffffff; border-radius: 1rem; border-left: 4px solid #2e7d32; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #1a1a1a;">⚙️ 数据管理</h1>
    </div>
    <div style="font-size: 0.9rem; color: #4b5563; line-height: 1.6;">
        上传质检 Excel 或申诉 CSV · 自动入库并刷新数仓/告警 · 支持多文件批量上传 · 数据维护与清理
    </div>
</div>
""", unsafe_allow_html=True)

# ---- 数据新鲜度面板 ----
with st.expander("📊 数据新鲜度概览", expanded=False):
    render_freshness_panel()

tab_import = st.tabs(["质检数据", "申诉数据", "Google Sheet", "新人质检数据", "新人批次管理", "新人状态管理", "一键刷新", "告警规则", "上传记录", "清除缓存", "清除数据"])


# 工具函数已迁移至 views/data_mgmt/_shared.py


# ==================== 质检数据 ====================
with tab_import[0]:
    st.markdown("### 上传质检 Excel")
    st.caption("支持 `.xlsx` / `.xls` 格式，可拖拽多个文件批量上传。")

    qa_files = st.file_uploader(
        "选择质检文件（支持拖拽多选）",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="qa_upload",
    )

    if qa_files:
        st.info(f"📋 已选择 {len(qa_files)} 个文件：")
        
        # 导入按钮放在文件列表正下方，显眼位置（type="primary" 让按钮更醒目）
        do_import = st.button("批量导入质检数据", key="import_qa", type="primary")
        
        # 预览每个文件
        for f in qa_files:
            with st.expander(f"📄 {f.name} ({f.size / 1024:.1f} KB)", expanded=False):
                preview = preview_file_rows(f, "qa")
                if preview["error"]:
                    st.error(f"读取失败：{preview['error']}")
                else:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("文件行数", f"{preview['rows']:,}")
                    col2.metric("列数", preview["columns"])
                    col3.metric("文件大小", f"{f.size / 1024:.1f} KB")
                    
                    # 检查是否已上传过
                    file_hash = compute_file_hash_from_bytes(f.getvalue())
                    existing = check_file_exists(file_hash)
                    if existing:
                        st.warning(
                            f"⚠️ 该文件已于 {existing['first_upload_time']} 上传过 "
                            f"（已上传 {existing['upload_count']} 次），导入时将自动跳过。"
                        )
                    
                    if preview["preview_df"] is not None and not preview["preview_df"].empty:
                        st.markdown("**数据预览（前5行）：**")
                        st.dataframe(preview["preview_df"].head(), use_container_width=True)

        if do_import:
            success_count = 0
            fail_count = 0
            skip_count = 0
            logs = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, qa_file in enumerate(qa_files):
                status_text.text(f"正在导入 {qa_file.name}...")
                progress_bar.progress((idx + 1) / len(qa_files) / 2)

                with tempfile.NamedTemporaryFile(suffix=Path(qa_file.name).suffix, delete=False) as tmp:
                    tmp.write(qa_file.getvalue())
                    tmp_path = tmp.name

                try:
                    result = subprocess.run(
                        [sys.executable, str(PROJECT_ROOT / "jobs/import_fact_data.py"), "--qa-file", tmp_path, "--source-name", qa_file.name],
                        capture_output=True,
                        text=True,
                        cwd=str(PROJECT_ROOT),
                    )
                    if result.returncode == 0:
                        import json
                        try:
                            output = json.loads(result.stdout)
                            inserted = output.get("qa_files", [{}])[0].get("inserted_rows", 0)
                            if inserted == 0:
                                skip_count += 1
                                logs.append(f"⏭️ {qa_file.name} 已跳过（文件内容已存在）")
                            else:
                                success_count += 1
                                logs.append(f"✅ {qa_file.name} 导入成功（{inserted} 行）")
                        except Exception:
                            success_count += 1
                            logs.append(f"✅ {qa_file.name} 导入成功")
                    else:
                        fail_count += 1
                        logs.append(f"❌ {qa_file.name} 导入失败：{result.stderr[:200]}")
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

            # 导入完成后自动刷新数仓+告警
            if success_count > 0:
                status_text.text("正在刷新数仓和告警...")
                progress_bar.progress(0.75)
                try:
                    refresh_result = subprocess.run(
                        [sys.executable, str(PROJECT_ROOT / "jobs/refresh_warehouse.py")],
                        capture_output=True, text=True,
                        cwd=str(PROJECT_ROOT),
                    )
                    if refresh_result.returncode == 0:
                        logs.append("🔄 数仓刷新成功")
                    else:
                        logs.append(f"⚠️ 数仓刷新失败：{refresh_result.stderr[:200]}")
                except Exception as e:
                    logs.append(f"⚠️ 数仓刷新异常：{e}")

                try:
                    alert_result = subprocess.run(
                        [sys.executable, str(PROJECT_ROOT / "jobs/refresh_alerts.py")],
                        capture_output=True, text=True,
                        cwd=str(PROJECT_ROOT),
                    )
                    if alert_result.returncode == 0:
                        logs.append("🔔 告警刷新成功")
                    else:
                        logs.append(f"⚠️ 告警刷新失败：{alert_result.stderr[:200]}")
                except Exception as e:
                    logs.append(f"⚠️ 告警刷新异常：{e}")

            progress_bar.progress(1.0)
            progress_bar.empty()
            status_text.empty()

            if success_count > 0:
                st.success(f"成功导入 {success_count} 个文件，已自动刷新数仓和告警" + (f"，{skip_count} 个跳过" if skip_count > 0 else "") + (f"，{fail_count} 个失败" if fail_count > 0 else ""))
                log_action("upload", "fact_qa_event", f"质检Excel导入 {success_count}个文件")
            elif skip_count > 0:
                st.warning(f"所有文件均已上传过，跳过 {skip_count} 个文件")
            else:
                st.error("所有文件导入失败")

            with st.expander("查看导入日志", expanded=(fail_count > 0)):
                st.code("\n".join(logs), language="text")

    st.markdown("---")
    st.caption("💡 提示：导入后自动刷新数仓和告警，无需手动操作。定时任务每天 13:00 也会自动同步企微文件。")

# ==================== 申诉数据 ====================
with tab_import[1]:
    st.markdown("### 上传申诉 CSV")
    st.caption("支持 `.csv` 格式（UTF-8 / GBK 编码），可拖拽多个文件批量上传。")

    appeal_files = st.file_uploader(
        "选择申诉文件（支持拖拽多选）",
        type=["csv"],
        accept_multiple_files=True,
        key="appeal_upload",
    )

    if appeal_files:
        st.info(f"📋 已选择 {len(appeal_files)} 个文件：")
        
        for f in appeal_files:
            with st.expander(f"📄 {f.name} ({f.size / 1024:.1f} KB)", expanded=False):
                preview = preview_file_rows(f, "appeal")
                if preview["error"]:
                    st.error(f"读取失败：{preview['error']}")
                else:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("文件行数", f"{preview['rows']:,}")
                    col2.metric("列数", preview["columns"])
                    col3.metric("文件大小", f"{f.size / 1024:.1f} KB")
                    
                    # 检查是否已上传过（使用分块哈希避免大文件内存溢出）
                    file_hash = compute_file_hash_chunked(f)
                    existing = check_file_exists(file_hash)
                    if existing:
                        st.warning(
                            f"⚠️ 该文件已于 {existing['first_upload_time']} 上传过 "
                            f"（已上传 {existing['upload_count']} 次），导入时将自动跳过。"
                        )
                    
                    if preview["preview_df"] is not None and not preview["preview_df"].empty:
                        st.markdown("**数据预览（前5行）：**")
                        st.dataframe(preview["preview_df"].head(), use_container_width=True)

    if st.button("批量导入申诉数据", key="import_appeal", disabled=(not appeal_files)):
        success_count = 0
        fail_count = 0
        skip_count = 0
        logs = []

        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, appeal_file in enumerate(appeal_files):
            status_text.text(f"正在导入 {appeal_file.name}...")
            progress_bar.progress((idx + 1) / len(appeal_files) / 2)

            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(appeal_file.getvalue())
                tmp_path = tmp.name

            try:
                result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "jobs/import_fact_data.py"), "--appeal-file", tmp_path, "--source-name", appeal_file.name],
                    capture_output=True,
                    text=True,
                    cwd=str(PROJECT_ROOT),
                )
                if result.returncode == 0:
                    import json
                    try:
                        output = json.loads(result.stdout)
                        inserted = output.get("appeal_files", [{}])[0].get("inserted_rows", 0)
                        if inserted == 0:
                            skip_count += 1
                            logs.append(f"⏭️ {appeal_file.name} 已跳过（文件内容已存在）")
                        else:
                            success_count += 1
                            logs.append(f"✅ {appeal_file.name} 导入成功（{inserted} 行）")
                    except Exception:
                        success_count += 1
                        logs.append(f"✅ {appeal_file.name} 导入成功")
                else:
                    fail_count += 1
                    logs.append(f"❌ {appeal_file.name} 导入失败：{result.stderr[:200]}")
            finally:
                Path(tmp_path).unlink(missing_ok=True)

        # 导入完成后自动刷新数仓+告警
        if success_count > 0:
            status_text.text("正在刷新数仓和告警...")
            progress_bar.progress(0.75)
            try:
                refresh_result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "jobs/refresh_warehouse.py")],
                    capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                )
                if refresh_result.returncode == 0:
                    logs.append("🔄 数仓刷新成功")
                else:
                    logs.append(f"⚠️ 数仓刷新失败：{refresh_result.stderr[:200]}")
            except Exception as e:
                logs.append(f"⚠️ 数仓刷新异常：{e}")

            try:
                alert_result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "jobs/refresh_alerts.py")],
                    capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                )
                if alert_result.returncode == 0:
                    logs.append("🔔 告警刷新成功")
                else:
                    logs.append(f"⚠️ 告警刷新失败：{alert_result.stderr[:200]}")
            except Exception as e:
                logs.append(f"⚠️ 告警刷新异常：{e}")

        progress_bar.progress(1.0)
        progress_bar.empty()
        status_text.empty()

        if success_count > 0:
            st.success(f"成功导入 {success_count} 个文件，已自动刷新数仓和告警" + (f"，{skip_count} 个跳过" if skip_count > 0 else "") + (f"，{fail_count} 个失败" if fail_count > 0 else ""))
            log_action("upload", "fact_appeal_event", f"申诉CSV导入 {success_count}个文件")
        elif skip_count > 0:
            st.warning(f"所有文件均已上传过，跳过 {skip_count} 个文件")
        else:
            st.error("所有文件导入失败")

        with st.expander("查看导入日志", expanded=(fail_count > 0)):
            st.code("\n".join(logs), language="text")

    st.markdown("---")
    st.caption("💡 提示：申诉数据也可以通过「Google Sheet」标签页直接拉取，无需手动上传。导入后自动刷新数仓和告警。")

# ==================== Google Sheet ====================
with tab_import[2]:
    st.markdown("### 从 Google Sheet 拉取申诉数据")
    st.caption("直接从配置好的 Google Sheet 拉取最新申诉数据，无需手动下载。")

    if st.button("拉取 Google Sheet", key="pull_gsheet"):
        with st.spinner("正在拉取 Google Sheet..."):
            result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "jobs/pull_google_sheet.py")],
                    capture_output=True,
                    text=True,
                    cwd=str(PROJECT_ROOT),
            )
            if result.returncode == 0:
                st.success("Google Sheet 拉取成功！")
                with st.expander("查看拉取日志", expanded=False):
                    st.code(result.stdout, language="text")
            else:
                st.error(f"拉取失败：\n{result.stderr}")

    st.markdown("---")
    st.caption("💡 提示：拉取后的数据会自动导入到 `fact_appeal_event` 表。")

# ==================== 新人质检数据 ====================
with tab_import[3]:
    st.markdown("### 👶 新人质检数据上传")
    st.caption("上传新人内检/外检质检 Excel 文件。文件名含 `10816` 识别为外检，含 `新人` 识别为内检。")

    nc_qa_files = st.file_uploader(
        "选择新人质检 Excel 文件（支持多文件）",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="nc_qa_uploader",
    )

    if nc_qa_files:
        for f in nc_qa_files:
            st.write(f"📄 **{f.name}** ({f.size / 1024:.1f} KB)")

        nc_stage_override = st.selectbox(
            "阶段覆盖（可选，默认自动识别）",
            options=["自动识别", "internal（内检）", "external（外检）"],
            key="nc_stage_override",
        )

        if st.button("📥 导入新人质检数据", key="import_nc_qa"):
            import subprocess, tempfile, sys as _sys
            total_imported = 0
            for f in nc_qa_files:
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                    tmp.write(f.getvalue())
                    tmp_path = tmp.name

                cmd = [
                    _sys.executable, str(PROJECT_ROOT / "jobs" / "import_newcomer_qa.py"),
                    "--file", tmp_path,
                    "--source-name", f.name,
                ]
                if nc_stage_override == "internal（内检）":
                    cmd.extend(["--stage", "internal"])
                elif nc_stage_override == "external（外检）":
                    cmd.extend(["--stage", "external"])

                with st.spinner(f"正在导入 {f.name}..."):
                    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))

                if result.returncode == 0:
                    st.success(f"✅ {f.name} 导入成功")
                    if result.stdout:
                        st.code(result.stdout, language="text")
                    total_imported += 1
                else:
                    st.error(f"❌ {f.name} 导入失败")
                    if result.stderr:
                        st.code(result.stderr, language="text")

                # 清理临时文件
                import os
                os.unlink(tmp_path)

            if total_imported > 0:
                st.cache_data.clear()
                st.info(f"共成功导入 {total_imported} 个文件，缓存已清除。")

    # 显示当前新人质检数据量
    st.markdown("---")
    try:
        nc_cnt = repo.fetch_one("SELECT COUNT(*) AS cnt FROM fact_newcomer_qa")
        st.info(f"📊 当前新人质检数据量：**{nc_cnt['cnt']:,}** 条")

        if nc_cnt["cnt"] > 0:
            # 显示按阶段分布
            stage_dist = repo.fetch_df("SELECT stage, COUNT(*) AS cnt FROM fact_newcomer_qa GROUP BY stage ORDER BY cnt DESC")
            if stage_dist is not None and not stage_dist.empty:
                st.caption("按阶段分布：" + " · ".join([f"{r['stage']}: {r['cnt']:,}" for _, r in stage_dist.iterrows()]))

            # 清空新人质检数据按钮
            st.markdown("---")
            if st.checkbox("⚠️ 我要清空新人质检数据", key="nc_qa_clear_confirm"):
                if st.button("🗑️ 清空 fact_newcomer_qa", key="nc_qa_clear"):
                    repo.execute("TRUNCATE TABLE fact_newcomer_qa")
                    st.success("新人质检数据已清空！")
                    st.cache_data.clear()
    except Exception as e:
        st.warning(f"查询新人数据失败：{e}")

# ==================== 新人批次管理 ====================
with tab_import[4]:
    st.markdown("### 📋 新人批次 / 姓名管理")
    st.caption("管理新人名单（dim_newcomer_batch）。支持上传 Excel/CSV 批量导入新人名单，也可以手动添加。")

    nc_mgmt_tab = st.radio("操作方式", ["📥 批量上传", "✏️ 手动添加", "📊 当前名单", "🗑️ 清空名单"], horizontal=True, key="nc_mgmt_mode")

    if nc_mgmt_tab == "📥 批量上传":
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

        nc_import_mode = st.radio("导入模式", ["追加（保留已有数据）", "覆盖（先清空再导入）"], horizontal=True, key="nc_import_mode")

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
                    # 自动补全
                    if "reviewer_alias" not in batch_df.columns:
                        batch_df["reviewer_alias"] = batch_df["reviewer_name"].apply(
                            lambda x: f"云雀联营-{x}" if x and not str(x).startswith("云雀联营-") else x
                        )
                    if "join_date" not in batch_df.columns:
                        batch_df["join_date"] = str(date.today())
                    if "team_name" not in batch_df.columns:
                        # 尝试从 batch_name 推断
                        batch_df["team_name"] = batch_df["batch_name"].apply(
                            lambda x: "黑虎泉" if "黑虎泉" in str(x) else ("青龙河" if "青龙河" in str(x) else ("白龙湖" if "白龙湖" in str(x) else "未分组"))
                        )

                    # 填充可选字段
                    for col in ["team_leader", "delivery_pm", "mentor_name", "owner"]:
                        if col not in batch_df.columns:
                            batch_df[col] = ""

                    # 覆盖模式：先清空
                    if nc_import_mode == "覆盖（先清空再导入）":
                        repo.execute("TRUNCATE TABLE dim_newcomer_batch")
                        st.warning("已清空旧数据")

                    # 逐行插入（使用 INSERT IGNORE 避免唯一键冲突）
                    inserted = 0
                    skipped = 0
                    seen_keys = set()  # 内存去重，避免CSV中重复行
                    for _, row in batch_df.iterrows():
                        name = str(row["reviewer_name"]).strip()
                        batch = str(row["batch_name"]).strip()
                        if not name or not batch or name == "nan" or batch == "nan":
                            skipped += 1
                            continue

                        # CSV 内部去重
                        dedup_key = (batch, name)
                        if dedup_key in seen_keys:
                            skipped += 1
                            continue
                        seen_keys.add(dedup_key)

                        # 非覆盖模式下检查数据库是否已存在
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
                            batch,
                            name,
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

            except Exception as e:
                st.error(f"导入失败：{e}")

    elif nc_mgmt_tab == "✏️ 手动添加":
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
                    team = new_team or ("黑虎泉" if "黑虎泉" in new_batch else ("青龙河" if "青龙河" in new_batch else ("白龙湖" if "白龙湖" in new_batch else "未分组")))
                    # 检查重复
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

    elif nc_mgmt_tab == "📊 当前名单":
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

                # 按批次筛选
                batch_filter = st.multiselect("筛选批次", options=sorted(all_members["batch_name"].unique().tolist()), key="nc_batch_filter")
                if batch_filter:
                    all_members = all_members[all_members["batch_name"].isin(batch_filter)]

                st.dataframe(all_members, use_container_width=True, height=400)

                # 导出 CSV
                csv_data = all_members.to_csv(index=False).encode("utf-8-sig")
                st.download_button("📥 导出 CSV", data=csv_data, file_name=f"newcomer_list_{date.today():%Y%m%d}.csv", mime="text/csv")
            else:
                st.info("暂无新人名单数据")
        except Exception as e:
            st.error(f"查询失败：{e}")

    elif nc_mgmt_tab == "🗑️ 清空名单":
        st.markdown("#### ⚠️ 清空新人名单")
        st.error("此操作将删除 dim_newcomer_batch 中的所有数据，不可逆！")
        try:
            cnt = repo.fetch_one("SELECT COUNT(*) AS cnt FROM dim_newcomer_batch")
            st.info(f"当前共 {cnt['cnt']} 条新人名单记录")
        except Exception:
            pass

        if st.checkbox("我确认要清空所有新人名单", key="nc_batch_clear_confirm"):
            confirm_text = st.text_input("请输入 DELETE 确认", key="nc_batch_clear_text", placeholder="输入 DELETE")
            if st.button("🗑️ 清空名单", key="nc_batch_clear", disabled=(confirm_text != "DELETE")):
                repo.execute("TRUNCATE TABLE dim_newcomer_batch")
                st.success("新人名单已清空！")
                st.cache_data.clear()

# ==================== 新人状态管理 ====================
with tab_import[5]:
    st.markdown("### 🔄 新人状态管理")
    st.caption("查看并管理新人的培训阶段状态。系统根据质检数据自动推断当前阶段，你可以一键确认晋级或手动调整。")

    from services.newcomer_lifecycle import (
        ensure_lifecycle_schema,
        batch_infer_stages,
        generate_promotion_recommendations,
        update_member_status,
        load_graduation_rules,
        load_milestones,
        get_status_label,
        STATUS_LABELS,
        DEFAULT_RULES,
    )

    # 确保表结构
    try:
        ensure_lifecycle_schema(repo)
    except Exception as e:
        st.error(f"初始化生命周期表失败：{e}")

    status_tab = st.radio(
        "功能选择",
        ["📊 状态总览", "🎯 晋级推荐", "⚙️ 毕业条件配置", "📜 里程碑记录"],
        horizontal=True, key="status_mgmt_mode",
    )

    if status_tab == "📊 状态总览":
        st.markdown("#### 状态同步")
        st.info("系统会根据已有质检数据推断每位新人的实际阶段。点击「同步」可自动将状态推进到正确的阶段。")

        if st.button("🔄 扫描并同步状态", key="sync_status", type="primary"):
            with st.spinner("正在分析所有新人的质检数据..."):
                try:
                    from services.newcomer_lifecycle import batch_sync_inferred_status
                    result = batch_sync_inferred_status(repo, operator="admin")
                    st.success(f"✅ 同步完成！更新 {result['updated']} 人，跳过 {result['skipped']} 人")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"同步失败：{e}")

        st.markdown("---")
        st.markdown("#### 当前状态分布")
        try:
            status_dist = repo.fetch_df("""
                SELECT status, COUNT(*) AS cnt
                FROM dim_newcomer_batch
                GROUP BY status ORDER BY cnt DESC
            """)
            if status_dist is not None and not status_dist.empty:
                cols = st.columns(min(len(status_dist), 6))
                for i, (_, row) in enumerate(status_dist.iterrows()):
                    label, color, bg = get_status_label(row["status"])
                    with cols[i % len(cols)]:
                        st.markdown(f"""
                        <div style="background:{bg}; border:1px solid {color}; border-radius:0.75rem; padding:0.75rem; text-align:center;">
                            <div style="font-size:0.75rem; color:{color};">{label}</div>
                            <div style="font-size:1.5rem; font-weight:700; color:{color};">{int(row['cnt'])}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("暂无新人数据")
        except Exception as e:
            st.warning(f"查询失败：{e}")

        st.markdown("---")
        st.markdown("#### 详细状态列表")
        try:
            inferred_df = batch_infer_stages(repo)
            if not inferred_df.empty:
                display_df = inferred_df.copy()
                display_df["当前状态"] = display_df["current_status"].apply(lambda s: get_status_label(s)[0])
                display_df["推断状态"] = display_df["inferred_status"].apply(lambda s: get_status_label(s)[0])
                display_df["需更新"] = display_df["needs_update"].apply(lambda x: "⚠️ 是" if x else "✅ 一致")
                st.dataframe(
                    display_df[["batch_name", "reviewer_name", "当前状态", "推断状态", "需更新"]].rename(
                        columns={"batch_name": "批次", "reviewer_name": "姓名"}
                    ),
                    use_container_width=True, hide_index=True, height=400,
                )
                needs_update_cnt = int(display_df["needs_update"].sum())
                if needs_update_cnt > 0:
                    st.warning(f"有 {needs_update_cnt} 人的状态与实际阶段不一致，建议点击上方「同步」按钮更新。")
            else:
                st.info("暂无需要状态管理的新人")
        except Exception as e:
            st.warning(f"推断状态失败：{e}")

        st.markdown("---")
        st.markdown("#### 手动调整状态")
        try:
            all_members = repo.fetch_df("""
                SELECT reviewer_name, batch_name, status
                FROM dim_newcomer_batch ORDER BY batch_name, reviewer_name
            """)
            if all_members is not None and not all_members.empty:
                member_options = [f"{r['reviewer_name']} ({r['batch_name']})" for _, r in all_members.iterrows()]
                selected_member = st.selectbox("选择人员", member_options, key="manual_status_member")
                if selected_member:
                    m_name = selected_member.split(" (")[0]
                    m_batch = selected_member.split("(")[1].rstrip(")")
                    m_current = all_members[(all_members["reviewer_name"] == m_name) & (all_members["batch_name"] == m_batch)].iloc[0]["status"]
                    st.caption(f"当前状态：{get_status_label(m_current)[0]}")

                    new_status = st.selectbox(
                        "新状态",
                        ["pending", "internal_training", "external_training", "formal_probation", "graduated", "exited"],
                        format_func=lambda s: get_status_label(s)[0],
                        key="manual_new_status",
                    )
                    manual_note = st.text_input("备注（可选）", key="manual_status_note", placeholder="如：提前毕业、转岗等")

                    if st.button("✅ 确认变更", key="apply_manual_status"):
                        if new_status == m_current:
                            st.warning("新状态与当前状态相同，无需变更")
                        else:
                            success = update_member_status(
                                repo, m_name, m_batch, new_status,
                                trigger_type="manual", operator="admin", note=manual_note or None,
                            )
                            if success:
                                st.success(f"✅ {m_name} 状态已更新为 {get_status_label(new_status)[0]}")
                                st.cache_data.clear()
                            else:
                                st.error("状态更新失败")
        except Exception as e:
            st.warning(f"加载人员列表失败：{e}")

    elif status_tab == "🎯 晋级推荐":
        st.markdown("#### 系统推荐晋级名单")
        st.info("系统根据每位新人的连续达标天数和累计质检量，自动检查是否满足晋级条件。")

        if st.button("🔍 扫描晋级条件", key="scan_promotion", type="primary"):
            with st.spinner("正在检查所有在训新人的晋级条件..."):
                try:
                    recommendations = generate_promotion_recommendations(repo)
                    st.session_state["promotion_recommendations"] = recommendations
                except Exception as e:
                    st.error(f"扫描失败：{e}")

        recommendations = st.session_state.get("promotion_recommendations", pd.DataFrame())
        if not isinstance(recommendations, pd.DataFrame) or recommendations.empty:
            st.info("暂无晋级推荐，请先点击「扫描晋级条件」按钮。")
        else:
            st.success(f"🎯 发现 {len(recommendations)} 位新人满足晋级条件！")

            for idx, rec in recommendations.iterrows():
                from_label = get_status_label(rec["current_status_mapped"])[0]
                to_label = get_status_label(rec["recommended_status"])[0]

                with st.container():
                    col_info, col_action = st.columns([3, 1])
                    with col_info:
                        st.markdown(f"""
                        **{rec['reviewer_name']}** · {rec['batch_name']} · {rec.get('team_name', '')}
                        <br><span style="font-size:0.85rem; color:#475569;">
                        {from_label} → {to_label} · {rec['evidence_summary']}
                        </span>
                        """, unsafe_allow_html=True)
                    with col_action:
                        if st.button(f"✅ 确认", key=f"promote_{idx}"):
                            success = update_member_status(
                                repo,
                                reviewer_name=rec["reviewer_name"],
                                batch_name=rec["batch_name"],
                                new_status=rec["recommended_status"],
                                trigger_type="auto",
                                rule_code=rec["rule_code"],
                                evidence=rec.get("evidence_json"),
                                operator="admin",
                                note=f"通过晋级推荐确认: {rec['rule_name']}",
                            )
                            if success:
                                st.success(f"✅ {rec['reviewer_name']} 已晋级为 {to_label}")
                                st.cache_data.clear()
                                st.rerun()
                    st.divider()

    elif status_tab == "⚙️ 毕业条件配置":
        st.markdown("#### 晋级/毕业条件规则")
        st.caption("配置每个阶段的晋级条件。规则修改后，下次扫描推荐时生效。")

        try:
            rules_df = repo.fetch_df("""
                SELECT rule_code, rule_name, from_status, to_status, metric,
                       compare_op, threshold, consecutive_days, min_qa_cnt, enabled, description
                FROM dim_graduation_rule ORDER BY from_status
            """)
            if rules_df is not None and not rules_df.empty:
                for _, rule in rules_df.iterrows():
                    from_label = get_status_label(rule["from_status"])[0]
                    to_label = get_status_label(rule["to_status"])[0]
                    status_icon = "🟢" if rule["enabled"] else "⚪"
                    with st.expander(f"{status_icon} {rule['rule_name']} ({from_label} → {to_label})", expanded=False):
                        st.caption(rule["description"] or "")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            new_threshold = st.number_input(
                                "阈值 (%)", value=float(rule["threshold"]),
                                min_value=0.0, max_value=100.0, step=0.5,
                                key=f"rule_threshold_{rule['rule_code']}",
                            )
                        with col2:
                            new_days = st.number_input(
                                "连续天数", value=int(rule["consecutive_days"]),
                                min_value=1, max_value=30, step=1,
                                key=f"rule_days_{rule['rule_code']}",
                            )
                        with col3:
                            new_min_qa = st.number_input(
                                "最低质检量", value=int(rule["min_qa_cnt"]),
                                min_value=1, max_value=500, step=10,
                                key=f"rule_qa_{rule['rule_code']}",
                            )
                        new_enabled = st.checkbox("启用", value=bool(rule["enabled"]), key=f"rule_enabled_{rule['rule_code']}")

                        if st.button("💾 保存", key=f"save_rule_{rule['rule_code']}"):
                            repo.execute("""
                                UPDATE dim_graduation_rule
                                SET threshold = %s, consecutive_days = %s, min_qa_cnt = %s, enabled = %s
                                WHERE rule_code = %s
                            """, [new_threshold, new_days, new_min_qa, 1 if new_enabled else 0, rule["rule_code"]])
                            st.success(f"✅ 规则 {rule['rule_name']} 已更新")
                            log_action("modify", "dim_graduation_rule", f"更新规则 {rule['rule_code']}: threshold={new_threshold}, days={new_days}, min_qa={new_min_qa}")
            else:
                st.info("暂无毕业条件规则，系统将自动初始化默认规则。")
        except Exception as e:
            st.warning(f"加载规则失败：{e}")

    elif status_tab == "📜 里程碑记录":
        st.markdown("#### 状态变更历史")
        try:
            milestones = load_milestones(repo, limit=100)
            if milestones is not None and not milestones.empty:
                display_ms = milestones.copy()
                display_ms["变更前"] = display_ms["from_status"].apply(lambda s: get_status_label(s)[0] if s else "—")
                display_ms["变更后"] = display_ms["to_status"].apply(lambda s: get_status_label(s)[0])
                display_ms["触发方式"] = display_ms["trigger_type"].map({
                    "auto": "🤖 自动推荐", "manual": "✋ 手动操作", "system": "⚙️ 系统同步"
                }).fillna("—")
                st.dataframe(
                    display_ms[["created_at", "reviewer_name", "batch_name", "变更前", "变更后", "触发方式", "operator", "note"]].rename(
                        columns={"created_at": "时间", "reviewer_name": "姓名", "batch_name": "批次", "operator": "操作人", "note": "备注"}
                    ),
                    use_container_width=True, hide_index=True, height=500,
                )
            else:
                st.info("暂无状态变更记录")
        except Exception as e:
            st.warning(f"加载里程碑失败：{e}")

# ==================== 一键刷新 ====================
with tab_import[6]:
    st.markdown("### 一键刷新数仓和告警")
    st.caption("重新聚合 mart 表并刷新告警规则。通常在数据异常或手动修改数据后使用。")

    if st.button("执行一键刷新", key="run_refresh"):
        with st.spinner("正在刷新数仓和告警..."):
            logs = []
            all_ok = True

            # 1. 刷新数仓
            try:
                refresh_result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "jobs/refresh_warehouse.py")],
                    capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                    timeout=300,
                )
                if refresh_result.returncode == 0:
                    logs.append("✅ 数仓刷新成功")
                else:
                    logs.append(f"❌ 数仓刷新失败：{refresh_result.stderr[:200]}")
                    all_ok = False
            except Exception as e:
                logs.append(f"❌ 数仓刷新异常：{e}")
                all_ok = False

            # 2. 刷新告警
            try:
                alert_result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "jobs/refresh_alerts.py")],
                    capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT),
                    timeout=120,
                )
                if alert_result.returncode == 0:
                    logs.append("✅ 告警刷新成功")
                else:
                    logs.append(f"❌ 告警刷新失败：{alert_result.stderr[:200]}")
                    all_ok = False
            except Exception as e:
                logs.append(f"❌ 告警刷新异常：{e}")
                all_ok = False

            if all_ok:
                st.success("一键刷新完成！")
            else:
                st.warning("刷新完成，但部分步骤失败")

            with st.expander("查看刷新日志", expanded=(not all_ok)):
                st.code("\n".join(logs), language="text")

    st.markdown("---")
    st.caption("💡 提示：定时任务每天 13:00 自动同步企微文件并刷新，通常不需要手动操作。")

# ==================== 告警规则管理 ====================
with tab_import[7]:
    st.markdown("### 🚨 告警规则管理")
    st.caption("在线查看和编辑告警触发规则。修改后下次刷新告警时生效。")

    try:
        rules_df = repo.fetch_df("""
            SELECT rule_code, rule_name, grain, target_level, metric_name,
                   compare_op, threshold_value, severity, enabled, rule_desc
            FROM dim_alert_rule
            ORDER BY severity, rule_code
        """)

        if rules_df.empty:
            st.info("暂无告警规则，请先运行 schema 初始化。")
        else:
            # 规则概览卡片
            enabled_cnt = int(rules_df["enabled"].sum())
            total_cnt = len(rules_df)
            p0_cnt = len(rules_df[rules_df["severity"] == "P0"])
            p1_cnt = len(rules_df[rules_df["severity"] == "P1"])
            p2_cnt = len(rules_df[rules_df["severity"] == "P2"])

            rc1, rc2, rc3, rc4, rc5 = st.columns(5)
            rc1.metric("总规则数", total_cnt)
            rc2.metric("已启用", enabled_cnt)
            rc3.metric("P0", p0_cnt)
            rc4.metric("P1", p1_cnt)
            rc5.metric("P2", p2_cnt)

            st.markdown("---")

            # 规则列表 - 可编辑
            for idx, rule in rules_df.iterrows():
                rule_code = rule["rule_code"]
                is_on = bool(rule["enabled"])
                sev_icon = {"P0": "🔴", "P1": "🟠", "P2": "🔵"}.get(rule["severity"], "⚪")

                with st.expander(
                    f"{sev_icon} **{rule['rule_name']}** | `{rule_code}` | "
                    f"阈值: {rule['threshold_value']} | {'✅ 启用' if is_on else '⏸️ 停用'}",
                    expanded=False,
                ):
                    col_info, col_edit = st.columns([1, 1])
                    with col_info:
                        st.markdown(f"""
| 属性 | 值 |
|------|------|
| **规则编码** | `{rule_code}` |
| **粒度** | {rule['grain']} |
| **目标层级** | {rule['target_level']} |
| **指标名** | {rule['metric_name']} |
| **比较符** | {rule['compare_op']} |
| **描述** | {rule['rule_desc'] or '—'} |
""")
                    with col_edit:
                        new_threshold = st.number_input(
                            "阈值", value=float(rule["threshold_value"]),
                            step=0.1, key=f"threshold_{rule_code}",
                            help="修改后点击下方按钮保存"
                        )
                        new_severity = st.selectbox(
                            "严重等级", options=["P0", "P1", "P2"],
                            index=["P0", "P1", "P2"].index(rule["severity"]),
                            key=f"severity_{rule_code}"
                        )
                        new_enabled = st.toggle(
                            "启用", value=is_on, key=f"enabled_{rule_code}"
                        )

                        if st.button("💾 保存修改", key=f"save_{rule_code}", use_container_width=True):
                            try:
                                repo.execute(
                                    """UPDATE dim_alert_rule
                                       SET threshold_value = %s, severity = %s, enabled = %s
                                       WHERE rule_code = %s""",
                                    [new_threshold, new_severity, 1 if new_enabled else 0, rule_code],
                                )
                                st.success(f"✅ 规则 `{rule_code}` 已更新")
                                log_action("modify", f"dim_alert_rule/{rule_code}",
                                           f"阈值→{new_threshold}, 等级→{new_severity}, 启用→{new_enabled}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"保存失败: {e}")

            st.markdown("---")
            st.markdown("##### 📝 操作说明")
            st.markdown("""
- **阈值修改**：直接修改数值后点击「保存修改」，下次告警刷新时生效
- **启用/停用**：关闭 toggle 可暂停某条规则，不会删除历史告警
- **等级调整**：修改 P0/P1/P2 影响告警展示优先级和 SLA 时限
- 如需新增规则，请联系管理员在数据库中添加
""")

    except Exception as e:
        st.error(f"加载告警规则失败: {e}")

# ==================== 上传记录 ====================
with tab_import[8]:
    st.markdown("### 📜 上传记录")
    st.caption("查看最近 50 条文件上传记录。")

    history = get_upload_history(limit=50)
    
    if not history:
        st.info("暂无上传记录")
    else:
        # 转换为 DataFrame 展示
        history_df = pd.DataFrame(history)
        history_df["upload_time"] = pd.to_datetime(history_df["upload_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        history_df["file_size"] = history_df["file_size_bytes"].apply(lambda x: f"{x / 1024:.1f} KB" if x else "-")
        
        # 状态颜色标记
        def status_icon(status):
            if status == "success":
                return "✅ 成功"
            elif status == "skipped":
                return "⏭️ 跳过"
            else:
                return "❌ 失败"
        
        history_df["状态"] = history_df["upload_status"].apply(status_icon)
        
        # 显示表格
        display_cols = ["upload_time", "file_name", "file_type", "file_size", "source_rows", "inserted_rows", "business_line", "状态"]
        st.dataframe(
            history_df[display_cols].rename(columns={
                "upload_time": "上传时间",
                "file_name": "文件名",
                "file_type": "类型",
                "file_size": "大小",
                "source_rows": "源行数",
                "inserted_rows": "入库行数",
                "business_line": "业务线",
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # 导出按钮
        csv = history_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 导出上传记录 (CSV)",
            data=csv,
            file_name=f"upload_history_{date.today():%Y%m%d}.csv",
            mime="text/csv"
        )

    # 审计日志
    st.markdown("---")
    st.markdown("### 📋 操作审计日志")
    st.caption("记录数据上传、规则修改、数据清除等关键操作，最近 100 条。")
    try:
        audit_df = repo.fetch_df("""
            SELECT created_at, action, target, detail, operator
            FROM sys_audit_log
            ORDER BY created_at DESC
            LIMIT 100
        """)
        if audit_df.empty:
            st.info("暂无操作记录")
        else:
            audit_df["created_at"] = pd.to_datetime(audit_df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            action_map = {"upload": "📤 上传", "delete": "🗑️ 删除", "modify": "✏️ 修改", "refresh": "🔄 刷新", "clear": "🧹 清除"}
            audit_df["action"] = audit_df["action"].map(action_map).fillna(audit_df["action"])
            st.dataframe(
                audit_df.rename(columns={
                    "created_at": "时间", "action": "操作", "target": "目标",
                    "detail": "详情", "operator": "操作人",
                }),
                use_container_width=True, hide_index=True, height=400,
            )
    except Exception:
        st.info("审计日志表尚未创建，请运行 schema 初始化。")

# ==================== 清除缓存 ====================
with tab_import[9]:
    st.markdown("### 清除 Streamlit 缓存")
    st.caption("如果看板数据展示异常（如组别名称未更新），可以清除缓存后刷新页面。")

    if st.button("清除缓存", key="clear_cache"):
        st.cache_data.clear()
        st.success("缓存已清除！请刷新浏览器页面（F5 或 Cmd+R）查看最新数据。")

    st.markdown("---")
    st.warning("⚠️ 清除缓存不会影响数据库数据，只是清除 Streamlit 的展示缓存。")

# ==================== 清除数据 ====================
with tab_import[10]:
    st.markdown("### 清除质检数据")
    st.caption("根据日期范围删除质检数据，或全部清空。⚠️ 此操作不可逆，请谨慎操作。")

    # 显示当前数据量
    total_cnt = repo.fetch_one("SELECT COUNT(*) AS cnt FROM fact_qa_event")["cnt"]
    st.info(f"📊 当前质检数据总量：**{total_cnt:,}** 条")

    # 显示新人数据量
    try:
        newcomer_cnt = repo.fetch_one("SELECT COUNT(*) AS cnt FROM fact_newcomer_qa")
        newcomer_batch_cnt = repo.fetch_one("SELECT COUNT(*) AS cnt FROM dim_newcomer_batch")
        if newcomer_cnt and newcomer_batch_cnt:
            st.caption(f"📋 新人相关数据：fact_newcomer_qa {newcomer_cnt['cnt']:,} 条 · dim_newcomer_batch {newcomer_batch_cnt['cnt']:,} 条（清除操作不影响新人数据）")
    except Exception:
        pass

    # 清除方式选择
    clear_mode = st.radio("清除方式", ["按日期范围清除", "全部清除"], horizontal=True, key="clear_mode")

    if clear_mode == "按日期范围清除":
        col1, col2 = st.columns(2)
        with col1:
            date_start = st.date_input("开始日期", value=date.today(), key="clear_start")
        with col2:
            date_end = st.date_input("结束日期", value=date.today(), key="clear_end")

        if date_start > date_end:
            st.error("开始日期不能晚于结束日期")
        else:
            # 预览要删除的数据
            preview_cnt = repo.fetch_one(
                "SELECT COUNT(*) AS cnt FROM fact_qa_event WHERE biz_date >= %s AND biz_date <= %s",
                [date_start, date_end]
            )["cnt"]

            st.warning(f"将删除 **{date_start}** 至 **{date_end}** 的质检数据，共 **{preview_cnt:,}** 条")

            confirm = st.checkbox(f"我确认要删除这 {preview_cnt:,} 条数据", key="confirm_range")
            
            # 二次确认：输入确认文字
            confirm_text = ""
            if confirm and preview_cnt > 0:
                st.error("🔒 **安全验证**：请在下方输入 `DELETE` 来确认删除操作")
                confirm_text = st.text_input("请输入 DELETE 确认删除", key="confirm_range_text", placeholder="输入 DELETE")

            if st.button("删除选中日期的数据", key="delete_range", disabled=(not confirm or preview_cnt == 0 or confirm_text != "DELETE")):
                with st.spinner("正在删除数据..."):
                    # 删除 fact 表数据
                    repo.execute(
                        "DELETE FROM fact_qa_event WHERE biz_date >= %s AND biz_date <= %s",
                        [date_start, date_end]
                    )
                    
                    # 清除日维度 mart 表
                    repo.execute("DELETE FROM mart_day_group WHERE biz_date >= %s AND biz_date <= %s", [date_start, date_end])
                    repo.execute("DELETE FROM mart_day_queue WHERE biz_date >= %s AND biz_date <= %s", [date_start, date_end])
                    repo.execute("DELETE FROM mart_day_auditor WHERE biz_date >= %s AND biz_date <= %s", [date_start, date_end])
                    repo.execute("DELETE FROM mart_day_error_topic WHERE biz_date >= %s AND biz_date <= %s", [date_start, date_end])
                    
                    # 清除周维度 mart 表（week_begin_date 对应周一，需扩展范围）
                    week_start = date_start - timedelta(days=date_start.weekday())
                    week_end = date_end - timedelta(days=date_end.weekday()) + timedelta(days=6)
                    repo.execute("DELETE FROM mart_week_group WHERE week_begin_date >= %s AND week_begin_date <= %s", [week_start, week_end])
                    repo.execute("DELETE FROM mart_week_queue WHERE week_begin_date >= %s AND week_begin_date <= %s", [week_start, week_end])
                    repo.execute("DELETE FROM mart_week_error_topic WHERE week_begin_date >= %s AND week_begin_date <= %s", [week_start, week_end])
                    
                    # 清除月维度 mart 表（month_begin_date 对应每月 1 号）
                    month_start = date_start.replace(day=1)
                    month_end = (date_end.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    month_end_begin = month_end.replace(day=1)
                    repo.execute("DELETE FROM mart_month_group WHERE month_begin_date >= %s AND month_begin_date <= %s", [month_start, month_end_begin])
                    repo.execute("DELETE FROM mart_month_queue WHERE month_begin_date >= %s AND month_begin_date <= %s", [month_start, month_end_begin])
                    repo.execute("DELETE FROM mart_month_error_topic WHERE month_begin_date >= %s AND month_begin_date <= %s", [month_start, month_end_begin])
                    
                    # 清空告警，等待刷新
                    repo.execute("DELETE FROM fact_alert_event WHERE 1=1")
                    
                    # 清空文件去重记录和上传日志（按日期范围清除时也全部清空，允许重新上传）
                    repo.execute("DELETE FROM fact_file_dedup")
                    repo.execute("DELETE FROM fact_upload_log")

                    st.success(f"已删除 {preview_cnt:,} 条数据！请点击「一键刷新」重新生成数仓和告警。")
                    log_action("delete", "fact_qa_event", f"按日期删除 {preview_cnt}条, 范围: {date_start}~{date_end}")
                    st.cache_data.clear()

    else:  # 全部清除
        st.error(f"⚠️ 警告：将删除全部 **{total_cnt:,}** 条质检数据，此操作不可逆！")

        confirm_all = st.checkbox(f"我确认要删除全部 {total_cnt:,} 条数据", key="confirm_all")

        # 二次确认：输入确认文字
        confirm_all_text = ""
        if confirm_all and total_cnt > 0:
            st.error("🔒 **安全验证**：请在下方输入 `DELETE ALL` 来确认清空操作")
            confirm_all_text = st.text_input("请输入 DELETE ALL 确认清空", key="confirm_all_text", placeholder="输入 DELETE ALL")

        if st.button("全部清空", key="delete_all", disabled=(not confirm_all or total_cnt == 0 or confirm_all_text != "DELETE ALL")):
            with st.spinner("正在清空数据..."):
                # 清空所有相关表（使用事务确保原子性）
                tables = [
                    "fact_qa_event",
                    "fact_appeal_event",
                    "mart_day_group",
                    "mart_day_queue",
                    "mart_day_auditor",
                    "mart_week_group",
                    "mart_week_queue",
                    "mart_month_group",
                    "mart_month_queue",
                    "mart_day_error_topic",
                    "mart_week_error_topic",
                    "mart_month_error_topic",
                    "fact_alert_event",
                    "fact_alert_status",
                    "fact_alert_status_history",
                    "fact_file_dedup",
                    "fact_upload_log",
                ]
                sql_list = [(f"DELETE FROM {tbl}", None) for tbl in tables]
                
                try:
                    repo.execute_in_transaction(sql_list)
                    st.success("数据已全部清空！请重新上传数据并刷新。")
                    log_action("delete", "ALL_TABLES", f"全部清空 {total_cnt}条质检数据")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"清空数据失败：{str(e)}")

    st.markdown("---")
    st.caption("💡 提示：清除数据后，需要重新执行「一键刷新」来重建数仓和告警。")

    # ==================== 数据健康检查 ====================
    st.markdown("---")
    st.markdown("### 🩺 数据健康检查")
    st.caption("自动检测常见的数据质量问题，帮助定位异常")
    render_health_check()