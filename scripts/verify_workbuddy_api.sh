#!/bin/bash

# WorkBuddy API验证脚本
# 测试所有前端需要的API接口

echo "🔍 WorkBuddy API验证测试"
echo "========================="
echo ""

BASE_URL="http://localhost:8000"
DATE="2026-04-20"

# 检查API服务是否运行
echo "1️⃣ 检查API服务..."
if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/health" | grep -q "200"; then
    echo "✅ API服务运行中"
else
    echo "❌ API服务未启动"
    echo "请先运行: cd ~/WorkBuddy/20260326191218 && ./start_api.sh"
    exit 1
fi

echo ""
echo "2️⃣ 测试Monitor接口..."

# Dashboard
echo -n "  - /api/v1/monitor/dashboard ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/monitor/dashboard?date=$DATE")
if echo "$RESPONSE" | jq -e '.date' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# Queue Ranking
echo -n "  - /api/v1/monitor/queue-ranking ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/monitor/queue-ranking?date=$DATE")
if echo "$RESPONSE" | jq -e '.[0].queue_name' > /dev/null 2>&1 || echo "$RESPONSE" | jq -e '. == []' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# Error Ranking
echo -n "  - /api/v1/monitor/error-ranking ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/monitor/error-ranking?date=$DATE")
if echo "$RESPONSE" | jq -e '.[0].error_type' > /dev/null 2>&1 || echo "$RESPONSE" | jq -e '. == []' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# Reviewer Ranking
echo -n "  - /api/v1/monitor/reviewer-ranking ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/monitor/reviewer-ranking?date=$DATE")
if echo "$RESPONSE" | jq -e '.[0].reviewer_name' > /dev/null 2>&1 || echo "$RESPONSE" | jq -e '. == []' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

echo ""
echo "3️⃣ 测试Analysis接口..."

# Error Overview
echo -n "  - /api/v1/analysis/error-overview ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/analysis/error-overview?start_date=$DATE&end_date=$DATE")
if echo "$RESPONSE" | jq -e '.summary' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# Error Heatmap
echo -n "  - /api/v1/analysis/error-heatmap ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/analysis/error-heatmap?start_date=$DATE&end_date=$DATE")
if echo "$RESPONSE" | jq -e '.heatmap' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# Root Cause
echo -n "  - /api/v1/analysis/root-cause ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/analysis/root-cause?start_date=$DATE&end_date=$DATE")
if echo "$RESPONSE" | jq -e '.categories' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

echo ""
echo "4️⃣ 测试Visualization接口..."

# Performance Trend
echo -n "  - /api/v1/visualization/performance-trend ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/visualization/performance-trend?start_date=$DATE&end_date=$DATE")
if echo "$RESPONSE" | jq -e '.dates' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# API Performance
echo -n "  - /api/v1/visualization/api-performance ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/visualization/api-performance?start_date=$DATE&end_date=$DATE")
if echo "$RESPONSE" | jq -e '.endpoints' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# Queue Distribution
echo -n "  - /api/v1/visualization/queue-distribution ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/visualization/queue-distribution?date=$DATE")
if echo "$RESPONSE" | jq -e '.queues' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

# Error Trend
echo -n "  - /api/v1/visualization/error-trend ... "
RESPONSE=$(curl -s "$BASE_URL/api/v1/visualization/error-trend?start_date=$DATE&end_date=$DATE")
if echo "$RESPONSE" | jq -e '.dates' > /dev/null 2>&1; then
    echo "✅"
else
    echo "❌"
    echo "    响应: $RESPONSE"
fi

echo ""
echo "========================="
echo "✅ WorkBuddy API验证完成！"
echo ""
echo "📊 API文档地址: http://localhost:8000/docs"
echo "🚀 前端访问地址: http://localhost:3000"
