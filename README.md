# 质培运营看板项目骨架

这套目录现在已经不是静态 demo，而是一版能继续接真实数据、直接往本机部署推进的骨架。

## 当前结构

```text
app.py
jobs/
  ├── import_fact_data.py
  ├── refresh_warehouse.py
  ├── validate_join_quality.py
  └── refresh_alerts.py
pages/
  └── 01_首页.py
services/
  └── dashboard_service.py
storage/
  ├── schema.sql
  └── repository.py
deliverables/
  ├── qa_ops_demo.html
  └── qa_dashboard_schema_duckdb.sql
```

## 各文件职责

### `app.py`
Streamlit 主入口。

负责：
- 页面入口说明
- 初始化 DuckDB schema
- 检查当前是否已有 fact 数据

### `storage/schema.sql`
项目内部真正执行的 DuckDB schema。

负责：
- fact 层
- mart 层
- alert 层
- 告警状态流转层
- 高频错误专题层
- 培训 / 整改动作代理与回收跟踪层

### `storage/repository.py`
所有 DuckDB 查询统一收口。

负责：
- 查询组别总览
- 查询队列下探
- 查询审核人下探
- 查询问题样本
- 查询趋势和异常
- 查询培训 / 整改动作后的 1 周 / 2 周回收结果

### `services/dashboard_service.py`
业务组装层。

负责：
- 日 / 周 / 月锚点归一化
- 页面 payload 组装
- 告警汇总、快速定位与建议动作生成
- 告警状态文案、历史查询与基础 SLA 计算
- 按告警规则切换到对应的联表样本 / 问题样本
- 培训动作建议生成
- 培训 / 整改动作代理的回收汇总与状态判定

### `pages/01_首页.py`
首页真实页面骨架。

负责：
- 日监控 / 周复盘 / 月管理切换
- P0 / P1 / P2 告警总览
- 告警待处理 / 已认领 / 已忽略 / 已解决统计
- 规则级 SLA 超时统计、阶段起点与截止时间展示
- 按状态 / 级别 / 对象层级 / 关键词筛选告警
- 按告警快速定位到组别 / 队列
- 首页直接做单条认领 / 忽略 / 已解决流转
- 首页直接做批量认领 / 忽略 / 已解决流转
- 直接展示告警处理历史
- 直接展示告警关联样本
- 直接展示培训 / 整改动作后的 1 周 / 2 周回收跟踪
- 导出当前告警样本 / 问题样本 / 回收跟踪 CSV
- 队列下探
- 审核人下探
- 问题样本明细展示

### `jobs/import_fact_data.py`
真实数据导入脚本。

负责：
- 读取 `.csv / .xlsx / .xls / .parquet`
- 按中英文字段别名自动对齐到 fact 表结构
- 为线下质检 / 线上申诉统一生成 `join_key`
- 补 `row_hash` 去重
- 写入 `fact_qa_event` / `fact_appeal_event`
- 记录 `etl_run_log`
- 导入完成后可自动刷新 mart

### `jobs/refresh_warehouse.py`
刷新仓库脚本。

负责：
- 重跑 `storage/schema.sql`
- 刷新 `vw_qa_base`
- 刷新 `mart_day_* / mart_week_* / mart_month_*`
- 刷新 `mart_training_action_recovery`
- 输出刷新后的关键表行数，方便核对

### `jobs/validate_join_quality.py`
联表质量校验脚本。

负责：
- 输出 `join_key` 命中率 / 回填率
- 输出缺失主键样本、未命中样本、孤儿申诉样本
- 帮你确认线下质检和线上申诉是否正确结合

### `jobs/refresh_alerts.py`
告警跑批脚本。

负责：
- 重算 `fact_alert_event`
- 根据规则表生成 P0 / P1 / P2 告警事件
- 当前覆盖联表命中率、缺失主键、申诉改判率、队列最终正确率等首批规则

---

## 如何跑起来

### 1. 安装依赖

```bash
pip install streamlit duckdb pandas openpyxl pyarrow
```

说明：
- `openpyxl` 用于读取 `.xlsx`
- `pyarrow` 用于读取 `.parquet`

### 2. 初始化数据库

```bash
streamlit run app.py
```

进入页面后点击：
- `初始化 Schema`

会在下面这个位置创建数据库：

```text
data/warehouse/qa.duckdb
```

### 3. 导入质检明细 / 申诉明细

只导入质检明细：

```bash
python3 jobs/import_fact_data.py \
  --qa-file /你的路径/qa_detail.xlsx
```

同时导入质检和申诉：

```bash
python3 jobs/import_fact_data.py \
  --qa-file /你的路径/qa_detail.xlsx \
  --appeal-file /你的路径/appeal_detail.xlsx
```

如果你只想先入 fact，不立刻刷新 mart：

```bash
python3 jobs/import_fact_data.py \
  --qa-file /你的路径/qa_detail.xlsx \
  --skip-refresh
```

脚本会输出：
- `source_rows`
- `inserted_rows`
- `dedup_rows`
- `warning_rows`
- `batch_id`

### 4. 单独刷新仓库

```bash
python3 jobs/refresh_warehouse.py
```

这个脚本适合：
- 你已经导入完多批明细，想统一刷新一次 mart
- 你改了 `storage/schema.sql`，想重跑结果层

### 5. 先跑联表质量校验

```bash
python3 jobs/validate_join_quality.py
```

如果你想把校验结果落成文件：

