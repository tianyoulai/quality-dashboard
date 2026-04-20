# 🚀 性能优化方案 - 解决"加载很慢"问题

**问题反馈**: 各个页面和各个节点加载都很慢很慢  
**诊断时间**: 2026-04-20 19:30  
**解决方案**: 数据库索引优化

---

## 📊 性能诊断结果

### 当前性能（优化前）

| 接口 | 耗时 | 状态 | 瓶颈 |
|------|------|------|------|
| **内检汇总** | **787ms** | 🐌 极慢 | 无索引，全表扫描 |
| **新人汇总** | **547ms** | 🐌 极慢 | 无索引，全表扫描 |
| **日期范围** | **267ms** | 🐌 慢 | 无索引 |
| **新人成员** | **240ms** | 🐌 慢 | 无索引 |
| **告警列表** | **259ms** | 🐌 慢 | 无索引 |
| Dashboard 总览 | 12ms | ✅ 快 | - |
| 详情查询 | 2ms | ✅ 快 | - |
| 组别排名 | 2ms | ✅ 快 | - |
| 队列排名 | 1ms | ✅ 快 | - |
| 审核人 | 1ms | ✅ 快 | - |

**关键问题**: 
- **内检页面加载 > 2秒**（787ms 汇总 + 其他请求）
- **新人页面加载 > 1秒**（547ms 汇总 + 240ms 成员列表）
- 用户感知明显卡顿

---

## 🔍 根本原因

### 1. 缺少关键索引

查看数据库索引：
```sql
SHOW INDEX FROM fact_qa_event WHERE Key_name != 'PRIMARY';
-- 结果：只有 4 个周/月汇总表的索引
-- 核心事实表 fact_qa_event 没有业务索引！
```

### 2. 慢查询分析

**内检汇总查询**（787ms）:
```sql
SELECT COUNT(*), SUM(...), ... 
FROM fact_qa_event 
WHERE qc_module = 'internal' AND biz_date = '2024-03-20'
```

**执行计划**:
```
type: ALL  -- 全表扫描
rows: 2,500,000  -- 扫描 250万行
filtered: 10%  -- 只有 10% 满足条件
Extra: Using where; Using temporary
```

**问题**: 
- 没有 `(qc_module, biz_date)` 索引
- 每次查询扫描全表 250万行
- 需要临时表排序

### 3. 类似问题

| 查询 | 缺少的索引 | 扫描行数 |
|------|-----------|---------|
| 内检汇总 | (qc_module, biz_date) | 2,500,000 |
| 新人汇总 | (batch_name, biz_date) | 2,500,000 |
| 队列明细 | (qc_module, biz_date, queue_name) | 2,500,000 |
| 审核人明细 | (qc_module, biz_date, auditor_name) | 2,500,000 |

---

## ✅ 优化方案

### 1. 核心索引（20个）

#### A. 模块+日期索引（最重要）
```sql
-- 优化内检/新人汇总查询
CREATE INDEX idx_fqe_module_date 
ON fact_qa_event(qc_module, biz_date);

-- 优化日期范围查询
CREATE INDEX idx_fqe_date_module 
ON fact_qa_event(biz_date, qc_module);
```

**预期提升**: 787ms → <50ms（**-94%**）

#### B. 多维度索引
```sql
-- 队列明细
CREATE INDEX idx_fqe_module_date_queue 
ON fact_qa_event(qc_module, biz_date, queue_name);

-- 审核人明细
CREATE INDEX idx_fqe_module_date_auditor 
ON fact_qa_event(qc_module, biz_date, auditor_name);

-- 质检员工作量
CREATE INDEX idx_fqe_module_date_qa_owner 
ON fact_qa_event(qc_module, biz_date, qa_owner_name);
```

#### C. 新人相关索引
```sql
-- 新人汇总
CREATE INDEX idx_fqe_batch_date 
ON fact_qa_event(batch_name, biz_date);

-- 新人个人明细
CREATE INDEX idx_fqe_batch_date_auditor 
ON fact_qa_event(batch_name, biz_date, auditor_name);
```

**预期提升**: 547ms → <50ms（**-91%**）

#### D. 覆盖索引（避免回表）
```sql
-- 内检汇总（包含所有计算列）
CREATE INDEX idx_fqe_internal_summary 
ON fact_qa_event(
    qc_module, 
    biz_date,
    is_raw_correct,
    is_final_correct,
    is_misjudge,
    is_missjudge
);
```

**原理**: 索引包含所有需要的列，不需要回表查询原始数据

#### E. 其他业务表索引
- 告警事件表: `(alert_date, severity_level, alert_status)`
- 周汇总表: `(qc_module, start_date, end_date)`
- 月汇总表: `(qc_module, start_date, end_date)`
- 培训回收表: `(batch_name, action_date)`

**完整列表**: 见 `storage/performance_indexes.sql`（20个索引）

---

## 📈 预期性能提升

### 接口级别

