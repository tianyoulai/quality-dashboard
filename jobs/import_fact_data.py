from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository


# ==========================================================
# 业务线映射规则（按文件名关键词匹配）
# 说明：只匹配业务关心的三条主线。非主线场景（如"迁移人力图片"等图片队列）
#       保持"未识别"，不纳入主看板统计。
# ==========================================================
BUSINESS_LINE_RULES = [
    {
        "keyword": "长沙云雀",
        "业务线": "A组-评论",
        "母业务": "A组",
        "子业务": "A组-评论",
    },
    {
        "keyword": "迁移人力ilabel",
        "业务线": "B组-评论",
        "母业务": "B组",
        "子业务": "B组-评论",
    },
    {
        "keyword": "账号",
        "业务线": "B组-账号",
        "母业务": "B组",
        "子业务": "B组-账号",
    },
]

# ==========================================================
# 文件名黑名单：命中则直接拒绝入库（不属于看板考核范围的队列）
# ==========================================================
FILENAME_BLACKLIST_KEYWORDS = [
    "15210",  # 迁移人力图片质检，非目标业务线
    "17125",  # 迁移人力17125质检，非目标业务线
]


def is_blacklisted_filename(filename: str) -> tuple[bool, str]:
    """判断文件名是否在黑名单中。

    Returns:
        tuple[bool, str]: (是否黑名单, 命中的关键词)
    """
    normalized = re.sub(r"\s+", "", filename).lower()
    for keyword in FILENAME_BLACKLIST_KEYWORDS:
        if keyword.lower() in normalized:
            return True, keyword
    return False, ""


# ==========================================================
# 内检/外检、正式/新人 自动检测规则
# ==========================================================

# 内检文件名关键词（优先级从高到低）
INTERNAL_INSPECT_KEYWORDS = [
    "内检", "内部质检", "内部质量", "内部抽检",
]
# 外检文件名关键词（如果同时出现内外检关键词，以显式匹配为准）
EXTERNAL_INSPECT_KEYWORDS = [
    "外检", "外部质检", "外部质量", "外部抽检",
]
# 新人正式队列关键词（会纳入新人追踪看板/毕业率考核）
NEWCOMER_KEYWORDS = [
    "新人", "新员工", "实习生", "培训期", "试用期",
    "18365",  # 新人内检队列号（正式考核）
]
# 新人试标队列关键词（练手/试标数据，不纳入新人正式考核）
NEWCOMER_TRIAL_KEYWORDS = [
    "10816",  # A组（长沙云雀）新人试标外检队列号
]


def detect_inspect_type(filename: str) -> str:
    """根据文件名自动检测检类（外检/内检）。

    规则：
    1. 文件名含内检关键词 → internal
    2. 文件名含外检关键词 → external
    3. 默认 → external（现有数据均为外检）
    """
    normalized = re.sub(r"\s+", "", filename).lower()
    for keyword in INTERNAL_INSPECT_KEYWORDS:
        if keyword.lower() in normalized:
            return "internal"
    for keyword in EXTERNAL_INSPECT_KEYWORDS:
        if keyword.lower() in normalized:
            return "external"
    return "external"


def detect_workforce_type(filename: str) -> str:
    """根据文件名自动检测人力类型。

    Returns:
        - "newcomer_trial": 新人试标（10816 等练手外检队列，不纳入新人正式考核）
        - "newcomer": 正式新人（纳入新人追踪/毕业率考核）
        - "formal": 正式人力

    优先级：newcomer_trial > newcomer > formal
    （试标文件名也会同时含"新人"字样，必须先判 trial 避免被一般规则吸走）
    """
    normalized = re.sub(r"\s+", "", filename).lower()
    for keyword in NEWCOMER_TRIAL_KEYWORDS:
        if keyword.lower() in normalized:
            return "newcomer_trial"
    for keyword in NEWCOMER_KEYWORDS:
        if keyword.lower() in normalized:
            return "newcomer"
    return "formal"


def identify_business_line(filename: str) -> tuple[str, str]:
    """根据文件名识别业务线。

    Returns:
        tuple[str, str]: (母业务, 子业务)，未匹配返回 ("未识别", "未识别")
    """
    normalized_name = re.sub(r"\s+", "", filename).lower()
    for rule in BUSINESS_LINE_RULES:
        keyword = re.sub(r"\s+", "", rule["keyword"]).lower()
        if keyword in normalized_name:
            return rule["母业务"], rule["子业务"]
    return "未识别", "未识别"


# extract_date_from_filename 已统一到 utils/date_parser.py
from utils.date_parser import extract_date_from_filename


QA_INSERT_COLUMNS = [
    "event_id",
    "biz_date",
    "qa_time",
    "import_date",
    "mother_biz",
    "sub_biz",
    "group_name",
    "queue_name",
    "scene_name",
    "channel_name",
    "content_type",
    "reviewer_name",
    "qa_owner_name",
    "trainer_name",
    "source_record_id",
    "comment_id",
    "dynamic_id",
    "account_id",
    "join_key",
    "raw_label",
    "final_label",
    "raw_judgement",
    "final_judgement",
    "qa_result",
    "error_type",
    "error_level",
    "error_reason",
    "risk_level",
    "training_topic",
    "is_raw_correct",
    "is_final_correct",
    "is_misjudge",
    "is_missjudge",
    "is_appealed",
    "is_appeal_reversed",
    "appeal_status",
    "appeal_reason",
    "comment_text",
    "qa_note",
    "inspect_type",
    "workforce_type",
    "batch_id",
    "source_file_name",
    "row_hash",
]

