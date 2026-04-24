# 📊 评论业务质检看板

基于 Streamlit 的评论审核质检数据分析看板，配合 DeepSeek 4.0 Pro AI 洞察 + 企微群自动推送。

## 功能模块

| 模块 | 说明 |
|------|------|
| **数据管理** | Excel/CSV 批量导入、新人名单管理、数据健康检查 |
| **总览** | 日/周/月维度正确率趋势、组别排名、KPI 达标监控 |
| **内检** | 内检质检数据分析、审核人排名、错误类型分布 |
| **明细查询** | 多维筛选 + 下钻、审核人/队列维度统计 |
| **新人追踪** | 批次概览、成长曲线、阶段对比、个人追踪、异常告警 |

## 报告推送

| 报告 | 触发 | 内容 |
|------|------|------|
| **日报** | 每日定时 | 正确率 + 分组表现 + 风险 + AI 洞察 |
| **周报** | 每周五 | 周趋势 + 周环比 + 周告警 + AI 洞察 |
| **新人日报** | 每日定时 | 批次表现 + 异常人员 + 培训建议 |

## 项目结构

```
quality-dashboard/
├── app.py                      # Streamlit 入口
├── pages/                      # Streamlit 多页面
│   ├── 00_数据管理.py
│   ├── 01_总览.py
│   ├── 02_内检.py
│   ├── 03_明细查询.py
│   └── 04_新人追踪.py
├── views/newcomer/             # 新人追踪子模块
├── services/                   # 业务逻辑层
│   ├── dashboard_service.py    # 主查询服务
│   ├── module_views.py         # 视图渲染
│   ├── newcomer_aggregates.py  # 新人聚合
│   └── wecom_push.py           # 企微推送
├── reports/                    # 报告引擎
│   ├── engine.py               # 数据采集 + AI 洞察
│   └── formatters/             # 格式化器（企微卡片/Markdown）
├── jobs/                       # 定时任务
│   ├── daily_report.py         # 日报生成 & 推送
│   ├── weekly_report.py        # 周报生成 & 推送
│   ├── newcomer_daily_report.py
│   ├── import_fact_data.py     # 主数据导入
│   ├── import_newcomer_qa.py   # 新人数据导入
│   └── ...
├── storage/                    # 数据层
│   ├── tidb_manager.py         # TiDB 连接池（单例）
│   ├── repository.py           # 数据仓库
│   └── schema.sql              # 表结构
├── utils/                      # 工具函数
├── config/                     # 配置（不提交 Git）
│   ├── settings.json           # 数据库/API 密钥
│   └── alert_modules.yaml      # 告警规则
└── .github/workflows/          # GitHub Actions
    └── daily-report.yml        # 自动化报告推送
```

## 快速开始

### 1. 配置

复制配置模板并填入实际值：

```bash
cp .env.example config/settings.json
# 编辑 config/settings.json，填入 TiDB、企微 Webhook、DeepSeek API Key
```

`config/settings.json` 格式：

```json
{
  "tidb": {
    "host": "your_host.tidbcloud.com",
    "port": 4000,
    "user": "your_user",
    "password": "your_password",
    "database": "your_db"
  },
  "wecom_webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key",
  "deepseek": {
    "api_key": "sk-your_key",
    "api_url": "https://api.deepseek.com/v1/chat/completions",
    "model": "deepseek-reasoner"
  },
  "dashboard_url": "https://your-app.streamlit.app/"
}
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动看板

```bash
streamlit run app.py
```

### 4. 生成报告

```bash
# 日报（dry-run 模式，不推送）
python jobs/daily_report.py --dry-run

# 周报
python jobs/weekly_report.py --dry-run

# 新人日报
python jobs/newcomer_daily_report.py --dry-run

# 实际推送
python jobs/daily_report.py
```

## 部署

### Streamlit Cloud（推荐）

1. Fork 本仓库到 GitHub
2. 在 [Streamlit Cloud](https://share.streamlit.io/) 创建应用
3. 在 Secrets 中配置 TiDB 连接信息
4. 自动部署完成

### GitHub Actions 定时报告

在仓库 Settings → Secrets 中配置：

| Secret | 说明 |
|--------|------|
| `TIDB_HOST` | TiDB 主机地址 |
| `TIDB_PORT` | TiDB 端口 |
| `TIDB_USER` | TiDB 用户名 |
| `TIDB_PASSWORD` | TiDB 密码 |
| `TIDB_DATABASE` | 数据库名 |
| `WECOM_WEBHOOK_URL` | 企微群 Webhook URL |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |

## 技术栈

- **前端**: Streamlit（Python）
- **数据库**: TiDB Cloud（MySQL 兼容）
- **AI**: DeepSeek 4.0 Pro（deepseek-reasoner）
- **推送**: 企业微信群 Webhook
- **CI/CD**: GitHub Actions + Streamlit Cloud
