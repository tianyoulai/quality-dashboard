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

# 设计系统 v3.0
from utils.design_system import ds
from utils.error_boundary import safe_section, run_safe
ds.inject_theme()

# 权限控制（可通过 config/settings.json 启用）
from utils.auth import require_role, render_admin_badge
render_admin_badge()
require_role("admin")

# Hero 区域（设计系统组件）
ds.hero("⚙️", "数据管理", "导入 · 刷新 · 维护", badges=["质检Excel", "申诉CSV", "新人批次", "告警规则"])

# ---- 数据新鲜度面板 ----
with st.expander("📊 数据新鲜度概览", expanded=False):
    try:
        render_freshness_panel()
    except Exception as _fp_err:
        st.warning(f"⚠️ 数据新鲜度加载失败：`{_fp_err}`")

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
            total_files = len(nc_qa_files)
            progress_bar = st.progress(0, text="准备导入...")
            status_area = st.empty()

            for idx, f in enumerate(nc_qa_files):
                progress_bar.progress((idx) / total_files, text=f"正在导入 ({idx+1}/{total_files}): {f.name}")

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

                result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))

                if result.returncode == 0:
                    status_area.success(f"✅ ({idx+1}/{total_files}) {f.name} 导入成功")
                    if result.stdout:
                        st.code(result.stdout, language="text")
                    total_imported += 1
                else:
                    status_area.error(f"❌ ({idx+1}/{total_files}) {f.name} 导入失败")
                    if result.stderr:
                        st.code(result.stderr, language="text")

                # 清理临时文件
                import os
                os.unlink(tmp_path)

                progress_bar.progress((idx + 1) / total_files, text=f"已完成 {idx+1}/{total_files}")

            progress_bar.progress(1.0, text="全部完成 ✅")

            if total_imported > 0:
                st.cache_data.clear()
                st.info(f"共成功导入 {total_imported}/{total_files} 个文件，缓存已清除。")

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
    from views.data_mgmt.newcomer_batch import render_newcomer_batch_tab
    render_newcomer_batch_tab()

# ==================== 新人状态管理 ====================
with tab_import[5]:
    from views.data_mgmt.newcomer_status import render_newcomer_status_tab
    render_newcomer_status_tab()

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