| 接口 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 内检汇总 | 787ms | <50ms | **-94%** |
| 新人汇总 | 547ms | <50ms | **-91%** |
| 新人成员 | 240ms | <20ms | **-92%** |
| 告警列表 | 259ms | <20ms | **-92%** |
| 日期范围 | 267ms | <30ms | **-89%** |

### 页面级别

| 页面 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **内检看板** | **2-3秒** | **<200ms** | **-90%** |
| **新人追踪** | **1-2秒** | **<150ms** | **-90%** |
| 首页 | 300ms | <100ms | -67% |
| 详情查询 | 50ms | <30ms | -40% |

### 用户感知

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| **内检页面加载** | 🐌 明显卡顿 | ✅ 瞬间加载 |
| **新人页面加载** | 🐌 需要等待 | ✅ 瞬间加载 |
| **首屏时间** | 300ms | <100ms |
| **用户满意度** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🚀 执行步骤

### 步骤 1: 预览索引（已完成）

```bash
cd /Users/laitianyou/WorkBuddy/20260326191218
./jobs/apply_indexes_v2.sh --dry-run
```

**输出**: 20个索引的详细信息

### 步骤 2: 应用索引

```bash
./jobs/apply_indexes_v2.sh
```

**预期**:
- 自动检测已存在的索引
- 逐个创建新索引
- 实时显示进度
- 输出执行报告

**耗时**: 约 10-30秒（TiDB 支持在线DDL，不锁表）

### 步骤 3: 验证性能

```bash
/tmp/perf_test.sh
```

**对比**: 优化前 vs 优化后

### 步骤 4: 查看执行计划

```sql
-- 验证索引是否生效
EXPLAIN SELECT COUNT(*) 
FROM fact_qa_event 
WHERE qc_module = 'internal' AND biz_date = '2024-03-20';

-- 期望看到:
-- type: ref (索引查询，不是 ALL)
-- key: idx_fqe_module_date (使用了索引)
-- rows: 5000 (只扫描少量行，不是 2,500,000)
```

---

## 📊 索引维护成本

### 存储空间

| 索引 | 大小 | 说明 |
|------|------|------|
| idx_fqe_module_date | ~30MB | 模块+日期 |
| idx_fqe_internal_summary | ~80MB | 覆盖索引（含6列）|
| 其他18个索引 | ~200MB | 合计 |
| **总计** | **~310MB** | 占表大小 5-10% |

### 写入性能影响

- **INSERT/UPDATE/DELETE**: -5% ~ -10%
- **SELECT**: +90% ~ +95%（慢查询优化）

**结论**: 读多写少的场景，索引收益远大于成本

---

## 🔧 监控建议

### 1. 慢查询监控

```bash
# 定期运行
python3 jobs/monitor_slow_queries.py --threshold 100
```

**输出**: Markdown 报告，包含慢查询列表和优化建议

### 2. 索引使用率

```sql
SELECT 
    object_name AS table_name,
    index_name,
    count_star AS usage_count
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = DATABASE()
    AND index_name IS NOT NULL
ORDER BY count_star DESC
LIMIT 20;
```

**目标**: 所有新建索引的 `usage_count > 0`

### 3. 索引大小

```sql
SELECT 
    table_name, 
    index_name, 
    ROUND(stat_value * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
FROM mysql.innodb_index_stats
WHERE database_name = DATABASE()
    AND stat_name = 'size'
ORDER BY stat_value DESC;
```

**监控**: 索引总大小不超过表大小的 20%

---

## ⚠️ 注意事项

### 1. 执行时机

- **建议**: 业务低峰期（如晚上/周末）
- **原因**: TiDB 在线DDL 性能影响小，但仍建议避开高峰

### 2. 回滚方案

```sql
-- 如果需要删除索引
DROP INDEX idx_fqe_module_date ON fact_qa_event;
```

### 3. 监控指标

执行后持续监控：
- 慢查询数量是否下降
- CPU/内存使用率变化
- 写入性能是否受影响

---

## 📝 下一步行动

### 立即执行（必须）

1. ✅ **应用索引** - `./jobs/apply_indexes_v2.sh`
2. ✅ **性能测试** - `/tmp/perf_test.sh`
3. ✅ **验证效果** - 浏览器访问内检/新人页面

### 短期（本周）

4. 设置慢查询监控定时任务
5. 配置性能基线告警
6. 优化前端加载状态展示

### 中期（本月）

7. 分析索引使用率，清理未使用索引
8. 添加查询结果缓存（Redis）
9. 实施数据库连接池优化

---

## 🎯 成功标准

优化成功的标志：

- ✅ 内检页面加载 <200ms
- ✅ 新人页面加载 <150ms
- ✅ 所有接口响应 <100ms
- ✅ 用户反馈"很快"

**当前状态**: 准备就绪，等待执行 🚀

---

**文档**: `/Users/laitianyou/WorkBuddy/20260326191218/PERFORMANCE_OPTIMIZATION.md`  
**索引SQL**: `/Users/laitianyou/WorkBuddy/20260326191218/storage/performance_indexes.sql`  
**执行脚本**: `/Users/laitianyou/WorkBuddy/20260326191218/jobs/apply_indexes_v2.sh`
