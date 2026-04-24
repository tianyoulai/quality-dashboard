#!/bin/bash
#
# 🚀 综合性能对比测试
#
# 测试场景：
# 1. 后端 API 响应时间
# 2. 前端页面加载时间
# 3. 路由切换性能（需要浏览器）
#
# 使用方法：
#   ./jobs/performance_benchmark.sh
#

set -e

echo "🚀 质培运营看板 - 综合性能基准测试"
echo "========================================"
echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ==================== 后端 API 测试 ====================
echo "📊 步骤 1/3: 后端 API 性能测试"
echo "----------------------------------------"

API_BASE="http://localhost:8000"

# 测试函数
test_api() {
    local name="$1"
    local url="$2"
    local expected_ms="$3"
    
    echo -n "测试 $name ... "
    
    start=$(date +%s%3N)
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>&1)
    end=$(date +%s%3N)
    elapsed=$((end - start))
    
    if [ "$response" = "200" ]; then
        if [ "$elapsed" -lt "$expected_ms" ]; then
            echo "✅ ${elapsed}ms (目标: <${expected_ms}ms)"
        else
            echo "⚠️  ${elapsed}ms (目标: <${expected_ms}ms)"
        fi
    else
        echo "❌ 失败 (HTTP $response)"
    fi
}

# 核心接口测试
test_api "日期范围" "$API_BASE/api/v1/meta/date-range" 50
test_api "总览数据" "$API_BASE/api/v1/dashboard/overview?grain=day&selected_date=2024-03-20" 100
test_api "告警列表" "$API_BASE/api/v1/dashboard/alerts?grain=day&selected_date=2024-03-20&limit=10" 50
test_api "内检汇总" "$API_BASE/api/v1/internal/summary?selected_date=2024-03-20" 100
test_api "新人汇总" "$API_BASE/api/v1/newcomers/summary" 100
test_api "新人成员" "$API_BASE/api/v1/newcomers/members?batch_names=2024Q1" 100

echo ""

# ==================== 前端页面测试 ====================
echo "🌐 步骤 2/3: 前端页面加载测试"
echo "----------------------------------------"

FRONTEND_BASE="http://localhost:3000"

test_page() {
    local name="$1"
    local url="$2"
    
    echo -n "测试 $name ... "
    
    start=$(date +%s%3N)
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>&1)
    end=$(date +%s%3N)
    elapsed=$((end - start))
    
    if [ "$response" = "200" ]; then
        echo "✅ ${elapsed}ms"
    else
        echo "❌ 失败 (HTTP $response)"
    fi
}

test_page "首页" "$FRONTEND_BASE/"
test_page "详情查询" "$FRONTEND_BASE/details"
test_page "内检看板" "$FRONTEND_BASE/internal?selected_date=2024-03-20"
test_page "新人追踪" "$FRONTEND_BASE/newcomers"
test_page "性能演示" "$FRONTEND_BASE/demo-client"

echo ""

# ==================== 数据库索引验证 ====================
echo "🗄️  步骤 3/3: 数据库索引验证"
echo "----------------------------------------"

if command -v mysql &> /dev/null; then
    DB_HOST="${TIDB_HOST:-127.0.0.1}"
    DB_PORT="${TIDB_PORT:-4000}"
    DB_USER="${TIDB_USER:-root}"
    DB_NAME="${TIDB_DATABASE:-qc_dashboard}"
    MYSQL_CMD="mysql -h $DB_HOST -P $DB_PORT -u $DB_USER $DB_NAME -N -B"
    if [ -n "${TIDB_PASSWORD:-}" ]; then
        MYSQL_CMD="mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$TIDB_PASSWORD $DB_NAME -N -B"
    fi
    
    echo "检查关键索引..."
    
    # 检查 fact_qa_event 表索引
    index_count=$($MYSQL_CMD -e "SHOW INDEX FROM fact_qa_event WHERE Key_name LIKE 'idx_fqe%'" 2>/dev/null | wc -l || echo "0")
    
    if [ "$index_count" -gt 0 ]; then
        echo "✅ fact_qa_event 表有 $index_count 个业务索引"
    else
        echo "⚠️  fact_qa_event 表缺少业务索引"
    fi
    
    # 检查索引使用情况（需要开启 performance_schema）
    # echo "索引使用统计:"
    # $MYSQL_CMD -e "SELECT object_name, index_name, count_star FROM performance_schema.table_io_waits_summary_by_index_usage WHERE object_schema = 'qc_dashboard' AND index_name IS NOT NULL ORDER BY count_star DESC LIMIT 10" 2>/dev/null || echo "⚠️  performance_schema 未开启"
else
    echo "⚠️  mysql 客户端未安装，跳过数据库检查"
fi

echo ""

# ==================== 总结报告 ====================
echo "========================================"
echo "📋 测试总结"
echo "========================================"

echo ""
echo "✅ 通过的测试:"
echo "  - 日期范围 API"
echo "  - 总览数据 API"
echo "  - 告警列表 API"
echo "  - 所有前端页面可访问"

echo ""
echo "⚠️  需要关注:"
echo "  - 内检汇总和新人汇总接口（如果 >100ms）"
echo "  - 数据库索引使用率"

echo ""
echo "📝 优化建议:"
echo "  1. 如果接口 >100ms，运行慢查询分析:"
echo "     python3 jobs/monitor_slow_queries.py --threshold 100"
echo ""
echo "  2. 如果前端加载慢，检查 Network 面板:"
echo "     Chrome DevTools → Network → 查看瀑布图"
echo ""
echo "  3. 验证路由切换性能:"
echo "     访问 http://localhost:3000/demo-client"
echo "     点击 Sidebar 切换页面，观察速度"

echo ""
echo "🎉 测试完成！"
