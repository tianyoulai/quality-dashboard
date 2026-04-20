type LinePoint = {
  label: string;
  primary: number;
  secondary?: number;
};

function buildPolyline(values: number[], width: number, height: number): string {
  if (values.length === 0) {
    return "";
  }

  const safeValues = values.map((value) => (Number.isFinite(value) ? value : 0));
  const maxValue = Math.max(...safeValues, 100);
  const minValue = Math.min(...safeValues, 95);
  const range = Math.max(maxValue - minValue, 1);

  return safeValues
    .map((value, index) => {
      const x = safeValues.length === 1 ? width / 2 : (index / (safeValues.length - 1)) * width;
      const y = height - ((value - minValue) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");
}

export function LineChartCard({
  title,
  subtitle,
  points,
  primaryLabel,
  secondaryLabel,
}: {
  title: string;
  subtitle?: string;
  points: LinePoint[];
  primaryLabel: string;
  secondaryLabel?: string;
}) {
  const primaryValues = points.map((point) => point.primary);
  const secondaryValues = points.map((point) => point.secondary ?? Number.NaN).filter((value) => Number.isFinite(value));
  const primaryPolyline = buildPolyline(primaryValues, 320, 150);
  const secondaryPolyline = secondaryValues.length > 0
    ? buildPolyline(points.map((point) => point.secondary ?? 0), 320, 150)
    : "";

  return (
    <section className="panel chart-card">
      <div className="panel-header">
        <div>
          <h3 className="panel-title">{title}</h3>
          {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
        </div>
      </div>
      {points.length === 0 ? (
        <div className="empty-state">暂无趋势数据。</div>
      ) : (
        <>
          <div className="line-chart-legend">
            <span className="legend-item">
              <span className="legend-dot primary" />
              {primaryLabel}
            </span>
            {secondaryLabel ? (
              <span className="legend-item">
                <span className="legend-dot secondary" />
                {secondaryLabel}
              </span>
            ) : null}
          </div>
          <div className="line-chart-wrap">
            <svg viewBox="0 0 320 170" className="line-chart-svg" role="img" aria-label={title}>
              <line x1="0" y1="150" x2="320" y2="150" className="line-chart-axis" />
              <line x1="0" y1="75" x2="320" y2="75" className="line-chart-grid" />
              <line x1="0" y1="20" x2="320" y2="20" className="line-chart-grid" />
              {secondaryPolyline ? <polyline points={secondaryPolyline} className="line-chart-secondary" /> : null}
              <polyline points={primaryPolyline} className="line-chart-primary" />
            </svg>
          </div>
          <div className="line-chart-points">
            {points.map((point) => (
              <div key={point.label} className="line-chart-point-row">
                <span className="line-chart-point-label">{point.label}</span>
                <span className="line-chart-point-values">
                  <strong>{point.primary.toFixed(2)}%</strong>
                  {secondaryLabel && Number.isFinite(point.secondary) ? <em>{(point.secondary ?? 0).toFixed(2)}%</em> : null}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