APPEAL_INSERT_COLUMNS = [
    "appeal_event_id",
    "biz_date",
    "appeal_time",
    "source_record_id",
    "comment_id",
    "dynamic_id",
    "account_id",
    "join_key",
    "group_name",
    "queue_name",
    "reviewer_name",
    "appeal_status",
    "appeal_result",
    "appeal_reason",
    "appeal_operator",
    "appeal_note",
    "is_reversed",
    "batch_id",
    "source_file_name",
    "row_hash",
]

QA_COLUMN_ALIASES = {
    "event_id": ["事件id", "eventid"],
    "biz_date": ["业务日期", "日期", "抽检日期", "质检日期", "质检时间", "一审时间", "qa日期"],
    "qa_time": ["质检时间", "抽检时间", "审核时间", "qa时间", "reviewtime", "质检完成时间"],
    "import_date": ["导入日期", "入仓日期"],
    "mother_biz": ["一级业务", "母业务", "业务线", "业务大类"],
    "sub_biz": ["二级业务", "子业务", "业务小类"],
    "group_name": ["组别", "团队", "组", "group", "母业务", "公司", "一审公司"],
    "queue_name": ["队列", "队列名", "队列名称", "queue", "子业务", "供应商"],
    "scene_name": ["场景", "场景名"],
    "channel_name": ["渠道", "渠道名"],
    "content_type": ["内容类型", "内容体裁"],
    "reviewer_name": ["审核人", "审核员", "reviewer", "审核账号", "一审员", "一审人员", "原始答案.operatorName", "operatorName"],
    "qa_owner_name": ["质检人", "质检员", "qa负责人", "qaowner", "抽检人"],
    "trainer_name": ["培训负责人", "培训人", "trainer"],
    "source_record_id": ["主键id", "主键ID", "源记录id", "记录id", "recordid", "sampleid", "样本id", "任务id", "objectId"],
    "comment_id": ["评论id", "评论ID", "commentid", "commentId"],
    "dynamic_id": ["动态id", "动态ID", "帖子id", "内容id", "dynamicid"],
    "account_id": ["账号id", "账号ID", "作者id", "accountid", "uid"],
    "raw_label": ["原始标签", "初判标签", "机审标签"],
    "final_label": ["最终标签", "复核标签", "终判标签"],
    "raw_judgement": ["原始判断", "初判结果", "机审结果", "一审结果", "一审结论"],
    "final_judgement": ["最终判断", "复核结果", "终判结果", "质检结果", "质检判", "质检结", "质检判断结果", "质检结果判断", "复核判断"],
    "qa_result": ["质检结果2", "qa结果", "质检判断", "判定结果", "质检结论"],
    "error_type": ["错误类型", "问题类型", "差错类型", "错误标签", "问题标签"],
    "error_level": ["错误级别", "问题级别"],
    "error_reason": ["错误原因", "问题原因", "归因", "错误分析"],
    "risk_level": ["风险等级", "风险级别"],
    "training_topic": ["培训专题", "培训主题", "训练专题", "专题"],
    "is_raw_correct": ["原始正确", "原始是否正确", "初判是否正确", "质检判断"],
    "is_final_correct": ["最终正确", "最终是否正确", "复核是否正确"],
    "is_misjudge": ["是否错判", "错判", "误判"],
    "is_missjudge": ["是否漏判", "漏判", "漏审"],
    "is_appealed": ["是否申诉", "申诉标记"],
    "is_appeal_reversed": ["是否改判", "申诉改判", "改判标记"],
    "appeal_status": ["申诉状态"],
    "appeal_reason": ["申诉原因"],
    "comment_text": ["评论文本", "文本", "内容文本", "样本文本", "文案"],
    "qa_note": ["质检备注", "备注", "qa备注"],
    "batch_id": ["批次id", "批次号"],
}

APPEAL_COLUMN_ALIASES = {
    "appeal_event_id": ["申诉事件id", "appealeventid"],
    "biz_date": ["业务日期", "日期", "申诉日期", "质检日期"],
    "appeal_time": ["申诉时间", "处理时间", "质检日期"],
    "source_record_id": ["主键id", "主键ID", "源记录id", "记录id", "recordid", "样本id", "任务id"],
    "comment_id": ["评论id", "评论ID", "commentid"],
    "dynamic_id": ["动态id", "动态ID", "帖子id", "内容id", "dynamicid"],
    "account_id": ["账号id", "账号ID", "作者id", "accountid", "uid"],
    "group_name": ["组别", "团队", "组", "一审公司", "公司", "母业务"],
    "queue_name": ["队列", "队列名", "子业务", "供应商"],
    "reviewer_name": ["审核人", "审核员", "reviewer", "一审员", "一审人员"],
    "raw_judgement": ["一审结果", "初审结果"],
    "appeal_status": ["申诉状态"],
    "appeal_result": ["申诉结果", "处理结果"],
    "appeal_reason": ["申诉理由", "申诉原因"],
    "appeal_operator": ["处理人", "申诉处理人", "operator", "申诉员A", "申诉员B"],
    "appeal_note": ["申诉备注", "质检备注", "备注"],
    "is_reversed": ["是否改判", "改判标记", "申诉是否成功"],
    "batch_id": ["批次id", "批次号"],
}

TRUE_TOKENS = {
    "1",
    "true",
    "t",
    "yes",
    "y",
    "是",
    "正确",
    "通过",
    "pass",
    "success",
    "成功",
    "已申诉",
    "已改判",
}
FALSE_TOKENS = {
    "0",
    "false",
    "f",
    "no",
    "n",
    "否",
    "错误",
    "不通过",
    "未通过",
    "fail",
    "失败",
    "未申诉",
}


@dataclass
class ImportSummary:
    dataset: str
    source_file: str
    source_rows: int
    inserted_rows: int
    dedup_rows: int
    warning_rows: int


@dataclass
class RunStats:
    run_id: str
    batch_id: str
    db_path: str
    qa_files: list[dict[str, Any]]
    appeal_files: list[dict[str, Any]]
    refreshed_marts: bool


def normalize_name(value: str) -> str:
    return re.sub(r"[\s\-_:/\\（）()\[\]【】,.]+", "", str(value).strip().lower())


def clean_text(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip()
    return normalized.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "null": pd.NA, "<NA>": pd.NA})


def parse_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.date


def parse_timestamp_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def to_boolean(series: pd.Series) -> pd.Series:
    text = clean_text(series)
    lowered = text.str.lower()
    result = pd.Series(pd.NA, index=series.index, dtype="boolean")
    result = result.mask(lowered.isin(TRUE_TOKENS), True)
    result = result.mask(lowered.isin(FALSE_TOKENS), False)
    return result


def coalesce_series(*series_list: pd.Series, dtype: str | None = None) -> pd.Series:
    if not series_list:
        raise ValueError("series_list 不能为空")

    result = series_list[0].copy()
    for series in series_list[1:]:
        result = result.combine_first(series)

    if dtype:
        return result.astype(dtype)
    return result


def keyword_flag(index: pd.Index, *series_list: pd.Series, keywords: list[str]) -> pd.Series:
    result = pd.Series(pd.NA, index=index, dtype="boolean")
    pattern = "|".join(re.escape(keyword) for keyword in keywords)
    for series in series_list:
        text = clean_text(series)
        mask = text.str.contains(pattern, na=False, case=False)
        result = result.mask(result.isna() & mask, True)
    return result


def infer_correct(index: pd.Index, *series_list: pd.Series) -> pd.Series:
    result = pd.Series(pd.NA, index=index, dtype="boolean")
    true_pattern = r"正确|通过|pass|success"
    false_pattern = r"错误|不通过|未通过|fail|驳回"

    for series in series_list:
        text = clean_text(series)
        lowered = text.str.lower()
        result = result.mask(result.isna() & lowered.isin(TRUE_TOKENS), True)
        result = result.mask(result.isna() & lowered.isin(FALSE_TOKENS), False)
        result = result.mask(result.isna() & text.str.contains(true_pattern, na=False, case=False), True)
        result = result.mask(result.isna() & text.str.contains(false_pattern, na=False, case=False), False)
    return result


def has_meaningful_text(index: pd.Index, *series_list: pd.Series) -> pd.Series:
    result = pd.Series(pd.NA, index=index, dtype="boolean")
    for series in series_list:
        text = clean_text(series)
        result = result.mask(result.isna() & text.notna(), True)
    return result


def read_table_file(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        last_error: Exception | None = None
        for encoding in ["utf-8-sig", "utf-8", "gb18030"]:
            try:
                return pd.read_csv(file_path, encoding=encoding, dtype=str)
            except Exception as exc:  # noqa: PERF203
                last_error = exc
        raise RuntimeError(f"CSV 读取失败：{file_path}，最后错误：{last_error}")

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path, dtype=str)

    if suffix == ".parquet":
        return pd.read_parquet(file_path)

    raise ValueError(f"暂不支持的文件格式：{file_path.suffix}")


def map_columns(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    normalized_source = {normalize_name(column): column for column in df.columns}
    mapped = pd.DataFrame(index=df.index)

    for target, candidate_aliases in aliases.items():
        source_column = None
        for candidate in [target, *candidate_aliases]:
            source_column = normalized_source.get(normalize_name(candidate))
            if source_column is not None:
                break
        mapped[target] = df[source_column] if source_column is not None else pd.NA

    return mapped


def build_row_hash(df: pd.DataFrame, key_columns: list[str]) -> pd.Series:
    text_frame = df[key_columns].copy()
    for column in key_columns:
        text_frame[column] = clean_text(text_frame[column]).fillna("")
    row_text = text_frame.agg("|".join, axis=1)
    return row_text.map(lambda value: hashlib.sha1(value.encode("utf-8")).hexdigest())


def build_join_key(
    source_record_id: pd.Series,
    comment_id: pd.Series,
    dynamic_id: pd.Series,
    account_id: pd.Series,
) -> pd.Series:
    source_record_id = clean_text(source_record_id)
    comment_id = clean_text(comment_id)
    dynamic_id = clean_text(dynamic_id)
    account_id = clean_text(account_id)

    join_key = pd.Series(pd.NA, index=source_record_id.index, dtype="string")
    join_key = join_key.mask(source_record_id.notna(), "record:" + source_record_id)

    comment_dynamic = comment_id.notna() & dynamic_id.notna()
    join_key = join_key.mask(join_key.isna() & comment_dynamic, "comment:" + comment_id.fillna("") + "|dynamic:" + dynamic_id.fillna(""))
    join_key = join_key.mask(join_key.isna() & comment_id.notna(), "comment:" + comment_id)
    join_key = join_key.mask(join_key.isna() & dynamic_id.notna(), "dynamic:" + dynamic_id)
    join_key = join_key.mask(join_key.isna() & account_id.notna(), "account:" + account_id)
    return join_key


def prepare_qa_frame(
    raw_df: pd.DataFrame,
    source_file_name: str,
    batch_id: str,
    import_day: date,
    inspect_type: str = "external",
    workforce_type: str = "formal",
) -> tuple[pd.DataFrame, int]:
    mapped = map_columns(raw_df, QA_COLUMN_ALIASES)
    index = mapped.index

    # 从文件名提取业务日期（优先级最高）
    biz_date_from_file = extract_date_from_filename(source_file_name)

    qa_time = parse_timestamp_series(mapped["qa_time"])

    # biz_date 优先级：文件名 > 数据列 > qa_time > 导入日期
    if biz_date_from_file:
        biz_date = pd.Series(biz_date_from_file, index=index)
    else:
        biz_date = coalesce_series(parse_date_series(mapped["biz_date"]), qa_time.dt.date, pd.Series(import_day, index=index))

    import_date = coalesce_series(parse_date_series(mapped["import_date"]), pd.Series(import_day, index=index))

    # 根据文件名识别业务线（优先级高于数据内容）
    mother_biz_from_file, sub_biz_from_file = identify_business_line(source_file_name)

    # 业务线：优先用文件名匹配，否则用数据内容
    if sub_biz_from_file != "未识别":
        mother_biz = pd.Series(mother_biz_from_file, index=index)
        sub_biz = pd.Series(sub_biz_from_file, index=index)
        # 如果文件名识别成功，group_name 使用映射后的 sub_biz
        group_name = pd.Series(sub_biz_from_file, index=index)
    else:
        mother_biz = coalesce_series(clean_text(mapped["mother_biz"]), pd.Series("未识别", index=index))
        sub_biz = coalesce_series(clean_text(mapped["sub_biz"]), pd.Series("未识别", index=index))
        group_name = coalesce_series(clean_text(mapped["group_name"]), clean_text(mapped["mother_biz"]), clean_text(mapped["sub_biz"]))
    queue_name = coalesce_series(clean_text(mapped["queue_name"]), clean_text(mapped["sub_biz"]))
    reviewer_name = clean_text(mapped["reviewer_name"])
    qa_owner_name = clean_text(mapped["qa_owner_name"])
    raw_judgement = clean_text(mapped["raw_judgement"])
    final_judgement = clean_text(mapped["final_judgement"])
    qa_result = clean_text(mapped["qa_result"])
    qa_note = clean_text(mapped["qa_note"])
    error_type = clean_text(mapped["error_type"])
    error_reason = clean_text(mapped["error_reason"])

    # ── error_type 自动推断 ──────────────────────────────────
    # 很多 CSV 没有独立的"错误类型"列，错判/漏判信息散落在
    # "质检判断"、"质检结果"、"一审结果"等字段中。
    # 在后续确定 is_misjudge / is_missjudge 后，会再做一次回填。
    # 这里先从文本字段做初步推断。
    _infer_et_sources = [raw_judgement, final_judgement, qa_result, qa_note]
    _infer_et = pd.Series(pd.NA, index=index, dtype="string")
    for _src in _infer_et_sources:
        _has_cuopan = _src.str.contains(r"错判|误判", na=False, case=False)
        _has_loupan = _src.str.contains(r"漏判|漏审", na=False, case=False)
        _infer_et = _infer_et.mask(_infer_et.isna() & _has_cuopan, "错判")
        _infer_et = _infer_et.mask(_infer_et.isna() & _has_loupan, "漏判")
    # 合并：优先用 CSV 原始 error_type，其次用推断值
    error_type = error_type.fillna(_infer_et)

    # 质检判断字段：正确/漏判/错判
    qa_judgement = clean_text(mapped["is_raw_correct"])
    
    # 从质检判断字段提取漏判/错判标记
    is_misjudge_from_judgement = qa_judgement.str.contains("错判|误判", na=False, case=False)
    is_missjudge_from_judgement = qa_judgement.str.contains("漏判|漏审", na=False, case=False)
    
    is_raw_correct = coalesce_series(
        to_boolean(mapped["is_raw_correct"]),
        ~is_misjudge_from_judgement & ~is_missjudge_from_judgement,  # 不是错判也不是漏判，就是正确
        infer_correct(index, mapped["is_raw_correct"], mapped["final_judgement"]),
        dtype="boolean",
    ).fillna(False)
    is_final_correct = coalesce_series(
        to_boolean(mapped["is_final_correct"]),
        infer_correct(index, mapped["final_judgement"], mapped["final_label"]),
        is_raw_correct,
        dtype="boolean",
    ).fillna(False)
    is_misjudge = coalesce_series(
        to_boolean(mapped["is_misjudge"]),
        is_misjudge_from_judgement,  # 优先从质检判断字段提取
        keyword_flag(index, error_type, error_reason, qa_result, qa_note, keywords=["错判", "误判"]),
        dtype="boolean",
    ).fillna(False)
    is_missjudge = coalesce_series(
        to_boolean(mapped["is_missjudge"]),
        is_missjudge_from_judgement,  # 优先从质检判断字段提取
        keyword_flag(index, error_type, error_reason, qa_result, qa_note, keywords=["漏判", "漏审"]),
        dtype="boolean",
    ).fillna(False)
    is_appealed = coalesce_series(
        to_boolean(mapped["is_appealed"]),
        has_meaningful_text(index, mapped["appeal_status"], mapped["appeal_reason"]),
        dtype="boolean",
    ).fillna(False)
    is_appeal_reversed = coalesce_series(
        to_boolean(mapped["is_appeal_reversed"]),
        keyword_flag(index, mapped["appeal_status"], mapped["qa_result"], keywords=["改判", "申诉成功"]),
        dtype="boolean",
    ).fillna(False)

    # ── error_type 最终回填（基于已确定的 is_misjudge / is_missjudge） ──
    # 对于仍为空的 error_type，根据判定结果补充分类
    _still_empty = error_type.isna()
    error_type = error_type.mask(_still_empty & is_misjudge, "错判")
    error_type = error_type.mask(error_type.isna() & is_missjudge, "漏判")
    # 对于不正确但既非错判也非漏判的记录，根据一审标签推断：
    # 一审=正常/空 → 漏判（漏掉了违规内容）；一审=具体违规标签 → 错判（误判为违规）
    _is_error_no_type = error_type.isna() & ~is_raw_correct
    _rj_is_normal = raw_judgement.str.lower().isin(["正常", "通过", "pass", ""]) | raw_judgement.isna()
    error_type = error_type.mask(_is_error_no_type & _rj_is_normal, "漏判")
    error_type = error_type.mask(_is_error_no_type & ~_rj_is_normal, "错判")

    prepared = pd.DataFrame(
        {
            "biz_date": biz_date,
            "qa_time": qa_time,
            "import_date": import_date,
            "mother_biz": mother_biz,  # 用文件名匹配的业务线
            "sub_biz": sub_biz,        # 用文件名匹配的业务线
            "group_name": group_name,
            "queue_name": queue_name,
            "scene_name": clean_text(mapped["scene_name"]),
            "channel_name": clean_text(mapped["channel_name"]),
            "content_type": clean_text(mapped["content_type"]),
            "reviewer_name": reviewer_name,
            "qa_owner_name": qa_owner_name,
            "trainer_name": clean_text(mapped["trainer_name"]),
            "source_record_id": clean_text(mapped["source_record_id"]),
            "comment_id": clean_text(mapped["comment_id"]),
            "dynamic_id": clean_text(mapped["dynamic_id"]),
            "account_id": clean_text(mapped["account_id"]),
            "raw_label": clean_text(mapped["raw_label"]),
            "final_label": clean_text(mapped["final_label"]),
            "raw_judgement": raw_judgement,
            "final_judgement": final_judgement,
            "qa_result": qa_result,
            "error_type": error_type,
            "error_level": clean_text(mapped["error_level"]),
            "error_reason": error_reason,
            "risk_level": clean_text(mapped["risk_level"]),
            "training_topic": clean_text(mapped["training_topic"]),
            "is_raw_correct": is_raw_correct,
            "is_final_correct": is_final_correct,
            "is_misjudge": is_misjudge,
            "is_missjudge": is_missjudge,
            "is_appealed": is_appealed,
            "is_appeal_reversed": is_appeal_reversed,
            "appeal_status": clean_text(mapped["appeal_status"]),
            "appeal_reason": clean_text(mapped["appeal_reason"]),
            "comment_text": clean_text(mapped["comment_text"]),
            "qa_note": qa_note,
            "inspect_type": inspect_type,
            "workforce_type": workforce_type,
            "batch_id": clean_text(mapped["batch_id"]).fillna(batch_id),
            "source_file_name": source_file_name,
        }
    )
    prepared["join_key"] = build_join_key(
        prepared["source_record_id"],
        prepared["comment_id"],
        prepared["dynamic_id"],
        prepared["account_id"],
    )
    prepared["row_hash"] = build_row_hash(
        prepared,
        [
            "biz_date",
            "qa_time",  # 新增：质检时间有较高唯一性
            "group_name",
            "queue_name",
            "reviewer_name",
            "source_record_id",
            "comment_id",
            "dynamic_id",
            "account_id",  # 新增：账号类业务的主键
            "raw_label",
            "final_label",
            "qa_result",
            "error_type",
            "qa_note",
            "comment_text",  # 新增：用评论文本区分没有主键的行
            "source_file_name",
        ],
    )
    event_id_seed = coalesce_series(
        clean_text(mapped["event_id"]),
        prepared["source_record_id"],
        prepared["comment_id"],
        prepared["dynamic_id"],
        prepared["account_id"],
    )
    prepared["event_id"] = clean_text(event_id_seed).fillna("qa-" + prepared["row_hash"].str[:16])

    warning_rows = int(parse_date_series(mapped["biz_date"]).isna().sum() + prepared["join_key"].isna().sum())
    return prepared[QA_INSERT_COLUMNS], warning_rows


def prepare_appeal_frame(raw_df: pd.DataFrame, source_file_name: str, batch_id: str, import_day: date) -> tuple[pd.DataFrame, int]:
    mapped = map_columns(raw_df, APPEAL_COLUMN_ALIASES)
    index = mapped.index

    # 从文件名提取业务日期（优先级最高）
    biz_date_from_file = extract_date_from_filename(source_file_name)

    appeal_time = parse_timestamp_series(mapped["appeal_time"])

    # biz_date 优先级：文件名 > 数据列 > appeal_time > 导入日期
    if biz_date_from_file:
        biz_date = pd.Series(biz_date_from_file, index=index)
    else:
        biz_date = coalesce_series(parse_date_series(mapped["biz_date"]), appeal_time.dt.date, pd.Series(import_day, index=index))

    source_record_id = clean_text(mapped["source_record_id"])
    comment_id = clean_text(mapped["comment_id"])
    dynamic_id = clean_text(mapped["dynamic_id"])
    account_id = clean_text(mapped["account_id"])
    appeal_result = clean_text(mapped["appeal_result"])
    raw_judgement = clean_text(mapped["raw_judgement"])
    appeal_status = clean_text(mapped["appeal_status"])

    is_reversed = coalesce_series(
        to_boolean(mapped["is_reversed"]),
        (raw_judgement.notna() & appeal_result.notna() & (raw_judgement.str.strip() != appeal_result.str.strip())).astype("boolean"),
        keyword_flag(index, mapped["appeal_status"], mapped["appeal_result"], keywords=["改判", "申诉成功"]),
        dtype="boolean",
    ).fillna(False)

    prepared = pd.DataFrame(
        {
            "biz_date": biz_date,
            "appeal_time": appeal_time,
            "source_record_id": source_record_id,
            "comment_id": comment_id,
            "dynamic_id": dynamic_id,
            "account_id": account_id,
            "group_name": coalesce_series(clean_text(mapped["group_name"]), clean_text(mapped["queue_name"])),
            "queue_name": clean_text(mapped["queue_name"]),
            "reviewer_name": clean_text(mapped["reviewer_name"]),
            "appeal_status": appeal_status,
            "appeal_result": appeal_result,
            "appeal_reason": clean_text(mapped["appeal_reason"]),
            "appeal_operator": clean_text(mapped["appeal_operator"]),
            "appeal_note": clean_text(mapped["appeal_note"]),
            "is_reversed": is_reversed,
            "batch_id": clean_text(mapped["batch_id"]).fillna(batch_id),
            "source_file_name": source_file_name,
        }
    )
    prepared["join_key"] = build_join_key(
        prepared["source_record_id"],
        prepared["comment_id"],
        prepared["dynamic_id"],
        prepared["account_id"],
    )
    prepared["row_hash"] = build_row_hash(
        prepared,
        [
            "biz_date",
            "source_record_id",
            "comment_id",
            "dynamic_id",
            "account_id",
            "appeal_status",
            "appeal_result",
            "appeal_reason",
            "source_file_name",
        ],
    )
    event_id_seed = coalesce_series(
        clean_text(mapped["appeal_event_id"]),
        prepared["source_record_id"],
        prepared["comment_id"],
        prepared["dynamic_id"],
        prepared["account_id"],
    )
    prepared["appeal_event_id"] = clean_text(event_id_seed).fillna("appeal-" + prepared["row_hash"].str[:16])

    warning_rows = int(parse_date_series(mapped["biz_date"]).isna().sum() + prepared["join_key"].isna().sum())
    return prepared[APPEAL_INSERT_COLUMNS], warning_rows


def insert_new_rows(
    conn: Any,
    table_name: str,
    insert_columns: list[str],
    stage_df: pd.DataFrame,
) -> tuple[int, int]:
    """插入数据到 fact 表，使用 INSERT IGNORE 保证重复上传时的幂等性。

    - 遇到主键/唯一键冲突时跳过该行（而不是整批失败）
    - 返回 (实际插入行数, 去重跳过行数)
    - 文件级去重仍由 fact_file_dedup 表控制，防止同一文件被完整重复处理
    """
    if stage_df.empty:
        return 0, 0

    source_rows = len(stage_df)
    # 使用 INSERT IGNORE，重复主键自动跳过
    inserted_rows = conn.insert_dataframe(table_name, stage_df, ignore_duplicates=True)
    dedup_rows = max(source_rows - inserted_rows, 0)
    return inserted_rows, dedup_rows


def write_etl_log(
    conn,
    *,
    run_id: str,
    job_name: str,
    source_rows: int,
    inserted_rows: int,
    dedup_rows: int,
    warning_rows: int,
    run_status: str,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO etl_run_log (
            run_id,
            job_name,
            start_time,
            end_time,
            run_status,
            source_rows,
            inserted_rows,
            dedup_rows,
            warning_rows,
            error_message
        )
        VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s)
        """,
        [run_id, job_name, run_status, source_rows, inserted_rows, dedup_rows, warning_rows, error_message],
    )


def write_upload_log(
    conn,
    *,
    upload_id: str,
    file_name: str,
    file_type: str,
    file_size_bytes: int,
    source_rows: int,
    inserted_rows: int,
    dedup_rows: int,
    business_line: str,
    upload_status: str,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO fact_upload_log (
            upload_id,
            file_name,
            file_type,
            file_size_bytes,
            source_rows,
            inserted_rows,
            dedup_rows,
            business_line,
            upload_status,
            error_message
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [upload_id, file_name, file_type, file_size_bytes, source_rows, inserted_rows, dedup_rows, business_line, upload_status, error_message],
    )


def check_file_duplicate(
    conn,
    file_hash: str,
    file_name: str,
    file_type: str,
    upload_id: str,
) -> bool:
    """检查文件是否已上传过（基于文件内容哈希）。

    Returns:
        True: 已上传过（跳过）
        False: 未上传过（继续导入）
    """
    result = conn.fetch_one(
        "SELECT file_hash, upload_count FROM fact_file_dedup WHERE file_hash = %s",
        [file_hash]
    )

    if result:
        conn.execute(
            "UPDATE fact_file_dedup SET upload_count = upload_count + 1 WHERE file_hash = %s",
            [file_hash]
        )
        return True

    conn.execute(
        """
        INSERT INTO fact_file_dedup (file_hash, file_name, file_type, first_upload_time, first_upload_id, upload_count)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, 1)
        """,
        [file_hash, file_name, file_type, upload_id]
    )
    return False


def compute_file_hash(file_path: Path) -> str:
    """计算文件内容哈希（用于去重）。"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def import_dataset(
    conn,
    *,
    dataset: str,
    file_path: Path,
    source_name: str,
    batch_id: str,
    import_day: date,
    upload_id: str,
    skip_dedup: bool = False,
    inspect_type: str | None = None,
    workforce_type: str | None = None,
) -> ImportSummary:
    # 黑名单拦截：命中的文件名直接拒绝入库（不属于看板考核范围）
    is_blacklist, hit_keyword = is_blacklisted_filename(source_name)
    if is_blacklist:
        file_size = file_path.stat().st_size if file_path.exists() else 0
        write_upload_log(
            conn,
            upload_id=upload_id,
            file_name=source_name,
            file_type=dataset,
            file_size_bytes=file_size,
            source_rows=0,
            inserted_rows=0,
            dedup_rows=0,
            business_line="黑名单",
            upload_status="skipped",
            error_message=f"文件名命中黑名单关键词「{hit_keyword}」，非看板考核范围，已跳过入库",
        )
        return ImportSummary(dataset, str(file_path), 0, 0, 0, 0)

    raw_df = read_table_file(file_path)
    file_size = file_path.stat().st_size if file_path.exists() else 0
    file_hash = compute_file_hash(file_path) if skip_dedup is False else ""
    
    # 自动检测 inspect_type 和 workforce_type（如果未显式指定）
    effective_inspect = inspect_type or detect_inspect_type(source_name)
    effective_workforce = workforce_type or detect_workforce_type(source_name)
    
    # 去重检测
    if not skip_dedup and check_file_duplicate(conn, file_hash, source_name, dataset, upload_id):
        # 文件已上传过，返回跳过信息
        mother_biz, sub_biz = identify_business_line(source_name)
        business_line = sub_biz if sub_biz != "未识别" else mother_biz
        write_upload_log(
            conn,
            upload_id=upload_id,
            file_name=source_name,
            file_type=dataset,
            file_size_bytes=file_size,
            source_rows=len(raw_df),
            inserted_rows=0,
            dedup_rows=len(raw_df),
            business_line=business_line,
            upload_status="skipped",
            error_message="文件内容已存在，跳过重复导入"
        )
        return ImportSummary(dataset, str(file_path), len(raw_df), 0, len(raw_df), 0)
    
    if dataset == "qa":
        prepared_df, warning_rows = prepare_qa_frame(
            raw_df, source_name, batch_id, import_day,
            inspect_type=effective_inspect,
            workforce_type=effective_workforce,
        )
        inserted_rows, dedup_rows = insert_new_rows(conn, "fact_qa_event", QA_INSERT_COLUMNS, prepared_df)
        mother_biz, sub_biz = identify_business_line(source_name)
        business_line = sub_biz if sub_biz != "未识别" else mother_biz
        write_upload_log(
            conn,
            upload_id=upload_id,
            file_name=source_name,
            file_type="qa",
            file_size_bytes=file_size,
            source_rows=len(prepared_df),
            inserted_rows=inserted_rows,
            dedup_rows=dedup_rows,
            business_line=business_line,
            upload_status="success"
        )
        return ImportSummary("qa", str(file_path), len(prepared_df), inserted_rows, dedup_rows, warning_rows)

    prepared_df, warning_rows = prepare_appeal_frame(raw_df, source_name, batch_id, import_day)
    inserted_rows, dedup_rows = insert_new_rows(conn, "fact_appeal_event", APPEAL_INSERT_COLUMNS, prepared_df)
    write_upload_log(
        conn,
        upload_id=upload_id,
        file_name=source_name,
        file_type="appeal",
        file_size_bytes=file_size,
        source_rows=len(prepared_df),
        inserted_rows=inserted_rows,
        dedup_rows=dedup_rows,
        business_line="",
        upload_status="success"
    )
    return ImportSummary("appeal", str(file_path), len(prepared_df), inserted_rows, dedup_rows, warning_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把质检/申诉明细文件导入 TiDB fact 表，并可选刷新 mart。")
    parser.add_argument("--qa-file", dest="qa_files", action="append", default=[], help="质检明细文件路径，可重复传多个")
    parser.add_argument("--appeal-file", dest="appeal_files", action="append", default=[], help="申诉明细文件路径，可重复传多个")
    parser.add_argument("--source-name", dest="source_names", action="append", default=[], help="原始文件名（用于业务线识别），与 --qa-file/--appeal-file 一一对应")
    parser.add_argument("--db-path", default=None, help="已废弃，保留兼容性")
    parser.add_argument("--batch-id", default=None, help="本次导入批次号；不传则自动生成")
    parser.add_argument("--skip-refresh", action="store_true", help="只导入 fact，不刷新 mart / 规则维表")
    parser.add_argument("--skip-dedup", action="store_true", help="跳过文件级去重检测（默认启用去重）")
    parser.add_argument("--inspect-type", choices=["external", "internal"], default=None, help="强制指定检类：external(外检) 或 internal(内检)，不传则自动检测")
    parser.add_argument("--workforce-type", choices=["formal", "newcomer"], default=None, help="强制指定人力类型：formal(正式) 或 newcomer(新人)，不传则自动检测")
    return parser.parse_args()


def ensure_files_exist(paths: list[str]) -> list[Path]:
    resolved = [Path(path).expanduser().resolve() for path in paths]
    missing = [str(path) for path in resolved if not path.exists()]
    if missing:
        raise FileNotFoundError(f"以下文件不存在：{missing}")
    return resolved


def main() -> None:
    args = parse_args()
    if not args.qa_files and not args.appeal_files:
        raise SystemExit("至少传一个 --qa-file 或 --appeal-file")

    qa_files = ensure_files_exist(args.qa_files)
    appeal_files = ensure_files_exist(args.appeal_files)
    source_names = args.source_names if args.source_names else None
    batch_id = args.batch_id or f"batch_{date.today():%Y%m%d}_{uuid.uuid4().hex[:8]}"
    run_id = uuid.uuid4().hex
    repo = DashboardRepository()
    repo.initialize_schema()

    qa_summaries: list[ImportSummary] = []
    appeal_summaries: list[ImportSummary] = []

    conn = repo.connect()
    for idx, file_path in enumerate(qa_files):
        # 获取原始文件名（用于业务线识别）
        source_name = source_names[idx] if source_names and idx < len(source_names) else file_path.name
        upload_id = f"upload_{run_id}_qa_{idx}"
        try:
            summary = import_dataset(
                conn, dataset="qa", file_path=file_path, source_name=source_name,
                batch_id=batch_id, import_day=date.today(), upload_id=upload_id,
                skip_dedup=args.skip_dedup,
                inspect_type=args.inspect_type,
                workforce_type=args.workforce_type,
            )
            qa_summaries.append(summary)
            write_etl_log(
                conn,
                run_id=f"{run_id}_qa_{len(qa_summaries)}",
                job_name=f"import_fact_qa_event:{source_name}",
                source_rows=summary.source_rows,
                inserted_rows=summary.inserted_rows,
                dedup_rows=summary.dedup_rows,
                warning_rows=summary.warning_rows,
                run_status="success" if summary.inserted_rows > 0 or summary.source_rows == 0 else "skipped",
            )
        except Exception as exc:
            write_etl_log(
                conn,
                run_id=f"{run_id}_qa_fail_{len(qa_summaries) + 1}",
                job_name=f"import_fact_qa_event:{source_name}",
                source_rows=0,
                inserted_rows=0,
                dedup_rows=0,
                warning_rows=0,
                run_status="failed",
                error_message=str(exc),
            )
            write_upload_log(
                conn,
                upload_id=upload_id,
                file_name=source_name,
                file_type="qa",
                file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                source_rows=0,
                inserted_rows=0,
                dedup_rows=0,
                business_line="",
                upload_status="failed",
                error_message=str(exc)
            )
            raise

    for idx, file_path in enumerate(appeal_files):
        source_name = source_names[len(qa_files) + idx] if source_names and (len(qa_files) + idx) < len(source_names) else file_path.name
        upload_id = f"upload_{run_id}_appeal_{idx}"
        try:
            summary = import_dataset(
                conn, dataset="appeal", file_path=file_path, source_name=source_name,
                batch_id=batch_id, import_day=date.today(), upload_id=upload_id,
                skip_dedup=args.skip_dedup
            )
            appeal_summaries.append(summary)
            write_etl_log(
                conn,
                run_id=f"{run_id}_appeal_{len(appeal_summaries)}",
                job_name=f"import_fact_appeal_event:{source_name}",
                source_rows=summary.source_rows,
                inserted_rows=summary.inserted_rows,
                dedup_rows=summary.dedup_rows,
                warning_rows=summary.warning_rows,
                run_status="success" if summary.inserted_rows > 0 or summary.source_rows == 0 else "skipped",
            )
        except Exception as exc:
            write_etl_log(
                conn,
                run_id=f"{run_id}_appeal_fail_{len(appeal_summaries) + 1}",
                job_name=f"import_fact_appeal_event:{file_path.name}",
                source_rows=0,
                inserted_rows=0,
                dedup_rows=0,
                warning_rows=0,
                run_status="failed",
                error_message=str(exc),
            )
            write_upload_log(
                conn,
                upload_id=upload_id,
                file_name=source_name,
                file_type="appeal",
                file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                source_rows=0,
                inserted_rows=0,
                dedup_rows=0,
                business_line="",
                upload_status="failed",
                error_message=str(exc)
            )
            raise

    refreshed_marts = False
    if not args.skip_refresh:
        repo.initialize_schema()
        refreshed_marts = True

    stats = RunStats(
        run_id=run_id,
        batch_id=batch_id,
        db_path="tidb",
        qa_files=[asdict(item) for item in qa_summaries],
        appeal_files=[asdict(item) for item in appeal_summaries],
        refreshed_marts=refreshed_marts,
    )
    print(json.dumps(asdict(stats), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
