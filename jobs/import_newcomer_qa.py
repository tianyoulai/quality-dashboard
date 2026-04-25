"""新人质检数据导入脚本。

支持两种格式：
- 外检（10816）：文件名含 "10816"，单 sheet，列名含 "原始答案.operatorName"
- 内检（18365）：文件名含 "新人" 或队列含 "新人评论测试"/"18365"，读取 "数据清洗" sheet

用法：
    python jobs/import_newcomer_qa.py --file <文件路径> [--source-name <原始文件名>]
    python jobs/import_newcomer_qa.py --file <文件路径> --stage internal  # 强制指定阶段
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository
from utils.date_parser import extract_date_from_filename


# ═══════════════════════════════════════════════════════════════
#  阶段识别规则
# ═══════════════════════════════════════════════════════════════

def detect_stage(filename: str, df: pd.DataFrame | None = None) -> str:
    """根据文件名和内容自动识别阶段。

    规则（已确认）：
    - 文件名含 "10816" → external（外部质检）
    - 文件名含 "新人" 或内容队列含 "新人评论测试"/"18365" → internal（内部质检）

    Returns:
        "external" 或 "internal"
    """
    name_lower = filename.lower()

    # 规则1：10816 = 外检（唯一判定标准）
    if "10816" in name_lower:
        return "external"

    # 规则2：文件名含"新人"
    if "新人" in filename:
        return "internal"

    # 规则3：检查数据内容中的队列名
    if df is not None:
        for col in ["队列", "queue_name", "供应商"]:
            if col in df.columns:
                values = df[col].dropna().astype(str).str.cat(sep=" ")
                if "新人评论测试" in values or "18365" in values:
                    return "internal"

    # 默认按内检处理
    return "internal"


# ═══════════════════════════════════════════════════════════════
#  外检数据解析（10816 格式）
# ═══════════════════════════════════════════════════════════════

def parse_external(df: pd.DataFrame, source_file: str, biz_date_override: date | None) -> pd.DataFrame:
    """解析外检文件。

    表头：质检时间, 质检员, objectId, commentId, 供应商,
          原始答案.operatorName, 原始答案.commentContent,
          原始答案.reasonNumberLabel, reasonNumberLabel, 对比
    """
    rows = []
    for _, r in df.iterrows():
        reviewer_full = str(r.get("原始答案.operatorName", "")).strip()
        reviewer_short = reviewer_full.replace("云雀联营-", "") if "云雀联营-" in reviewer_full else reviewer_full

        raw_judgement = str(r.get("原始答案.reasonNumberLabel", "")).strip()
        final_judgement = str(r.get("reasonNumberLabel", "")).strip()

        # 正确判定：对比列 True = 正确
        compare_val = str(r.get("对比", "")).strip().lower()
        is_correct = 1 if compare_val in ("true", "1", "是", "正确") else 0

        # 错判/漏判推断
        is_misjudge = 0
        is_missjudge = 0
        error_type = None
        if not is_correct and raw_judgement and final_judgement:
            if raw_judgement != "正常" and final_judgement == "正常":
                is_misjudge = 1  # 错判：标了违规但实际正常
                error_type = "错判"
            elif raw_judgement == "正常" and final_judgement != "正常":
                is_missjudge = 1  # 漏判：标了正常但实际违规
                error_type = "漏判"
            else:
                error_type = "判定不一致"

        qa_time = pd.to_datetime(r.get("质检时间"), errors="coerce")
        biz_d = biz_date_override or (qa_time.date() if pd.notna(qa_time) else date.today())

        # 行去重哈希
        hash_src = f"{r.get('objectId', '')}|{r.get('commentId', '')}|{reviewer_full}|{source_file}"
        row_hash = hashlib.sha1(hash_src.encode()).hexdigest()

        rows.append({
            "biz_date": biz_d,
            "qa_time": qa_time if pd.notna(qa_time) else None,
            "reviewer_name": reviewer_full,
            "reviewer_short_name": reviewer_short,
            "batch_name": None,  # 后续通过映射表回填
            "stage": "external",
            "queue_name": str(r.get("供应商", "")).strip(),
            "qa_owner_name": str(r.get("质检员", "")).strip(),
            "source_record_id": str(r.get("objectId", "")).strip().rstrip("\t"),
            "comment_id": str(r.get("commentId", "")).strip().rstrip("\t"),
            "dynamic_id": None,
            "comment_text": str(r.get("原始答案.commentContent", "")).strip(),
            "raw_judgement": raw_judgement,
            "final_judgement": final_judgement,
            "error_type": error_type,
            "qa_note": None,
            "is_correct": is_correct,
            "is_misjudge": is_misjudge,
            "is_missjudge": is_missjudge,
            "source_file_name": source_file,
            "row_hash": row_hash,
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════
#  内检数据解析（数据清洗 sheet 格式）
# ═══════════════════════════════════════════════════════════════

def parse_internal(df: pd.DataFrame, source_file: str, biz_date_override: date | None) -> pd.DataFrame:
    """解析内检文件（数据清洗 sheet）。

    表头：质检时间, 一审时间, 质检员, 动态ID, 评论ID, 队列,
          一审公司, 一审人员, 评论文本, 一审结果, 错误类型,
          质检结果, 质检备注, 备注
    """
    rows = []
    for _, r in df.iterrows():
        reviewer_full = str(r.get("一审人员", "")).strip()
        reviewer_short = reviewer_full.replace("云雀联营-", "") if "云雀联营-" in reviewer_full else reviewer_full

        raw_judgement = str(r.get("一审结果", "")).strip()
        final_judgement = str(r.get("质检结果", "")).strip()
        error_type = str(r.get("错误类型", "")).strip()

        # 正确判定：一审结果 == 质检结果 且 错误类型 == "正常"
        if error_type in ("正常", "", "nan", "None"):
            is_correct = 1
        else:
            is_correct = 0

        # 错判/漏判
        is_misjudge = 1 if error_type == "误判" or error_type == "错判" else 0
        is_missjudge = 1 if error_type == "漏判" or error_type == "漏审" else 0
        # 如果错误类型不是上面的特定值但不正确，看一审/质检结果推断
        if not is_correct and not is_misjudge and not is_missjudge:
            if raw_judgement != "正常" and final_judgement == "正常":
                is_misjudge = 1
            elif raw_judgement == "正常" and final_judgement != "正常":
                is_missjudge = 1

        qa_time = pd.to_datetime(r.get("质检时间"), errors="coerce")
        review_time = pd.to_datetime(r.get("一审时间"), errors="coerce")
        biz_d = biz_date_override or (
            review_time.date() if pd.notna(review_time)
            else qa_time.date() if pd.notna(qa_time)
            else date.today()
        )

        hash_src = f"{r.get('动态ID', '')}|{r.get('评论ID', '')}|{reviewer_full}|{source_file}"
        row_hash = hashlib.sha1(hash_src.encode()).hexdigest()

        qa_note_parts = [
            str(r.get("质检备注", "")).strip(),
            str(r.get("备注", "")).strip(),
        ]
        qa_note = " | ".join(p for p in qa_note_parts if p and p not in ("nan", "None", ""))

        rows.append({
            "biz_date": biz_d,
            "qa_time": qa_time if pd.notna(qa_time) else None,
            "reviewer_name": reviewer_full,
            "reviewer_short_name": reviewer_short,
            "batch_name": None,
            "stage": "internal",
            "queue_name": str(r.get("队列", "")).strip(),
            "qa_owner_name": str(r.get("质检员", "")).strip(),
            "source_record_id": None,
            "comment_id": str(r.get("评论ID", "")).strip(),
            "dynamic_id": str(r.get("动态ID", "")).strip(),
            "comment_text": str(r.get("评论文本", "")).strip(),
            "raw_judgement": raw_judgement,
            "final_judgement": final_judgement,
            "error_type": error_type if error_type not in ("正常", "nan", "None", "") else None,
            "qa_note": qa_note or None,
            "is_correct": is_correct,
            "is_misjudge": is_misjudge,
            "is_missjudge": is_missjudge,
            "source_file_name": source_file,
            "row_hash": row_hash,
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════
#  入库逻辑
# ═══════════════════════════════════════════════════════════════

def backfill_batch_name(df: pd.DataFrame, repo: DashboardRepository) -> pd.DataFrame:
    """根据 dim_newcomer_batch 回填 batch_name，并支持时间范围归属。"""
    try:
        mapping_df = repo.fetch_df(
            "SELECT reviewer_name, reviewer_alias, batch_name, join_date, effective_start_date, effective_end_date FROM dim_newcomer_batch"
        )
    except Exception:
        return df

    if mapping_df.empty:
        return df

    df = df.copy().reset_index(drop=True)
    df["_row_id"] = range(len(df))
    df["_biz_date"] = pd.to_datetime(df.get("biz_date"), errors="coerce").dt.date

    mapping_df = mapping_df.copy()
    join_dates = pd.to_datetime(mapping_df["join_date"], errors="coerce").dt.date
    start_dates = pd.to_datetime(mapping_df["effective_start_date"], errors="coerce").dt.date
    mapping_df["_start_date"] = start_dates.where(pd.notna(start_dates), join_dates)
    mapping_df["_end_date"] = pd.to_datetime(mapping_df["effective_end_date"], errors="coerce").dt.date

    candidates = df.merge(
        mapping_df[["reviewer_name", "reviewer_alias", "batch_name", "_start_date", "_end_date"]],
        left_on="reviewer_short_name",
        right_on="reviewer_name",
        how="left",
        suffixes=("", "_dim"),
    )
    alias_candidates = df.merge(
        mapping_df[["reviewer_name", "reviewer_alias", "batch_name", "_start_date", "_end_date"]],
        left_on="reviewer_name",
        right_on="reviewer_alias",
        how="left",
        suffixes=("", "_dim"),
    )
    merged = pd.concat([candidates, alias_candidates], ignore_index=True)

    valid_mask = merged["batch_name"].notna()
    valid_mask &= merged["_start_date"].isna() | (merged["_biz_date"] >= merged["_start_date"])
    valid_mask &= merged["_end_date"].isna() | (merged["_biz_date"] <= merged["_end_date"])
    matched = merged.loc[valid_mask, ["_row_id", "batch_name", "_start_date"]].copy()

    if not matched.empty:
        matched["_start_sort"] = pd.to_datetime(matched["_start_date"], errors="coerce")
        matched = matched.sort_values(["_row_id", "_start_sort", "batch_name"], ascending=[True, False, True])
        matched = matched.drop_duplicates(subset=["_row_id"], keep="first")
        df["batch_name"] = matched.set_index("_row_id")["batch_name"].reindex(df["_row_id"])
    else:
        df["batch_name"] = None

    return df.drop(columns=["_row_id", "_biz_date"])


def import_file(file_path: str, source_name: str | None = None, force_stage: str | None = None) -> dict:
    """导入单个新人质检文件。

    Returns:
        dict: {"source_file": str, "stage": str, "source_rows": int,
               "inserted_rows": int, "dedup_rows": int}
    """
    path = Path(file_path)
    display_name = source_name or path.name

    # 读取文件
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        # 尝试读"数据清洗"sheet（内检格式），失败则读默认 sheet
        try:
            xl = pd.ExcelFile(path)
            if "数据清洗" in xl.sheet_names:
                raw_df = pd.read_excel(path, sheet_name="数据清洗", dtype=str)
            else:
                raw_df = pd.read_excel(path, dtype=str)
        except Exception:
            raw_df = pd.read_excel(path, dtype=str)
    elif suffix == ".csv":
        for enc in ["utf-8-sig", "utf-8", "gb18030"]:
            try:
                raw_df = pd.read_csv(path, encoding=enc, dtype=str)
                break
            except Exception:
                continue
        else:
            raise RuntimeError(f"CSV 读取失败: {path}")
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")

    if raw_df.empty:
        return {"source_file": display_name, "stage": "unknown",
                "source_rows": 0, "inserted_rows": 0, "dedup_rows": 0}

    # 识别阶段
    stage = force_stage or detect_stage(display_name, raw_df)

    # 从文件名提取日期
    biz_date_override = extract_date_from_filename(display_name)

    # 解析
    if stage == "external":
        prepared_df = parse_external(raw_df, display_name, biz_date_override)
    else:
        prepared_df = parse_internal(raw_df, display_name, biz_date_override)

    if prepared_df.empty:
        return {"source_file": display_name, "stage": stage,
                "source_rows": len(raw_df), "inserted_rows": 0, "dedup_rows": 0}

    # 回填 batch_name
    repo = DashboardRepository()
    prepared_df = backfill_batch_name(prepared_df, repo)

    # 去重：检查 row_hash 是否已存在
    existing_hashes = set()
    try:
        hash_list = prepared_df["row_hash"].dropna().unique().tolist()
        if hash_list:
            # 分批查询避免 SQL 过长
            batch_size = 500
            for i in range(0, len(hash_list), batch_size):
                batch = hash_list[i:i + batch_size]
                placeholders = ",".join(["%s"] * len(batch))
                result = repo.fetch_df(
                    f"SELECT row_hash FROM fact_newcomer_qa WHERE row_hash IN ({placeholders})",
                    batch,
                )
                if not result.empty:
                    existing_hashes.update(result["row_hash"].tolist())
    except Exception:
        pass  # 表不存在时忽略

    source_rows = len(prepared_df)
    if existing_hashes:
        prepared_df = prepared_df[~prepared_df["row_hash"].isin(existing_hashes)]
    dedup_rows = source_rows - len(prepared_df)

    # 入库
    inserted_rows = 0
    if not prepared_df.empty:
        # 确保列顺序与表一致（去掉 id，自增主键）
        insert_cols = [
            "biz_date", "qa_time", "reviewer_name", "reviewer_short_name",
            "batch_name", "stage", "queue_name", "qa_owner_name",
            "source_record_id", "comment_id", "dynamic_id", "comment_text",
            "raw_judgement", "final_judgement", "error_type", "qa_note",
            "is_correct", "is_misjudge", "is_missjudge",
            "source_file_name", "row_hash",
        ]
        insert_df = prepared_df[insert_cols].copy()

        # 清理 NaN
        insert_df = insert_df.where(insert_df.notna(), None)

        inserted_rows = repo.insert_dataframe("fact_newcomer_qa", insert_df)

    return {
        "source_file": display_name,
        "stage": stage,
        "source_rows": source_rows,
        "inserted_rows": inserted_rows,
        "dedup_rows": dedup_rows,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="新人质检数据导入")
    parser.add_argument("--file", required=True, help="文件路径")
    parser.add_argument("--source-name", default=None, help="原始文件名（用于阶段识别和日期提取）")
    parser.add_argument("--stage", choices=["internal", "external"], default=None, help="强制指定阶段")
    args = parser.parse_args()

    result = import_file(args.file, args.source_name, args.stage)

    # JSON 输出（供 Streamlit subprocess 调用解析）
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
