import { ReactNode } from "react";

export function SummaryCard({
  label,
  value,
  hint,
  tone = "neutral",
  delta,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "neutral" | "danger" | "warning" | "success";
  delta?: string;
}) {
  return (
    <div className={`summary-card ${tone}`}>
      <div className="summary-label">{label}</div>
      <div className="summary-value-row">
        <span className="summary-value">{value}</span>
        {delta ? (
          <span className={`summary-delta ${delta.startsWith("+") ? "delta-up" : delta.startsWith("-") ? "delta-down" : ""}`}>
            {delta}
          </span>
        ) : null}
      </div>
      {hint ? <div className="summary-hint">{hint}</div> : null}
    </div>
  );
}
