"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { StatusChip } from "@/components/status-chip";
import { requestApi } from "@/lib/api";
import { buildQueryString, pickText } from "@/lib/formatters";

type AlertRow = Record<string, unknown>;

type BulkUpdateResult = {
  updated_count: number;
  alert_ids: string[];
  alert_status: string;
  owner_name?: string | null;
  handle_note?: string | null;
};

const STATUS_OPTIONS = [
  { value: "claimed", label: "批量认领" },
  { value: "resolved", label: "批量解决" },
  { value: "ignored", label: "批量忽略" },
  { value: "open", label: "重新打开" },
] as const;

export function AlertBulkPanel({
  alerts,
  grain,
  selectedDate,
  groupName,
  selectedAlertId,
  demoFixture,
}: {
  alerts: AlertRow[];
  grain: string;
  selectedDate: string;
  groupName?: string;
  selectedAlertId?: string;
  demoFixture?: string;
}) {
  const router = useRouter();
  const selectableAlerts = useMemo(
    () => alerts.filter((item) => pickText(item.alert_id, "") !== ""),
    [alerts],
  );
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [alertStatus, setAlertStatus] = useState<(typeof STATUS_OPTIONS)[number]["value"]>("claimed");
  const [ownerName, setOwnerName] = useState("");
  const [handleNote, setHandleNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function toggleAlert(alertId: string) {
    setSelectedIds((current) =>
      current.includes(alertId) ? current.filter((item) => item !== alertId) : [...current, alertId],
    );
  }

  function selectAll() {
    setSelectedIds(selectableAlerts.map((item) => pickText(item.alert_id, "")).filter(Boolean));
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  function buildAlertHref(row: AlertRow): string {
    const alertId = pickText(row.alert_id, "");
    return (
      buildQueryString({
        grain,
        selected_date: selectedDate,
        group_name: groupName || pickText(row.alert_group_name, "") || undefined,
        queue_name: pickText(row.alert_queue_name, "") || undefined,
        alert_id: alertId,
        demo_fixture: demoFixture || undefined,
      }) || "/"
    );
  }

  async function submitBulkUpdate() {
    if (selectedIds.length === 0) {
      setError("请先选择至少一条告警。");
      setSuccess(null);
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await requestApi<BulkUpdateResult>("/api/v1/dashboard/alerts/bulk-update", {
        method: "PATCH",
        body: {
          alert_ids: selectedIds,
          alert_status: alertStatus,
          owner_name: ownerName || null,
          handle_note: handleNote || null,
        },
      });
      setSuccess(`已更新 ${result.updated_count} 条告警，状态变更为「${STATUS_OPTIONS.find((item) => item.value === alertStatus)?.label || alertStatus}」。`);
      setSelectedIds([]);
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "批量更新失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3 className="panel-title">告警批量流转</h3>
          <p className="panel-subtitle">这块已经不只是看数据，而是开始把告警处置动作真正迁到新前台；单条详情也可以直接从这里打开。</p>
        </div>
      </div>
      {error ? <div className="error-banner">{error}</div> : null}
      {success ? <div className="success-banner">{success}</div> : null}
      <div className="action-grid">
        <div className="form-field">
          <label htmlFor="alert_status">批量动作</label>
          <select
            id="alert_status"
            className="select"
            value={alertStatus}
            onChange={(event) => setAlertStatus(event.target.value as (typeof STATUS_OPTIONS)[number]["value"])}
          >
            {STATUS_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="owner_name">处理人</label>
          <input
            id="owner_name"
            className="input"
            value={ownerName}
            onChange={(event) => setOwnerName(event.target.value)}
            placeholder="可选，建议写 owner / 处理人"
          />
        </div>
        <div className="form-field action-grid-wide">
          <label htmlFor="handle_note">处理备注</label>
          <textarea
            id="handle_note"
            className="textarea"
            value={handleNote}
            onChange={(event) => setHandleNote(event.target.value)}
            placeholder="记录为什么认领、忽略或解决，后续回看更省事。"
          />
        </div>
      </div>
      <div className="form-actions">
        <span className="kpi-pill">已选 {selectedIds.length} 条</span>
        <button type="button" className="button" onClick={selectAll}>
          全选
        </button>
        <button type="button" className="button" onClick={clearSelection}>
          清空
        </button>
        <button type="button" className="button primary" disabled={submitting} onClick={submitBulkUpdate}>
          {submitting ? "提交中..." : "执行批量流转"}
        </button>
      </div>
      {alerts.length === 0 ? (
        <div className="empty-state">当前日期下没有可流转的告警。</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>选择</th>
                <th>级别</th>
                <th>状态</th>
                <th>规则</th>
                <th>对象</th>
                <th>Owner</th>
                <th>SLA</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((row, index) => {
                const alertId = pickText(row.alert_id, "");
                const checked = selectedIds.includes(alertId);
                const focused = alertId && selectedAlertId === alertId;
                const severityClass = row.severity === "P0" ? "alert-row-severity-p0" : row.severity === "P1" ? "alert-row-severity-p1" : "alert-row-severity-p2";
                return (
                  <tr key={alertId || `${row.rule_name}-${index}`} className={`${focused ? "alert-row-selected" : ""} ${severityClass}`}>
                    <td>
                      {alertId ? (
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleAlert(alertId)}
                          aria-label={`选择告警 ${alertId}`}
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <StatusChip
                        value={row.severity}
                        tone={row.severity === "P0" ? "danger" : row.severity === "P1" ? "warning" : "neutral"}
                      />
                    </td>
                    <td>
                      <StatusChip
                        value={row.alert_status_label}
                        tone={row.alert_status === "resolved" ? "success" : row.alert_status === "open" ? "warning" : "neutral"}
                      />
                    </td>
                    <td>{pickText(row.rule_name)}</td>
                    <td>{pickText(row.target_key)}</td>
                    <td>{pickText(row.owner_name)}</td>
                    <td>{pickText(row.sla_label)}</td>
                    <td>
                      {alertId ? (
                        <Link className="table-link" href={buildAlertHref(row)}>
                          {focused ? "详情已打开" : "查看详情"}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
