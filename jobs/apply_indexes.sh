#!/bin/bash
#
# 🚀 一键应用高性能索引（直接SQL版本）
# 
# 功能：
#   1. 读取 performance_indexes.sql
#   2. 提取所有 CREATE INDEX 语句
#   3. 通过 mysql 客户端执行
#   4. 输出执行结果和耗时
#
# 使用方法：
#   ./jobs/apply_indexes.sh
#   ./jobs/apply_indexes.sh --dry-run  # 仅显示将要执行的SQL
#

set -e

# 配置（从环境变量读取，或使用默认值）
DB_HOST="${TIDB_HOST:-127.0.0.1}"
DB_PORT="${TIDB_PORT:-4000}"
DB_USER="${TIDB_USER:-root}"
DB_PASS="${TIDB_PASSWORD:-}"
DB_NAME="${TIDB_DATABASE:-qc_dashboard}"
SQL_FILE="storage/performance_indexes.sql"

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
fi

echo "🚀 高性能索引应用工具"
echo "========================================"
echo "📄 SQL 文件: $SQL_FILE"
echo "🔧 数据库: $DB_HOST:$DB_PORT/$DB_NAME"
echo "🔧 模式: $([ "$DRY_RUN" = true ] && echo 'DRY-RUN（预览）' || echo '实际执行')"
echo "========================================"
echo ""

# 检查 SQL 文件
if [[ ! -f "$SQL_FILE" ]]; then
    echo "❌ SQL 文件不存在: $SQL_FILE"
    exit 1
fi

# 提取所有 CREATE INDEX 语句
statements=$(grep -i "^CREATE INDEX" "$SQL_FILE" | grep -v "^--")
count=$(echo "$statements" | wc -l | tr -d ' ')

echo "📊 找到 $count 个 CREATE INDEX 语句"
echo ""

if [[ "$DRY_RUN" = true ]]; then
    echo "将执行以下 SQL 语句："
    echo "----------------------------------------"
    echo "$statements"
    echo "----------------------------------------"
    exit 0
fi

# 构造 mysql 命令
MYSQL_CMD="mysql -h $DB_HOST -P $DB_PORT -u $DB_USER"
if [[ -n "$DB_PASS" ]]; then
    MYSQL_CMD="$MYSQL_CMD -p$DB_PASS"
fi
MYSQL_CMD="$MYSQL_CMD $DB_NAME"

# 执行索引创建
success=0
skip=0
fail=0
total_time=0

i=1
while IFS= read -r stmt; do
    echo -n "[$i/$count] "
    
    # 提取索引名
    index_name=$(echo "$stmt" | sed -E 's/.*IF NOT EXISTS ([^ ]+) .*/\1/')
    
    start=$(date +%s%3N)
    if output=$($MYSQL_CMD -e "$stmt" 2>&1); then
        end=$(date +%s%3N)
        elapsed=$((end - start))
        
        if echo "$output" | grep -qi "duplicate"; then
            echo "⏭️  索引 $index_name 已存在，跳过"
            ((skip++))
        else
            echo "✅ 成功创建 $index_name (${elapsed}ms)"
            ((success++))
            total_time=$((total_time + elapsed))
        fi
    else
        echo "❌ 失败: $index_name"
        echo "   错误: $output"
        ((fail++))
    fi
    
    ((i++))
done <<< "$statements"

# 总结报告
echo ""
echo "========================================"
echo "📊 执行总结"
echo "========================================"
echo "✅ 成功创建: $success 个"
echo "⏭️  已存在跳过: $skip 个"
echo "❌ 失败: $fail 个"
echo "⏱️  总耗时: $((total_time / 1000))s"

if [[ $success -gt 0 ]]; then
    echo ""
    echo "🎉 索引创建完成！"
    echo ""
    echo "📝 建议执行以下步骤："
    echo "  1. 运行性能测试: /tmp/perf_test.sh"
    echo "  2. 验证索引使用: EXPLAIN SELECT ..."
    echo "  3. 监控慢查询日志"
    echo "  4. 对比优化前后性能"
fi

exit $fail
