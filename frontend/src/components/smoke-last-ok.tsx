"use client";

import { useEffect, useSyncExternalStore } from "react";

/**
 * <SmokeLastOk /> —— /smoke 页的小标签组件。
 *
 * 定位：只做 client 侧"上次 ok 时间"的渲染与写入，不参与 server 端拉接口。
 *
 * 行为：
 *   - status === "ok" 时，挂载后立即把 {ts, latencyMs} 写入 localStorage。
 *   - 不论 status 是什么，都尝试读 localStorage，把"上次 ok"展示出来（方便判断最后一次成功是多久之前）。
 *
 * key 规则：smoke:lastOk:${checkKey}，checkKey 用 CheckResult.key（meta/home/details/newcomers）。
 *
 * 实现要点：
 *   用 useSyncExternalStore 把 localStorage 当成一个外部 store，避免 useEffect 里
 *   同步 setState 触发的 react-hooks/set-state-in-effect lint 警告。localStorage 没有
 *   同页 change 事件，所以 subscribe 只用于同源 `storage`（跨 tab）；同页写入后自己手动
 *   dispatch 一次 storage-like 事件来触发重渲染。
 */
type Props = {
  checkKey: string;
  status: "ok" | "warn" | "error";
  latencyMs: number;
};

type LastOk = {
  ts: number;
  latencyMs: number;
};

const STORAGE_PREFIX = "smoke:lastOk:";
/** 自定义事件名：同页写入 localStorage 后手动派发，跨 tab 交给浏览器原生 storage 事件。 */
const CUSTOM_EVENT = "smoke:last-ok-updated";

function formatAgo(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 0) return "刚刚";
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec} 秒前`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;
  const day = Math.floor(hour / 24);
  return `${day} 天前`;
}

function readFromStorage(storageKey: string): LastOk | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LastOk>;
    if (typeof parsed.ts === "number" && typeof parsed.latencyMs === "number") {
      return { ts: parsed.ts, latencyMs: parsed.latencyMs };
    }
    return null;
  } catch {
    return null;
  }
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

export function SmokeLastOk({ checkKey, status, latencyMs }: Props) {
  const storageKey = `${STORAGE_PREFIX}${checkKey}`;

  // server 端渲染阶段直接返回 null，等 client 端挂载后从 localStorage 同步。
  const lastOk = useSyncExternalStore<LastOk | null>(
    subscribe,
    () => readFromStorage(storageKey),
    () => null,
  );

  // 本次 ok 时写入 localStorage；派发自定义事件让 useSyncExternalStore 重新取值。
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (status !== "ok") return;
    const payload: LastOk = { ts: Date.now(), latencyMs };
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(payload));
      window.dispatchEvent(new Event(CUSTOM_EVENT));
    } catch {
      // localStorage 满了或被禁用时静默降级，不影响页面本身
    }
  }, [status, latencyMs, storageKey]);

  if (!lastOk) {
    return <span className="kpi-pill">上次 ok：尚无记录</span>;
  }

  return (
    <span className="kpi-pill" title={new Date(lastOk.ts).toLocaleString()}>
      上次 ok：{formatAgo(lastOk.ts)} · {lastOk.latencyMs} ms
    </span>
  );
}
