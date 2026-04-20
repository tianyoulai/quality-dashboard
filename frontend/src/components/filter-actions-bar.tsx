"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useRef, useState, useTransition } from "react";

/**
 * 通用筛选表单的 actions 区（client）。
 *
 * 承担三件事（和 Next 16 RSC 场景里 server form 配合）：
 *  1. submit 按钮点一下立刻 disable + 文案变"查询中…"，避免原生 GET 提交毫无反馈。
 *  2. submit 前把空值字段先 `disabled = true`，浏览器不再把 `?a=&b=` 塞进 URL。
 *     保护策略：type='hidden' 和 type='date' 一律跳过（business context/日期必填）。
 *  3. "重置筛选"一键清掉 `resettableFieldNames` 列的字段 + 日期回到默认，
 *     然后 router.push 到 `basePath?resetQuery`（由调用方决定默认查询串）。
 *
 * 不做的事：
 *  - 不改变 form 的 method/action，保持原生 GET 提交。
 *  - 不 override hidden 上下文字段（focus_xxx / dashboard_xxx / detail_page 等）。
 */

export type FilterActionsBarProps = {
  /** submit 按钮文案（默认"查询"）。 */
  submitLabel?: string;
  /** submit 中文案（默认"查询中…"）。 */
  submitLoadingLabel?: string;
  /** 是否展示重置按钮（默认 true）。 */
  showReset?: boolean;
  /** 重置按钮文案（默认"重置筛选"）。 */
  resetLabel?: string;
  /** 重置中文案（默认"重置中…"）。 */
  resetLoadingLabel?: string;
  /** 重置后跳转的基础 path（例如 /details 或 /newcomers）。 */
  basePath: string;
  /**
   * 重置后附加的 query 字符串（不含 "?"）。默认空串，跳转到纯 basePath。
   * 例如 details 页要保留日期，传 `date_start=2026-04-19&date_end=2026-04-19`。
   */
  resetQueryString?: string;
  /** 日期字段默认值（重置时回填；没有日期字段可不传）。 */
  defaultDateStart?: string;
  defaultDateEnd?: string;
  /** 重置时需要清空的字段 name 列表（不会碰 hidden 和 date）。 */
  resettableFieldNames: string[];
  /** 附加的按钮 / 链接（导出、字段说明、分享等），原样 render 在 submit/reset 之后。 */
  extras?: ReactNode;
};

export function FilterActionsBar({
  submitLabel = "查询",
  submitLoadingLabel = "查询中…",
  showReset = true,
  resetLabel = "重置筛选",
  resetLoadingLabel = "重置中…",
  basePath,
  resetQueryString = "",
  defaultDateStart,
  defaultDateEnd,
  resettableFieldNames,
  extras,
}: FilterActionsBarProps) {
  const router = useRouter();
  const [isResetting, startTransition] = useTransition();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const anchorRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const anchor = anchorRef.current;
    if (!anchor) {
      return;
    }
    const form = anchor.closest("form");
    if (!form) {
      return;
    }

    const handleSubmit = () => {
      const fields = form.querySelectorAll<
        HTMLInputElement | HTMLSelectElement
      >("input:not([type='hidden']), select");
      fields.forEach((f) => {
        if (f instanceof HTMLInputElement) {
          if (f.type === "checkbox") {
            if (!f.checked) {
              f.disabled = true;
            }
            return;
          }
          if (f.type === "date") {
            return;
          }
          if (f.value === "") {
            f.disabled = true;
          }
          return;
        }
        if (f instanceof HTMLSelectElement) {
          // multi-select：所有 option 都没选中才算空
          if (f.multiple) {
            const anySelected = Array.from(f.selectedOptions).some(
              (opt) => opt.value !== "",
            );
            if (!anySelected) {
              f.disabled = true;
            }
            return;
          }
          if (f.value === "") {
            f.disabled = true;
          }
        }
      });
      setIsSubmitting(true);
    };

    form.addEventListener("submit", handleSubmit);
    return () => {
      form.removeEventListener("submit", handleSubmit);
    };
  }, []);

  const handleReset = () => {
    const anchor = anchorRef.current;
    if (!anchor) {
      return;
    }
    const form = anchor.closest("form");
    if (!form) {
      return;
    }
    resettableFieldNames.forEach((name) => {
      const elements = form.querySelectorAll<
        HTMLSelectElement | HTMLInputElement
      >(`[name='${name}']`);
      elements.forEach((el) => {
        if (el instanceof HTMLSelectElement) {
          if (el.multiple) {
            Array.from(el.options).forEach((opt) => {
              opt.selected = false;
            });
          } else {
            el.value = "";
          }
        } else if (el instanceof HTMLInputElement) {
          if (el.type === "checkbox") {
            el.checked = false;
          } else {
            el.value = "";
          }
        }
      });
    });
    if (defaultDateStart !== undefined) {
      const dateStart = form.querySelector<HTMLInputElement>(
        "[name='date_start']",
      );
      if (dateStart) {
        dateStart.value = defaultDateStart;
      }
    }
    if (defaultDateEnd !== undefined) {
      const dateEnd = form.querySelector<HTMLInputElement>(
        "[name='date_end']",
      );
      if (dateEnd) {
        dateEnd.value = defaultDateEnd;
      }
    }
    startTransition(() => {
      const target = resetQueryString
        ? `${basePath}?${resetQueryString}`
        : basePath;
      router.push(target);
    });
  };

  return (
    <>
      {/* anchor 仅用于 closest('form')，不占视觉空间 */}
      <span ref={anchorRef} style={{ display: "none" }} aria-hidden="true" />
      <button
        type="submit"
        className="button primary"
        disabled={isSubmitting}
      >
        {isSubmitting ? submitLoadingLabel : submitLabel}
      </button>
      {showReset ? (
        <button
          type="button"
          className="button"
          onClick={handleReset}
          disabled={isResetting}
        >
          {isResetting ? resetLoadingLabel : resetLabel}
        </button>
      ) : null}
      {extras}
    </>
  );
}
