# ============================================================
# QC 统一看板 API - Docker 镜像
# ============================================================
# 基础镜像：Python 3.11
# 运行：uvicorn 启动 FastAPI
# ============================================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（如果需要编译扩展）
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY api/ ./api/
COPY storage/ ./storage/
COPY services/ ./services/
COPY utils/ ./utils/
COPY config/ ./config/

# 创建日志目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health', timeout=5)"

# 启动命令
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
