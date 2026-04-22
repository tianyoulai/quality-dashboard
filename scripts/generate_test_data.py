#!/usr/bin/env python3
"""
快速测试数据生成器 - 为Agent查询功能准备Mock数据

生成今日（2026-04-21）的测试数据，验证Agent查询功能。
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from storage.tidb_manager import TiDBManager


def generate_test_data():
    """生成测试数据"""
    db = TiDBManager()
    today = datetime.now().strftime("%Y-%m-%d")
    
    print(f"📊 开始生成 {today} 的测试数据...")
    
    # 测试数据
    test_records = [
        # 队列A：正确率92%
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "张三", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "张三", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "李四", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "李四", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "李四", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "张三", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "张三", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "张三", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "李四", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "李四", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "张三", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "张三", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "李四", "error_type": "违规引流", "is_final_correct": 0, "is_misjudge": 1, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "李四", "error_type": "低质导流", "is_final_correct": 0, "is_misjudge": 1, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列A", "reviewer_name": "王五", "error_type": "违规引流", "is_final_correct": 0, "is_misjudge": 0, "is_missjudge": 1},
        
        # 队列B：正确率85%（需要关注）
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": None, "is_final_correct": 1, "is_misjudge": 0, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": "违规引流", "is_final_correct": 0, "is_misjudge": 1, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "王五", "error_type": "政治敏感", "is_final_correct": 0, "is_misjudge": 1, "is_missjudge": 0},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": "低质导流", "is_final_correct": 0, "is_misjudge": 0, "is_missjudge": 1},
        {"biz_date": today, "queue_name": "评论队列B", "reviewer_name": "赵六", "error_type": "违规引流", "is_final_correct": 0, "is_misjudge": 1, "is_missjudge": 0},
    ]
    
    # 插入数据
    insert_query = """
    INSERT INTO fact_qa_event 
    (biz_date, queue_name, reviewer_name, error_type, is_final_correct, is_misjudge, is_missjudge)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        # 先清理今日数据（如果存在）
        db.execute(f"DELETE FROM fact_qa_event WHERE biz_date = '{today}'")
        print(f"✅ 已清理 {today} 的旧数据")
        
        # 批量插入
        for record in test_records:
            db.execute(
                insert_query,
                (
                    record["biz_date"],
                    record["queue_name"],
                    record["reviewer_name"],
                    record["error_type"],
                    record["is_final_correct"],
                    record["is_misjudge"],
                    record["is_missjudge"]
                )
            )
        
        print(f"✅ 成功插入 {len(test_records)} 条测试数据")
        
        # 验证数据
        verify_query = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_final_correct = 1 THEN 1 ELSE 0 END) as correct,
            ROUND(SUM(CASE WHEN is_final_correct = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as accuracy
        FROM fact_qa_event
        WHERE biz_date = '{today}'
        """
        
        result = db.execute_query(verify_query)
        if result:
            total, correct, accuracy = result[0]
            print(f"\n📊 数据验证:")
            print(f"   - 总记录数: {total}")
            print(f"   - 正确数: {correct}")
            print(f"   - 正确率: {accuracy}%")
        
        print(f"\n✅ 测试数据生成完成！")
        print(f"\n🧪 现在可以测试Agent查询:")
        print(f'   curl -X POST "http://localhost:8000/api/v1/agent/query" \\')
        print(f'     -H "Content-Type: application/json" \\')
        print(f'     -d \'{{"query": "今天数据怎么样？"}}\'')
        
    except Exception as e:
        print(f"❌ 数据插入失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    generate_test_data()