```bash
python3 jobs/validate_join_quality.py \
  --output deliverables/join_quality_report.json
```

这个脚本会直接给你几类最关键的信息：
- `qa_match_rate`：线下质检样本整体命中线上申诉的比例
- `qa_match_rate_when_key_present`：有 `join_key` 的样本里，真正能联上的比例
- `qa_result_backfill_rate`：能拿到线上最终结果并回填的比例
- `unmatched_qa_samples`：线下有、线上没联上的样本
- `missing_join_key_samples`：主键缺失，根本没法联表的样本
- `orphan_appeal_samples`：线上申诉有、线下质检找不到的样本
- `conflicting_appeal_keys`：同一个 `join_key` 下有多条申诉记录的样本

### 6. 跑告警批次

```bash
python3 jobs/refresh_alerts.py
```

如果你只想回刷最近 30 天：

```bash
python3 jobs/refresh_alerts.py \
  --lookback-days 30
```

当前已落地的告警规则包括：
- 组别日原始正确率过低
- 队列日最终正确率过低
- 队列日漏判率过高
- 组别日申诉改判率过高
- 全局日联表命中率过低
- 全局日缺失关联主键占比过高
- 组别周原始正确率较上周下跌超 1.5 个百分点
- 队列周漏判率较上周上升超 0.2 个百分点
- 队列月度单一错误类型占比高于 35%

### 7. 打开首页页面

```bash
streamlit run app.py
```

然后进入：
- `pages/01_首页.py`

只要 `fact_qa_event` 已经有数据，且你跑过告警批次，页面就会开始展示真实指标和异常卡片，并支持按状态 / 级别 / 对象层级 / 关键词先把告警筛干净，再按告警直接定位到对应组别 / 队列继续下探，还能直接看到这条告警对应的联表异常样本或业务问题样本；如果你要拉给业务复盘，也可以直接把当前告警样本或问题样本导出成 CSV。现在首页除了支持单条告警认领 / 忽略 / 已解决，也支持对当前筛选结果或手动选中的多条告警做统一流转，并记录处理人和备注；同时会按规则优先匹配更细的 SLA 时限，展示当前阶段起点、SLA 截止时间、总超时 / 待处理超时 / 已认领超时统计，以及单条告警的处理历史。最新还补了一块“培训 / 整改回收跟踪”，会把 `ERROR_TYPE_SHARE_GT_15_QUEUE_WEEK` 这类未收敛告警在被认领 / 解决后，继续跟踪动作当周、1 周后、2 周后的错误占比变化，用来快速判断这次动作有没有把问题压下去。

---

## 当前导入脚本支持什么

### 支持的输入格式
- CSV
- Excel (`.xlsx / .xls`)
- Parquet

### 支持的字段对齐方式
脚本不是死卡英文列名，而是会按常见别名自动识别，比如：

- `业务日期 / 日期 / biz_date`
- `组别 / group_name`
- `队列 / queue_name`
- `审核人 / reviewer_name`
- `错误类型 / error_type`
- `质检结果 / qa_result`
- `申诉状态 / appeal_status`

也就是说，你现在手上的表头只要不是太离谱，大概率不用先手改一遍字段名。

### 当前主键结合策略
旧版线上逻辑里，质检和申诉是靠 `评论ID + 动态ID` 结合，再取申诉侧最新一条结果。

现在这版 DuckDB 里我把它收敛成统一 `join_key`：
- 优先用 `source_record_id / 主键ID`
- 没有主键时，回退为 `评论ID + 动态ID`
- 再没有时，回退为单独 `评论ID / 动态ID / 账号ID`

然后：
- `fact_appeal_event` 先按 `join_key` 取最新申诉记录
- `vw_qa_base` 再把线上申诉结果回填到线下质检样本
- `final_accuracy_rate / appeal_reverse_rate` 都基于联表后的结果算

### 当前去重策略
按 `row_hash` 去重，哈希会综合以下信息生成：
- 业务日期
- 组别 / 队列 / 审核人
- 记录 ID / 评论 ID / 动态 ID
- 标签 / 结果 / 错误类型 / 备注
- 来源文件名

这套策略的目的很直接：
**避免同一批文件反复导入，也尽量避免同一条样本被重复落库。**

---

## 现在还没补完的部分

这版已经能导入明细、校验联表质量并跑日 / 周 / 月三层首批与第二批告警，但还没补完下面几件事：

1. 更完整的训练动作异常闭环（比如培训后 1 周 / 2 周是否真正回收、整改动作是否见效）
2. 原始文件字段映射的外部配置化
3. SLA 自动通知 / 升级策略（超时提醒、升级催办）
4. 自动任务调度
5. 更完整的 Streamlit 页面美化

---

## 我建议你接下来的推进顺序

### 第一步
拿一份真实质检明细先跑 `jobs/import_fact_data.py`。

目标不是一口气全量，而是先验证：
- 字段能不能识别
- 日期能不能正常归一
- `fact_qa_event` 能不能顺利落数

### 第二步
跑 `jobs/refresh_warehouse.py`，核对 `mart_day_group`、`mart_week_group`、`mart_month_group` 有没有结果。

### 第三步
打开首页，检查：
- 组别切换
- 队列下探
- 审核人下探
- 问题样本明细

### 第四步
跑 `jobs/refresh_alerts.py`，把异常卡片真正点亮，并先验证首批规则是否符合你的业务感知。

---

## 我的判断

现