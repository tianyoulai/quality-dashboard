"use client";

import { useState, useMemo, ReactNode } from "react";

import { pickText } from "@/lib/formatters";

type SortDir = "asc" | "desc" | null;

const DEFAULT_PAGE_SIZE = 20;

/**
 * DataTable 列定义。
 *
 * 说明：React 19 RSC 下 Server → Client 不允许直接传函数。
 * 因此在新代码里应使用 `cells` 预渲染模式（见下方 DataTableRow），
 * 不要在列定义里挂 `render: (row) => ...`。
 * 老代码里仍有 `render` 使用方式，这里保留只是为了过渡期兼容，
 * **切勿**在 server component 里用 `render`；此字段仅供 client-only 场景。
 */
export type TableColumn<T extends Record<string, unknown>> = {
  key: keyof T | string;
  label: string;
  /** @deprecated RSC 不允许 server→client 传函数；请改用 DataTableRow 的 cells 预渲染。 */
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  /** 排序时使用的原始字段 key；不指定则用 key。 */
  sortKey?: string;
};

/**
 * 预渲染行数据。
 * - `raw`：用于排序/搜索的原始字段值。
 * - `cells`：server 侧已经渲染好的 ReactNode，DataTable 只负责布局。
 * - `key`：稳定的 React key；可选，缺省用数组 index。
 */
export type DataTableRow<T extends Record<string, unknown> = Record<string, unknown>> = {
  raw: T;
  cells: Record<string, ReactNode>;
  key?: string | number;
};

type DataTableProps<T extends Record<string, unknown>> = {
  title: string;
  subtitle?: string;
  columns: TableColumn<T>[];
  /** 新 API：预渲染的行；推荐用于 server components。 */
  rows?: DataTableRow<T>[];
  /** 老 API：原始行；仅在 client 调用点使用，并配合 columns.render。 */
  rawRows?: T[];
  emptyText?: string;
  pageSize?: number;
  paginated?: boolean;
  searchable?: boolean;
};

function parseComparable(value: unknown): number | string {
  if (value == null) return "";
  if (typeof value === "number") return value;
  const str = String(value).trim();
  const num = Number(str);
  return !isNaN(num) && str !== "" ? num : str;
}

function normalizeRows<T extends Record<string, unknown>>(
  rows: DataTableRow<T>[] | undefined,
  rawRows: T[] | undefined,
  columns: TableColumn<T>[],
): DataTableRow<T>[] {
  if (rows && rows.length >= 0) {
    // 若传了新 API，直接用
    if (rows.length > 0 || !rawRows) return rows;
  }
  if (rawRows) {
    // 兼容老 API：用 render 临时生成 cells（只在 client 调用点会走到）
    return rawRows.map((row, idx) => {
      const cells: Record<string, ReactNode> = {};
      columns.forEach((col) => {
        const k = String(col.key);
        cells[k] = col.render ? col.render(row) : pickText(row[col.key as keyof T]);
      });
      return { raw: row, cells, key: idx };
    });
  }
  return [];
}

export function DataTable<T extends Record<string, unknown>>({
  title,
  subtitle,
  columns,
  rows,
  rawRows,
  emptyText = "暂无数据",
  pageSize = DEFAULT_PAGE_SIZE,
  paginated = true,
  searchable = false,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchText, setSearchText] = useState("");

  const normalizedRows = useMemo(
    () => normalizeRows(rows, rawRows, columns),
    [rows, rawRows, columns],
  );

  /* Filter rows by search text —— 搜索只看 raw 字段，性能更好也更稳。 */
  const lowerSearch = searchText.trim().toLowerCase();
  const filteredRows = useMemo(() => {
    if (!searchable || !lowerSearch) return normalizedRows;
    return normalizedRows.filter((row) =>
      columns.some((col) => {
        const raw = row.raw[col.key as keyof T];
        return pickText(raw).toLowerCase().includes(lowerSearch);
      }),
    );
  }, [normalizedRows, columns, lowerSearch, searchable]);

  /* Hooks must be unconditional — always call */
  const hasSortable = columns.some((c) => c.sortable);
  const sortedRows = useMemo(() => {
    if (!hasSortable || !sortKey || !sortDir) return filteredRows;
    const col = columns.find((c) => String(c.key) === sortKey);
    const fieldKey = (col?.sortKey ?? sortKey) as keyof T;

    return [...filteredRows].sort((a, b) => {
      const aVal = parseComparable(a.raw[fieldKey]);
      const bVal = parseComparable(b.raw[fieldKey]);

      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      const aStr = String(aVal).localeCompare(String(bVal), "zh-CN", { numeric: true });
      return sortDir === "asc" ? aStr : -aStr;
    });
  }, [filteredRows, sortKey, sortDir, hasSortable, columns]);

  const processedRows = hasSortable ? sortedRows : filteredRows;
  const totalCount = processedRows.length;
  const totalPages = paginated ? Math.max(1, Math.ceil(totalCount / pageSize)) : 1;
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const pagedRows = paginated
    ? processedRows.slice((safeCurrentPage - 1) * pageSize, safeCurrentPage * pageSize)
    : processedRows;

  function handleSortClick(key: string) {
    if (sortKey === key) {
      if (sortDir === "asc") setSortDir("desc");
      else if (sortDir === "desc") {
        setSortKey(null);
        setSortDir(null);
      }
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setCurrentPage(1);
  }

  function handleSearchChange(value: string) {
    setSearchText(value);
    setCurrentPage(1);
  }

  function renderSortIndicator(key: string): ReactNode {
    if (sortKey !== key) {
      return <span className="sort-indicator sort-inactive">↕</span>;
    }
    return (
      <span className={`sort-indicator ${sortDir === "asc" ? "sort-asc" : "sort-desc"}`}>
        {sortDir === "asc" ? "↑" : "↓"}
      </span>
    );
  }

  function renderPagination() {
    if (!paginated || totalPages <= 1) return null;

    const pageNumbers: (number | string)[] = [];
    const maxVisible = 7;

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) pageNumbers.push(i);
    } else {
      pageNumbers.push(1);
      if (safeCurrentPage > 3) pageNumbers.push("…");
      const start = Math.max(2, safeCurrentPage - 1);
      const end = Math.min(totalPages - 1, safeCurrentPage + 1);
      for (let i = start; i <= end; i++) pageNumbers.push(i);
      if (safeCurrentPage < totalPages - 2) pageNumbers.push("…");
      pageNumbers.push(totalPages);
    }

    return (
      <div className="pagination">
        <div className="pagination-info">
          共 {totalCount} 条，每页 {pageSize} 条
          {searchable && lowerSearch && totalCount !== normalizedRows.length
            ? `（筛选自 ${normalizedRows.length} 条）`
            : ""}
        </div>
        <div className="pagination-controls">
          <button
            className="pagination-btn"
            disabled={safeCurrentPage <= 1}
            onClick={() => setCurrentPage(safeCurrentPage - 1)}
          >
            ‹
          </button>
          {pageNumbers.map((item, idx) =>
            typeof item === "string" ? (
              <span key={`ellipsis-${idx}`} className="pagination-ellipsis">…</span>
            ) : (
              <button
                key={item}
                className={`pagination-btn${item === safeCurrentPage ? " active" : ""}`}
                onClick={() => setCurrentPage(item)}
              >
                {item}
              </button>
            ),
          )}
          <button
            className="pagination-btn"
            disabled={safeCurrentPage >= totalPages}
            onClick={() => setCurrentPage(safeCurrentPage + 1)}
          >
            ›
          </button>
        </div>
      </div>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3 className="panel-title">{title}</h3>
          {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
        </div>
      </div>
      {searchable && normalizedRows.length > 0 ? (
        <div className="table-search-bar">
          <input
            type="text"
            className="table-search-input"
            placeholder="搜索关键词..."
            value={searchText}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
          {lowerSearch ? (
            <span className="table-search-count">匹配 {totalCount} 条</span>
          ) : null}
        </div>
      ) : null}
      {totalCount === 0 ? (
        <div className="empty-state">
          <span className="empty-state-icon">📭</span>
          <span className="empty-state-text">{emptyText}</span>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {columns.map((column) => {
                    const colKey = String(column.key);
                    return (
                      <th
                        key={colKey}
                        className={column.sortable ? "sortable-th" : ""}
                        onClick={() => column.sortable && handleSortClick(colKey)}
                      >
                        <span className="th-label">{column.label}</span>
                        {column.sortable && renderSortIndicator(colKey)}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {pagedRows.map((row, index) => (
                  <tr key={row.key ?? index}>
                    {columns.map((column) => {
                      const colKey = String(column.key);
                      const cell = row.cells[colKey];
                      return (
                        <td key={colKey}>
                          {cell !== undefined ? cell : pickText(row.raw[column.key as keyof T])}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {renderPagination()}
        </>
      )}
    </section>
  );
}
