"""新人生命周期管理服务。

职责：
  1. 自动推断每位新人当前所处阶段（基于质检数据）
  2. 检查是否满足晋级/毕业条件（基于可配置规则）
  3. 生成晋级推荐列表
  4. 执行状态变更 + 写入里程碑记录
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from storage.repository import DashboardRepository


# ═══════════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════════

# 完整的新人状态流
# 实际业务: 内检 → 外检 → 正式队列(=毕业)
# formal_probation 保留用于自动推断（检测到正式队列数据时标记）
STATUS_FLOW = [
    "pending",              # 待开始：已录入名单但无任何质检数据
    "internal_training",    # 内检培训中：已有内检质检数据
    "external_training",    # 外检培训中：已有外检质检数据
    "formal_probation",     # 已进入正式队列（自动推断用）
    "graduated",            # 已毕业：正式上线
    "exited",               # 已退出：离职/淘汰
]

STATUS_LABELS = {
    "pending":           ("⏳ 待开始",    "#94a3b8", "#f8fafc"),
    "internal_training": ("🏫 内检培训中", "#8b5cf6", "#f5f3ff"),
    "external_training": ("🔍 外检培训中", "#3b82f6", "#eff6ff"),
    "formal_probation":  ("✅ 正式队列",  "#f59e0b", "#fffbeb"),
    "graduated":         ("🎓 已毕业",    "#10b981", "#ecfdf5"),
    "exited":            ("🚪 已退出",    "#6b7280", "#f9fafb"),
    # 兼容旧 status
    "training":          ("📚 培训中",    "#8b5cf6", "#f5f3ff"),
}

# 默认晋级条件
# 正式上线 = 进入正式队列 = 毕业（新人培训结束）
DEFAULT_RULES = [
    {
        "rule_code": "INTERNAL_TO_EXTERNAL",
        "rule_name": "内检 → 外检",
        "from_status": "internal_training",
        "to_status": "external_training",
        "metric": "accuracy_rate",
        "compare_op": ">=",
        "threshold": 90.0,
        "consecutive_days": 3,
        "min_qa_cnt": 30,
        "description": "连续3天内检正确率≥90%且累计质检量≥30，建议进入外检",
    },
    {
        "rule_code": "EXTERNAL_TO_FORMAL",
        "rule_name": "外检 → 正式上线",
        "from_status": "external_training",
        "to_status": "graduated",
        "metric": "accuracy_rate",
        "compare_op": ">=",
        "threshold": 98.0,
        "consecutive_days": 3,
        "min_qa_cnt": 50,
        "description": "连续3天外检正确率≥98%且累计质检量≥50，建议正式上线（毕业）",
    },
]


# ═══════════════════════════════════════════════════════════════
#  Schema 保障
# ═══════════════════════════════════════════════════════════════

def ensure_lifecycle_schema(repo: DashboardRepository) -> None:
    """确保新人生命周期相关表存在。"""
    # 里程碑记录表
    repo.execute("""
        CREATE TABLE IF NOT EXISTS fact_newcomer_milestone (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            reviewer_name VARCHAR(128) NOT NULL COMMENT '审核人姓名',
            batch_name VARCHAR(128) COMMENT '所属批次',
            from_status VARCHAR(32) COMMENT '变更前状态',
            to_status VARCHAR(32) NOT NULL COMMENT '变更后状态',
            rule_code VARCHAR(64) COMMENT '触发规则编码',
            trigger_type VARCHAR(16) NOT NULL DEFAULT 'manual' COMMENT 'auto/manual/system',
            evidence TEXT COMMENT '状态变更依据（JSON）',
            operator VARCHAR(64) DEFAULT 'system' COMMENT '操作人',
            note TEXT COMMENT '备注',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 毕业条件规则表
    repo.execute("""
        CREATE TABLE IF NOT EXISTS dim_graduation_rule (
            rule_code VARCHAR(64) PRIMARY KEY,
            rule_name VARCHAR(256),
            from_status VARCHAR(32) NOT NULL COMMENT '触发状态',
            to_status VARCHAR(32) NOT NULL COMMENT '目标状态',
            metric VARCHAR(64) NOT NULL COMMENT '考核指标: accuracy_rate/misjudge_rate/missjudge_rate',
            compare_op VARCHAR(8) NOT NULL DEFAULT '>=' COMMENT '比较运算符',
            threshold DOUBLE NOT NULL COMMENT '阈值',
            consecutive_days INT NOT NULL DEFAULT 3 COMMENT '需连续达标天数',
            min_qa_cnt INT NOT NULL DEFAULT 30 COMMENT '最低累计质检量',
            enabled TINYINT(1) DEFAULT 1,
            description TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    # 插入默认规则（不覆盖已有的）
    for rule in DEFAULT_RULES:
        repo.execute("""
            INSERT IGNORE INTO dim_graduation_rule
            (rule_code, rule_name, from_status, to_status, metric, compare_op,
             threshold, consecutive_days, min_qa_cnt, enabled, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
        """, [
            rule["rule_code"], rule["rule_name"], rule["from_status"],
            rule["to_status"], rule["metric"], rule["compare_op"],
            rule["threshold"], rule["consecutive_days"], rule["min_qa_cnt"],
            rule["description"],
        ])


# ═══════════════════════════════════════════════════════════════
#  自动推断当前阶段（基于质检数据）
# ═══════════════════════════════════════════════════════════════

def infer_current_stage(repo: DashboardRepository, reviewer_name: str) -> str:
    """根据质检数据推断审核人当前实际所处阶段。

    逻辑（与文件名/队列识别一致）：
    - 有 formal（正式队列）数据 → graduated（进入正式队列=毕业）
    - 有 external 阶段数据 → external_training
    - 有 internal 阶段数据 → internal_training
    - 无任何数据 → pending
    """
    short_name = reviewer_name.replace("云雀联营-", "") if "云雀联营-" in reviewer_name else reviewer_name

    # 检查新人质检表
    newcomer_stages = repo.fetch_df("""
        SELECT DISTINCT stage FROM fact_newcomer_qa
        WHERE reviewer_name = %s OR reviewer_short_name = %s OR reviewer_name = %s
    """, [reviewer_name, short_name, short_name])

    stages = set()
    if newcomer_stages is not None and not newcomer_stages.empty:
        stages.update(newcomer_stages["stage"].tolist())

    # 检查正式质检表
    formal_check = repo.fetch_one("""
        SELECT COUNT(*) AS cnt FROM mart_day_auditor
        WHERE reviewer_name = %s OR reviewer_name = %s
    """, [reviewer_name, short_name])
    if formal_check and formal_check["cnt"] > 0:
        stages.add("formal")

    if "formal" in stages:
        return "graduated"  # 进入正式队列 = 毕业
    if "external" in stages:
        return "external_training"
    if "internal" in stages:
        return "internal_training"
    return "pending"


def batch_infer_stages(repo: DashboardRepository) -> pd.DataFrame:
    """批量推断所有新人的当前阶段。

    Returns:
        DataFrame: columns=[reviewer_name, batch_name, current_status, inferred_status, needs_update]
    """
    members = repo.fetch_df("""
        SELECT reviewer_name, reviewer_alias, batch_name, status
        FROM dim_newcomer_batch
        WHERE status NOT IN ('graduated', 'exited')
    """)
    if members is None or members.empty:
        return pd.DataFrame()

    # 批量查新人质检数据中的阶段
    newcomer_stages = repo.fetch_df("""
        SELECT
            COALESCE(n.reviewer_name, q.reviewer_short_name, q.reviewer_name) AS dim_name,
            n.batch_name,
            GROUP_CONCAT(DISTINCT q.stage) AS stages
        FROM fact_newcomer_qa q
        LEFT JOIN dim_newcomer_batch n
          ON (q.reviewer_name = n.reviewer_alias
              OR q.reviewer_short_name = n.reviewer_name
              OR q.reviewer_name = n.reviewer_name)
        WHERE n.reviewer_name IS NOT NULL
        GROUP BY dim_name, n.batch_name
    """)

    # 批量查正式质检数据
    formal_reviewers = repo.fetch_df("""
        SELECT DISTINCT m.reviewer_name AS formal_name, n.reviewer_name AS dim_name, n.batch_name
        FROM mart_day_auditor m
        JOIN dim_newcomer_batch n
          ON (m.reviewer_name = n.reviewer_alias OR m.reviewer_name = n.reviewer_name)
    """)

    # 合并推断
    results = []
    for _, row in members.iterrows():
        name = row["reviewer_name"]
        batch = row["batch_name"]
        current = row["status"]

        stages = set()
        # 从新人质检数据
        if newcomer_stages is not None and not newcomer_stages.empty:
            match = newcomer_stages[
                (newcomer_stages["dim_name"] == name) &
                (newcomer_stages["batch_name"] == batch)
            ]
            if not match.empty:
                stage_str = match.iloc[0]["stages"]
                if stage_str:
                    stages.update(stage_str.split(","))

        # 从正式质检数据
        if formal_reviewers is not None and not formal_reviewers.empty:
            formal_match = formal_reviewers[
                (formal_reviewers["dim_name"] == name) &
                (formal_reviewers["batch_name"] == batch)
            ]
            if not formal_match.empty:
                stages.add("formal")

        if "formal" in stages:
            inferred = "graduated"  # 进入正式队列 = 毕业
        elif "external" in stages:
            inferred = "external_training"
        elif "internal" in stages:
            inferred = "internal_training"
        else:
            inferred = "pending"

        # 兼容旧 status
        mapped_current = current
        if current == "training":
            mapped_current = "internal_training"  # 旧值默认映射

        needs_update = mapped_current != inferred
        results.append({
            "reviewer_name": name,
            "batch_name": batch,
            "current_status": current,
            "inferred_status": inferred,
            "needs_update": needs_update,
        })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════
#  晋级条件检查
# ═══════════════════════════════════════════════════════════════

def load_graduation_rules(repo: DashboardRepository) -> list[dict]:
    """加载所有启用的毕业条件规则。"""
    df = repo.fetch_df("""
        SELECT rule_code, rule_name, from_status, to_status, metric,
               compare_op, threshold, consecutive_days, min_qa_cnt, description
        FROM dim_graduation_rule
        WHERE enabled = 1
        ORDER BY FIELD(from_status, 'internal_training', 'external_training', 'formal_probation')
    """)
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def check_promotion_eligibility(
    repo: DashboardRepository,
    reviewer_name: str,
    batch_name: str,
    current_status: str,
) -> list[dict]:
    """检查某人是否满足晋级条件。

    Returns:
        list[dict]: 每个满足的规则，包含 rule + evidence
    """
    rules = load_graduation_rules(repo)
    applicable_rules = [r for r in rules if r["from_status"] == current_status]
    if not applicable_rules:
        return []

    short_name = reviewer_name.replace("云雀联营-", "") if "云雀联营-" in reviewer_name else reviewer_name
    alias = f"云雀联营-{reviewer_name}" if not reviewer_name.startswith("云雀联营-") else reviewer_name

    results = []
    for rule in applicable_rules:
        stage_map = {
            "internal_training": "internal",
            "external_training": "external",
            "formal_probation": "formal",
        }
        target_stage = stage_map.get(rule["from_status"], "internal")

        # 获取每日数据
        if target_stage in ("internal", "external"):
            daily_df = repo.fetch_df("""
                SELECT biz_date,
                       COUNT(*) AS qa_cnt,
                       SUM(is_correct) AS correct_cnt,
                       ROUND(SUM(is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS accuracy_rate,
                       ROUND(SUM(is_misjudge) * 100.0 / NULLIF(COUNT(*), 0), 2) AS misjudge_rate,
                       ROUND(SUM(is_missjudge) * 100.0 / NULLIF(COUNT(*), 0), 2) AS missjudge_rate
                FROM fact_newcomer_qa
                WHERE (reviewer_name = %s OR reviewer_short_name = %s OR reviewer_name = %s)
                  AND stage = %s
                GROUP BY biz_date
                ORDER BY biz_date DESC
            """, [alias, short_name, short_name, target_stage])
        else:
            daily_df = repo.fetch_df("""
                SELECT biz_date,
                       SUM(qa_cnt) AS qa_cnt,
                       SUM(raw_correct_cnt) AS correct_cnt,
                       ROUND(SUM(raw_correct_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS accuracy_rate,
                       ROUND(SUM(misjudge_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS misjudge_rate,
                       ROUND(SUM(missjudge_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS missjudge_rate
                FROM mart_day_auditor
                WHERE (reviewer_name = %s OR reviewer_name = %s)
                GROUP BY biz_date
                ORDER BY biz_date DESC
            """, [alias, short_name])

        if daily_df is None or daily_df.empty:
            continue

        # 检查累计质检量
        total_qa = int(daily_df["qa_cnt"].sum())
        if total_qa < rule["min_qa_cnt"]:
            continue

        # 检查连续天数达标
        metric_col = rule["metric"]
        threshold = float(rule["threshold"])
        compare_op = rule["compare_op"]
        consecutive_needed = int(rule["consecutive_days"])

        if metric_col not in daily_df.columns:
            continue

        daily_df[metric_col] = pd.to_numeric(daily_df[metric_col], errors="coerce").fillna(0)

        # 从最近一天开始往前数
        consecutive_count = 0
        daily_values = []
        for _, day_row in daily_df.iterrows():
            val = float(day_row[metric_col])
            if _compare(val, compare_op, threshold):
                consecutive_count += 1
                daily_values.append({"date": str(day_row["biz_date"]), "value": val})
            else:
                break

        if consecutive_count >= consecutive_needed:
            results.append({
                "rule": rule,
                "evidence": {
                    "total_qa_cnt": total_qa,
                    "consecutive_days": consecutive_count,
                    "recent_values": daily_values[:consecutive_needed],
                    "metric": metric_col,
                    "threshold": threshold,
                },
            })

    return results


def _compare(value: float, op: str, threshold: float) -> bool:
    """执行比较操作。"""
    if op == ">=":
        return value >= threshold
    if op == ">":
        return value > threshold
    if op == "<=":
        return value <= threshold
    if op == "<":
        return value < threshold
    if op == "==":
        return value == threshold
    return False


# ═══════════════════════════════════════════════════════════════
#  批量生成晋级推荐
# ═══════════════════════════════════════════════════════════════

def generate_promotion_recommendations(repo: DashboardRepository) -> pd.DataFrame:
    """批量检查所有在训新人，生成晋级推荐列表。

    Returns:
        DataFrame: columns=[reviewer_name, batch_name, team_name, current_status,
                            recommended_status, rule_name, evidence_summary, consecutive_days, total_qa]
    """
    ensure_lifecycle_schema(repo)

    members = repo.fetch_df("""
        SELECT reviewer_name, batch_name, team_name, team_leader,
               delivery_pm, owner, status
        FROM dim_newcomer_batch
        WHERE status NOT IN ('graduated', 'exited')
    """)
    if members is None or members.empty:
        return pd.DataFrame()

    recommendations = []
    for _, member in members.iterrows():
        name = member["reviewer_name"]
        batch = member["batch_name"]
        current = member["status"]

        # 映射旧 status
        mapped_status = current
        if current == "training":
            # 先推断实际阶段
            inferred = infer_current_stage(repo, name)
            mapped_status = inferred

        eligible = check_promotion_eligibility(repo, name, batch, mapped_status)
        for item in eligible:
            rule = item["rule"]
            evidence = item["evidence"]
            recommendations.append({
                "reviewer_name": name,
                "batch_name": batch,
                "team_name": member.get("team_name", ""),
                "team_leader": member.get("team_leader", ""),
                "owner": member.get("owner", ""),
                "current_status": current,
                "current_status_mapped": mapped_status,
                "recommended_status": rule["to_status"],
                "rule_code": rule["rule_code"],
                "rule_name": rule["rule_name"],
                "evidence_summary": f"连续{evidence['consecutive_days']}天{evidence['metric']}"
                                    f"达标(最近值: {evidence['recent_values'][0]['value']:.1f}%), "
                                    f"累计质检量{evidence['total_qa_cnt']}",
                "consecutive_days": evidence["consecutive_days"],
                "total_qa": evidence["total_qa_cnt"],
                "evidence_json": str(evidence),
            })

    return pd.DataFrame(recommendations) if recommendations else pd.DataFrame()


# ═══════════════════════════════════════════════════════════════
#  执行状态变更
# ═══════════════════════════════════════════════════════════════

def update_member_status(
    repo: DashboardRepository,
    reviewer_name: str,
    batch_name: str,
    new_status: str,
    trigger_type: str = "manual",
    rule_code: str | None = None,
    evidence: str | None = None,
    operator: str = "system",
    note: str | None = None,
) -> bool:
    """更新新人状态并记录里程碑。

    Args:
        trigger_type: 'auto' | 'manual' | 'system'
    """
    # 查询当前状态
    current = repo.fetch_one(
        "SELECT status FROM dim_newcomer_batch WHERE reviewer_name = %s AND batch_name = %s",
        [reviewer_name, batch_name],
    )
    if not current:
        return False

    old_status = current["status"]
    if old_status == new_status:
        return True  # 已是目标状态

    # 更新 dim_newcomer_batch
    repo.execute(
        "UPDATE dim_newcomer_batch SET status = %s WHERE reviewer_name = %s AND batch_name = %s",
        [new_status, reviewer_name, batch_name],
    )

    # 如果是毕业，设置 effective_end_date
    if new_status == "graduated":
        repo.execute(
            "UPDATE dim_newcomer_batch SET effective_end_date = %s WHERE reviewer_name = %s AND batch_name = %s AND effective_end_date IS NULL",
            [date.today(), reviewer_name, batch_name],
        )

    # 写入里程碑
    repo.execute("""
        INSERT INTO fact_newcomer_milestone
        (reviewer_name, batch_name, from_status, to_status, rule_code,
         trigger_type, evidence, operator, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [
        reviewer_name, batch_name, old_status, new_status,
        rule_code, trigger_type, evidence, operator, note,
    ])

    return True


def batch_sync_inferred_status(repo: DashboardRepository, operator: str = "system") -> dict:
    """批量同步推断状态到数据库（仅同步 pending → 实际阶段）。

    只做"向前推进"，不做"回退"。
    旧 status='training' 会被自动映射到正确的细分状态。
    """
    ensure_lifecycle_schema(repo)
    inferred_df = batch_infer_stages(repo)
    if inferred_df.empty:
        return {"updated": 0, "skipped": 0}

    updated = 0
    skipped = 0
    for _, row in inferred_df.iterrows():
        if not row["needs_update"]:
            skipped += 1
            continue

        current = row["current_status"]
        inferred = row["inferred_status"]

        # 只向前推进，不回退
        flow_order = {s: i for i, s in enumerate(STATUS_FLOW)}
        current_order = flow_order.get(current, 0)
        # 旧 training 映射
        if current == "training":
            current_order = 1  # 等价于 internal_training
        inferred_order = flow_order.get(inferred, 0)

        if inferred_order <= current_order:
            skipped += 1
            continue

        success = update_member_status(
            repo,
            reviewer_name=row["reviewer_name"],
            batch_name=row["batch_name"],
            new_status=inferred,
            trigger_type="system",
            evidence=f"基于质检数据自动推断: 检测到{inferred}阶段数据",
            operator=operator,
            note="系统自动同步推断状态",
        )
        if success:
            updated += 1
        else:
            skipped += 1

    return {"updated": updated, "skipped": skipped}


# ═══════════════════════════════════════════════════════════════
#  里程碑查询
# ═══════════════════════════════════════════════════════════════

def load_milestones(
    repo: DashboardRepository,
    reviewer_name: str | None = None,
    batch_name: str | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    """查询里程碑记录。"""
    sql = """
        SELECT reviewer_name, batch_name, from_status, to_status,
               rule_code, trigger_type, evidence, operator, note, created_at
        FROM fact_newcomer_milestone
        WHERE 1=1
    """
    params: list = []
    if reviewer_name:
        sql += " AND reviewer_name = %s"
        params.append(reviewer_name)
    if batch_name:
        sql += " AND batch_name = %s"
        params.append(batch_name)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    return repo.fetch_df(sql, params)


def get_status_label(status: str) -> tuple[str, str, str]:
    """获取状态的 (标签文本, 颜色, 背景色)。"""
    return STATUS_LABELS.get(status, ("未知", "#94a3b8", "#f8fafc"))
