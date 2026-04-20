"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { requestApi } from "@/lib/api";

type AlertStatus = "open" | "claimed" | "ignored" | "resolved";

type AlertUpdateResult = {
  alert_id: string;
  alert_status: AlertStatus;
  owner_name?: string | null;
  handle_note?: string | null;
  history?: Array<Record<string, unknown>>;
};

const QUICK_ACTIONS: Array<{ value: AlertStatus; label: string; hint: string }> = [
  { value: "claimed", label: "认领", hint: "开始接手处理" },
  { value: "resolved", label: "解决", hint: "确认已闭环" },
  { value: "ignored", label: "忽略", hint: "确认暂不处理" },
  { value: "open", label: "重新打开", hint: "回到待处理" },
];

export function AlertQuickActions({
  alertId,
  currentStatus,
  currentStatusLabel,
  initialOwnerName,
  initialHandleNote,
}: {
  alertId: string;
  currentStatus?: string;
  currentStatusLabel?: string;
  initialOwnerName?: string;
  initialHandleNote?: string;
}) {
  const router = useRouter();
  const [ownerName, setOwnerName] = useState(initialOwnerName || "");
  const [handleNote, setHandleNote] = useState(initialHandleNote || "");
  const [submittingStatus, setSubmittingStatus] = useState<AlertStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    setOwnerName(initialOwnerName || "");
  }, [alertId, initialOwnerName]);

  useEffect(() => {
    setHandleNote(initialHandleNote || "");
  }, [alertId, initialHandleNote]);

  async function submitSingleUpdate(alertStatus: AlertStatus) {
    setSubmittingStatus(alertStatus);
    setError(null);
    setSuccess(null);

    try {
      await requestApi<AlertUpdateResult>(`/api/v1/dashboard/alerts/${encodeURIComponent(alertId)}`, {
        method: "PATCH",
        body: {
          alert_status: alertStatus,
          owner_name: ownerName.trim() || null,
          handle_note: handleNote.trim() || null,
        },
      });

      const actionLabel = QUICK_ACTIONS.find((item) => item.value === alertStatus)?.label || alertStatus;
      const ownerText = ownerName.trim() ? `，处理人：${ownerName.trim()}` : "";
      setSuccess(`已把这条告警更新为「${actionLabel}」${ownerText}。处理历史会在刷新后同步更新。`);
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "单条告警状态更新失败");
    } finally {
      setSubmittingStatus(null);
    }
  }

  return (
    <div className="section-stack">
      <div className="kpi-row">
        <span className="kpi-pill">当前状态：{currentStatusLabel || currentStatus || "—"}</span>
        <span className="kpi-pill">支持直接补处理人和备注后再流转</span>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      <div className="action-grid">
        <div className="form-field">
          <label htmlFor={`alert-owner-${alertId}`}>处理人</label>
          <input
            id={`alert-owner-${alertId}`}
            className="input"
            value={ownerName}
            onChange={(event) => setOwnerName(event.target.value)}
            placeholder="建议写 owner / 处理人"
          />
        </div>
        <div className="form-field action-grid-wide">
          <label htmlFor={`alert-note-${alertId}`}>处理备注</label>
          <textarea
            id={`alert-note-${alertId}`}
            className="textarea"
            value={handleNote}
            onChange={(event) => setHandleNote(event.target.value)}
            placeholder="记录为什么认领、忽略或解决，后续看历史更清楚。"
          />
        </div>
      </div>

      <div className="alert-action-buttons">
        {QUICK_ACTIONS.map((item) => {
          const isSubmitting = submittingStatus === item.value;
          const isCurrentStatus = currentStatus === item.value;
          return (
            <button
              key={item.value}
              type="button"
              className={`button ${isCurrentStatus ? "primary" : ""}`}
              disabled={submittingStatus !== null}
              onClick={() => submitSingleUpdate(item.value)}
              title={item.hint}
            >
              {isSubmitting ? `${item.label}中...` : isCurrentStatus ? `当前：${item.label}` : item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
