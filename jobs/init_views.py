#!/usr/bin/env python3
"""初始化数据库视图（从 schema.sql 提取 VIEW 定义）。"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from storage.tidb_manager import TiDBManager


def init_views():
    """执行 schema.sql 中的视图创建语句。"""
    schema_path = PROJECT_ROOT / "storage" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    # 提取所有视图定义（DROP VIEW IF EXISTS ... 和 CREATE VIEW ...）
    view_statements = []
    lines = schema_sql.split("\n")
    current_stmt = []
    in_view = False
    
    for line in lines:
        if line.strip().startswith("DROP VIEW IF EXISTS"):
            in_view = True
            current_stmt = [line]
        elif in_view:
            current_stmt.append(line)
            if line.strip().endswith(";"):
                view_statements.append("\n".join(current_stmt))
                current_stmt = []
                in_view = False
    
    print(f"📋 找到 {len(view_statements)} 个视图定义")
    
    # 创建连接管理器并获取连接
    manager = TiDBManager()
    with manager.get_connection() as conn:
        cursor = conn.cursor()
        for i, stmt in enumerate(view_statements, 1):
            # 提取视图名
            view_name = stmt.split("DROP VIEW IF EXISTS")[1].split(";")[0].strip()
            print(f"  {i}. 创建视图: {view_name}")
            try:
                # 视图创建语句包含多条 SQL（DROP + CREATE），需要分开执行
                for sub_stmt in stmt.split(";"):
                    sub_stmt = sub_stmt.strip()
                    if sub_stmt:
                        cursor.execute(sub_stmt)
                print(f"     ✅ 创建成功")
            except Exception as e:
                print(f"     ⚠️  创建失败: {e}")
        cursor.close()
    
    print("✅ 视图初始化完成")


if __name__ == "__main__":
    init_views()
