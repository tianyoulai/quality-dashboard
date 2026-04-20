-- ============================================================
-- 数据库索引优化方案 - 基于慢查询分析
-- ============================================================
-- 优化目标：
--   1. 告警查询（按日期 + 状态 + 级别）
--   2. 组别/队列查询（按日期 + 组别/队列）
--   3. 审核人查询（按日期 + 队列 + 审核人）
--   4. 联表查询（join_key）
--   5. 培训回收查询（按日期 + 组别 + 规则）
--
-- 使用方法：
--   在 TiDB 中执行：
--     source /path/to/index_optimization.sql
--   或在 Python 脚本中：
--     repo.initialize_schema("storage/index_optimization.sql")
-- ============================================================

-- ═══════════════════════════════════════════════════════════════
--  fact_qa_event 表索引优化
-- ═══════════════════════════════════════════════════════════════

-- 已有索引（保留）：
-- idx_fqe_biz_date (biz_date)
-- idx_fqe_sub_biz (sub_biz)
-- idx_fqe_join_key (join_key)
-- idx_fqe_row_hash (row_hash)
-- idx_fqe_inspect_type (inspect_type)
-- idx_fqe_workforce_type (workforce_type)

-- ★ 新增复合索引：组别维度查询（覆盖 90% 的查询场景）
-- 场景：WHERE biz_date = ? AND group_name = ?
CREATE INDEX IF NOT EXISTS idx_fqe_date_group 
ON fact_qa_event (biz_date, group_name);

-- ★ 新增复合索引：队列维度查询
-- 场景：WHERE biz_date = ? AND queue_name = ?
CREATE INDEX IF NOT EXISTS idx_fqe_date_queue 
ON fact_qa_event (biz_date, queue_name);

-- ★ 新增复合索引：审核人维度查询
-- 场景：WHERE biz_date = ? AND queue_name = ? AND reviewer_name = ?
CREATE INDEX IF NOT EXISTS idx_fqe_date_queue_reviewer 
ON fact_qa_event (biz_date, queue_name, reviewer_name);

-- ★ 新增复合索引：错误类型分析
-- 场景：WHERE biz_date = ? AND queue_name = ? AND error_type = ?
CREATE INDEX IF NOT EXISTS idx_fqe_date_queue_error 
ON fact_qa_event (biz_date, queue_name, error_type);

-- ★ 新增复合索引：内检/外检分离查询
-- 场景：WHERE biz_date = ? AND inspect_type = ?
CREATE INDEX IF NOT EXISTS idx_fqe_date_inspect 
ON fact_qa_event (biz_date, inspect_type);

-- ★ 新增复合索引：新人追踪查询
-- 场景：WHERE biz_date >= ? AND workforce_type = 'newcomer' AND reviewer_name = ?
CREATE INDEX IF NOT EXISTS idx_fqe_date_workforce_reviewer 
ON fact_qa_event (biz_date, workforce_type, reviewer_name);

-- ═══════════════════════════════════════════════════════════════
--  fact_alert_event 表索引优化
-- ═══════════════════════════════════════════════════════════════

-- ★ 新增复合索引：告警查询（按日期 + 粒度）
-- 场景：WHERE grain = ? AND alert_date = ?
CREATE INDEX IF NOT EXISTS idx_fae_grain_date 
ON fact_alert_event (grain, alert_date);

-- ★ 新增复合索引：告警查询（按日期 + 级别 + 状态）
-- 场景：WHERE alert_date = ? AND alert_level = ? AND is_resolved = ?
-- 注意：这里假设 fact_alert_event 表有 alert_level 和 is_resolved 字段
-- 如果没有，请先在 schema.sql 中添加
CREATE INDEX IF NOT EXISTS idx_fae_date_level_resolved 
ON fact_alert_event (alert_date, alert_level, is_resolved);

-- ★ 新增复合索引：按组别查询告警
-- 场景：WHERE alert_date >= ? AND group_name = ?
CREATE INDEX IF NOT EXISTS idx_fae_date_group 
ON fact_alert_event (alert_date, group_name);

-- ★ 新增复合索引：按队列查询告警
-- 场景：WHERE alert_date >= ? AND queue_name = ?
CREATE INDEX IF NOT EXISTS idx_fae_date_queue 
ON fact_alert_event (alert_date, queue_name);

-- ★ 新增复合索引：按规则查询告警
-- 场景：WHERE alert_date >= ? AND rule_code = ?
CREATE INDEX IF NOT EXISTS idx_fae_date_rule 
ON fact_alert_event (alert_date, rule_code);

-- ═══════════════════════════════════════════════════════════════
--  fact_alert_status 表索引优化
-- ═══════════════════════════════════════════════════════════════

-- ★ 新增复合索引：告警状态查询
-- 场景：WHERE alert_id = ? ORDER BY updated_at DESC
CREATE INDEX IF NOT EXISTS idx_fas_alert_time 
ON fact_alert_status (alert_id, updated_at DESC);

-- ★ 新增复合索引：按处理人查询
-- 场景：WHERE owner_name = ? AND alert_status = ?
CREATE INDEX IF NOT EXISTS idx_fas_owner_status 
ON fact_alert_status (owner_name, alert_status);

-- ═══════════════════════════════════════════════════════════════
--  fact_appeal_event 表索引优化
-- ═══════════════════════════════════════════════════════════════

