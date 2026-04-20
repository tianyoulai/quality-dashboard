-- ======================================
-- 🚀 高性能索引优化方案
-- ======================================
-- 目标：将慢查询从 500-800ms 降至 <50ms
-- 策略：为高频查询添加精准复合索引
--
-- 生成时间：2026-04-20
-- ======================================

-- ======================================
-- 1. fact_qa_event 核心索引（最重要！）
-- ======================================

-- 索引 1: 按模块+日期查询（内检/新人汇总最常用）
-- 覆盖查询: WHERE qc_module = 'internal' AND biz_date = '...'
CREATE INDEX IF NOT EXISTS idx_fqe_module_date 
ON fact_qa_event(qc_module, biz_date);

-- 索引 2: 按日期+模块查询（日期范围查询）
-- 覆盖查询: WHERE biz_date BETWEEN '...' AND '...' AND qc_module = '...'
CREATE INDEX IF NOT EXISTS idx_fqe_date_module 
ON fact_qa_event(biz_date, qc_module);

-- 索引 3: 按模块+日期+队列（队列明细查询）
-- 覆盖查询: WHERE qc_module = 'internal' AND biz_date = '...' AND queue_name = '...'
CREATE INDEX IF NOT EXISTS idx_fqe_module_date_queue 
ON fact_qa_event(qc_module, biz_date, queue_name);

-- 索引 4: 按模块+日期+审核人（审核人明细查询）
-- 覆盖查询: WHERE qc_module = 'internal' AND biz_date = '...' AND auditor_name = '...'
CREATE INDEX IF NOT EXISTS idx_fqe_module_date_auditor 
ON fact_qa_event(qc_module, biz_date, auditor_name);

-- 索引 5: 按模块+日期+质检员（质检员工作量查询）
-- 覆盖查询: WHERE qc_module = 'internal' AND biz_date = '...' AND qa_owner_name = '...'
CREATE INDEX IF NOT EXISTS idx_fqe_module_date_qa_owner 
ON fact_qa_event(qc_module, biz_date, qa_owner_name);

-- ======================================
-- 2. 新人相关索引
-- ======================================

-- 索引 6: 按批次+日期（新人成员查询）
-- 覆盖查询: WHERE batch_name IN (...) AND biz_date >= '...'
CREATE INDEX IF NOT EXISTS idx_fqe_batch_date 
ON fact_qa_event(batch_name, biz_date);

-- 索引 7: 按批次+日期+审核人（新人个人明细）
CREATE INDEX IF NOT EXISTS idx_fqe_batch_date_auditor 
ON fact_qa_event(batch_name, biz_date, auditor_name);

-- ======================================
-- 3. 聚合表索引（mart_*_group）
-- ======================================

-- 索引 8: 日汇总表（已存在，检查）
CREATE INDEX IF NOT EXISTS idx_mdg_group_date 
ON mart_day_group(group_name, biz_date);

CREATE INDEX IF NOT EXISTS idx_mdg_queue_date 
ON mart_day_group(queue_name, biz_date);

