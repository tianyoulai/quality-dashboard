import { SkeletonSummaryCard, SkeletonTable } from "@/components/skeleton-loader";

export default function Loading() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr", minHeight: "100vh", background: "#f3f6fb" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 18, padding: 28 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          <SkeletonSummaryCard />
          <SkeletonSummaryCard />
          <SkeletonSummaryCard />
        </div>
        <SkeletonTable rows={8} cols={6} />
      </div>
    </div>
  );
}