-- 已有索引（保留）：
-- idx_fae_join_key (join_key)

-- ★ 新增复合索引：按日期查询申诉
-- 场景：WHERE biz_date >= ? AND appeal_status = ?
CREATE INDEX IF NOT EXISTS idx_fape_date_status 
ON fact_appeal_event (biz_date, appeal_status);

-- ★ 新增复合索引：按队列查询申诉
-- 场景：WHERE biz_date >= ? AND queue_name = ?
CREATE INDEX IF NOT EXISTS idx_fape_date_queue 
ON fact_appeal_event (biz_date, queue_name);

-- ═══════════════════════════════════════════════════════════════
--  mart_day_group / mart_week_group / mart_month_group 索引优化
-- ═══════════════════════════════════════════════════════════════

-- ★ 新增复合索引：组别趋势查询
-- 场景：WHERE group_name = ? AND biz_date >= ? ORDER BY biz_date
CREATE INDEX IF NOT EXISTS idx_mdg_group_date 
ON mart_day_group (group_name, biz_date);

CREATE INDEX IF NOT EXISTS idx_mwg_group_date 
ON mart_week_group (group_name, week_begin_date);

CREATE INDEX IF NOT EXISTS idx_mmg_group_date 
ON mart_month_group (group_name, month_begin_date);

-- ═══════════════════════════════════════════════════════════════
--  mart_day_queue / mart_week_queue / mart_month_queue 索引优化
-- ═══════════════════════════════════════════════════════════════

-- ★ 新增复合索引：队列趋势查询
-- 场景：WHERE queue_name = ? AND biz_date >= ? ORDER BY biz_date
CREATE INDEX IF NOT EXISTS idx_mdq_queue_date 
ON mart_day_queue (queue_name, biz_date);

CREATE INDEX IF NOT EXISTS idx_mwq_queue_date 
ON mart_week_queue (queue_name, week_begin_date);

CREATE INDEX IF NOT EXISTS idx_mmq_queue_date 
ON mart_month_queue (queue_name, month_begin_date);

-- ★ 新增复合索引：按组别查询队列列表
-- 场景：WHERE group_name = ? AND biz_date = ?
CREATE INDEX IF NOT EXISTS idx_mdq_group_date 
ON mart_day_queue (group_name, biz_date);

-- ═══════════════════════════════════════════════════════════════
--  mart_training_action_recovery 索引优化
-- ═══════════════════════════════════════════════════════════════

-- ★ 新增复合索引：培训回收查询
-- 场景：WHERE action_week = ? AND group_name = ? AND rule_code = ?
CREATE INDEX IF NOT EXISTS idx_mtar_week_group_rule 
ON mart_training_action_recovery (action_week, group_name, rule_code);

-- ★ 新增复合索引：按告警ID查询回收
-- 场景：WHERE alert_id = ?
CREATE INDEX IF NOT EXISTS idx_mtar_alert 
ON mart_training_action_recovery (alert_id);

-- ═══════════════════════════════════════════════════════════════
--  索引使用情况监控查询
-- ═══════════════════════════════════════════════════════════════

-- 查看表的所有索引：
-- SHOW INDEX FROM fact_qa_event;
-- SHOW INDEX FROM fact_alert_event;

-- 查看索引使用情况（TiDB）：
-- SELECT 
--     TABLE_NAME,
--     INDEX_NAME,
--     SEQ_IN_INDEX,
--     COLUMN_NAME,
--     CARDINALITY
-- FROM information_schema.STATISTICS
-- WHERE TABLE_SCHEMA = DATABASE()
--   AND TABLE_NAME IN ('fact_qa_event', 'fact_alert_event', 'mart_day_group')
-- ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- 分析慢查询（需要开启慢查询日志）：
-- SELECT 
--     DIGEST_TEXT,
--     AVG_LATENCY / 1000000 as avg_latency_ms,
--     EXEC_COUNT,
--     FIRST_SEEN,
--     LAST_SEEN
-- FROM information_schema.statements_summary
-- WHERE AVG_LATENCY / 1000000 > 500  -- 大于 500ms
-- ORDER BY AVG_LATENCY DESC
-- LIMIT 20;

-- ═══════════════════════════════════════════════════════════════
--  索引优化建议
-- ═══════════════════════════════════════════════════════════════

-- 1. 监控索引命中率
--    定期检查是否有未使用的索引（占用空间但不提升性能）
--    
-- 2. 避免冗余索引
--    如果已有 (a, b, c)，则不需要再建 (a), (a, b)
--    
-- 3. 选择性高的列放在前面
--    例如：biz_date 选择性高于 group_name，所以 (biz_date, group_name) 优于 (group_name, biz_date)
--    
-- 4. 覆盖索引优化
--    如果查询只需要索引中的列，可以避免回表（SELECT biz_date, group_name FROM ... WHERE ...）
--    
-- 5. 索引维护成本
--    每增加一个索引，INSERT/UPDATE/DELETE 的性能会下降 5-10%
--    权衡读写比例，只为高频查询建索引
--
-- 6. TiDB 特有优化
--    - 分区表：按月分区时序数据，查询只扫描相关分区
--    - 列式存储（TiFlash）：OLAP 分析查询可以使用列存副本
--    - SQL Plan Cache：相同查询模式会复用执行计划
