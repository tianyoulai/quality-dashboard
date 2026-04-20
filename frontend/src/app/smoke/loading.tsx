import { SkeletonPanel } from "@/components/skeleton-loader";

export default function Loading() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18, padding: 28, minHeight: "100vh", background: "#f3f6fb" }}>
      <SkeletonPanel />
    </div>
  );
}