-- 索引 9: 周汇总表
CREATE INDEX IF NOT EXISTS idx_mwg_module_start_end 
ON mart_week_group(qc_module, start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_mwg_queue_dates 
ON mart_week_group(queue_name, start_date, end_date);

-- 索引 10: 月汇总表
CREATE INDEX IF NOT EXISTS idx_mmg_module_start_end 
ON mart_month_group(qc_module, start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_mmg_queue_dates 
ON mart_month_group(queue_name, start_date, end_date);

-- ======================================
-- 4. 其他业务表索引
-- ======================================

-- 索引 11: 告警事件表（日期+级别+状态）
CREATE INDEX IF NOT EXISTS idx_fae_date_severity_status 
ON fact_alert_event(alert_date, severity_level, alert_status);

-- 索引 12: 告警状态表（日期+模块）
CREATE INDEX IF NOT EXISTS idx_fas_date_module 
ON fact_alert_status(status_date, qc_module);

-- 索引 13: 申诉事件表（日期+队列）
CREATE INDEX IF NOT EXISTS idx_fape_date_queue 
ON fact_appeal_event(appeal_date, queue_name);

-- 索引 14: 培训回收表（批次+动作日期）
CREATE INDEX IF NOT EXISTS idx_mtar_batch_action_date 
ON mart_training_action_recovery(batch_name, action_date);

-- ======================================
-- 5. 覆盖索引（包含常用列，避免回表）
-- ======================================

-- 覆盖索引 1: 内检汇总（包含所有计算列）
CREATE INDEX IF NOT EXISTS idx_fqe_internal_summary 
ON fact_qa_event(
    qc_module, 
    biz_date,
    is_raw_correct,
    is_final_correct,
    is_misjudge,
    is_missjudge
);

-- 覆盖索引 2: 队列排名（包含队列名和正确率）
CREATE INDEX IF NOT EXISTS idx_fqe_queue_ranking 
ON fact_qa_event(
    qc_module,
    biz_date,
    queue_name,
    is_raw_correct
);

-- 覆盖索引 3: 审核人排名（包含审核人和正确率）
CREATE INDEX IF NOT EXISTS idx_fqe_auditor_ranking 
ON fact_qa_event(
    qc_module,
    biz_date,
    auditor_name,
    is_raw_correct,
    is_misjudge,
    is_missjudge
);

-- ======================================
-- 6. 查询性能验证
-- ======================================

-- 验证 SQL（执行后查看 EXPLAIN 结果）
-- 示例 1: 内检汇总（应使用 idx_fqe_module_date）
-- EXPLAIN SELECT COUNT(*) FROM fact_qa_event WHERE qc_module = 'internal' AND biz_date = '2024-03-20';

-- 示例 2: 队列排名（应使用 idx_fqe_module_date_queue）
-- EXPLAIN SELECT queue_name, COUNT(*) FROM fact_qa_event WHERE qc_module = 'internal' AND biz_date = '2024-03-20' GROUP BY queue_name;

-- 示例 3: 新人汇总（应使用 idx_fqe_batch_date）
-- EXPLAIN SELECT batch_name, COUNT(*) FROM fact_qa_event WHERE batch_name IN ('2024Q1', '2024Q2') AND biz_date >= '2024-01-01' GROUP BY batch_name;

-- ======================================
-- 7. 索引维护建议
-- ======================================

-- 📊 查看索引大小
-- SELECT 
--     table_name, 
--     index_name, 
--     ROUND(stat_value * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
-- FROM mysql.innodb_index_stats
-- WHERE database_name = DATABASE()
--     AND stat_name = 'size'
-- ORDER BY stat_value DESC;

-- 🔍 查看索引使用情况
-- SELECT 
--     object_schema,
--     object_name,
--     index_name,
--     count_star AS usage_count
-- FROM performance_schema.table_io_waits_summary_by_index_usage
-- WHERE object_schema = DATABASE()
--     AND index_name IS NOT NULL
-- ORDER BY count_star DESC;

-- 🧹 清理未使用的索引（谨慎！）
-- SELECT CONCAT('DROP INDEX ', index_name, ' ON ', table_name, ';')
-- FROM information_schema.statistics
-- WHERE table_schema = DATABASE()
--     AND index_name NOT IN (
--         SELECT index_name 
--         FROM performance_schema.table_io_waits_summary_by_index_usage
--         WHERE object_schema = DATABASE() AND count_star > 0
--     )
--     AND index_name != 'PRIMARY';

-- ======================================
-- 8. 预期性能提升
-- ======================================

/*
优化前：
- 内检汇总: 787ms
- 新人汇总: 547ms
- 告警查询: 259ms

优化后（预期）：
- 内检汇总: <50ms  (-94%)
- 新人汇总: <50ms  (-91%)
- 告警查询: <20ms  (-92%)

总体页面加载：
- 首屏: 14ms → <10ms
- 内检页: 2-3s → <200ms
- 新人页: 1-2s → <200ms
*/

-- ======================================
-- 9. 执行计划
-- ======================================

/*
执行步骤：

1. 在测试环境执行本脚本
2. 使用 EXPLAIN 验证索引生效
3. 运行性能测试脚本（/tmp/perf_test.sh）
4. 对比优化前后性能
5. 确认无问题后在生产环境执行
6. 监控慢查询日志
7. 定期清理未使用的索引

注意事项：
- 创建索引期间会锁表（TiDB 较短）
- 每个索引占用存储空间（约 10-50MB/索引）
- 写入性能会略微下降（5-10%）
- 建议在业务低峰期执行
*/

-- ======================================
-- 完成！执行此脚本后，所有慢查询应降至 <50ms
-- ======================================
