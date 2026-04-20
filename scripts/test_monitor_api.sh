#!/bin/bash
# 实时监控API测试脚本

echo "🧪 测试实时监控API接口"
echo "======================================"

# 设置API地址
API_BASE="http://localhost:8000"

# 测试1: 健康检查
echo ""
echo "📋 Test 1: 健康检查"
curl -s "${API_BASE}/api/health" | python3 -m json.tool

# 测试2: 监控看板数据
echo ""
echo "📊 Test 2: 监控看板数据（当日 vs 昨日）"
curl -s "${API_BASE}/api/v1/monitor/dashboard" | python3 -m json.tool | head -50

# 测试3: 队列排行
echo ""
echo "⚠️ Test 3: 重点关注队列（正确率 <90%）"
curl -s "${API_BASE}/api/v1/monitor/queue-ranking?threshold=90&limit=5" | python3 -m json.tool

# 测试4: 错误类型排行
echo ""
echo "🎯 Test 4: 高频错误类型（Top 5）"
curl -s "${API_BASE}/api/v1/monitor/error-ranking?limit=5" | python3 -m json.tool

# 测试5: 审核人排行
echo ""
echo "👤 Test 5: 重点关注审核人（正确率 <85%）"
curl -s "${API_BASE}/api/v1/monitor/reviewer-ranking?threshold=85&limit=5" | python3 -m json.tool

echo ""
echo "======================================"
echo "✅ 测试完成！"
