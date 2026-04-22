#!/bin/bash
# ============================================================
# QC 统一看板 - 一键部署脚本
# 使用方式：
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh [dev|prod]
# ============================================================

set -e  # 遇到错误立即退出

ENV=${1:-dev}
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo "========================================"
echo "  QC 统一看板 部署脚本 [${ENV}]"
echo "========================================"
echo ""

cd "$PROJECT_DIR"

# ---------- 检查 .env ----------
if [ ! -f ".env" ]; then
  echo "⚠️  未找到 .env 文件，从模板复制..."
  cp .env.example .env
  echo "📝 请编辑 .env 填写 TiDB 数据库配置后重新运行"
  echo "   vi .env"
  exit 1
fi

# 检查数据库配置是否已填写
if grep -q "your_tidb_username" .env; then
  echo "❌ 请先在 .env 中填写真实的 TiDB 配置"
  echo "   vi .env"
  exit 1
fi

echo "✅ .env 配置检查通过"

# ---------- 检查 Docker ----------
if ! command -v docker &>/dev/null; then
  echo "❌ Docker 未安装，请先安装 Docker"
  exit 1
fi
if ! docker info &>/dev/null; then
  echo "❌ Docker 未启动，请先启动 Docker Desktop"
  exit 1
fi
echo "✅ Docker 运行正常"

# ---------- 拉取/构建镜像 ----------
echo ""
echo "🔨 构建 Docker 镜像..."
docker compose build --no-cache

# ---------- 停止旧容器 ----------
echo ""
echo "🛑 停止旧容器..."
docker compose down --remove-orphans 2>/dev/null || true

# ---------- 启动新容器 ----------
echo ""
echo "🚀 启动容器..."
docker compose up -d

# ---------- 等待健康检查 ----------
echo ""
echo "⏳ 等待服务启动（最多60秒）..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "✅ 后端 API 已就绪"
    break
  fi
  sleep 2
  echo "   等待中... ($((i*2))s)"
done

# ---------- 验证 ----------
echo ""
echo "🧪 验证服务..."

API_STATUS=$(curl -sf http://localhost:8000/api/health 2>/dev/null && echo "OK" || echo "FAIL")
FRONTEND_STATUS=$(curl -sf http://localhost:3000 >/dev/null 2>&1 && echo "OK" || echo "FAIL")

echo "  后端 API:   http://localhost:8000  [$API_STATUS]"
echo "  前端页面:   http://localhost:3000  [$FRONTEND_STATUS]"
echo "  API 文档:   http://localhost:8000/api/docs"
echo ""

if [ "$API_STATUS" = "OK" ] && [ "$FRONTEND_STATUS" = "OK" ]; then
  echo "🎉 部署成功！"
else
  echo "⚠️  部分服务未就绪，请检查日志："
  echo "   docker compose logs api"
  echo "   docker compose logs frontend"
fi

echo ""
echo "常用命令："
echo "  查看日志：  docker compose logs -f"
echo "  停止服务：  docker compose down"
echo "  重启服务：  docker compose restart"
echo ""
