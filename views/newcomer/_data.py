"""新人追踪 — 数据加载层。

所有 SQL 查询函数集中在这里。
主页面 (04_新人追踪.py) 调用这些函数后组装 ctx 字典传给各视图模块。

注意：
  - 函数内引用 repo 和辅助函数（batch_effective_join_condition 等）
    通过参数或模块级全局变量获取。
  - Streamlit 缓存装饰器在此模块中不可用（因为 import 顺序），
    缓存由主页面负责。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from storage.repository import DashboardRepository


def create_data_loaders(repo: "DashboardRepository", helpers: dict):
    """工厂函数：返回一组绑定了 repo 和辅助函数的数据加载 callable。

    Parameters
    ----------
    repo : DashboardRepository
        数据库操作对象
    helpers : dict
        包含以下 key 的辅助函数/表达式字典：
        - batch_effective_start_expr: callable(dim_alias) -> str
        - batch_effective_join_condition: callable(fact_alias, dim_alias, ...) -> str
        - reviewer_name_in_condition: callable(fact_alias, aliases, ...) -> (str, list)
        - _extract_short_names: callable(aliases) -> list[str]
        - get_table_columns: callable(table_name) -> set[str]
    """

    batch_effective_start_expr = helpers["batch_effective_start_expr"]
    batch_effective_join_condition = helpers["batch_effective_join_condition"]
    reviewer_name_in_condition = helpers["reviewer_name_in_condition"]
    _extract_short_names = helpers["_extract_short_names"]
    get_table_columns = helpers["get_table_columns"]

    def load_batch_list() -> pd.DataFrame:
        return repo.fetch_df(f"""
            SELECT
                batch_name,
                MIN(join_date) AS join_date,
                MIN({batch_effective_start_expr('d')}) AS effective_start_date,
                MAX(effective_end_date) AS effective_end_date,
                COUNT(*) AS total_cnt,
                GROUP_CONCAT(DISTINCT team_leader ORDER BY team_leader) AS leader_names,
                GROUP_CONCAT(DISTINCT delivery_pm ORDER BY delivery_pm) AS delivery_pms,
                GROUP_CONCAT(DISTINCT mentor_name ORDER BY mentor_name) AS mentor_names,
                GROUP_CONCAT(DISTINCT team_name ORDER BY team_name) AS teams,
                GROUP_CONCAT(DISTINCT owner ORDER BY owner) AS owners,
                SUM(CASE WHEN status = 'graduated' THEN 1 ELSE 0 END) AS graduated_cnt,
                SUM(CASE WHEN status = 'training' THEN 1 ELSE 0 END) AS training_cnt
            FROM dim_newcomer_batch d
            GROUP BY batch_name
            ORDER BY MIN({batch_effective_start_expr('d')}) DESC
        """)

    def load_newcomer_members(
        batch_names: list[str] | None = None,
        owner: str | None = None,
        team_name: str | None = None,
    ) -> pd.DataFrame:
        sql = """
            SELECT batch_name, reviewer_name, reviewer_alias, join_date,
                   COALESCE(effective_start_date, join_date) AS effective_start_date,
                   effective_end_date,
                   team_name, team_leader, delivery_pm, mentor_name, owner, status
            FROM dim_newcomer_batch
        """
        conditions: list[str] = []
        params: list[str] = []
        if batch_names:
            placeholders = ", ".join(["%s"] * len(batch_names))
            conditions.append(f"batch_name IN ({placeholders})")
            params.extend(batch_names)
        if owner:
            conditions.append("owner = %s")
            params.append(owner)
        if team_name:
            conditions.append("team_name = %s")
            params.append(team_name)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY batch_name, team_name, reviewer_name"
        return repo.fetch_df(sql, params)

    def load_newcomer_qa_daily(
        batch_names: list[str] | None = None,
        reviewer_aliases: list[str] | None = None,
        stage: str | None = None,
    ) -> pd.DataFrame:
        if reviewer_aliases == []:
            return pd.DataFrame()
        sql = f"""
            SELECT
                q.biz_date, q.reviewer_name, q.stage, n.batch_name, n.team_name,
                n.reviewer_name AS short_name,
                COUNT(*) AS qa_cnt,
                SUM(q.is_correct) AS correct_cnt,
                ROUND(SUM(q.is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS accuracy_rate,
                ROUND(SUM(q.is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS sample_accuracy_rate,
                ROUND(SUM(q.is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS reviewer_accuracy_rate,
                SUM(q.is_misjudge) AS misjudge_cnt,
                SUM(q.is_missjudge) AS missjudge_cnt
            FROM fact_newcomer_qa q
            JOIN dim_newcomer_batch n
              ON {batch_effective_join_condition("q", "n")}
        """
        conditions: list[str] = []
        params: list[str] = []
        if batch_names:
            placeholders = ", ".join(["%s"] * len(batch_names))
            conditions.append(f"n.batch_name IN ({placeholders})")
            params.extend(batch_names)
        if reviewer_aliases:
            cond, cond_params = reviewer_name_in_condition("q", reviewer_aliases)
            conditions.append(cond)
            params.extend(cond_params)
        if stage:
            conditions.append("q.stage = %s")
            params.append(stage)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " GROUP BY q.biz_date, q.reviewer_name, q.stage, n.batch_name, n.team_name, n.reviewer_name"
        sql += " ORDER BY q.biz_date"
        return repo.fetch_df(sql, params)

    def load_formal_qa_daily(
        batch_names: list[str] | None = None,
        reviewer_aliases: list[str] | None = None,
    ) -> pd.DataFrame:
        if reviewer_aliases == []:
            return pd.DataFrame()
        sql = f"""
            SELECT
                m.biz_date, m.reviewer_name, 'formal' AS stage,
                n.batch_name, n.team_name, n.reviewer_name AS short_name,
                SUM(m.qa_cnt) AS qa_cnt,
                SUM(m.raw_correct_cnt) AS correct_cnt,
                ROUND(SUM(m.raw_correct_cnt) * 100.0 / NULLIF(SUM(m.qa_cnt), 0), 2) AS accuracy_rate,
                ROUND(SUM(m.raw_correct_cnt) * 100.0 / NULLIF(SUM(m.qa_cnt), 0), 2) AS sample_accuracy_rate,
                ROUND(SUM(m.raw_correct_cnt) * 100.0 / NULLIF(SUM(m.qa_cnt), 0), 2) AS reviewer_accuracy_rate,
                SUM(m.misjudge_cnt) AS misjudge_cnt,
                SUM(m.missjudge_cnt) AS missjudge_cnt
            FROM mart_day_auditor m
            JOIN dim_newcomer_batch n
              ON {batch_effective_join_condition("m", "n", has_short_name=False)}
            WHERE 1 = 1
        """
        params: list[str] = []
        if batch_names:
            placeholders = ", ".join(["%s"] * len(batch_names))
            sql += f" AND n.batch_name IN ({placeholders})"
            params.extend(batch_names)
        if reviewer_aliases:
            short_names = _extract_short_names(reviewer_aliases)
            all_names = list(set(reviewer_aliases + short_names))
            placeholders = ", ".join(["%s"] * len(all_names))
            sql += f" AND m.reviewer_name IN ({placeholders})"
            params.extend(all_names)
        sql += " GROUP BY m.biz_date, m.reviewer_name, n.batch_name, n.team_name, n.reviewer_name"
        sql += " ORDER BY m.biz_date"
        return repo.fetch_df(sql, params)

    def load_newcomer_error_detail(reviewer_alias: str, limit: int = 100) -> pd.DataFrame:
        """查询近期错误明细——同时查新人内/外检 + 正式阶段，合并后返回。"""
        short_name = reviewer_alias.replace("云雀联营-", "") if "云雀联营-" in reviewer_alias else reviewer_alias
        # 1. 新人内/外检错误
        newcomer_errors = repo.fetch_df("""
            SELECT biz_date, stage, queue_name, content_type,
                   training_topic, risk_level, comment_text,
                   raw_judgement, final_judgement, error_type, qa_note,
                   is_correct, is_misjudge, is_missjudge
            FROM fact_newcomer_qa
            WHERE (reviewer_name = %s OR reviewer_short_name = %s OR reviewer_name = %s)
              AND is_correct = 0
            ORDER BY biz_date DESC, qa_time DESC
            LIMIT %s
        """, [reviewer_alias, short_name, short_name, limit])
        # 2. 正式阶段错误（vw_qa_base）
        formal_errors = repo.fetch_df("""
            SELECT biz_date, 'formal' AS stage, queue_name, content_type,
                   training_topic, risk_level, comment_text,
                   raw_judgement,
                   COALESCE(final_review_result, raw_judgement) AS final_judgement,
                   error_type, qa_note,
                   is_final_correct AS is_correct,
                   0 AS is_misjudge, 0 AS is_missjudge
            FROM vw_qa_base
            WHERE (reviewer_name = %s OR reviewer_name = %s)
              AND is_final_correct = 0
            ORDER BY biz_date DESC, qa_time DESC
            LIMIT %s
        """, [reviewer_alias, short_name, limit])
        frames = [df for df in [newcomer_errors, formal_errors] if df is not None and not df.empty]
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        return combined.sort_values("biz_date", ascending=False).head(limit)

    def load_person_all_qa_records(reviewer_alias: str, limit: int = 200) -> pd.DataFrame:
        short_name = reviewer_alias.replace("云雀联营-", "") if "云雀联营-" in reviewer_alias else reviewer_alias
        newcomer_df = repo.fetch_df("""
            SELECT biz_date, stage, queue_name, content_type,
                   training_topic, risk_level, comment_text,
                   raw_judgement, final_judgement, error_type, qa_note, is_correct
            FROM fact_newcomer_qa
            WHERE (reviewer_name = %s OR reviewer_short_name = %s OR reviewer_name = %s)
            ORDER BY biz_date DESC, qa_time DESC
            LIMIT %s
        """, [reviewer_alias, short_name, short_name, limit])
        formal_df = repo.fetch_df("""
            SELECT biz_date, 'formal' AS stage, queue_name, content_type,
                   training_topic, risk_level, comment_text,
                   raw_judgement,
                   COALESCE(final_review_result, raw_judgement) AS final_judgement,
                   error_type, qa_note, is_final_correct AS is_correct
            FROM vw_qa_base
            WHERE (reviewer_name = %s OR reviewer_name = %s)
              AND workforce_type = 'formal'
            ORDER BY biz_date DESC, qa_time DESC
            LIMIT %s
        """, [reviewer_alias, short_name, limit])
        frames = [df for df in [newcomer_df, formal_df] if df is not None and not df.empty]
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        return combined.sort_values("biz_date", ascending=False).head(limit)

    def load_newcomer_error_summary(
        batch_names: list[str] | None = None,
        reviewer_aliases: list[str] | None = None,
    ) -> pd.DataFrame:
        if reviewer_aliases == []:
            return pd.DataFrame()
        sql = f"""
            SELECT
                n.batch_name, n.team_name, n.team_leader,
                COALESCE(NULLIF(TRIM(n.delivery_pm), ''), '未填写') AS delivery_pm,
                COALESCE(NULLIF(TRIM(n.owner), ''), '未填写') AS owner_name,
                COALESCE(NULLIF(TRIM(q.error_type), ''), '未标注') AS error_type,
                COUNT(*) AS error_cnt
            FROM fact_newcomer_qa q
            JOIN dim_newcomer_batch n
              ON {batch_effective_join_condition("q", "n")}
            WHERE q.is_correct = 0
        """
        params: list[str] = []
        if batch_names:
            placeholders = ", ".join(["%s"] * len(batch_names))
            sql += f" AND n.batch_name IN ({placeholders})"
            params.extend(batch_names)
        if reviewer_aliases:
            cond, cond_params = reviewer_name_in_condition("q", reviewer_aliases)
            sql += f" AND {cond}"
            params.extend(cond_params)
        sql += " GROUP BY n.batch_name, n.team_name, n.team_leader, n.delivery_pm, n.owner, error_type ORDER BY error_cnt DESC"
        return repo.fetch_df(sql, params)

    def load_formal_dimension_detail(
        batch_names: list[str] | None = None,
        reviewer_aliases: list[str] | None = None,
    ) -> pd.DataFrame:
        fact_columns = get_table_columns("fact_qa_event")
        required = {"reviewer_name", "training_topic", "risk_level", "content_type", "is_raw_correct"}
        if reviewer_aliases == [] or not required.issubset(fact_columns):
            return pd.DataFrame()
        sql = f"""
            SELECT
                n.batch_name, n.team_name,
                COALESCE(NULLIF(TRIM(f.training_topic), ''), '未标注') AS training_topic,
                COALESCE(NULLIF(TRIM(f.risk_level), ''), '未标注') AS risk_level,
                COALESCE(NULLIF(TRIM(f.content_type), ''), '未标注') AS content_type,
                COUNT(*) AS qa_cnt,
                SUM(CASE WHEN f.is_raw_correct = 1 THEN 1 ELSE 0 END) AS correct_cnt
            FROM fact_qa_event f
            JOIN dim_newcomer_batch n
              ON {batch_effective_join_condition("f", "n", has_short_name=False)}
            WHERE 1 = 1
        """
        params: list[str] = []
        if batch_names:
            placeholders = ", ".join(["%s"] * len(batch_names))
            sql += f" AND n.batch_name IN ({placeholders})"
            params.extend(batch_names)
        if reviewer_aliases:
            short_names = _extract_short_names(reviewer_aliases)
            all_names = list(set(reviewer_aliases + short_names))
            placeholders = ", ".join(["%s"] * len(all_names))
            sql += f" AND f.reviewer_name IN ({placeholders})"
            params.extend(all_names)
        sql += " GROUP BY n.batch_name, n.team_name, training_topic, risk_level, content_type ORDER BY qa_cnt DESC"
        return repo.fetch_df(sql, params)

    def load_newcomer_dimension_detail(
        batch_names: list[str] | None = None,
        reviewer_aliases: list[str] | None = None,
    ) -> pd.DataFrame:
        fact_columns = get_table_columns("fact_newcomer_qa")
        required = {"reviewer_name", "stage", "training_topic", "risk_level", "content_type", "is_correct"}
        if reviewer_aliases == [] or not required.issubset(fact_columns):
            return pd.DataFrame()
        sql = f"""
            SELECT
                n.batch_name, n.team_name, q.stage,
                COALESCE(NULLIF(TRIM(q.training_topic), ''), '未标注') AS training_topic,
                COALESCE(NULLIF(TRIM(q.risk_level), ''), '未标注') AS risk_level,
                COALESCE(NULLIF(TRIM(q.content_type), ''), '未标注') AS content_type,
                COUNT(*) AS qa_cnt,
                SUM(CASE WHEN q.is_correct = 1 THEN 1 ELSE 0 END) AS correct_cnt
            FROM fact_newcomer_qa q
            JOIN dim_newcomer_batch n
              ON {batch_effective_join_condition("q", "n")}
            WHERE 1 = 1
        """
        params: list[str] = []
        if batch_names:
            placeholders = ", ".join(["%s"] * len(batch_names))
            sql += f" AND n.batch_name IN ({placeholders})"
            params.extend(batch_names)
        if reviewer_aliases:
            cond, cond_params = reviewer_name_in_condition("q", reviewer_aliases)
            sql += f" AND {cond}"
            params.extend(cond_params)
        sql += " GROUP BY n.batch_name, n.team_name, q.stage, training_topic, risk_level, content_type ORDER BY qa_cnt DESC"
        return repo.fetch_df(sql, params)

    def load_unmatched_newcomer_rows() -> pd.DataFrame:
        fact_columns = get_table_columns("fact_newcomer_qa")
        practice_expr = "COALESCE(is_practice_sample, 0)" if "is_practice_sample" in fact_columns else "0"
        return repo.fetch_df(f"""
            SELECT reviewer_name, stage,
                   MAX({practice_expr}) AS is_practice_sample,
                   COUNT(*) AS row_cnt,
                   MIN(biz_date) AS start_date,
                   MAX(biz_date) AS end_date
            FROM fact_newcomer_qa
            WHERE batch_name IS NULL OR batch_name = ''
            GROUP BY reviewer_name, stage
            ORDER BY row_cnt DESC, reviewer_name
        """)

    return {
        "load_batch_list": load_batch_list,
        "load_newcomer_members": load_newcomer_members,
        "load_newcomer_qa_daily": load_newcomer_qa_daily,
        "load_formal_qa_daily": load_formal_qa_daily,
        "load_newcomer_error_detail": load_newcomer_error_detail,
        "load_person_all_qa_records": load_person_all_qa_records,
        "load_newcomer_error_summary": load_newcomer_error_summary,
        "load_formal_dimension_detail": load_formal_dimension_detail,
        "load_newcomer_dimension_detail": load_newcomer_dimension_detail,
        "load_unmatched_newcomer_rows": load_unmatched_newcomer_rows,
    }
