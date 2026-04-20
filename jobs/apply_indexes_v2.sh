#!/bin/bash
#
# 🚀 高性能索引应用工具（改进版）
#
# 功能：
#   1. 从 performance_indexes.sql 提取完整的 CREATE INDEX 语句
#   2. 逐条执行并显示进度
#   3. 自动检测已存在的索引并跳过
#   4. 输出详细的执行报告
#
# 使用方法：
#   ./jobs/apply_indexes_v2.sh
#   ./jobs/apply_indexes_v2.sh --dry-run
#

set -e

# 配置
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

# 构造 mysql 命令
MYSQL_CMD="mysql -h $DB_HOST -P $DB_PORT -u $DB_USER"
if [[ -n "$DB_PASS" ]]; then
    MYSQL_CMD="$MYSQL_CMD -p$DB_PASS"
fi
MYSQL_CMD="$MYSQL_CMD $DB_NAME -N -B"  # -N 无表头, -B 批处理模式

# 提取完整的 CREATE INDEX 语句（多行）
# 使用 awk 处理多行语句
statements=$(awk '
    /^CREATE INDEX IF NOT EXISTS/ {
        stmt = $0
        while (substr($0, length($0), 1) != ";") {
            getline
            stmt = stmt " " $0
        }
        # 压缩空白字符
        gsub(/[[:space:]]+/, " ", stmt)
        print stmt
    }
' "$SQL_FILE")

count=$(echo "$statements" | wc -l | tr -d ' ')

if [[ $count -eq 0 ]]; then
    echo "❌ 没有找到有效的 CREATE INDEX 语句"
    exit 1
fi

echo "📊 找到 $count 个 CREATE INDEX 语句"
echo ""

if [[ "$DRY_RUN" = true ]]; then
    echo "将执行以下 SQL 语句："
    echo "----------------------------------------"
    i=1
    while IFS= read -r stmt; do
        index_name=$(echo "$stmt" | sed -E 's/.*IF NOT EXISTS ([^ ]+) .*/\1/')
        table_name=$(echo "$stmt" | sed -E 's/.*ON ([^ (]+).*/\1/')
        columns=$(echo "$stmt" | sed -E 's/.*\(([^)]+)\).*/\1/')
        
        echo "[$i/$count] $index_name"
        echo "  表: $table_name"
        echo "  列: $columns"
        echo ""
        ((i++))
    done <<< "$statements"
    echo "----------------------------------------"
    echo ""
    echo "执行命令以应用索引:"
    echo "  ./jobs/apply_indexes_v2.sh"
    exit 0
fi

# 实际执行
success=0
skip=0
fail=0
total_time=0

i=1
while IFS= read -r stmt; do
    # 提取索引名和表名
    index_name=$(echo "$stmt" | sed -E 's/.*IF NOT EXISTS ([^ ]+) .*/\1/')
    table_name=$(echo "$stmt" | sed -E 's/.*ON ([^ (]+).*/\1/')
    
    echo -n "[$i/$count] $index_name ($table_name) ... "
    
    # 检查索引是否已存在
    existing=$($MYSQL_CMD -e "SHOW INDEX FROM $table_name WHERE Key_name = '$index_name'" 2>&1 | wc -l | tr -d ' ')
    
    if [[ $existing -gt 0 ]]; then
        echo "⏭️  已存在"
        ((skip++))
    else
        # 执行创建
        start=$(date +%s%3N)
        if $MYSQL_CMD -e "$stmt" 2>&1 > /tmp/mysql_output_$$; then
            end=$(date +%s%3N)
            elapsed=$((end - start))
            echo "✅ 成功 (${elapsed}ms)"
            ((success++))
            total_time=$((total_time + elapsed))
        else
            echo "❌ 失败"
            cat /tmp/mysql_output_$$
            ((fail++))
        fi
        rm -f /tmp/mysql_output_$$
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

if [[ $success -gt 0 || $skip -gt 0 ]]; then
    echo "⏱️  总耗时: $(printf "%.2f" $(echo "$total_time / 1000" | bc -l))s"
fi

if [[ $success -gt 0 ]]; then
    echo ""
    echo "🎉 索引创建完成！"
    echo ""
    echo "📝 下一步："
    echo "  1. 性能测试: /tmp/perf_test.sh"
    echo "  2. 查看执行计划: EXPLAIN SELECT ..."
    echo "  3. 前后对比："
    echo ""
    echo "     优化前         优化后（预期）"
    echo "     --------       --------"
    echo "     内检: 787ms → <50ms"
    echo "     新人: 547ms → <50ms"
    echo "     告警: 259ms → <20ms"
    echo ""
fi

exit $fail
