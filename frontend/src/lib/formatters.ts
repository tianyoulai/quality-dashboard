export function toPercent(value: unknown, digits = 2): string {
  const numberValue = Number(value);
  if (Number.isNaN(numberValue)) {
    return "—";
  }
  return `${numberValue.toFixed(digits)}%`;
}

export function toNumber(value: unknown): number {
  const numberValue = Number(value);
  return Number.isNaN(numberValue) ? 0 : numberValue;
}

export function toInteger(value: unknown): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(toNumber(value));
}

export function toDateInputValue(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  return value.slice(0, 10);
}

export function toDisplayDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return value.slice(0, 10);
}

export function pickText(value: unknown, fallback = "—"): string {
  if (value === null || value === undefined) {
    return fallback;
  }
  const text = String(value).trim();
  return text ? text : fallback;
}

export function buildQueryString(params: Record<string, string | null | undefined>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      searchParams.set(key, value);
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}
