#!/bin/bash
# ============================================================
# 13:00 合并任务：企微文件同步 + 新人数据入库
# 由 launchd com.tianyoulai.qa-sync 调用
# ============================================================
set -euo pipefail

PROJECT_ROOT="/Users/laitianyou/WorkBuddy/20260326191218"
PYTHON="$PROJECT_ROOT/.venv/bin/python"

echo "============================================================"
echo "📋 [1/2] 企微文件同步 sync_from_wework.py"
echo "============================================================"
"$PYTHON" "$PROJECT_ROOT/jobs/sync_from_wework.py"
SYNC_EXIT=$?
if [ $SYNC_EXIT -ne 0 ]; then
    echo "❌ sync_from_wework 失败 (exit=$SYNC_EXIT)，继续执行新人入库"
fi

echo ""
echo "============================================================"
echo "👶 [2/2] 新人数据入库 daily_newcomer_refresh.py"
echo "============================================================"
"$PYTHON" "$PROJECT_ROOT/jobs/daily_newcomer_refresh.py" --scan-days 3 --deep-scan
NEWCOMER_EXIT=$?

echo ""
echo "============================================================"
echo "📋 执行完成汇总"
echo "  sync_from_wework: $([ $SYNC_EXIT -eq 0 ] && echo '✅' || echo '❌')"
echo "  newcomer_refresh: $([ $NEWCOMER_EXIT -eq 0 ] && echo '✅' || echo '❌')"
echo "============================================================"

# 任一失败则整体返回非0
if [ $SYNC_EXIT -ne 0 ] || [ $NEWCOMER_EXIT -ne 0 ]; then
    exit 1
fi
