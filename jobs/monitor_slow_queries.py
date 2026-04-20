"""慢查询监控脚本 - 定时抓取 TiDB 慢查询日志并生成报告。

功能：
1. 查询 information_schema.statements_summary 中的慢查询
2. 按平均延迟、执行次数排序
3. 生成可读的 Markdown 报告
4. 可选：发送告警到企业微信/邮件

运行方式：
    # 查询最近的慢查询（默认阈值 500ms）
    python3 jobs/monitor_slow_queries.py
    
    # 自定义阈值
    python3 jobs/monitor_slow_queries.py --threshold 800
    
    # 生成报告到文件
    python3 jobs/monitor_slow_queries.py --output deliverables/slow_queries_report.md
    
    # 只显示 Top 10
    python3 jobs/monitor_slow_queries.py --limit 10
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from storage.tidb_manager import TiDBManager
from utils.logger import get_logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_log = get_logger("monitor.slow_queries")


def fetch_slow_queries(threshold_ms: int = 500, limit: int = 50) -> pd.DataFrame:
    """从 TiDB 抓取慢查询统计。
    
    Args:
        threshold_ms: 慢查询阈值（毫秒）
        limit: 返回结果数量
        
    Returns:
        包含慢查询信息的 DataFrame
    """
    manager = TiDBManager()
    
    sql = """
        SELECT 
            DIGEST_TEXT as query_pattern,
            ROUND(AVG_LATENCY / 1000000, 2) as avg_latency_ms,
            ROUND(MAX_LATENCY / 1000000, 2) as max_latency_ms,
            ROUND(MIN_LATENCY / 1000000, 2) as min_latency_ms,
            EXEC_COUNT as exec_count,
            ROUND(SUM_LATENCY / 1000000, 2) as total_latency_ms,
            ROUND(AVG_MEM / 1024 / 1024, 2) as avg_mem_mb,
            FIRST_SEEN,
            LAST_SEEN
        FROM information_schema.statements_summary
        WHERE AVG_LATENCY / 1000000 > %s
          AND DIGEST_TEXT NOT LIKE '%%information_schema%%'
          AND DIGEST_TEXT NOT LIKE '%%SHOW%%'
        ORDER BY AVG_LATENCY DESC
        LIMIT %s
    """
    
    with manager.get_connection() as conn:
        df = pd.read_sql(sql, conn, params=(threshold_ms, limit))
    
    _log.info(f"抓取到 {len(df)} 条慢查询（阈值 {threshold_ms}ms）")
    return df


def generate_markdown_report(df: pd.DataFrame, threshold_ms: int) -> str:
    """生成 Markdown 格式的慢查询报告。
    
    Args:
        df: 慢查询数据
        threshold_ms: 阈值
        
    Returns:
        Markdown 格式的报告文本
    """
    if df.empty:
        return f"# 慢查询报告\n\n✅ 未发现慢查询（阈值 {threshold_ms}ms）\n"
    
    report = f"""# 慢查询报告

**生成时间：** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**阈值：** {threshold_ms}ms  
**慢查询数量：** {len(df)}

---

## 📊 Top 慢查询（按平均延迟排序）

| 排名 | 平均延迟 | 最大延迟 | 执行次数 | 总耗时 | 平均内存 | 首次出现 | 最后出现 |
|------|----------|----------|----------|--------|----------|----------|----------|
"""
    
    for i, row in df.iterrows():
        rank = i + 1
        report += (
            f"| {rank} | {row['avg_latency_ms']:.2f}ms | {row['max_latency_ms']:.2f}ms | "
            f"{row['exec_count']} | {row['total_latency_ms']:.2f}ms | {row['avg_mem_mb']:.2f}MB | "
            f"{row['FIRST_SEEN']} | {row['LAST_SEEN']} |\n"
        )
    
    report += "\n---\n\n## 📝 查询详情\n\n"
    
    for i, row in df.iterrows():
        rank = i + 1
        query = row['query_pattern'][:500]  # 截断过长的查询
        report += f"""
### {rank}. 查询 #{rank}

**平均延迟：** {row['avg_latency_ms']:.2f}ms  
**执行次数：** {row['exec_count']}  
**最后出现：** {row['LAST_SEEN']}

```sql
{query}
```

---
"""
    
    report += "\n## 💡 优化建议\n\n"
    report += """
1. **检查索引覆盖**：查询是否命中了合适的索引？
   ```sql
   EXPLAIN SELECT ...
   ```

2. **避免全表扫描**：WHERE 条件是否能使用索引？

3. **减少返回列数**：只 SELECT 需要的列，避免 `SELECT *`

4. **分页优化**：大数据量分页使用 `WHERE id > ?` 代替 `OFFSET`

5. **缓存热点数据**：高频查询的结果可以缓存 5 分钟

6. **查询改写**：复杂 JOIN 可以拆分为多次查询 + 应用层组装
"""
    
    return report


def send_alert(report: str, threshold_ms: int, count: int) -> None:
    """发送慢查询告警（可选）。
    
    Args:
        report: 报告内容
        threshold_ms: 阈值
        count: 慢查询数量
    """
    # TODO: 集成企业微信/邮件告警
    # 示例：
    # if count > 10:
    #     send_wecom_alert(f"⚠️  发现 {count} 个慢查询！阈值 {threshold_ms}ms")
    pass


def main():
    parser = argparse.ArgumentParser(description="TiDB 慢查询监控工具")
    parser.add_argument(
        "--threshold",
        type=int,
        default=500,
        help="慢查询阈值（毫秒），默认 500ms"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="返回结果数量，默认 50"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出报告到文件（Markdown 格式）"
    )
    parser.add_argument(
        "--alert",
        action="store_true",
        help="发送告警到企业微信（需配置）"
    )
    
    args = parser.parse_args()
    
    # 抓取慢查询
    df = fetch_slow_queries(threshold_ms=args.threshold, limit=args.limit)
    
    # 生成报告
    report = generate_markdown_report(df, threshold_ms=args.threshold)
    
    # 输出到控制台
    print(report)
    
    # 保存到文件
    if args.output:
        output_path = PROJECT_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        _log.info(f"报告已保存到 {output_path}")
    
    # 发送告警
    if args.alert and len(df) > 0:
        send_alert(report, threshold_ms=args.threshold, count=len(df))
    
    # 返回状态码
    if len(df) > 10:
        _log.warning(f"⚠️  发现 {len(df)} 个慢查询，建议优化！")
        return 1
    elif len(df) > 0:
        _log.info(f"✅ 发现 {len(df)} 个慢查询，性能尚可")
        return 0
    else:
        _log.info("✅ 未发现慢查询，性能良好")
        return 0


if __name__ == "__main__":
    exit(main())
