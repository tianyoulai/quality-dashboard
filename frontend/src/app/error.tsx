"use client";

import { useEffect } from "react";

type ErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

/**
 * 全局错误边界。
 *
 * 捕获 RSC 和客户端渲染错误，显示友好的错误页面 + 重试按钮。
 * digest 是 Next.js 自动生成的错误摘要（生产环境可用作追踪 ID）。
 */
export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    // 可选：把错误上报到监控服务
    console.error("[ErrorBoundary]", error);
  }, [error]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        padding: 40,
        background: "#f3f6fb",
        gap: 16,
      }}
    >
      <div style={{ fontSize: 48 }}>⚠️</div>
      <h2 style={{ margin: 0, color: "#1e293b", fontSize: 20 }}>页面加载出错</h2>
      <p style={{ margin: 0, color: "#64748b", maxWidth: 480, textAlign: "center", lineHeight: 1.6 }}>
        {error.message || "未知错误，请稍后重试。"}
      </p>
      {error.digest && (
        <p style={{ margin: 0, color: "#94a3b8", fontSize: 12 }}>
          错误摘要：{error.digest}
        </p>
      )}
      <button
        onClick={reset}
        style={{
          marginTop: 8,
          padding: "8px 24px",
          background: "#3b82f6",
          color: "#fff",
          border: "none",
          borderRadius: 6,
          fontSize: 14,
          cursor: "pointer",
        }}
      >
        重新加载
      </button>
    </div>
  );
}
