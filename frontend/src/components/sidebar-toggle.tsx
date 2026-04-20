"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

const STORAGE_KEY = "sidebar-collapsed";
const CUSTOM_EVENT = "sidebar-collapsed-updated";

function readCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "true";
}

function subscribe(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  window.addEventListener(CUSTOM_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(CUSTOM_EVENT, callback);
  };
}

export function SidebarToggle() {
  const collapsed = useSyncExternalStore(subscribe, readCollapsed, () => false);

  // 首次挂载时同步 DOM class（副作用只操作 DOM 不 setState，不触发 lint 错误）
  useEffect(() => {
    document.querySelector(".app-shell")?.classList.toggle("sidebar-collapsed", collapsed);
  }, [collapsed]);

  const toggle = useCallback(() => {
    const next = !readCollapsed();
    document.querySelector(".app-shell")?.classList.toggle("sidebar-collapsed", next);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(next));
      window.dispatchEvent(new Event(CUSTOM_EVENT));
    } catch {
      // localStorage 不可用时静默降级
    }
  }, []);

  return (
    <button className="sidebar-toggle" onClick={toggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
      {collapsed ? "»" : "«"}
    </button>
  );
}
