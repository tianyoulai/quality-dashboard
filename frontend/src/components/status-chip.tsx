import { pickText } from "@/lib/formatters";

export function StatusChip({
  value,
  tone = "neutral",
}: {
  value: unknown;
  tone?: "neutral" | "danger" | "warning" | "success";
}) {
  return <span className={`status-chip ${tone}`}>{pickText(value)}</span>;
}
