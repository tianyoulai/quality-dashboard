"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

const STORAGE_KEY = "theme";
const CUSTOM_EVENT = "theme-updated";

function readIsDark(): boolean {
  if (typeof window === "undefined") return false;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "dark") return true;
  if (stored === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
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

function applyTheme(dark: boolean) {
  document.documentElement.classList.toggle("dark", dark);
  try {
    window.localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
    window.dispatchEvent(new Event(CUSTOM_EVENT));
  } catch {
    // localStorage 不可用时静默降级
  }
}

export function ThemeToggle() {
  // server snapshot = false → SSR 渲染 🌙；client mount 后 useSyncExternalStore 取真实值。
  const dark = useSyncExternalStore(subscribe, readIsDark, () => false);

  // 首次挂载时同步 DOM class（副作用只操作 DOM 不 setState，不触发 lint 错误）
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const toggle = useCallback(() => {
    applyTheme(!readIsDark());
  }, []);

  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      suppressHydrationWarning
    >
      {dark ? "☀️" : "🌙"}
    </button>
  );
}
