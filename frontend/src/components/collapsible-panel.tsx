"use client";

import { useState, useRef } from "react";

type CollapsiblePanelProps = {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  summary?: React.ReactNode; /* 折叠时显示的简要信息 */
};

export function CollapsiblePanel({
  title,
  subtitle,
  defaultOpen = false,
  children,
  summary,
}: CollapsiblePanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const contentRef = useRef<HTMLDivElement>(null);

  return (
    <section className={`panel ${isOpen ? "" : "panel--collapsed"}`}>
      <button
        type="button"
        className="collapsible-toggle"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
      >
        <div>
          <h3 className="panel-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span
              className="collapsible-chevron"
              style={{
                display: "inline-block",
                transition: "transform 0.2s ease",
                transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                fontSize: "0.75rem",
                color: "#94a3b8",
              }}
            >
              ▶
            </span>
            {title}
          </h3>
          {subtitle && !isOpen && <p className="panel-subtitle">{subtitle}</p>}
        </div>
        {summary && !isOpen && (
          <div className="collapsible-summary">{summary}</div>
        )}
      </button>

      <div
        ref={contentRef}
        className="collapsible-content"
        style={{
          display: isOpen ? "block" : "none",
          overflow: isOpen ? "visible" : "hidden",
        }}
      >
        {children}
      </div>
    </section>
  );
}
