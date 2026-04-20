import Link from "next/link";
import { ReactNode } from "react";

import { BackToTop } from "@/components/back-to-top";
import { SidebarToggle } from "@/components/sidebar-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { NAV_ITEMS } from "@/lib/navigation";

export function AppShell({
  currentPath,
  title,
  subtitle,
  actions,
  lastRefresh,
  children,
}: {
  currentPath: string;
  title: string;
  subtitle: string;
  actions?: ReactNode;
  lastRefresh?: string;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <div className="brand-mark">🧭</div>
          <h1 className="brand-title">QC统一看板</h1>
          <p className="brand-subtitle">质检总览、明细下钻与新人追踪</p>
        </div>
        <nav className="nav-list">
          {NAV_ITEMS.map((item) => {
            const isActive = currentPath === item.href;
            return (
              <Link key={item.key} href={item.href} className={`nav-item${isActive ? " active" : ""}`}>
                <div className="nav-label-row">
                  <span>{item.label}</span>
                  {isActive ? <span className="nav-badge">当前</span> : null}
                </div>
                <span className="nav-description">{item.description}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <SidebarToggle />
            <ThemeToggle />
          </div>
          {lastRefresh ? (
            <div className="sidebar-refresh">数据截至 {lastRefresh}</div>
          ) : null}
        </div>
      </aside>
      <main className="page-main">
        <header className="hero-card">
          <div>
            <div className="eyebrow">QC Dashboard Frontend</div>
            <h2 className="hero-title">{title}</h2>
            <p className="hero-subtitle">{subtitle}</p>
          </div>
          {actions ? <div className="hero-actions">{actions}</div> : null}
        </header>
        {children}
      </main>
      <BackToTop />
    </div>
  );
}
