import Link from "next/link";

export default function NotFound() {
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
      <div style={{ fontSize: 48 }}>🔍</div>
      <h2 style={{ margin: 0, color: "#1e293b", fontSize: 20 }}>页面不存在</h2>
      <p style={{ margin: 0, color: "#64748b" }}>你访问的页面可能已被移动或删除。</p>
      <Link
        href="/"
        style={{
          marginTop: 8,
          padding: "8px 24px",
          background: "#3b82f6",
          color: "#fff",
          borderRadius: 6,
          fontSize: 14,
          textDecoration: "none",
        }}
      >
        返回首页
      </Link>
    </div>
  );
}
