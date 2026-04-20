"use client";

import { useState, type ReactNode } from "react";

/**
 * 原生 <a href> 下载没有任何中间反馈，点完按钮在后端生成大 CSV 时用户会觉得"坏了"。
 * 这个 client 组件在点击瞬间置 loading + 文案切换，2 秒后自动复位（浏览器已经开始下载或 302 返回了，足够盖住感知）。
 * 不阻断跳转——只给触感，不改变原生 GET 行为，导出失败仍然按后端返回走，保持与之前一致。
 */

export type ExportButtonProps = {
  href: string;
  label: string;
  loadingLabel?: string;
  /** 可选扩展样式，比如放到 form-actions 里需要 block */
  className?: string;
  /** 允许传入额外元素，比如 hover 提示；没有就不传。 */
  children?: ReactNode;
  /** 支持 data-role 之类标记，方便 smoke_checks.py 继续用 selector 抓到按钮。 */
  dataRole?: string;
};

export function ExportButton({
  href,
  label,
  loadingLabel = "准备导出…",
  className,
  dataRole,
}: ExportButtonProps) {
  const [isPending, setIsPending] = useState(false);

  const handleClick = () => {
    setIsPending(true);
    // 2 秒后复位；不做 navigation 监听，因为浏览器处理 CSV 下载通常不会触发 visibilitychange 也不会跳页。
    window.setTimeout(() => setIsPending(false), 2000);
  };

  return (
    <a
      className={className ?? "button"}
      href={href}
      onClick={handleClick}
      aria-busy={isPending ? "true" : undefined}
      aria-disabled={isPending ? "true" : undefined}
      data-role={dataRole}
      style={isPending ? { opacity: 0.6, pointerEvents: "none" } : undefined}
    >
      {isPending ? loadingLabel : label}
    </a>
  );
}
