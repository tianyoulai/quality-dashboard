#!/bin/bash
# ============================================================
# QC 统一看板 - 一键部署脚本
# ============================================================
# 功能：
#   1. 检查环境依赖（Docker/Docker Compose）
#   2. 构建镜像
#   3. 启动服务
#   4. 运行健康检查
# ============================================================

set -e  # 遇到错误立即退出

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 QC 统一看板 - 部署开始"
echo "================================"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，正在复制模板..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请编辑后重新运行"
    exit 0
fi

# 停止旧容器
echo ""
echo "🛑 停止旧容器..."
docker-compose down

# 构建镜像
echo ""
echo "🔨 构建镜像..."
docker-compose build --no-cache

# 启动服务
echo ""
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo ""
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo ""
echo "🏥 健康检查..."

# 检查 API
if curl -f http://localhost:8000/api/health &> /dev/null; then
    echo "✅ API 服务正常"
else
    echo "❌ API 服务异常"
    docker-compose logs api
    exit 1
fi

# 检查前端
if curl -f http://localhost:3000 &> /dev/null; then
    echo "✅ 前端服务正常"
else
    echo "❌ 前端服务异常"
    docker-compose logs frontend
    exit 1
fi

echo ""
echo "================================"
echo "✅ 部署成功！"
echo ""
echo "📋 服务地址："
echo "  - 前端: http://localhost:3000"
echo "  - API: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/api/docs"
echo ""
echo "📝 常用命令："
echo "  - 查看日志: docker-compose logs -f"
echo "  - 停止服务: docker-compose down"
echo "  - 重启服务: docker-compose restart"
echo "================================"
