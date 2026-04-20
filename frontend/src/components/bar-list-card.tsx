type BarItem = {
  label: string;
  value: number;
  meta?: string;
  tone?: "primary" | "success" | "warning" | "danger" | "neutral";
};

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

export function BarListCard({
  title,
  subtitle,
  items,
  suffix = "",
}: {
  title: string;
  subtitle?: string;
  items: BarItem[];
  suffix?: string;
}) {
  const maxValue = items.reduce((max, item) => Math.max(max, item.value), 0);

  return (
    <section className="panel chart-card">
      <div className="panel-header">
        <div>
          <h3 className="panel-title">{title}</h3>
          {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
        </div>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">暂无可展示的分布数据。</div>
      ) : (
        <div className="metric-bars">
          {items.map((item) => {
            const width = maxValue > 0 ? (item.value / maxValue) * 100 : 0;
            return (
              <div key={`${item.label}-${item.meta || ""}`} className="metric-bar-row">
                <div className="metric-bar-label-row">
                  <span className="metric-bar-label">{item.label}</span>
                  <span className="metric-bar-value">{`${item.value.toFixed(2).replace(/\.00$/, "")}${suffix}`}</span>
                </div>
                <div className="metric-bar-track">
                  <div
                    className={`metric-bar-fill ${item.tone || "primary"}`}
                    style={{ width: `${clampPercent(width)}%` }}
                  />
                </div>
                {item.meta ? <div className="metric-bar-meta">{item.meta}</div> : null}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
