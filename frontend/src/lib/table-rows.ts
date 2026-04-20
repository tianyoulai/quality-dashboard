import type { ReactNode } from "react";

import type { DataTableRow } from "@/components/data-table";

/**
 * 把 server 侧原始行映射成 DataTable 的预渲染行。
 *
 * - `rawRows`: server 拿到的原始对象数组
 * - `cellBuilders`: 每列的渲染函数，在 server 阶段执行，产出 ReactNode。
 *   没列出的 key 由 DataTable 在客户端用 `pickText(raw[key])` 兜底。
 *
 * 使用示例（server component）：
 * ```tsx
 * rows={buildTableRows(queueRows, {
 *   queue_name: (r) => pickText(r.queue_name),
 *   qa_cnt: (r) => toInteger(r.qa_cnt),
 *   final_accuracy_rate: (r) => toPercent(r.final_accuracy_rate),
 * })}
 * ```
 *
 * 这样 columns 里就不要再写 `render: (row) => ...` 了 —— 它是 server→client 不能传的函数。
 */
export function buildTableRows<T extends Record<string, unknown>>(
  rawRows: readonly T[],
  cellBuilders: Partial<Record<string, (row: T, index: number) => ReactNode>>,
  getKey?: (row: T, index: number) => string | number,
): DataTableRow<T>[] {
  return rawRows.map((row, index) => {
    const cells: Record<string, ReactNode> = {};
    for (const [colKey, builder] of Object.entries(cellBuilders)) {
      if (builder) {
        cells[colKey] = builder(row, index);
      }
    }
    return {
      raw: row,
      cells,
      key: getKey ? getKey(row, index) : index,
    };
  });
}
