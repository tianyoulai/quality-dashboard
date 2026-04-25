# 📊 评论业务质检看板

[![CI — Tests & Lint](https://github.com/YOUR_ORG/quality-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/quality-dashboard/actions/workflows/ci.yml)

基于 Streamlit 的评论审核质检数据分析看板，配合 DeepSeek 4.0 Pro AI 洞察 + 企微群自动推送。

📖 **[用户使用手册](docs/USER_GUIDE.md)** — 面向业务人员的操作指南

## 功能模块

| 模块 | 说明 |
|------|------|
| **数据管理** | Excel/CSV 批量导入、新人名单管理、告警规则管理、数据健康检查、操作审计日志 |
| **总览** | 日/周/月维度正确率趋势、组别排名、KPI 达标监控、组别下探分析 |
| **内检** | 内检质检数据分析、审核人排名、错误类型 TOP5 分布、审核一致性分析（一审 vs 终审偏差） |
| **明细查询** | 多维筛选 + 下钻、快速时间范围、审核人/队列维度统计、数据洞察 |
| **新人追踪** | 批次概览、成长曲线、阶段对比、个人追踪、异常告警 |

## 报告推送

| 报告 | 触发 | 内容 |
|------|------|------|
| **日报** | 每日 18:20 | 正确率 + 分组表现 + 风险 + AI 洞察 |
| **周报** | 每周五 18:30 | 周趋势 + 周环比 + 周告警 + AI 洞察 |
| **新人日报** | 每日 18:20 | 批次表现 + 异常人员 + 培训建议 |

## 项目结构

```
quality-dashboard/
├── app.py                          # Streamlit 入口
├── pages/                          # Streamlit 多页面
│   ├── 00_数据管理.py              # 数据导入/规则管理/健康检查
│   ├── 01_总览.py                  # 多维度数据总览
│   ├── 02_内检.py                  # 内检分析
│   ├── 03_明细查询.py              # 多维明细查询
│   └── 04_新人追踪.py              # 新人质检追踪
├── views/                          # 页面子模块
│   ├── dashboard/                  # 总览页子模块
│   ├── newcomer/                   # 新人追踪子模块
│   └── data_mgmt/                  # 数据管理子模块
├── services/                       # 业务逻辑层
│   ├── dashboard_service.py        # 主查询服务
│   ├── module_views.py             # 视图渲染
│   ├── newcomer_aggregates.py      # 新人聚合
│   ├── newcomer_lifecycle.py       # 新人生命周期管理
│   └── wecom_push.py               # 企微推送
├── reports/                        # 报告引擎
│   ├── engine.py                   # 数据采集 + AI 洞察
│   └── formatters/                 # 格式化器（企微卡片/Markdown）
├── jobs/                           # 定时任务 & 脚本
│   ├── daily_report.py             # 日报生成 & 推送
│   ├── weekly_report.py            # 周报生成 & 推送
│   ├── newcomer_daily_report.py    # 新人日报
│   ├── auto_maintenance.py         # 自动归档 & 健康检查
│   ├── import_fact_data.py         # 主数据导入
│   ├── import_newcomer_qa.py       # 新人数据导入
│   ├── refresh_warehouse.py        # 数仓刷新
│   ├── refresh_alerts.py           # 告警刷新
│   └── ...
├── storage/                        # 数据层
│   ├── tidb_manager.py             # TiDB 连接池（单例）
│   └── repository.py               # 数据仓库
├── utils/                          # 工具函数
│   ├── audit.py                    # 操作审计日志
│   ├── auth.py                     # 轻量权限控制
│   ├── export_center.py            # 导出中心
│   ├── design_system.py            # 统一设计系统（色彩/排版/组件）
│   ├── error_boundary.py           # 全局错误边界
│   ├── cache.py                    # 缓存管理
│   ├── helpers.py                  # 通用工具
│   ├── date_parser.py              # 日期解析
│   ├── constants.py                # 常量定义
│   ├── logger.py                   # 日志系统
│   └── alert_module.py             # 告警模块
├── config/                         # 配置（不提交 Git）
│   ├── settings.json               # 数据库/API 密钥
│   └── alert_modules.yaml          # 告警规则
└── .github/workflows/
    └── daily-report.yml            # GitHub Actions 统一调度
```

## 快速开始

### 1. 配置

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

# 实际推送（去掉 --dry-run）
python jobs/daily_report.py
```

## 测试

项目使用 pytest 进行单元测试，覆盖核心纯函数模块。

```bash
# 安装测试依赖
pip install pytest pytest-cov

# 运行全部测试
python -m pytest tests/ -v

# 运行测试 + 覆盖率报告
python -m pytest tests/ --cov=utils --cov-report=term-missing
```

测试覆盖模块：
- `utils/helpers.py` — 数据序列化、CSV 导出、安全百分比（覆盖率 96%）
- `utils/date_parser.py` — 文件名日期解析（覆盖率 86%）
- `utils/design_system.py` — 设计系统常量和纯函数
- `utils/error_boundary.py` — 错误边界上下文管理器
- `services/newcomer_lifecycle.py` — 新人状态常量和规则

### CI 自动化

每次 push 或 PR 到 main 分支时，GitHub Actions 会自动运行：

1. **语法检查**：对所有 `.py` 文件执行 `py_compile`
2. **单元测试**：运行 pytest 并生成覆盖率报告
3. **导入链检查**：验证核心模块导入无断裂

CI 配置文件：`.github/workflows/ci.yml`

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
| `TIDB_PORT` | TiDB 端口（默认 4000） |
| `TIDB_USER` | TiDB 用户名 |
| `TIDB_PASSWORD` | TiDB 密码 |
| `TIDB_DATABASE` | 数据库名 |
| `WECOM_WEBHOOK_URL` | 企微群 Webhook URL |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `DEEPSEEK_API_URL` | DeepSeek API URL |

Actions 统一调度：
- 日报 + 新人日报：每天 UTC 10:20（北京 18:20）
- 周报：每周五 UTC 10:30（北京 18:30）
- 支持手动触发，可选择报告类型（daily/weekly/newcomer/all）

## 技术栈

- **前端**: Streamlit（Python）
- **数据库**: TiDB Cloud（MySQL 兼容）
- **AI**: DeepSeek 4.0 Pro（deepseek-reasoner）
- **推送**: 企业微信群 Webhook
- **CI/CD**: GitHub Actions + Streamlit Cloud
