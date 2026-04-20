"use client";

/**
 * Skeleton / loading placeholder components.
 * Used for summary cards, tables and generic panels
 * while data is being fetched.
 */

export function SkeletonSummaryCard() {
  return (
    <div className="summary-card skeleton-card">
      <div className="skeleton-line skeleton-w40" />
      <div className="skeleton-line skeleton-w60 skeleton-mt8" />
      <div className="skeleton-line skeleton-w80 skeleton-mt8" />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <div className="skeleton-line skeleton-w30 skeleton-h6" />
          <div className="skeleton-line skeleton-w50 skeleton-mt4" />
        </div>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              {Array.from({ length: cols }, (_, i) => (
                <th key={i}><div className="skeleton-line skeleton-w40" /></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: rows }, (_, rowIdx) => (
              <tr key={rowIdx}>
                {Array.from({ length: cols }, (_, colIdx) => (
                  <td key={colIdx}><div className={`skeleton-line ${colIdx === 0 ? "skeleton-w60" : "skeleton-w40"}`} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function SkeletonPanel() {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <div className="skeleton-line skeleton-w40 skeleton-h6" />
          <div className="skeleton-line skeleton-w60 skeleton-mt4" />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="skeleton-line skeleton-w100" />
        <div className="skeleton-line skeleton-w80" />
        <div className="skeleton-line skeleton-w60" />
      </div>
    </section>
  );
}
