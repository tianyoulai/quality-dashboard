# 生产环境部署指南

## 🚀 部署前准备

### 1. 环境要求

- **服务器**: 2核4G 以上
- **操作系统**: Ubuntu 20.04+ / CentOS 8+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **网络**: 公网 IP + 域名（如需 HTTPS）

### 2. 安全配置

#### 2.1 防火墙规则

```bash
# 只开放必要端口
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

#### 2.2 创建专用用户

```bash
# 不要用 root 运行应用
sudo useradd -m -s /bin/bash qc-dashboard
sudo usermod -aG docker qc-dashboard
```

---

## 📦 部署步骤

### Step 1: 克隆代码

```bash
# 使用专用用户
su - qc-dashboard

# 克隆仓库
git clone <your-repo-url> /home/qc-dashboard/app
cd /home/qc-dashboard/app
```

### Step 2: 配置环境变量

```bash
# 复制模板
cp .env.example .env

# 编辑配置（填写生产 TiDB 连接信息）
vim .env
```

**.env 示例（生产环境）**:
```bash
# TiDB 配置（使用 TiDB Cloud 生产集群）
TIDB_HOST=gateway01.prod.tidbcloud.com
TIDB_PORT=4000
TIDB_USER=your_prod_user
TIDB_PASSWORD=<替换为你的数据库密码>
TIDB_DATABASE=qc_dashboard_prod

# API 配置
API_ALLOW_ORIGINS=https://qc-dashboard.your-domain.com
API_SLOW_THRESHOLD_MS=800

# 日志配置
LOG_LEVEL=INFO

# Next.js 配置
NEXT_PUBLIC_API_BASE_URL=https://qc-dashboard.your-domain.com/api
```

### Step 3: 构建和启动服务

```bash
# 一键部署
./deploy.sh

# 或手动执行
docker-compose build
docker-compose up -d
```

### Step 4: 验证服务

```bash
# 检查容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 健康检查
curl http://localhost:8000/api/health
curl http://localhost:3000
```

---

## 🌐 配置反向代理（Nginx）

### Step 1: 安装 Nginx

```bash
sudo apt-get update
sudo apt-get install nginx -y
```

### Step 2: 配置站点

创建配置文件：`/etc/nginx/sites-available/qc-dashboard`

```nginx
# HTTP → HTTPS 重定向
server {
    listen 80;
    server_name qc-dashboard.your-domain.com;
    
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    server_name qc-dashboard.your-domain.com;

    # SSL 证书（Let's Encrypt）
    ssl_certificate /etc/letsencrypt/live/qc-dashboard.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/qc-dashboard.your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 日志
    access_log /var/log/nginx/qc-dashboard.access.log;
    error_log /var/log/nginx/qc-dashboard.error.log;
}
```

### Step 3: 启用站点

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/qc-dashboard /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

---

## 🔒 配置 HTTPS（Let's Encrypt）

### Step 1: 安装 Certbot

```bash
sudo apt-get install certbot python3-certbot-nginx -y
```

### Step 2: 申请证书

```bash
sudo certbot --nginx -d qc-dashboard.your-domain.com
```

### Step 3: 自动续期

```bash
# Certbot 会自动添加 cron 任务，验证：
sudo certbot renew --dry-run
```

---

## 📊 配置监控（Prometheus + Grafana）

### Step 1: 启动监控堆栈

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

### Step 2: 访问 Grafana

```
URL: http://your-domain:3001
用户名: admin
密码: admin（首次登录后修改）
```

### Step 3: 导入仪表盘

1. 登录 Grafana
2. 点击 "+" → "Import"
3. 使用官方模板 ID：
   - **Docker 容器**: 193
   - **Node Exporter**: 1860
   - **Nginx**: 12708

### Step 4: 配置告警（可选）

在 Grafana 中配置告警规则，通知到企业微信/邮件。

---

## 📝 配置日志聚合（Fluentd + ES + Kibana）

### Step 1: 启动日志堆栈

```bash
docker-compose -f docker-compose.logging.yml up -d
```

### Step 2: 访问 Kibana

```
URL: http://your-domain:5601
```

### Step 3: 创建索引模式

1. 打开 Kibana
2. Management → Stack Management → Index Patterns
3. 创建索引模式: `qc-logs-*`
4. 选择时间字段: `@timestamp`

### Step 4: 查询日志

使用 Kibana Discover 查询和分析日志。

---

## 🔄 CI/CD 配置（GitHub Actions）

创建文件：`.github/workflows/deploy.yml`

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker images
        run: |
          docker-compose build
      
      - name: Push to Registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker-compose push
      
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /home/qc-dashboard/app
            git pull origin main
            docker-compose pull
            docker-compose up -d
            docker-compose ps
```

---

## 🛠️ 运维命令

### 日常操作

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
docker-compose logs -f frontend

# 重启服务
docker-compose restart api
docker-compose restart frontend

# 更新服务
git pull origin main
docker-compose build
docker-compose up -d
```

### 数据库操作

```bash
# 初始化 schema
docker-compose exec api python -c "from storage.repository import DashboardRepository; repo = DashboardRepository(); repo.initialize_schema()"

# 导入数据
docker-compose exec api python jobs/import_fact_data.py --qa-file /path/to/data.xlsx

# 刷新仓库
docker-compose exec api python jobs/refresh_warehouse.py
```

### 监控和诊断

```bash
# 慢查询监控
docker-compose exec api python jobs/monitor_slow_queries.py --threshold 500

# 连接池监控
docker-compose exec api python jobs/monitor_connection_pool.py --threshold 0.8

# 负载测试
pip install locust
locust -f jobs/load_test.py --host=https://qc-dashboard.your-domain.com --users 100 --spawn-rate 10
```

---

## 📈 性能优化建议

### 1. 数据库优化

```bash
# 应用索引优化
docker-compose exec api python -c "from storage.repository import DashboardRepository; repo = DashboardRepository(); repo.initialize_schema('storage/index_optimization.sql')"

# 定期分析表
docker-compose exec api python -c "
from storage.tidb_manager import TiDBManager
manager = TiDBManager()
with manager.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('ANALYZE TABLE fact_qa_event')
    cursor.execute('ANALYZE TABLE fact_alert_event')
"
```

### 2. 增加 API Workers

编辑 `Dockerfile`:

```dockerfile
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "8"]
```

### 3. 启用 Redis 缓存

```bash
# docker-compose.yml 中已包含 Redis
# 在代码中配置 Redis 连接（暂未实现，待后续迭代）
```

---

## 🔧 故障排查

### 问题1: 容器启动失败

```bash
# 查看详细日志
docker-compose logs api

# 检查配置
docker-compose config

# 重新构建
docker-compose build --no-cache
docker-compose up -d
```

### 问题2: 数据库连接失败

```bash
# 测试连接
docker-compose exec api python -c "
from storage.tidb_manager import TiDBManager
manager = TiDBManager()
print(manager.health_check())
"

# 检查环境变量
docker-compose exec api env | grep TIDB
```

### 问题3: 前端页面空白

```bash
# 检查前端日志
docker-compose logs frontend

# 检查环境变量
docker-compose exec frontend env | grep NEXT_PUBLIC

# 重启前端
docker-compose restart frontend
```

### 问题4: Nginx 502 错误

```bash
# 检查 API 是否正常
curl http://localhost:8000/api/health

# 检查 Nginx 日志
sudo tail -f /var/log/nginx/qc-dashboard.error.log

# 检查 SELinux（CentOS）
sudo setenforce 0
```

---

## 🔐 安全加固

### 1. 修改默认密码

```bash
# Grafana 密码（首次登录后修改）
# Elasticsearch 密码（如启用安全功能）
```

### 2. 限制 Docker Socket 访问

```bash
sudo chmod 660 /var/run/docker.sock
```

### 3. 定期更新

```bash
# 更新系统
sudo apt-get update && sudo apt-get upgrade -y

# 更新 Docker 镜像
docker-compose pull
docker-compose up -d
```

### 4. 配置自动备份

```bash
# 备份数据库（TiDB Cloud 自动备份）
# 备份配置文件
tar -czf backup-$(date +%Y%m%d).tar.gz .env docker-compose.yml
```

---

## 📚 参考资料

- [Docker 部署最佳实践](https://docs.docker.com/develop/dev-best-practices/)
- [Nginx 性能优化](https://www.nginx.com/blog/tuning-nginx/)
- [Let's Encrypt 文档](https://letsencrypt.org/docs/)
- [Prometheus 监控指南](https://prometheus.io/docs/introduction/overview/)
- [TiDB Cloud 文档](https://docs.pingcap.com/tidbcloud/)
