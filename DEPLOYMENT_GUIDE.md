# 队列看板系统 - 部署指南

**版本**: v1.0.0-beta  
**更新时间**: 2026-04-22  
**适用环境**: 开发环境、测试环境、生产环境

---

## 📋 目录

1. [环境要求](#环境要求)
2. [快速开始](#快速开始)
3. [详细部署步骤](#详细部署步骤)
4. [配置说明](#配置说明)
5. [健康检查](#健康检查)
6. [常见问题](#常见问题)
7. [故障排查](#故障排查)

---

## 环境要求

### 必需环境

| 组件 | 版本要求 | 说明 |
|-----|---------|------|
| **Python** | ≥ 3.9 | 后端运行环境 |
| **Node.js** | ≥ 18.0 | 前端运行环境 |
| **TiDB** | ≥ 6.0 | 数据库（或MySQL 8.0+） |
| **npm** | ≥ 9.0 | 前端包管理器 |

### 可选环境

| 组件 | 用途 |
|-----|------|
| **Docker** | 容器化部署 |
| **Nginx** | 反向代理 |
| **Redis** | 缓存（未来优化） |

### 系统要求

- **内存**: 最低 2GB，推荐 4GB+
- **磁盘**: 最低 5GB 可用空间
- **网络**: 能访问 TiDB 数据库

---

## 快速开始

### 方式1: 本地开发模式（推荐新手）

```bash
# 1. 克隆项目
cd ~/WorkBuddy/20260326191218

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填写 TiDB 连接信息

# 3. 安装后端依赖
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 4. 安装前端依赖
cd frontend
npm install
cd ..

# 5. 启动后端（终端1）
./start_api.sh
# 访问: http://localhost:8000/api/health

# 6. 启动前端（终端2）
./start_frontend.sh
# 访问: http://localhost:3000
```

**预计耗时**: 10-15分钟

---

### 方式2: Docker部署（推荐生产环境）

```bash
# 1. 配置环境变量
cp .env.example .env
vim .env  # 填写 TiDB 连接信息

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 访问系统
# 前端: http://localhost:3000
# 后端: http://localhost:8000/api/docs
```

**预计耗时**: 5分钟

---

## 详细部署步骤

### Step 1: 获取代码

```bash
# 如果是Git仓库
git clone <repository-url>
cd qc-dashboard

# 或者直接进入项目目录
cd ~/WorkBuddy/20260326191218
```

### Step 2: 配置数据库

#### 2.1 创建数据库（如果还没有）

```sql
CREATE DATABASE IF NOT EXISTS qc_dashboard 
  DEFAULT CHARACTER SET utf8mb4 
  COLLATE utf8mb4_unicode_ci;
```

#### 2.2 确认数据表存在

项目使用的主表：`fact_qa_event`

必需字段：
- `biz_date` (日期)
- `queue_name` (队列名称)
- `reviewer_name` (审核人)
- `is_final_correct` (是否最终正确)
- `is_misjudge` (是否误判)
- `is_appealed` (是否申诉)
- `error_type` (错误类型)

#### 2.3 验证数据

```sql
-- 检查数据量
SELECT biz_date, COUNT(*) as count
FROM fact_qa_event
WHERE biz_date >= '2026-03-26'
GROUP BY biz_date
ORDER BY biz_date DESC
LIMIT 7;

-- 应该看到最近7天的数据
```

### Step 3: 配置环境变量

#### 3.1 复制配置模板

```bash
cp .env.example .env
```

#### 3.2 编辑 .env 文件

**必填项**:
```bash
# TiDB 连接信息（从DBA获取）
TIDB_HOST=your-tidb-host.tidbcloud.com
TIDB_PORT=4000
TIDB_USER=your_username
TIDB_PASSWORD=your_password
TIDB_DATABASE=qc_dashboard
```

**可选项**:
```bash
# API 配置
API_ALLOW_ORIGINS=http://localhost:3000,http://your-domain.com
API_SLOW_THRESHOLD_MS=800

# 日志配置
LOG_LEVEL=INFO

# 前端配置
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

#### 3.3 配置前端环境变量

```bash
cd frontend
cp .env.local.example .env.local  # 如果有的话
```

编辑 `frontend/.env.local`:
```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Step 4: 安装依赖

#### 4.1 后端依赖

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 验证安装
python -c "import fastapi; print('FastAPI安装成功')"
```

#### 4.2 前端依赖

```bash
cd frontend
npm install

# 验证安装
npm list next react
```

### Step 5: 数据库连接测试

```bash
# 测试数据库连接
python -c "
from storage.tidb_manager import TiDBManager
db = TiDBManager()
result = db.execute_query('SELECT COUNT(*) FROM fact_qa_event', ())
print(f'✅ 数据库连接成功，共有 {result[0][0]} 条记录')
"
```

**期望输出**: `✅ 数据库连接成功，共有 XXXXX 条记录`

### Step 6: 启动后端服务

#### 方式A: 使用启动脚本（推荐）

```bash
# 在项目根目录
./start_api.sh

# 期望输出:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# INFO:     Application startup complete.
```

#### 方式B: 手动启动

```bash
source .venv/bin/activate
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 方式C: 指定端口和主机

```bash
PORT=8080 HOST=0.0.0.0 ./start_api.sh
```

### Step 7: 启动前端服务

#### 方式A: 使用启动脚本（推荐）

```bash
# 在项目根目录，新开一个终端
./start_frontend.sh

# 期望输出:
# ▲ Next.js running on http://localhost:3000
```

#### 方式B: 手动启动

```bash
cd frontend
npm run dev
```

#### 方式C: 生产构建

```bash
cd frontend
npm run build
npm start
```

### Step 8: 验证部署

#### 8.1 后端健康检查

```bash
curl http://localhost:8000/api/health
```

**期望输出**:
```json
{
  "ok": true,
  "service": "qc-dashboard-api",
  "version": "0.1.0",
  "routers": {
    "monitor": true,
    "analysis": true,
    "visualization": true
  }
}
```

#### 8.2 前端访问测试

打开浏览器访问:
- **首页**: http://localhost:3000
- **实时监控**: http://localhost:3000/monitor
- **错误分析**: http://localhost:3000/error-analysis
- **数据可视化**: http://localhost:3000/visualization

#### 8.3 API文档访问

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

---

## 配置说明

### 后端配置文件

#### 1. 环境变量 (.env)

| 变量名 | 说明 | 默认值 | 示例 |
|-------|------|--------|------|
| `TIDB_HOST` | TiDB主机地址 | 无 | `gateway.tidbcloud.com` |
| `TIDB_PORT` | TiDB端口 | 4000 | `4000` |
| `TIDB_USER` | 数据库用户名 | 无 | `root` |
| `TIDB_PASSWORD` | 数据库密码 | 无 | `password123` |
| `TIDB_DATABASE` | 数据库名 | `qc_dashboard` | `qc_dashboard` |
| `API_ALLOW_ORIGINS` | CORS允许的源 | `*` | `http://localhost:3000` |
| `API_SLOW_THRESHOLD_MS` | 慢请求阈值(ms) | 800 | `1000` |
| `LOG_LEVEL` | 日志级别 | `INFO` | `DEBUG` |

#### 2. 启动参数

```bash
# 自定义端口
PORT=8080 ./start_api.sh

# 自定义主机（允许外部访问）
HOST=0.0.0.0 ./start_api.sh

# 指定Python解释器
PYTHON_BIN=/usr/bin/python3 ./start_api.sh
```

### 前端配置文件

#### 1. 环境变量 (.env.local)

```bash
# API 基础地址
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# 如果部署到子路径（例如 /qc-dashboard）
# NEXT_PUBLIC_BASE_PATH=/qc-dashboard
```

#### 2. 启动参数

```bash
# 自定义端口
PORT=3001 ./start_frontend.sh

# 指定API地址
QC_API_BASE_URL=http://192.168.1.100:8000 ./start_frontend.sh
```

---

## 健康检查

### 后端健康检查

```bash
# 基础健康检查
curl http://localhost:8000/api/health

# 检查特定路由
curl http://localhost:8000/api/v1/monitor/dashboard?date=2026-04-01

# 检查API文档
curl http://localhost:8000/api/docs
```

### 前端健康检查

```bash
# 检查首页
curl http://localhost:3000

# 检查特定页面
curl http://localhost:3000/monitor
```

### 数据库连接检查

```bash
# 使用Python脚本检查
python -c "
from storage.tidb_manager import TiDBManager
db = TiDBManager()
try:
    result = db.execute_query('SELECT 1', ())
    print('✅ 数据库连接正常')
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
"
```

---

## 常见问题

### Q1: 后端启动失败，提示 "ModuleNotFoundError"

**原因**: Python依赖未安装或虚拟环境未激活

**解决**:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Q2: 前端启动失败，提示 "Cannot find module 'next'"

**原因**: npm依赖未安装

**解决**:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Q3: 数据库连接失败

**原因**: TiDB连接信息错误或网络不通

**解决**:
```bash
# 1. 检查 .env 文件配置
cat .env | grep TIDB

# 2. 测试网络连通性
telnet <TIDB_HOST> <TIDB_PORT>

# 3. 验证用户名密码
mysql -h <TIDB_HOST> -P <TIDB_PORT> -u <USER> -p
```

### Q4: CORS 错误

**现象**: 前端控制台报错 "CORS policy: No 'Access-Control-Allow-Origin' header"

**解决**:
```bash
# 在 .env 中添加前端地址
API_ALLOW_ORIGINS=http://localhost:3000,http://your-domain.com
```

### Q5: 页面显示"加载中..."不结束

**原因**: API请求失败或数据为空

**排查**:
```bash
# 1. 检查后端是否运行
curl http://localhost:8000/api/health

# 2. 检查API响应
curl http://localhost:8000/api/v1/monitor/dashboard?date=2026-04-01

# 3. 查看浏览器Console错误
# 打开开发者工具 (F12) -> Console
```

### Q6: 端口被占用

**现象**: "Address already in use"

**解决**:
```bash
# 查找占用端口的进程
lsof -i :8000  # 查看8000端口
lsof -i :3000  # 查看3000端口

# 杀死进程
kill -9 <PID>

# 或使用其他端口
PORT=8001 ./start_api.sh
```

---

## 故障排查

### 1. 后端日志查看

```bash
# 如果使用systemd
journalctl -u qc-dashboard-api -f

# 如果使用Docker
docker-compose logs -f api

# 如果直接运行
tail -f logs/dashboard.log
```

### 2. 前端日志查看

```bash
# 开发模式：终端输出
# 生产模式：
tail -f frontend/.next/logs/out.log
```

### 3. 数据库查询慢

**排查步骤**:
```sql
-- 查看慢查询
SHOW PROCESSLIST;

-- 分析查询计划
EXPLAIN SELECT * FROM fact_qa_event WHERE biz_date = '2026-04-01';

-- 检查索引
SHOW INDEX FROM fact_qa_event;
```

**优化建议**:
- 确保 `biz_date` 字段有索引
- 限制查询时间范围
- 使用缓存

### 4. 内存占用过高

**排查**:
```bash
# 查看进程内存
ps aux | grep python
ps aux | grep node

# 查看系统内存
free -h
```

**优化**:
- 减少并发请求数
- 增加系统内存
- 优化SQL查询

---

## 生产环境建议

### 1. 使用进程管理器

#### 方式A: systemd（推荐Linux）

创建 `/etc/systemd/system/qc-dashboard-api.service`:
```ini
[Unit]
Description=QC Dashboard API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/qc-dashboard
Environment="PATH=/path/to/qc-dashboard/.venv/bin"
ExecStart=/path/to/qc-dashboard/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable qc-dashboard-api
sudo systemctl start qc-dashboard-api
sudo systemctl status qc-dashboard-api
```

#### 方式B: PM2（推荐Node.js生态）

```bash
# 安装PM2
npm install -g pm2

# 启动后端
pm2 start ./start_api.sh --name qc-api

# 启动前端
cd frontend
pm2 start npm --name qc-frontend -- start

# 查看状态
pm2 status

# 查看日志
pm2 logs qc-api
pm2 logs qc-frontend

# 设置开机自启
pm2 startup
pm2 save
```

### 2. 配置Nginx反向代理

创建 `/etc/nginx/sites-available/qc-dashboard`:
```nginx
server {
    listen 80;
    server_name qc-dashboard.your-domain.com;

    # 前端
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置:
```bash
sudo ln -s /etc/nginx/sites-available/qc-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. 日志轮转

创建 `/etc/logrotate.d/qc-dashboard`:
```
/path/to/qc-dashboard/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 644 www-data www-data
}
```

### 4. 监控告警

建议配置:
- **应用监控**: 使用 Prometheus + Grafana
- **日志监控**: 使用 ELK Stack
- **告警**: 配置 Alertmanager

---

## 安全建议

1. **不要将 `.env` 文件提交到Git**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **使用强密码**
   - TiDB密码至少12位
   - 包含大小写字母、数字、特殊字符

3. **限制API访问**
   - 配置 `API_ALLOW_ORIGINS` 仅允许可信域名
   - 考虑添加API认证

4. **定期更新依赖**
   ```bash
   pip list --outdated
   npm outdated
   ```

---

## 附录

### A. 目录结构

```
~/WorkBuddy/20260326191218/
├── api/                    # 后端API代码
│   ├── main.py            # FastAPI入口
│   ├── routers/           # 路由模块
│   └── exceptions.py      # 异常处理
├── frontend/              # Next.js前端
│   ├── src/
│   │   ├── app/          # 页面路由
│   │   └── lib/          # API客户端
│   └── package.json
├── storage/               # 数据库管理
│   └── tidb_manager.py
├── logs/                  # 日志文件
├── .env                   # 环境变量（需创建）
├── .env.example          # 环境变量模板
├── requirements.txt      # Python依赖
├── start_api.sh          # 后端启动脚本
└── start_frontend.sh     # 前端启动脚本
```

### B. 端口说明

| 服务 | 默认端口 | 说明 |
|-----|---------|------|
| 后端API | 8000 | FastAPI服务 |
| 前端Web | 3000 | Next.js开发服务器 |
| TiDB | 4000 | 数据库连接端口 |

### C. 环境变量完整列表

参见 `.env.example` 文件

---

## 联系支持

- **文档**: `docs/`
- **问题反馈**: 提交Issue或联系团队管理员
- **用户手册**: 参见 `USER_GUIDE.md`

---

**部署文档版本**: v1.0.0  
**最后更新**: 2026-04-22  
**维护者**: 质培团队
