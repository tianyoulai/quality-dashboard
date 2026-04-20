"""数据库连接池监控 - 定时检查 TiDB 连接池健康状态。

功能：
1. 监控连接池使用情况（活跃连接数 / 总连接数）
2. 检测连接泄漏（长时间未释放的连接）
3. 检测连接池耗尽风险
4. 生成监控报告

运行方式：
    # 实时监控（输出到控制台）
    python3 jobs/monitor_connection_pool.py
    
    # 生成报告到文件
    python3 jobs/monitor_connection_pool.py --output deliverables/pool_status.json
    
    # 设置告警阈值（连接使用率超过 80% 时告警）
    python3 jobs/monitor_connection_pool.py --threshold 0.8
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from storage.tidb_manager import TiDBManager
from utils.logger import get_logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_log = get_logger("monitor.connection_pool")


def get_connection_pool_status(manager: TiDBManager) -> dict[str, any]:
    """获取连接池状态信息。
    
    Returns:
        包含连接池状态的字典
    """
    pool = manager._ensure_pool()
    
    # 连接池配置信息
    pool_size = pool._pool_size
    pool_name = pool._pool_name
    
    # 当前活跃连接数（通过内部状态获取）
    # 注意：mysql-connector-python 的连接池实现比较简单，
    # 没有直接暴露活跃连接数的 API，我们通过间接方式估算
    try:
        # 尝试获取一个连接，测试池是否可用
        conn = pool.get_connection()
        conn.close()
        pool_available = True
    except Exception as e:
        _log.error(f"连接池不可用: {e}")
        pool_available = False
    
    # 从 TiDB 查询当前会话数（更准确的方式）
    try:
        with manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_connections,
                    SUM(CASE WHEN COMMAND != 'Sleep' THEN 1 ELSE 0 END) as active_connections
                FROM information_schema.PROCESSLIST
                WHERE USER = %s
            """, (manager.config.user,))
            row = cursor.fetchone()
            total_connections = row[0] if row else 0
            active_connections = row[1] if row else 0
    except Exception as e:
        _log.warning(f"无法查询会话数: {e}")
        total_connections = 0
        active_connections = 0
    
    usage_ratio = active_connections / pool_size if pool_size > 0 else 0
    
    return {
        "pool_name": pool_name,
        "pool_size": pool_size,
        "total_connections": total_connections,
        "active_connections": active_connections,
        "usage_ratio": round(usage_ratio, 2),
        "pool_available": pool_available,
        "timestamp": datetime.now().isoformat(),
    }


def check_long_running_queries(manager: TiDBManager, threshold_seconds: int = 60) -> list[dict]:
    """检查长时间运行的查询（可能是连接泄漏）。
    
    Args:
        manager: TiDB 管理器
        threshold_seconds: 超过多少秒算慢查询
        
    Returns:
        长时间运行的查询列表
    """
    try:
        with manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    ID as session_id,
                    USER as user,
                    DB as database_name,
                    COMMAND,
                    TIME as duration_seconds,
                    STATE,
                    INFO as query_text
                FROM information_schema.PROCESSLIST
                WHERE USER = %s
                  AND TIME > %s
                  AND COMMAND != 'Sleep'
                ORDER BY TIME DESC
            """, (manager.config.user, threshold_seconds))
            results = cursor.fetchall()
            return results
    except Exception as e:
        _log.warning(f"无法查询长时间运行的查询: {e}")
        return []


def generate_report(
    status: dict,
    long_queries: list[dict],
    threshold: float
) -> dict:
    """生成监控报告。
    
    Args:
        status: 连接池状态
        long_queries: 长时间运行的查询
        threshold: 告警阈值
        
    Returns:
        报告字典
    """
    # 判断是否需要告警
    alerts = []
    
    if not status["pool_available"]:
        alerts.append({
            "level": "ERROR",
            "message": "连接池不可用！",
            "suggestion": "检查数据库连接配置和网络"
        })
    
    if status["usage_ratio"] >= threshold:
        alerts.append({
            "level": "WARNING",
            "message": f"连接使用率过高: {status['usage_ratio']*100:.1f}%",
            "suggestion": "考虑增加连接池大小或优化查询"
        })
    
    if len(long_queries) > 0:
        alerts.append({
            "level": "WARNING",
            "message": f"发现 {len(long_queries)} 个长时间运行的查询",
            "suggestion": "检查是否有连接泄漏或慢查询"
        })
    
    return {
        "summary": {
            "pool_status": "healthy" if len(alerts) == 0 else "warning",
            "alert_count": len(alerts),
        },
        "pool_status": status,
        "long_running_queries": long_queries[:10],  # 只显示前 10 个
        "alerts": alerts,
        "timestamp": datetime.now().isoformat(),
    }


def print_report(report: dict) -> None:
    """打印报告到控制台。"""
    print("\n" + "="*60)
    print("📊 数据库连接池监控报告")
    print("="*60)
    
    status = report["pool_status"]
    print(f"\n🔌 连接池状态:")
    print(f"  - 连接池名称: {status['pool_name']}")
    print(f"  - 最大连接数: {status['pool_size']}")
    print(f"  - 当前总连接: {status['total_connections']}")
    print(f"  - 活跃连接数: {status['active_connections']}")
    print(f"  - 使用率: {status['usage_ratio']*100:.1f}%")
    print(f"  - 连接池可用: {'✅ 是' if status['pool_available'] else '❌ 否'}")
    
    if report["alerts"]:
        print(f"\n⚠️  告警 ({len(report['alerts'])} 条):")
        for alert in report["alerts"]:
            icon = "🔴" if alert["level"] == "ERROR" else "🟡"
            print(f"  {icon} [{alert['level']}] {alert['message']}")
            print(f"     建议: {alert['suggestion']}")
    else:
        print(f"\n✅ 无告警，连接池运行正常")
    
    if report["long_running_queries"]:
        print(f"\n🐌 长时间运行的查询:")
        for i, query in enumerate(report["long_running_queries"], 1):
            print(f"  {i}. 会话 {query['session_id']}: {query['duration_seconds']}秒")
            print(f"     状态: {query['STATE']}")
            print(f"     查询: {query['query_text'][:100]}...")
    
    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="数据库连接池监控工具")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="连接使用率告警阈值（0-1），默认 0.8（80%%）"
    )
    parser.add_argument(
        "--slow-query-threshold",
        type=int,
        default=60,
        help="慢查询阈值（秒），默认 60 秒"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出报告到文件（JSON 格式）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="监控间隔（秒），设置后会持续监控，默认 0（只执行一次）"
    )
    
    args = parser.parse_args()
    
    manager = TiDBManager()
    
    while True:
        try:
            # 获取连接池状态
            status = get_connection_pool_status(manager)
            
            # 检查长时间运行的查询
            long_queries = check_long_running_queries(
                manager,
                threshold_seconds=args.slow_query_threshold
            )
            
            # 生成报告
            report = generate_report(status, long_queries, args.threshold)
            
            # 打印到控制台
            print_report(report)
            
            # 保存到文件
            if args.output:
                output_path = PROJECT_ROOT / args.output
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                _log.info(f"报告已保存到 {output_path}")
            
            # 如果设置了间隔，等待后继续监控
            if args.interval > 0:
                time.sleep(args.interval)
            else:
                break
                
        except KeyboardInterrupt:
            print("\n监控已停止")
            break
        except Exception as e:
            _log.error(f"监控失败: {e}")
            if args.interval == 0:
                return 1
            time.sleep(args.interval)
    
    # 返回状态码
    if report["alerts"]:
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
