"use client";

import { useState } from "react";

import { requestApi } from "@/lib/api";

type TrainingDailySendResult = {
  ok?: boolean;
  message?: string;
  detail_url?: string | null;
  detail_query_key?: string | null;
  detail_share_token?: string | null;
  has_data?: boolean;
};

function readText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function splitMentionList(value: string): string[] {
  return value
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function TrainingDailySendPanel({
  batchNames,
  owner,
  teamName,
  detailStage,
  detailRiskLevel,
  detailErrorType,
  detailReviewerAlias,
  detailReviewerName,
  markdown,
  asOfDate,
  hasData,
  reliabilityLabel,
  reliabilityIssues,
  currentDetailHref,
  recommendedDetailUrl,
  legacyDetailUrl,
}: {
  batchNames: string[];
  owner?: string;
  teamName?: string;
  detailStage?: string;
  detailRiskLevel?: string;
  detailErrorType?: string;
  detailReviewerAlias?: string;
  detailReviewerName?: string;
  markdown: string;
  asOfDate?: string;
  hasData: boolean;
  reliabilityLabel: string;
  reliabilityIssues: string[];
  currentDetailHref: string;
  recommendedDetailUrl?: string;
  legacyDetailUrl?: string;
}) {
  const [detailUrlInput, setDetailUrlInput] = useState("");
  const [webhookOverride, setWebhookOverride] = useState("");
  const [mentionsInput, setMentionsInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [sentDetailUrl, setSentDetailUrl] = useState("");

  const downloadFileName = `training_daily_${readText(asOfDate) || "latest"}.md`;

  function handleDownload() {
    const blob = new Blob([markdown || ""], { type: "text/markdown;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = downloadFileName;
    link.click();
    window.URL.revokeObjectURL(url);
  }

  async function handleSend() {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    setSentDetailUrl("");

    try {
      const result = await requestApi<TrainingDailySendResult>("/api/v1/newcomers/training-daily/test-send", {
        method: "POST",
        body: {
          batch_names: batchNames,
          owner: owner || null,
          team_name: teamName || null,
          webhook_url: webhookOverride.trim() || null,
          detail_url: detailUrlInput.trim() || null,
          detail_stage: detailStage || null,
          detail_risk_level: detailRiskLevel || null,
          detail_error_type: detailErrorType || null,
          detail_reviewer_alias: detailReviewerAlias || null,
          detail_reviewer_name: detailReviewerName || null,
          mentioned_list: splitMentionList(mentionsInput),
        },
      });

      if (result.ok) {
        setSuccess(`发送完成：${readText(result.message) || "ok"}`);
        setSentDetailUrl(readText(result.detail_url));
      } else {
        setError(`发送失败：${readText(result.message) || "未知错误"}`);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "发送失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3 className="panel-title">企业微信群测试发送（统一主入口）</h3>
          <p className="panel-subtitle">这里是日常查看培训日报、错误明细和做群消息测试的统一入口；Streamlit 只保留兜底发送。这里直接走测试发送接口，把当前筛选范围的培训日报发到企业微信群，核对正文、错误标签和详情跳转是不是一致。</p>
        </div>
      </div>

      <div className="section-stack">
        <div className="inline-note">
          默认优先使用项目里已配置的企业微信群 webhook；你也可以临时覆盖。当前数据状态：{reliabilityLabel}{hasData ? "" : "（当前会发送空态日报说明，不算异常）"}
        </div>

        {reliabilityIssues.length > 0 ? (
          <div className="info-banner">数据提醒：{reliabilityIssues.slice(0, 4).join("；")}</div>
        ) : (
          <div className="success-banner">当前训练日报口径下暂无额外可靠性异常。</div>
        )}

        {error ? <div className="error-banner">{error}</div> : null}
        {success ? <div className="success-banner">{success}</div> : null}

        <div className="inline-note">
          当前 Next 页分享视角：<a className="table-link" href={currentDetailHref}>{currentDetailHref}</a>
        </div>

        {recommendedDetailUrl ? (
          <div className="inline-note">
            推荐随消息带出的外部详情链接：<a className="table-link" href={recommendedDetailUrl} target="_blank" rel="noreferrer">{recommendedDetailUrl}</a>
          </div>
        ) : (
          <div className="info-banner">当前还没配置外部详情页基址；如果你想让群消息里带可直接打开的详情链接，可以手填完整链接后再发送。</div>
        )}

        {legacyDetailUrl ? (
          <div className="panel-subtitle">如果外部系统还没兼容短链接参数，也可以继续参考旧链接：{legacyDetailUrl}</div>
        ) : null}

        {sentDetailUrl ? (
          <div className="inline-note">
            本次随消息带出的详情链接：<a className="table-link" href={sentDetailUrl} target="_blank" rel="noreferrer">{sentDetailUrl}</a>
          </div>
        ) : null}

        <div className="action-grid">
          <div className="form-field">
            <label htmlFor="training-daily-detail-url">详情链接（可空）</label>
            <input
              id="training-daily-detail-url"
              className="input"
              value={detailUrlInput}
              onChange={(event) => setDetailUrlInput(event.target.value)}
              placeholder="留空则优先走后端自动拼装的详情链接"
            />
          </div>
          <div className="form-field">
            <label htmlFor="training-daily-webhook">临时 webhook（可空）</label>
            <input
              id="training-daily-webhook"
              className="input"
              type="password"
              value={webhookOverride}
              onChange={(event) => setWebhookOverride(event.target.value)}
              placeholder="为空则读取项目配置"
            />
          </div>
          <div className="form-field action-grid-wide">
            <label htmlFor="training-daily-mentions">提醒 userId（逗号或换行分隔，可空）</label>
            <textarea
              id="training-daily-mentions"
              className="textarea"
              value={mentionsInput}
              onChange={(event) => setMentionsInput(event.target.value)}
              placeholder="例如 zhangsan,lisi；这里要填企业微信 userId，不是中文姓名"
            />
          </div>
        </div>

        <div className="form-actions">
          <button type="button" className="button" onClick={handleDownload}>下载日报 Markdown</button>
          <button type="button" className="button primary" disabled={submitting} onClick={handleSend}>
            {submitting ? "发送中..." : "发送培训日报测试消息"}
          </button>
        </div>
      </div>
    </section>
  );
}
