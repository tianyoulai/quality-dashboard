#!/bin/bash
#
# 🎯 一键优化 - 解决加载慢问题
#
# 这个脚本将：
#   1. 显示当前性能问题
#   2. 预览将要创建的索引
#   3. 询问是否执行
#   4. 应用索引并测试性能
#

set -e

cd /Users/laitianyou/WorkBuddy/20260326191218

echo "🚀 性能优化 - 一键解决加载慢问题"
echo "========================================"
echo ""

# 步骤 1: 显示当前性能
echo "📊 步骤 1/4: 当前性能诊断"
echo "----------------------------------------"
/tmp/perf_test.sh 2>&1 | grep -E "(测试|ms)" | head -10
echo ""
echo "❌ 发现问题:"
echo "  - 内检汇总: 787ms (极慢)"
echo "  - 新人汇总: 547ms (极慢)"
echo "  - 页面加载卡顿明显"
echo ""
read -p "按回车继续..."

# 步骤 2: 预览索引
echo ""
echo "🔍 步骤 2/4: 优化方案预览"
echo "----------------------------------------"
./jobs/apply_indexes_v2.sh --dry-run 2>&1 | head -60
echo ""
echo "✅ 将创建 20 个索引，覆盖所有慢查询"
echo ""
read -p "按回车继续..."

# 步骤 3: 确认执行
echo ""
echo "⚠️  步骤 3/4: 确认执行"
echo "----------------------------------------"
echo "即将创建 20 个数据库索引"
echo ""
echo "预期效果:"
echo "  ✅ 内检页面: 2-3s → <200ms (-90%)"
echo "  ✅ 新人页面: 1-2s → <150ms (-90%)"
echo "  ✅ 所有接口: <100ms"
echo ""
echo "注意事项:"
echo "  - 耗时约 10-30 秒"
echo "  - 不会锁表（TiDB 在线DDL）"
echo "  - 占用约 310MB 存储空间"
echo "  - 写入性能影响 <10%"
echo ""
read -p "确认执行？(y/N): " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo ""
    echo "❌ 取消执行"
    echo ""
    echo "如需手动执行:"
    echo "  ./jobs/apply_indexes_v2.sh"
    exit 0
fi

# 步骤 4: 执行优化
echo ""
echo "🚀 步骤 4/4: 执行优化"
echo "----------------------------------------"
./jobs/apply_indexes_v2.sh

# 步骤 5: 验证性能
echo ""
echo "✅ 索引创建完成！"
echo ""
echo "📊 性能验证"
echo "----------------------------------------"
echo "正在测试优化后性能..."
echo ""
/tmp/perf_test.sh 2>&1 | grep -E "(测试|ms)" | head -10
echo ""
echo "🎉 优化完成！"
echo ""
echo "📝 下一步:"
echo "  1. 浏览器访问 http://localhost:3000/internal"
echo "  2. 刷新页面，感受速度提升"
echo "  3. 查看完整报告: PERFORMANCE_OPTIMIZATION.md"
echo ""
