import { SkeletonSummaryCard, SkeletonTable } from "@/components/skeleton-loader";

export default function Loading() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr", minHeight: "100vh", background: "#f3f6fb" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 18, padding: 28 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
          <SkeletonSummaryCard />
          <SkeletonSummaryCard />
          <SkeletonSummaryCard />
          <SkeletonSummaryCard />
        </div>
        <SkeletonTable rows={6} cols={5} />
        <SkeletonTable rows={4} cols={3} />
      </div>
    </div>
  );
}
