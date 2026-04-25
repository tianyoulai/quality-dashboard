"""修复历史数据中 error_type 为空的记录。

用法：
    python jobs/fix_error_type.py             # 执行修复
    python jobs/fix_error_type.py --dry-run   # 仅预览，不实际更新

原理：
    1. 优先从 raw_judgement / final_judgement / qa_result / qa_note 推断错判/漏判
    2. 再从 is_misjudge / is_missjudge 标记推断
    3. 剩余不正确但无法分类的标记为"判定不一致"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository


def fix_error_type(dry_run: bool = False) -> dict:
    """修复 fact_qa_event 中 error_type 为空的记录。"""
    repo = DashboardRepository()

    # 1. 统计当前空 error_type 的记录数
    count_sql = """
        SELECT COUNT(*) AS cnt
        FROM fact_qa_event
        WHERE is_raw_correct = 0
          AND (error_type IS NULL OR TRIM(error_type) = '')
    """
    count_df = repo.fetch_df(count_sql)
    total_empty = int(count_df.iloc[0]["cnt"]) if not count_df.empty else 0
    print(f"📊 待修复记录数：{total_empty}")

    if total_empty == 0:
        print("✅ 无需修复，所有错误记录已有 error_type")
        return {"total_empty": 0, "updated": 0}

    if dry_run:
        # 预览修复结果
        preview_sql = """
            SELECT
                CASE
                    WHEN COALESCE(raw_judgement,'') LIKE '%%错判%%'
                      OR COALESCE(raw_judgement,'') LIKE '%%误判%%'
                      OR COALESCE(final_judgement,'') LIKE '%%错判%%'
                      OR COALESCE(qa_result,'') LIKE '%%错判%%'
                      OR COALESCE(qa_note,'') LIKE '%%错判%%'
                    THEN '错判'
                    WHEN COALESCE(raw_judgement,'') LIKE '%%漏判%%'
                      OR COALESCE(raw_judgement,'') LIKE '%%漏审%%'
                      OR COALESCE(final_judgement,'') LIKE '%%漏判%%'
                      OR COALESCE(qa_result,'') LIKE '%%漏判%%'
                      OR COALESCE(qa_note,'') LIKE '%%漏判%%'
                    THEN '漏判'
                    WHEN is_misjudge = 1 THEN '错判'
                    WHEN is_missjudge = 1 THEN '漏判'
                    WHEN TRIM(COALESCE(raw_judgement, '')) IN ('', '正常', '通过', 'pass')
                    THEN '漏判'
                    ELSE '错判'
                END AS inferred_type,
                COUNT(*) AS cnt
            FROM fact_qa_event
            WHERE is_raw_correct = 0
              AND (error_type IS NULL OR TRIM(error_type) = '')
            GROUP BY 1
            ORDER BY 2 DESC
        """
        preview_df = repo.fetch_df(preview_sql)
        print("\n📋 修复预览（dry-run）：")
        for _, row in preview_df.iterrows():
            print(f"   {row['inferred_type']}: {row['cnt']} 条")
        return {"total_empty": total_empty, "updated": 0, "preview": preview_df.to_dict("records")}

    # 2. 执行修复：从文本字段推断 error_type
    update_sql_1 = """
        UPDATE fact_qa_event
        SET error_type = CASE
            WHEN COALESCE(raw_judgement,'') LIKE '%%错判%%'
              OR COALESCE(raw_judgement,'') LIKE '%%误判%%'
              OR COALESCE(final_judgement,'') LIKE '%%错判%%'
              OR COALESCE(qa_result,'') LIKE '%%错判%%'
              OR COALESCE(qa_note,'') LIKE '%%错判%%'
            THEN '错判'
            WHEN COALESCE(raw_judgement,'') LIKE '%%漏判%%'
              OR COALESCE(raw_judgement,'') LIKE '%%漏审%%'
              OR COALESCE(final_judgement,'') LIKE '%%漏判%%'
              OR COALESCE(qa_result,'') LIKE '%%漏判%%'
              OR COALESCE(qa_note,'') LIKE '%%漏判%%'
            THEN '漏判'
            ELSE NULL
        END
        WHERE is_raw_correct = 0
          AND (error_type IS NULL OR TRIM(error_type) = '')
          AND (
              COALESCE(raw_judgement,'') LIKE '%%错判%%'
              OR COALESCE(raw_judgement,'') LIKE '%%误判%%'
              OR COALESCE(raw_judgement,'') LIKE '%%漏判%%'
              OR COALESCE(raw_judgement,'') LIKE '%%漏审%%'
              OR COALESCE(final_judgement,'') LIKE '%%错判%%'
              OR COALESCE(final_judgement,'') LIKE '%%漏判%%'
              OR COALESCE(qa_result,'') LIKE '%%错判%%'
              OR COALESCE(qa_result,'') LIKE '%%漏判%%'
              OR COALESCE(qa_note,'') LIKE '%%错判%%'
              OR COALESCE(qa_note,'') LIKE '%%漏判%%'
          )
    """
    repo.execute(update_sql_1)
    print("✅ 第 1 步完成：从文本字段推断错判/漏判")

    # 3. 从 is_misjudge / is_missjudge 标记推断
    update_sql_2 = """
        UPDATE fact_qa_event
        SET error_type = CASE
            WHEN is_misjudge = 1 THEN '错判'
            WHEN is_missjudge = 1 THEN '漏判'
            ELSE NULL
        END
        WHERE is_raw_correct = 0
          AND (error_type IS NULL OR TRIM(error_type) = '')
          AND (is_misjudge = 1 OR is_missjudge = 1)
    """
    repo.execute(update_sql_2)
    print("✅ 第 2 步完成：从 is_misjudge/is_missjudge 标记推断")

    # 4. 剩余不正确但无法分类的：根据一审标签推断
    # 一审=正常/空 → 漏判（一审漏掉了违规内容）
    update_sql_3a = """
        UPDATE fact_qa_event
        SET error_type = '漏判'
        WHERE is_raw_correct = 0
          AND (error_type IS NULL OR TRIM(error_type) = '')
          AND TRIM(COALESCE(raw_judgement, '')) IN ('', '正常', '通过', 'pass')
    """
    repo.execute(update_sql_3a)
    print("✅ 第 3a 步完成：一审=正常/空 → 漏判")

    # 一审=具体违规标签 → 错判（一审误判为违规）
    update_sql_3b = """
        UPDATE fact_qa_event
        SET error_type = '错判'
        WHERE is_raw_correct = 0
          AND (error_type IS NULL OR TRIM(error_type) = '')
    """
    repo.execute(update_sql_3b)
    print("✅ 第 3b 步完成：一审=违规标签 → 错判")

    # 5. 统计修复结果
    result_sql = """
        SELECT error_type, COUNT(*) AS cnt
        FROM fact_qa_event
        WHERE is_raw_correct = 0
        GROUP BY 1
        ORDER BY 2 DESC
    """
    result_df = repo.fetch_df(result_sql)
    print("\n📊 修复后 error_type 分布：")
    for _, row in result_df.iterrows():
        et = row["error_type"] if row["error_type"] else "仍为空"
        print(f"   {et}: {row['cnt']} 条")

    remaining = repo.fetch_df(count_sql)
    still_empty = int(remaining.iloc[0]["cnt"]) if not remaining.empty else 0
    updated = total_empty - still_empty

    print(f"\n✅ 修复完成！共更新 {updated} 条记录（剩余 {still_empty} 条仍为空）")
    return {"total_empty": total_empty, "updated": updated, "still_empty": still_empty}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="修复历史数据中 error_type 为空的记录")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际更新")
    args = parser.parse_args()
    fix_error_type(dry_run=args.dry_run)
