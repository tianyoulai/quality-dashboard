# Docker 部署指南

## 📦 快速开始

### 1. 前置要求

- Docker 20.10+
- Docker Compose 2.0+

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写 TiDB 连接信息
vim .env
```

### 3. 一键部署

```bash
# 使用部署脚本
./deploy.sh
```

或手动部署：

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 4. 访问服务

- **前端**: http://localhost:3000
- **API**: http://localhost:8000
- **API 文档**: http://localhost:8000/api/docs

---

## 🛠️ 常用命令

### 服务管理

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启服务
docker-compose restart

# 重启单个服务
docker-compose restart api
docker-compose restart frontend
```

### 日志查看

```bash
# 查看所有日志
docker-compose logs -f

# 查看指定服务日志
docker-compose logs -f api
docker-compose logs -f frontend

# 查看最近 100 行日志
docker-compose logs --tail=100 api
```

### 进入容器

```bash
# 进入 API 容器
docker-compose exec api bash

# 进入前端容器
docker-compose exec frontend sh

# 运行 Python 脚本
docker-compose exec api python jobs/monitor_slow_queries.py
```

### 数据库操作

```bash
# 初始化数据库 schema
docker-compose exec api python -c "from storage.repository import DashboardRepository; repo = DashboardRepository(); repo.initialize_schema()"

# 导入数据
docker-compose exec api python jobs/import_fact_data.py --qa-file /path/to/data.xlsx

# 刷新仓库
docker-compose exec api python jobs/refresh_warehouse.py
```

---

## 🔧 环境变量说明

### TiDB 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TIDB_HOST` | TiDB 主机地址 | - |
| `TIDB_PORT` | TiDB 端口 | 4000 |
| `TIDB_USER` | 用户名 | - |
| `TIDB_PASSWORD` | 密码 | - |
| `TIDB_DATABASE` | 数据库名 | test |

### API 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `API_ALLOW_ORIGINS` | CORS 允许的源 | * |
| `API_SLOW_THRESHOLD_MS` | 慢请求阈值（毫秒） | 800 |
| `LOG_LEVEL` | 日志级别 | INFO |

### 前端配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | API 基础地址 | http://localhost:8000 |

---

## 🐛 故障排查

### 1. 容器启动失败

```bash
# 查看容器状态
docker-compose ps

# 查看错误日志
docker-compose logs api
docker-compose logs frontend

# 重新构建镜像
docker-compose build --no-cache
docker-compose up -d
```

### 2. API 连接不上

```bash
# 检查 API 健康状态
curl http://localhost:8000/api/health

# 检查容器端口映射
docker ps | grep qc-dashboard-api

# 检查防火墙
# macOS: System Preferences > Security & Privacy > Firewall
# Linux: sudo ufw status
```

### 3. 前端访问不了

```bash
# 检查前端容器日志
docker-compose logs frontend

# 检查环境变量
docker-compose exec frontend env | grep NEXT_PUBLIC

# 重启前端
docker-compose restart frontend
```

### 4. 数据库连接失败

```bash
# 检查 TiDB 配置
docker-compose exec api python -c "from storage.tidb_manager import TiDBManager; m = TiDBManager(); print(m.config)"

# 测试数据库连接
docker-compose exec api python -c "from storage.tidb_manager import TiDBManager; m = TiDBManager(); print(m.health_check())"
```

---

## 📊 性能优化

### 1. 调整 API Workers

编辑 `Dockerfile`：

```dockerfile
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "8"]
```

建议 workers 数量 = CPU 核心数 × 2 + 1

### 2. 调整连接池大小

编辑 `.env`：

```bash
# 增大连接池（需要在代码中支持从环境变量读取）
TIDB_POOL_SIZE=10
```

### 3. 启用 Redis 缓存

```bash
# docker-compose.yml 中已包含 Redis 服务
# 在代码中配置 Redis 连接
```

---

## 🔒 生产环境部署

### 1. 使用外部数据库

不要在生产环境的 Docker Compose 中运行数据库，使用云服务（TiDB Cloud）。

### 2. 使用反向代理

```nginx
# Nginx 配置示例
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 启用 HTTPS

使用 Let's Encrypt 或云服务商的 SSL 证书。

### 4. 限制资源使用

编辑 `docker-compose.yml`：

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

---

## 📈 监控与日志

### 1. 日志持久化

日志目录 `./logs` 已挂载到宿主机，可以使用日志收集工具（如 Fluentd、Logstash）采集。

### 2. 监控指标

使用 Prometheus + Grafana 监控容器：

```bash
# 安装 cAdvisor
docker run -d \
  --name=cadvisor \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --publish=8080:8080 \
  google/cadvisor:latest
```

---

## 🔄 CI/CD 集成

### GitHub Actions 示例

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build and push
        run: |
          docker-compose build
          docker-compose push
      
      - name: Deploy to server
        run: |
          ssh user@server "cd /app && docker-compose pull && docker-compose up -d"
```

---

## 📚 参考资料

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Next.js Docker 部署](https://nextjs.org/docs/deployment#docker-image)
- [FastAPI 部署](https://fastapi.tiangolo.com/deployment/)
