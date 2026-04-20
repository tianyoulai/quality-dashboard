import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { BarListCard } from "@/components/bar-list-card";
import { CollapsiblePanel } from "@/components/collapsible-panel";
import { DataTable } from "@/components/data-table";
import { FilterActionsBar } from "@/components/filter-actions-bar";
import { LineChartCard } from "@/components/line-chart-card";
import { SummaryCard } from "@/components/summary-card";
import { TrainingDailySendPanel } from "@/components/training-daily-send-panel";
import { safeFetchApi } from "@/lib/api";
import { pickText, toDateInputValue, toInteger, toPercent, toNumber } from "@/lib/formatters";
import { buildTableRows } from "@/lib/table-rows";

type SearchParams = Record<string, string | string[] | undefined>;

export const metadata: Metadata = {
  title: "新人追踪",
};

type Row = Record<string, unknown>;
type LinePoint = {
  label: string;
  primary: number;
  secondary?: number;
};

type PageProps = {
  searchParams?: Promise<SearchParams>;
};

function readParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function readMultiParam(value: string | string[] | undefined): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => item.trim()).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function getRows(value: unknown): Row[] {
  return Array.isArray(value) ? (value as Row[]) : [];
}

const COMPACT_QUERY_KEY = "nc";

function appendMultiValueParam(query: URLSearchParams, key: string, values: string[]) {
  values.forEach((value) => {
    if (value) {
      query.append(key, value);
    }
  });
}

function appendOptionalParam(query: URLSearchParams, key: string, value?: string) {
  if (value) {
    query.set(key, value);
  }
}

function buildScopeQueryParams({
  batchNames,
  owner,
  teamName,
}: {
  batchNames: string[];
  owner?: string;
  teamName?: string;
}) {
  const query = new URLSearchParams();
  appendMultiValueParam(query, "batch_names", batchNames);
  appendOptionalParam(query, "owner", owner);
  appendOptionalParam(query, "team_name", teamName);
  return query;
}

function decodeCompactShareToken(tokenValue: string | string[] | undefined): Record<string, string | string[]> {
  const token = readParam(tokenValue)?.trim();
  if (!token) {
    return {};
  }

  try {
    const normalizedToken = token.replace(/-/g, "+").replace(/_/g, "/");
    const paddedToken = normalizedToken.padEnd(Math.ceil(normalizedToken.length / 4) * 4, "=");
    const parsed = JSON.parse(Buffer.from(paddedToken, "base64").toString("utf-8")) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object") {
      return {};
    }

    const decoded: Record<string, string | string[]> = {};
    const rawBatches = parsed.b;
    if (Array.isArray(rawBatches)) {
      const batchValues = rawBatches.map((value) => String(value || "").trim()).filter(Boolean);
      if (batchValues.length > 0) {
        decoded.batch = batchValues;
      }
    } else if (typeof rawBatches === "string" && rawBatches.trim()) {
      decoded.batch = [rawBatches.trim()];
    }

    [
      ["o", "owner"],
      ["t", "team"],
      ["s", "detail_stage"],
      ["r", "detail_risk"],
      ["e", "detail_error_type"],
      ["ra", "detail_reviewer_alias"],
      ["rn", "detail_reviewer"],
      ["v", "view"],
    ].forEach(([compactKey, verboseKey]) => {
      const value = parsed[compactKey];
      if (typeof value === "string" && value.trim()) {
        decoded[verboseKey] = value.trim();
      }
    });

    return decoded;
  } catch {
    return {};
  }
}

/**
 * 把一组筛选字段打成 base64url token（和 decodeCompactShareToken 对称）。
 *
 * 用途：只给"打开当前页分享视角"这种要发出去的链接用，把
 * batch_names=xx&batch_names=yy&batch_names=zz&detail_stage=...&detail_risk=...
 * 这种十几个 key 的长 URL 压缩到一个 `?nc=<token>`，分享时短一个量级。
 *
 * 注意：只 encode 有值的字段；batch 作为数组放进 `b`；其它走 L107-115 映射。
 * 返回空字符串时调用方应该回落到原生 URL（避免 `?nc=` 挂空）。
 */
function encodeCompactShareToken({
  batchNames,
  owner,
  teamName,
  detailStage,
  detailRisk,
  detailErrorType,
  detailReviewerAlias,
  detailReviewerName,
  view,
}: {
  batchNames?: string[];
  owner?: string;
  teamName?: string;
  detailStage?: string;
  detailRisk?: string;
  detailErrorType?: string;
  detailReviewerAlias?: string;
  detailReviewerName?: string;
  view?: string;
}): string {
  const payload: Record<string, string | string[]> = {};
  const cleanBatches = (batchNames || []).map((value) => String(value || "").trim()).filter(Boolean);
  if (cleanBatches.length > 0) {
    payload.b = cleanBatches;
  }
  const pairs: [string, string | undefined][] = [
    ["o", owner],
    ["t", teamName],
    ["s", detailStage],
    ["r", detailRisk],
    ["e", detailErrorType],
    ["ra", detailReviewerAlias],
    ["rn", detailReviewerName],
    ["v", view],
  ];
  pairs.forEach(([key, value]) => {
    const trimmed = (value || "").trim();
    if (trimmed) {
      payload[key] = trimmed;
    }
  });
  if (Object.keys(payload).length === 0) {
    return "";
  }
  const base64 = Buffer.from(JSON.stringify(payload), "utf-8").toString("base64");
  // URL-safe：+ / = → - _ (去 padding)
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function readCompactParam(compactPayload: Record<string, string | string[]>, key: string): string {
  const value = compactPayload[key];
  if (Array.isArray(value)) {
    return value[0] || "";
  }
  return typeof value === "string" ? value : "";
}

function readCompactMultiParam(compactPayload: Record<string, string | string[]>, key: string): string[] {
  const value = compactPayload[key];
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function splitSummaryValues(rows: Row[], key: string): string[] {
  return Array.from(
    rows.reduce((values, row) => {
      pickText(row[key], "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean)
        .forEach((value) => values.add(value));
      return values;
    }, new Set<string>()),
  ).sort((left, right) => left.localeCompare(right, "zh-CN"));
}

function buildNewcomerPageHref({
  batchNames,
  owner,
  teamName,
  reviewerAlias,
  detailStage,
  detailRisk,
  detailErrorType,
  detailReviewerAlias,
  detailPage,
}: {
  batchNames: string[];
  owner?: string;
  teamName?: string;
  reviewerAlias?: string;
  detailStage?: string;
  detailRisk?: string;
  detailErrorType?: string;
  detailReviewerAlias?: string;
  detailPage?: number;
}) {
  const query = buildScopeQueryParams({ batchNames, owner, teamName });
  appendOptionalParam(query, "reviewer_alias", reviewerAlias);
  appendOptionalParam(query, "detail_stage", detailStage);
  appendOptionalParam(query, "detail_risk", detailRisk);
  appendOptionalParam(query, "detail_error_type", detailErrorType);
  appendOptionalParam(query, "detail_reviewer_alias", detailReviewerAlias);
  if (detailPage && detailPage > 1) {
    query.set("detail_page", String(detailPage));
  }
  return query.toString() ? `/newcomers?${query.toString()}` : "/newcomers";
}

function formatReliabilityLabel(value: unknown): string {
  const normalized = pickText(value, "ok").toLowerCase();
  if (normalized === "error") {
    return "异常";
  }
  if (normalized === "warn") {
    return "需关注";
  }
  return "正常";
}

function formatStageLabel(value: unknown): string {
  const stage = pickText(value, "").toLowerCase();
  if (stage === "training") {
    return "📘 标准培训";
  }
  if (stage === "internal") {
    return "🏫 内检";
  }
  if (stage === "external") {
    return "🔍 外检";
  }
  if (stage === "formal") {
    return "✅ 正式上线";
  }
  return "—";
}

function formatBatchStageLabel(labelValue: unknown, stageValue: unknown): string {
  const explicitLabel = pickText(labelValue, "");
  if (explicitLabel) {
    return explicitLabel;
  }
  const stage = pickText(stageValue, "").toLowerCase();
  if (stage === "pending") {
    return "待开始";
  }
  return formatStageLabel(stage);
}

function formatMemberStatus(value: unknown): string {
  const status = pickText(value, "").toLowerCase();
  if (status === "training") {
    return "培训中";
  }
  if (status === "graduated") {
    return "已转正";
  }
  if (status === "left") {
    return "已离开";
  }
  return pickText(value, "—") || "—";
}

function summarizeBatchNames(batchNames: string[]): string {
  if (batchNames.length === 0) {
    return "未选择批次";
  }
  if (batchNames.length <= 2) {
    return batchNames.join(" / ");
  }
  return `${batchNames.slice(0, 2).join(" / ")} 等 ${batchNames.length} 批`;
}

function safePercent(numerator: number, denominator: number): number {
  if (!Number.isFinite(denominator) || denominator <= 0) {
    return 0;
  }
  return (numerator * 100) / denominator;
}

function getSampleAccuracy(row: Row): number {
  if (row.sample_accuracy !== undefined && row.sample_accuracy !== null && row.sample_accuracy !== "") {
    return toNumber(row.sample_accuracy);
  }
  if (row.sample_accuracy_rate !== undefined && row.sample_accuracy_rate !== null && row.sample_accuracy_rate !== "") {
    return toNumber(row.sample_accuracy_rate);
  }
  return toNumber(row.accuracy_rate);
}

function formatSignedPercent(value: unknown, digits = 2): string {
  const numericValue = toNumber(value);
  const prefix = numericValue > 0 ? "+" : "";
  return `${prefix}${numericValue.toFixed(digits)}%`;
}

function getBatchRiskTone(riskLabelValue: unknown): "danger" | "warning" | "success" | "neutral" {
  const riskLabel = pickText(riskLabelValue, "");
  if (riskLabel.includes("试标风险") || riskLabel.includes("风险批次")) {
    return "danger";
  }
  if (riskLabel.includes("试标关注") || riskLabel.includes("关注批次")) {
    return "warning";
  }
  if (riskLabel.includes("试标稳定") || riskLabel.includes("稳定批次")) {
    return "success";
  }
  return "neutral";
}

function getBatchRiskDisplayRank(row: Row): number {
  if (row.display_rank !== undefined && row.display_rank !== null && row.display_rank !== "") {
    return toNumber(row.display_rank);
  }
  const riskLabel = pickText(row.risk_label, "");
  if (riskLabel.includes("试标风险") || riskLabel.includes("风险批次")) {
    return 0;
  }
  if (riskLabel.includes("试标关注") || riskLabel.includes("关注批次")) {
    return 1;
  }
  if (riskLabel.includes("暂未进入评估")) {
    return 2;
  }
  if (riskLabel.includes("试标稳定") || riskLabel.includes("稳定批次")) {
    return 3;
  }
  return 4;
}

function sortBatchWatchRows(rows: Row[]): Row[] {
  return [...rows].sort((left, right) => {
    const displayRankDiff = getBatchRiskDisplayRank(left) - getBatchRiskDisplayRank(right);
    if (displayRankDiff !== 0) {
      return displayRankDiff;
    }
    const riskRankDiff = toNumber(left.risk_rank) - toNumber(right.risk_rank);
    if (riskRankDiff !== 0) {
      return riskRankDiff;
    }
    const p0Diff = toNumber(right.p0_cnt) - toNumber(left.p0_cnt);
    if (p0Diff !== 0) {
      return p0Diff;
    }
    const p1Diff = toNumber(right.p1_cnt) - toNumber(left.p1_cnt);
    if (p1Diff !== 0) {
      return p1Diff;
    }
    const gapDiff = toNumber(right.sample_gap_pct ?? right.gap_pct) - toNumber(left.sample_gap_pct ?? left.gap_pct);
    if (gapDiff !== 0) {
      return gapDiff;
    }
    const sampleAccDiff = toNumber(left.sample_accuracy) - toNumber(right.sample_accuracy);
    if (sampleAccDiff !== 0) {
      return sampleAccDiff;
    }
    const qaDiff = toNumber(right.qa_cnt) - toNumber(left.qa_cnt);
    if (qaDiff !== 0) {
      return qaDiff;
    }
    return pickText(left.batch_name, "").localeCompare(pickText(right.batch_name, ""), "zh-CN");
  });
}

function buildBatchOverviewHref({
  row,
  owner,
  teamName,
}: {
  row: Row;
  owner?: string;
  teamName?: string;
}): string {
  const batchName = pickText(row.batch_name, "");
  const currentStage = pickText(row.current_stage, "").toLowerCase();
  const detailStage = ["internal", "external", "formal"].includes(currentStage) ? currentStage : undefined;
  return buildNewcomerPageHref({
    batchNames: batchName ? [batchName] : [],
    owner,
    teamName,
    detailStage,
    detailPage: 1,
  });
}

function buildGroupKey(row: Row, groupKeys: string[]): string {
  return groupKeys.map((key) => pickText(row[key], "")).join("__wb__");
}

function buildDualAccuracyGroup(rows: Row[], groupKeys: string[]): Row[] {
  const reviewerBucket = new Map<string, Row>();

  rows.forEach((row) => {
    const reviewerName = pickText(row.reviewer_name, "");
    const shortName = pickText(row.short_name, reviewerName);
    const memberKey = reviewerName || shortName;
    if (!memberKey) {
      return;
    }

    const groupValueEntries = groupKeys.map((key) => [key, row[key]] as const);
    const reviewerKey = `${groupValueEntries.map(([, value]) => pickText(value, "")).join("__wb__")}__reviewer__${memberKey}`;
    const current = reviewerBucket.get(reviewerKey) || Object.fromEntries(groupValueEntries);

    reviewerBucket.set(reviewerKey, {
      ...current,
      reviewer_name: reviewerName,
      short_name: shortName,
      member_key: memberKey,
      qa_cnt: toNumber(current.qa_cnt) + toNumber(row.qa_cnt),
      correct_cnt: toNumber(current.correct_cnt) + toNumber(row.correct_cnt),
      misjudge_cnt: toNumber(current.misjudge_cnt) + toNumber(row.misjudge_cnt),
      missjudge_cnt: toNumber(current.missjudge_cnt) + toNumber(row.missjudge_cnt),
    });
  });

  const groupBucket = new Map<string, Row>();

  reviewerBucket.forEach((reviewerRow) => {
    const groupKey = buildGroupKey(reviewerRow, groupKeys);
    const current = groupBucket.get(groupKey) || Object.fromEntries(groupKeys.map((key) => [key, reviewerRow[key]]));
    const reviewerAccuracy = safePercent(toNumber(reviewerRow.correct_cnt), toNumber(reviewerRow.qa_cnt));
    const memberNames = (current.member_names instanceof Set ? current.member_names : new Set<string>()) as Set<string>;
    const memberKey = pickText(reviewerRow.member_key, pickText(reviewerRow.reviewer_name, pickText(reviewerRow.short_name, "")));
    if (memberKey) {
      memberNames.add(memberKey);
    }

    groupBucket.set(groupKey, {
      ...current,
      qa_cnt: toNumber(current.qa_cnt) + toNumber(reviewerRow.qa_cnt),
      correct_cnt: toNumber(current.correct_cnt) + toNumber(reviewerRow.correct_cnt),
      misjudge_cnt: toNumber(current.misjudge_cnt) + toNumber(reviewerRow.misjudge_cnt),
      missjudge_cnt: toNumber(current.missjudge_cnt) + toNumber(reviewerRow.missjudge_cnt),
      reviewer_accuracy_total: toNumber(current.reviewer_accuracy_total) + reviewerAccuracy,
      reviewer_cnt: toNumber(current.reviewer_cnt) + 1,
      member_names: memberNames,
    });
  });

  return [...groupBucket.values()].map((groupRow) => {
    const qaCnt = toNumber(groupRow.qa_cnt);
    const correctCnt = toNumber(groupRow.correct_cnt);
    const reviewerCnt = toNumber(groupRow.reviewer_cnt);
    const sampleAccuracy = safePercent(correctCnt, qaCnt);
    const perCapitaAccuracy = reviewerCnt > 0 ? toNumber(groupRow.reviewer_accuracy_total) / reviewerCnt : 0;
    const misjudgeRate = safePercent(toNumber(groupRow.misjudge_cnt), qaCnt);
    const missjudgeRate = safePercent(toNumber(groupRow.missjudge_cnt), qaCnt);

    return {
      ...groupRow,
      member_cnt: (groupRow.member_names instanceof Set ? groupRow.member_names.size : 0),
      sample_accuracy: Number(sampleAccuracy.toFixed(2)),
      per_capita_accuracy: Number(perCapitaAccuracy.toFixed(2)),
      accuracy_rate: Number(sampleAccuracy.toFixed(2)),
      accuracy_gap: Number((sampleAccuracy - perCapitaAccuracy).toFixed(2)),
      misjudge_rate: Number(misjudgeRate.toFixed(2)),
      missjudge_rate: Number(missjudgeRate.toFixed(2)),
      issue_rate: Number((misjudgeRate + missjudgeRate).toFixed(2)),
    };
  });
}

function computeDualAccuracyStats(rows: Row[]): Row {
  if (rows.length === 0) {
    return {
      qa_cnt: 0,
      correct_cnt: 0,
      member_cnt: 0,
      sample_accuracy: 0,
      per_capita_accuracy: 0,
      accuracy_gap: 0,
      issue_rate: 0,
    };
  }

  const result = buildDualAccuracyGroup(rows.map((row) => ({ ...row, __scope__: "selected" })), ["__scope__"]);
  return result[0] || {
    qa_cnt: 0,
    correct_cnt: 0,
    member_cnt: 0,
    sample_accuracy: 0,
    per_capita_accuracy: 0,
    accuracy_gap: 0,
    issue_rate: 0,
  };
}

function aggregateDualAccuracyTrend(rows: Row[]): LinePoint[] {
  return buildDualAccuracyGroup(rows, ["biz_date"])
    .map((row) => ({
      label: toDateInputValue(pickText(row.biz_date, "")) || pickText(row.biz_date, "—"),
      primary: toNumber(row.sample_accuracy),
      secondary: toNumber(row.per_capita_accuracy),
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

function normalizeLinePoints(rows: Row[]): LinePoint[] {
  return rows
    .map((row) => ({
      label: pickText(row.label, toDateInputValue(row.biz_date as string | undefined) || "—"),
      primary: toNumber(row.primary ?? row.sample_accuracy),
      secondary: row.secondary !== undefined || row.per_capita_accuracy !== undefined
        ? toNumber(row.secondary ?? row.per_capita_accuracy)
        : undefined,
    }))
    .filter((row) => row.label);
}

function aggregateStageSampleTrend(rows: Row[]) {
  const bucket = new Map<string, { internalScore: number; internalQa: number; externalScore: number; externalQa: number }>();

  rows.forEach((row) => {
    const dateKey = toDateInputValue(row.biz_date as string | undefined);
    if (!dateKey) {
      return;
    }

    const entry = bucket.get(dateKey) || { internalScore: 0, internalQa: 0, externalScore: 0, externalQa: 0 };
    const qaCnt = toNumber(row.qa_cnt);
    const accuracy = getSampleAccuracy(row);
    const stage = pickText(row.stage, "").toLowerCase();

    if (stage === "internal") {
      entry.internalScore += qaCnt * accuracy;
      entry.internalQa += qaCnt;
    } else if (stage === "external") {
      entry.externalScore += qaCnt * accuracy;
      entry.externalQa += qaCnt;
    }

    bucket.set(dateKey, entry);
  });

  return [...bucket.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([label, entry]) => ({
      label,
      primary: entry.internalQa > 0 ? entry.internalScore / entry.internalQa : 0,
      secondary: entry.externalQa > 0 ? entry.externalScore / entry.externalQa : 0,
    }));
}

function aggregateTrainingFormalSampleTrend(trainingRows: Row[], formalRows: Row[]) {
  const bucket = new Map<string, { trainingScore: number; trainingQa: number; formalScore: number; formalQa: number }>();

  trainingRows.forEach((row) => {
    const dateKey = toDateInputValue(row.biz_date as string | undefined);
    if (!dateKey) {
      return;
    }
    const entry = bucket.get(dateKey) || { trainingScore: 0, trainingQa: 0, formalScore: 0, formalQa: 0 };
    const qaCnt = toNumber(row.qa_cnt);
    entry.trainingScore += qaCnt * getSampleAccuracy(row);
    entry.trainingQa += qaCnt;
    bucket.set(dateKey, entry);
  });

  formalRows.forEach((row) => {
    const dateKey = toDateInputValue(row.biz_date as string | undefined);
    if (!dateKey) {
      return;
    }
    const entry = bucket.get(dateKey) || { trainingScore: 0, trainingQa: 0, formalScore: 0, formalQa: 0 };
    const qaCnt = toNumber(row.qa_cnt);
    entry.formalScore += qaCnt * getSampleAccuracy(row);
    entry.formalQa += qaCnt;
    bucket.set(dateKey, entry);
  });

  return [...bucket.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([label, entry]) => ({
      label,
      primary: entry.trainingQa > 0 ? entry.trainingScore / entry.trainingQa : 0,
      secondary: entry.formalQa > 0 ? entry.formalScore / entry.formalQa : 0,
    }));
}

function aggregateStageSummary(rows: Row[]) {
  const order = ["internal", "external", "formal"];
  const stageRows = buildDualAccuracyGroup(rows, ["stage"]);
  return stageRows
    .filter((row) => order.includes(pickText(row.stage, "").toLowerCase()))
    .sort((left, right) => order.indexOf(pickText(left.stage, "").toLowerCase()) - order.indexOf(pickText(right.stage, "").toLowerCase()))
    .map((row) => ({
      ...row,
      stage_label: formatStageLabel(row.stage),
    }));
}

function normalizeFormalRows(formalRows: Row[], members: Row[]): Row[] {
  const memberLookup = new Map<string, Row>();
  members.forEach((row) => {
    const alias = pickText(row.reviewer_alias, "");
    if (alias && !memberLookup.has(alias)) {
      memberLookup.set(alias, row);
    }
  });

  return formalRows
    .map((row) => {
      const alias = pickText(row.reviewer_name, "");
      const member = memberLookup.get(alias);
      return {
        ...row,
        reviewer_name: alias,
        stage: "formal",
        batch_name: pickText(row.batch_name, pickText(member?.batch_name, "未归属批次")),
        team_name: pickText(row.team_name, pickText(member?.team_name, "未分组")),
        short_name: pickText(row.short_name, pickText(member?.reviewer_name, alias)),
      };
    })
    .filter((row) => pickText(row.reviewer_name, "") !== "");
}

function aggregateBatchCompare(batchRows: Row[], combinedRows: Row[]) {
  const batchSummary = new Map(
    buildDualAccuracyGroup(combinedRows, ["batch_name"]).map((row) => [pickText(row.batch_name, ""), row]),
  );
  const teamSummary = buildDualAccuracyGroup(combinedRows, ["batch_name", "team_name"]);
  const teamLookup = teamSummary.reduce((map, row) => {
    const batchName = pickText(row.batch_name, "");
    const items = map.get(batchName) || [];
    items.push(row);
    map.set(batchName, items);
    return map;
  }, new Map<string, Row[]>());

  return batchRows
    .map((row) => {
      const batchName = pickText(row.batch_name, "");
      const stats = batchSummary.get(batchName);
      const teams = [...(teamLookup.get(batchName) || [])].sort(
        (left, right) => toNumber(right.sample_accuracy) - toNumber(left.sample_accuracy) || toNumber(right.per_capita_accuracy) - toNumber(left.per_capita_accuracy),
      );
      const bestTeam = teams[0];
      const worstTeam = teams[teams.length - 1];
      const joinDate = toDateInputValue(row.join_date as string | undefined);
      const trainingDays = joinDate ? Math.max(0, Math.floor((Date.now() - new Date(`${joinDate}T00:00:00`).getTime()) / 86400000)) : 0;

      return {
        batch_name: batchName,
        join_date: joinDate,
        total_cnt: toNumber(row.total_cnt),
        training_cnt: toNumber(row.training_cnt),
        graduated_cnt: toNumber(row.graduated_cnt),
        member_cnt: toNumber(stats?.member_cnt),
        qa_cnt: toNumber(stats?.qa_cnt),
        sample_accuracy: toNumber(stats?.sample_accuracy),
        per_capita_accuracy: toNumber(stats?.per_capita_accuracy),
        accuracy_rate: toNumber(stats?.sample_accuracy),
        accuracy_gap: toNumber(stats?.accuracy_gap),
        issue_rate: toNumber(stats?.issue_rate),
        training_days: trainingDays,
        best_team_name: pickText(bestTeam?.team_name, "—"),
        best_team_acc: toNumber(bestTeam?.sample_accuracy),
        best_team_per_capita_acc: toNumber(bestTeam?.per_capita_accuracy),
        worst_team_name: pickText(worstTeam?.team_name, "—"),
        worst_team_acc: toNumber(worstTeam?.sample_accuracy),
        worst_team_per_capita_acc: toNumber(worstTeam?.per_capita_accuracy),
        sample_gap_pct: bestTeam && worstTeam ? toNumber(bestTeam.sample_accuracy) - toNumber(worstTeam.sample_accuracy) : 0,
        per_capita_gap_pct: bestTeam && worstTeam ? toNumber(bestTeam.per_capita_accuracy) - toNumber(worstTeam.per_capita_accuracy) : 0,
        owners: pickText(row.owners, "未填写"),
      };
    })
    .sort(
      (left, right) => toNumber(right.sample_gap_pct) - toNumber(left.sample_gap_pct) || toNumber(left.sample_accuracy) - toNumber(right.sample_accuracy),
    );
}

function aggregatePersonStage(personRows: Row[]) {
  const bucket = new Map<string, { qaCnt: number; correctCnt: number; misjudgeCnt: number; missjudgeCnt: number }>();

  personRows.forEach((row) => {
    const stage = pickText(row.stage, "").toLowerCase();
    if (!stage) {
      return;
    }
    const entry = bucket.get(stage) || { qaCnt: 0, correctCnt: 0, misjudgeCnt: 0, missjudgeCnt: 0 };
    entry.qaCnt += toNumber(row.qa_cnt);
    entry.correctCnt += toNumber(row.correct_cnt);
    entry.misjudgeCnt += toNumber(row.misjudge_cnt);
    entry.missjudgeCnt += toNumber(row.missjudge_cnt);
    bucket.set(stage, entry);
  });

  return ["internal", "external", "formal"]
    .filter((stage) => bucket.has(stage))
    .map((stage) => {
      const entry = bucket.get(stage)!;
      return {
        stage,
        stage_label: formatStageLabel(stage),
        qa_cnt: entry.qaCnt,
        accuracy_rate: entry.qaCnt > 0 ? (entry.correctCnt * 100) / entry.qaCnt : 0,
        misjudge_rate: entry.qaCnt > 0 ? (entry.misjudgeCnt * 100) / entry.qaCnt : 0,
        missjudge_rate: entry.qaCnt > 0 ? (entry.missjudgeCnt * 100) / entry.qaCnt : 0,
      };
    });
}

export default async function NewcomersPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const compactPayload = decodeCompactShareToken(params[COMPACT_QUERY_KEY]);
  const summaryResult = await safeFetchApi<Record<string, unknown>>("/api/v1/newcomers/summary");
  const batches = getRows(summaryResult.data?.batches);
  const ownerOptions = splitSummaryValues(batches, "owners");
  const teamOptions = splitSummaryValues(batches, "teams");
  const defaultBatchNames = batches.slice(0, Math.min(batches.length, 2)).map((row) => pickText(row.batch_name, "")).filter(Boolean);
  const requestedBatchNames = readMultiParam(params.batch_names);
  const compactBatchNames = readCompactMultiParam(compactPayload, "batch");
  const selectedBatchNames = requestedBatchNames.length > 0 ? requestedBatchNames : (compactBatchNames.length > 0 ? compactBatchNames : defaultBatchNames);
  const requestedOwner = readParam(params.owner) || readCompactParam(compactPayload, "owner");
  const selectedOwner = ownerOptions.includes(requestedOwner) ? requestedOwner : "";
  const requestedTeamName = readParam(params.team_name) || readParam(params.team) || readCompactParam(compactPayload, "team");
  const selectedTeamName = teamOptions.includes(requestedTeamName) ? requestedTeamName : "";

  const selectedScopeQuery = buildScopeQueryParams({
    batchNames: selectedBatchNames,
    owner: selectedOwner || undefined,
    teamName: selectedTeamName || undefined,
  });

  const membersResult = selectedBatchNames.length > 0
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/members?${selectedScopeQuery.toString()}`)
    : { data: null, error: null };
  const qaDailyResult = selectedBatchNames.length > 0
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/qa-daily?${selectedScopeQuery.toString()}`)
    : { data: null, error: null };
  const aggregateResult = selectedBatchNames.length > 0
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/aggregates?${selectedScopeQuery.toString()}`)
    : { data: null, error: null };
  const errorSummaryResult = selectedBatchNames.length > 0
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/error-summary?${selectedScopeQuery.toString()}`)
    : { data: null, error: null };

  const metrics = (summaryResult.data?.metrics as Record<string, unknown> | undefined) || {};
  const aggregateData = (aggregateResult.data as Record<string, unknown> | undefined) || {};
  const members = getRows(membersResult.data?.items);
  const qaDaily = getRows(qaDailyResult.data?.items);
  const errorSummary = getRows(errorSummaryResult.data?.items);
  const reviewerAliases = members.map((item) => pickText(item.reviewer_alias, "")).filter((value) => value && value !== "—");

  const requestedReviewerAlias = readParam(params.reviewer_alias) || "";
  const selectedReviewerAlias = reviewerAliases.includes(requestedReviewerAlias) ? requestedReviewerAlias : (reviewerAliases[0] || "");

  const requestedDetailStage = (readParam(params.detail_stage) || readCompactParam(compactPayload, "detail_stage")).toLowerCase();
  const selectedDetailStage = ["internal", "external", "formal"].includes(requestedDetailStage) ? requestedDetailStage : "";
  const requestedDetailRisk = readParam(params.detail_risk) || readCompactParam(compactPayload, "detail_risk");
  const requestedDetailErrorType = readParam(params.detail_error_type) || readCompactParam(compactPayload, "detail_error_type");
  const requestedDetailReviewerAlias = readParam(params.detail_reviewer_alias) || readCompactParam(compactPayload, "detail_reviewer_alias");
  const requestedDetailReviewerName = readParam(params.detail_reviewer) || readCompactParam(compactPayload, "detail_reviewer");

  let selectedDetailReviewerAlias = reviewerAliases.includes(requestedDetailReviewerAlias) ? requestedDetailReviewerAlias : "";
  if (!selectedDetailReviewerAlias && requestedDetailReviewerName) {
    const matchedDetailMember = members.find((row) => {
      const reviewerName = pickText(row.reviewer_name, "");
      const shortName = pickText(row.short_name, reviewerName);
      const reviewerAlias = pickText(row.reviewer_alias, "");
      return [reviewerName, shortName, reviewerAlias].includes(requestedDetailReviewerName);
    });
    selectedDetailReviewerAlias = pickText(matchedDetailMember?.reviewer_alias, "");
  }
  const selectedDetailReviewerMember = members.find((row) => pickText(row.reviewer_alias, "") === selectedDetailReviewerAlias);
  const selectedDetailReviewerName = pickText(selectedDetailReviewerMember?.reviewer_name, requestedDetailReviewerName);

  const formalDailyQuery = new URLSearchParams();
  selectedBatchNames.forEach((batchName) => formalDailyQuery.append("batch_names", batchName));
  reviewerAliases.forEach((alias) => formalDailyQuery.append("reviewer_aliases", alias));
  const formalDailyResult = reviewerAliases.length > 0
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/formal-daily?${formalDailyQuery.toString()}`)
    : { data: null, error: null };
  const personDetailResult = selectedReviewerAlias
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/person-detail?reviewer_alias=${encodeURIComponent(selectedReviewerAlias)}&limit=80`)
    : { data: null, error: null };

  const trainingDailyQuery = new URLSearchParams(selectedScopeQuery.toString());
  appendOptionalParam(trainingDailyQuery, "detail_stage", selectedDetailStage || undefined);
  appendOptionalParam(trainingDailyQuery, "detail_risk_level", requestedDetailRisk || undefined);
  appendOptionalParam(trainingDailyQuery, "detail_error_type", requestedDetailErrorType || undefined);
  appendOptionalParam(trainingDailyQuery, "detail_reviewer_alias", selectedDetailReviewerAlias || undefined);
  appendOptionalParam(trainingDailyQuery, "detail_reviewer_name", selectedDetailReviewerName || undefined);
  const trainingDailyMarkdownResult = selectedBatchNames.length > 0
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/training-daily/markdown?${trainingDailyQuery.toString()}`)
    : { data: null, error: null };

  const detailPage = Math.max(Number.parseInt(readParam(params.detail_page) || "1", 10) || 1, 1);
  const detailLimit = 30;
  const errorDetailsQuery = new URLSearchParams(selectedScopeQuery.toString());
  appendOptionalParam(errorDetailsQuery, "stage", selectedDetailStage || undefined);
  appendOptionalParam(errorDetailsQuery, "risk_level", requestedDetailRisk || undefined);
  appendOptionalParam(errorDetailsQuery, "error_type", requestedDetailErrorType || undefined);
  appendOptionalParam(errorDetailsQuery, "reviewer_alias", selectedDetailReviewerAlias || undefined);
  appendOptionalParam(errorDetailsQuery, "reviewer_name", selectedDetailReviewerName || undefined);
  errorDetailsQuery.set("page", String(detailPage));
  errorDetailsQuery.set("limit", String(detailLimit));
  const errorDetailsResult = selectedBatchNames.length > 0
    ? await safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/error-details?${errorDetailsQuery.toString()}`)
    : { data: null, error: null };

  const formalDaily = getRows(formalDailyResult.data?.items);
  const formalRows = normalizeFormalRows(formalDaily, members);
  const combinedQaRows = [...qaDaily, ...formalRows];
  const selectedBatchRowsFromAggregate = getRows(aggregateData.batch_scope);
  const selectedBatchRows = selectedBatchRowsFromAggregate.length > 0
    ? selectedBatchRowsFromAggregate
    : batches.filter((row) => selectedBatchNames.includes(pickText(row.batch_name, "")));
  const selectedBatchLabel = summarizeBatchNames(selectedBatchNames);
  const aggregateOverview = ((aggregateData.overview as Row | undefined) || {});
  const aggregatedTrainingTrend = normalizeLinePoints(getRows(aggregateData.training_trend));
  const aggregatedFormalTrend = normalizeLinePoints(getRows(aggregateData.formal_trend));
  const aggregatedStageSummaryRows = getRows(aggregateData.stage_summary);
  const aggregatedBatchCompareRows = getRows(aggregateData.batch_compare);
  const selectedDualStats = Object.keys(aggregateOverview).length > 0 ? aggregateOverview : computeDualAccuracyStats(combinedQaRows);
  const trainingDualTrend: LinePoint[] = aggregatedTrainingTrend.length > 0 ? aggregatedTrainingTrend : aggregateDualAccuracyTrend(qaDaily);
  const formalDualTrend: LinePoint[] = aggregatedFormalTrend.length > 0 ? aggregatedFormalTrend : aggregateDualAccuracyTrend(formalRows);
  const stageSummaryRows: Row[] = aggregatedStageSummaryRows.length > 0 ? aggregatedStageSummaryRows : aggregateStageSummary(combinedQaRows);
  const batchCompareRows = aggregatedBatchCompareRows.length > 0 ? aggregatedBatchCompareRows : aggregateBatchCompare(selectedBatchRows, combinedQaRows);
  const batchWatchRows = getRows(aggregateData.batch_watch);
  const batchPromotionRows = getRows(aggregateData.batch_promotion);
  // 把晋升状态按 batch_name 合并到 batch_watch，前端一张表直接展示
  const promotionMap = new Map<string, Row>(
    batchPromotionRows.map((row) => [pickText(row.batch_name, ""), row]),
  );
  const enrichedBatchWatchRows: Row[] = batchWatchRows.map((row) => {
    const promoRow = promotionMap.get(pickText(row.batch_name, ""));
    return promoRow ? { ...row, ...promoRow } : row;
  });
  const sortedBatchWatchRows = sortBatchWatchRows(enrichedBatchWatchRows);
  const priorityBatchRows = (() => {
    const focusRows = sortedBatchWatchRows.filter((row) => getBatchRiskDisplayRank(row) <= 2);
    return (focusRows.length > 0 ? focusRows : sortedBatchWatchRows).slice(0, 3);
  })();
  const pendingEvaluationBatchCount = batchWatchRows.filter((row) => pickText(row.risk_label, "").includes("暂未进入评估")).length;
  const trialAttentionBatchCount = batchWatchRows.filter((row) => {
    const riskLabel = pickText(row.risk_label, "");
    return riskLabel.includes("试标风险") || riskLabel.includes("试标关注");
  }).length;
  const formalAttentionBatchCount = batchWatchRows.filter((row) => {
    const riskLabel = pickText(row.risk_label, "");
    return riskLabel.includes("风险批次") || riskLabel.includes("关注批次");
  }).length;
  const p0TriggeredBatchCount = batchWatchRows.filter((row) => toNumber(row.p0_cnt) > 0).length;
  const canPromoteBatchCount = batchPromotionRows.filter((row) => {
    const ps = pickText(row.promotion_status, "");
    return ps.startsWith("can_promote");
  }).length;
  const notReadyBatchCount = batchPromotionRows.filter((row) => pickText(row.promotion_status, "") === "not_ready").length;
  const teamDistribution = Array.from(
    members.reduce((map, row) => {
      const key = pickText(row.team_name, "未分组");
      map.set(key, (map.get(key) || 0) + 1);
      return map;
    }, new Map<string, number>()),
  )
    .sort((left, right) => right[1] - left[1])
    .slice(0, 8)
    .map(([label, value]) => ({ label, value, meta: `${value} 人`, tone: "primary" as const }));
  const gapLeaderboard = batchCompareRows
    .slice(0, 8)
    .map((row) => ({
      label: pickText(row.batch_name, "未命名批次"),
      value: toNumber(row.sample_gap_pct),
      meta: `${pickText(row.best_team_name, "—")} vs ${pickText(row.worst_team_name, "—")} · 人均差值 ${toPercent(row.per_capita_gap_pct)}`,
      tone: toNumber(row.sample_gap_pct) >= 4 ? "danger" as const : (toNumber(row.sample_gap_pct) >= 2.5 ? "warning" as const : "primary" as const),
    }));
  const stageCardLookup = stageSummaryRows.reduce<Map<string, Row>>((map, row) => {
    const stageKey = pickText(row.stage, "").toLowerCase();
    map.set(stageKey, row);
    return map;
  }, new Map<string, Row>());
  const selectedPersonInfo = members.find((row) => pickText(row.reviewer_alias, "") === selectedReviewerAlias);
  const personNewcomerRows = qaDaily.filter((row) => pickText(row.reviewer_name, "") === selectedReviewerAlias);
  const personFormalRows = formalRows.filter((row) => pickText(row.reviewer_name, "") === selectedReviewerAlias);
  const personCombinedRows = [...personNewcomerRows, ...personFormalRows];
  const personStageRows = aggregatePersonStage(personCombinedRows);
  const personStageTrend = aggregateStageSampleTrend(personNewcomerRows);
  const personTrainingFormalTrend = aggregateTrainingFormalSampleTrend(personNewcomerRows, personFormalRows);
  const personDetailRows = getRows(personDetailResult.data?.items);
  const personErrorRows = personDetailRows.filter((row) => toNumber(row.is_correct) === 0);

  const trainingDailyData = (trainingDailyMarkdownResult.data as Record<string, unknown> | undefined) || {};
  const trainingDailyPayload = (trainingDailyData.payload as Record<string, unknown> | undefined) || {};
  const trainingDailyMarkdown = pickText(trainingDailyData.markdown, "");
  const trainingFocusRows = getRows(trainingDailyPayload.training_focus);
  const errorSamplePreviewRows = getRows(trainingDailyPayload.error_samples_preview);
  const recentRiskRows = getRows(trainingDailyPayload.recent_person_perf).filter((row) => {
    const riskLevel = pickText(row.risk_level, "").toUpperCase();
    return riskLevel === "P0" || riskLevel === "P1";
  });
  const trainingDailyReliability = (trainingDailyPayload.data_reliability as Record<string, unknown> | undefined) || {};
  const trainingDailyReliabilityIssues = Array.isArray(trainingDailyReliability.issues)
    ? trainingDailyReliability.issues.map((item) => pickText(item, "")).filter(Boolean)
    : [];
  const trainingDailyHasData = Boolean(trainingDailyPayload.has_data);
  const trainingDailyAsOfDate = pickText(trainingDailyPayload.as_of_date, "");
  const currentDetailHref = buildNewcomerPageHref({
    batchNames: selectedBatchNames,
    owner: selectedOwner || undefined,
    teamName: selectedTeamName || undefined,
    reviewerAlias: selectedReviewerAlias || undefined,
    detailStage: selectedDetailStage || undefined,
    detailRisk: requestedDetailRisk || undefined,
    detailErrorType: requestedDetailErrorType || undefined,
    detailReviewerAlias: selectedDetailReviewerAlias || undefined,
    detailPage,
  });
  // 分享用短链：把所有筛选字段压到 ?nc=<token>，通常能把 URL 从 ~400 字符压到 ~80。
  // 空 token（没任何筛选）时回落到干净的 /newcomers，避免 ?nc= 挂空。
  const shareToken = encodeCompactShareToken({
    batchNames: selectedBatchNames,
    owner: selectedOwner || undefined,
    teamName: selectedTeamName || undefined,
    detailStage: selectedDetailStage || undefined,
    detailRisk: requestedDetailRisk || undefined,
    detailErrorType: requestedDetailErrorType || undefined,
    detailReviewerAlias: selectedDetailReviewerAlias || undefined,
  });
  const shareDetailHref = shareToken ? `/newcomers?${COMPACT_QUERY_KEY}=${shareToken}` : "/newcomers";
  const externalDetailUrl = pickText(trainingDailyData.detail_url, "");
  const legacyExternalDetailUrl = pickText(trainingDailyData.detail_url_legacy, "");
  const detailRows = getRows(errorDetailsResult.data?.items);
  const detailHasMore = Boolean(errorDetailsResult.data?.has_more);

  const detailRiskOptionSet = new Set<string>();
  [...detailRows, ...errorSamplePreviewRows].forEach((row) => {
    const value = pickText(row.risk_level, "");
    if (value) {
      detailRiskOptionSet.add(value);
    }
  });
  if (requestedDetailRisk) {
    detailRiskOptionSet.add(requestedDetailRisk);
  }
  const detailRiskOptions = Array.from(detailRiskOptionSet).sort((left, right) => left.localeCompare(right, "zh-CN"));

  const detailErrorTypeOptionSet = new Set<string>();
  [...detailRows, ...errorSamplePreviewRows, ...getRows(trainingDailyPayload.error_summary)].forEach((row) => {
    const value = pickText(row.error_type, "");
    if (value) {
      detailErrorTypeOptionSet.add(value);
    }
  });
  if (requestedDetailErrorType) {
    detailErrorTypeOptionSet.add(requestedDetailErrorType);
  }
  const detailErrorTypeOptions = Array.from(detailErrorTypeOptionSet).sort((left, right) => left.localeCompare(right, "zh-CN"));

  const detailReviewerOptions = members.map((member, index) => {
    const alias = pickText(member.reviewer_alias, "");
    return {
      key: `${alias || "reviewer"}-${index}`,
      alias,
      label: `${pickText(member.reviewer_name, alias)}（${pickText(member.batch_name, "未分批")} · ${pickText(member.team_name, "未分组")}）`,
    };
  }).filter((item) => item.alias);
  if (selectedDetailReviewerAlias && !detailReviewerOptions.some((item) => item.alias === selectedDetailReviewerAlias)) {
    detailReviewerOptions.unshift({
      key: `detail-${selectedDetailReviewerAlias}`,
      alias: selectedDetailReviewerAlias,
      label: `${selectedDetailReviewerName || selectedDetailReviewerAlias}（当前分享参数）`,
    });
  }

  const detailPrevHref = detailPage > 1
    ? buildNewcomerPageHref({
      batchNames: selectedBatchNames,
      owner: selectedOwner || undefined,
      teamName: selectedTeamName || undefined,
      reviewerAlias: selectedReviewerAlias || undefined,
      detailStage: selectedDetailStage || undefined,
      detailRisk: requestedDetailRisk || undefined,
      detailErrorType: requestedDetailErrorType || undefined,
      detailReviewerAlias: selectedDetailReviewerAlias || undefined,
      detailPage: detailPage - 1,
    })
    : "";
  const detailNextHref = detailHasMore
    ? buildNewcomerPageHref({
      batchNames: selectedBatchNames,
      owner: selectedOwner || undefined,
      teamName: selectedTeamName || undefined,
      reviewerAlias: selectedReviewerAlias || undefined,
      detailStage: selectedDetailStage || undefined,
      detailRisk: requestedDetailRisk || undefined,
      detailErrorType: requestedDetailErrorType || undefined,
      detailReviewerAlias: selectedDetailReviewerAlias || undefined,
      detailPage: detailPage + 1,
    })
    : "";

  const totalGapRisk = batchCompareRows.filter((row) => toNumber(row.sample_gap_pct) >= 2.5).length;
  const totalPersonQa = personCombinedRows.reduce((sum, row) => sum + toNumber(row.qa_cnt), 0);
  const selectedScopePeople = selectedBatchRows.reduce((sum, row) => sum + toNumber(row.total_cnt), 0);

  const errors = [
    summaryResult.error,
    membersResult.error,
    qaDailyResult.error,
    aggregateResult.error,
    errorSummaryResult.error,
    formalDailyResult.error,
    personDetailResult.error,
    trainingDailyMarkdownResult.error,
    errorDetailsResult.error,
  ].filter(Boolean);

  return (
    <AppShell
      currentPath="/newcomers"
      title="新人追踪"
      subtitle="按批次、阶段、个人查看新人培训表现与风险评估"
    >
      {errors.length > 0 ? <div className="error-banner">接口异常：{errors.join("；")}</div> : null}

      <div className="grid grid-4">
        <SummaryCard label="新人总人数" value={toInteger(metrics.total_people)} hint="所有已映射到批次的新人数。" />
        <SummaryCard label="批次数" value={toInteger(metrics.total_batches)} hint="当前新人批次覆盖数量。" />
        <SummaryCard label="当前选择" value={selectedBatchNames.length} hint={`当前批次：${selectedBatchLabel}`} />
        <SummaryCard label="未匹配记录" value={toInteger(metrics.unmatched_rows)} hint="说明还有新人样本没成功挂到批次。" tone="warning" />
      </div>

      <CollapsiblePanel
        title="批次与个人筛选"
        subtitle="支持批次 + Owner + 基地联动筛选；展开调整追踪范围。"
        defaultOpen={false}
        summary={
          <span>
            当前批次：{selectedBatchLabel} {selectedOwner ? `· Owner: ${selectedOwner}` : ""} {selectedTeamName ? `· 基地: ${selectedTeamName}` : ""} {selectedReviewerAlias ? `· 追踪: ${selectedReviewerAlias}` : ""}
          </span>
        }
      >
        <form className="section-stack">
          {selectedDetailStage ? <input type="hidden" name="detail_stage" value={selectedDetailStage} /> : null}
          {requestedDetailRisk ? <input type="hidden" name="detail_risk" value={requestedDetailRisk} /> : null}
          {requestedDetailErrorType ? <input type="hidden" name="detail_error_type" value={requestedDetailErrorType} /> : null}
          {selectedDetailReviewerAlias ? <input type="hidden" name="detail_reviewer_alias" value={selectedDetailReviewerAlias} /> : null}
          <input type="hidden" name="detail_page" value="1" />
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="batch_names">批次（可多选）</label>
              <select id="batch_names" name="batch_names" className="select" defaultValue={selectedBatchNames} multiple style={{ minHeight: 180 }}>
                {batches.map((batch, index) => {
                  const value = pickText(batch.batch_name, "");
                  return value ? <option key={`${value}-${index}`} value={value}>{value}</option> : null;
                })}
              </select>
            </div>
            <div className="section-stack">
              <div className="form-field">
                <label htmlFor="owner">质培 Owner</label>
                <select id="owner" name="owner" className="select" defaultValue={selectedOwner}>
                  <option value="">全部 Owner</option>
                  {ownerOptions.map((owner) => (
                    <option key={owner} value={owner}>{owner}</option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="team_name">基地 / 团队</label>
                <select id="team_name" name="team_name" className="select" defaultValue={selectedTeamName}>
                  <option value="">全部基地 / 团队</option>
                  {teamOptions.map((teamName) => (
                    <option key={teamName} value={teamName}>{teamName}</option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="reviewer_alias">个人追踪对象</label>
                <select id="reviewer_alias" name="reviewer_alias" className="select" defaultValue={selectedReviewerAlias}>
                  {members.map((member, index) => {
                    const alias = pickText(member.reviewer_alias, "");
                    const reviewerName = pickText(member.reviewer_name, alias);
                    const batchName = pickText(member.batch_name, "未分批");
                    const teamName = pickText(member.team_name, "未分组");
                    return alias ? (
                      <option key={`${alias}-${index}`} value={alias}>{`${reviewerName}（${batchName} · ${teamName}）`}</option>
                    ) : null;
                  })}
                </select>
              </div>
            </div>
          </div>
          <div className="form-actions">
            <FilterActionsBar
              submitLabel="更新追踪范围"
              basePath="/newcomers"
              resetQueryString={(() => {
                const keep = new URLSearchParams();
                if (selectedDetailStage) keep.set("detail_stage", selectedDetailStage);
                if (requestedDetailRisk) keep.set("detail_risk", requestedDetailRisk);
                if (requestedDetailErrorType) keep.set("detail_error_type", requestedDetailErrorType);
                if (selectedDetailReviewerAlias) keep.set("detail_reviewer_alias", selectedDetailReviewerAlias);
                return keep.toString();
              })()}
              resettableFieldNames={["batch_names", "owner", "team_name", "reviewer_alias"]}
              extras={(
                <span className="panel-subtitle">
                  多选批次时可按住 Command / Ctrl 继续选择；这里的 Owner / 基地也会同步影响培训日报和错误明细下钻。
                </span>
              )}
            />
          </div>
        </form>
      </CollapsiblePanel>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">业务说明与指标口径</h3>
            <p className="panel-subtitle">页面统一按“标准培训 → 内检 → 外检 → 正式上线”跟踪新人批次；只有出现正式阶段数据且至少有成员转正后，才显示“正式上线”。</p>
          </div>
        </div>
        <div className="grid grid-2">
          <div className="section-stack">
            <div className="info-banner">
              未正式上线前，批次风险统一显示为“试标风险 / 试标关注 / 试标稳定”；正式上线后，才切换为“风险批次 / 关注批次 / 稳定批次”。如果当前还没有可评估样本，则显示“暂未进入评估”。
            </div>
            <ul style={{ margin: 0, paddingLeft: "1.2rem", color: "#475569", lineHeight: 1.75 }}>
              <li>标准培训：已建批次，但还没有任何内检或外检样本。</li>
              <li>内检：已出现 internal 样本，但还没进入外检或正式上线。</li>
              <li>外检：已出现 external 样本，但还没满足正式上线条件。</li>
              <li>正式上线：必须同时满足“存在 formal 数据 + 至少 1 位成员已转正”。</li>
            </ul>
          </div>
          <div className="section-stack">
            <div className="panel-subtitle" style={{ color: "#334155", lineHeight: 1.75 }}>
              红黄绿分档先看是否已有可评估样本，再看近 7 天风险人数、批次样本正确率和团队样本差值：
            </div>
            <ul style={{ margin: 0, paddingLeft: "1.2rem", color: "#475569", lineHeight: 1.75 }}>
              <li>灰色：qa_cnt ≤ 0，当前暂无试标样本，暂未进入评估。</li>
              <li>红色：命中任一条件即触发——近 7 天有 P0、样本正确率 &lt; 95%、团队样本正确率差值 ≥ 4%。</li>
              <li>黄色：未命中红色但命中任一条件——近 7 天有 P1、样本正确率 &lt; 97%、团队样本正确率差值 ≥ 2.5%。</li>
              <li>绿色：红黄条件都未命中。</li>
              <li>P0：近 7 天样本正确率 &lt; 90% 或漏判率 ≥ 2%；P1：近 7 天样本正确率 &lt; 95% 或总问题率 ≥ 2.5%。</li>
              <li><strong>阶段晋级门槛（与风险分档并行）</strong>：内检 → 外检需批次样本正确率 ≥90% 连续 3 天；外检 → 正式上线需 ≥98% 连续 3 天。</li>
            </ul>
          </div>
        </div>
        <div className="grid grid-6">
          <SummaryCard label="暂未进入评估批次" value={pendingEvaluationBatchCount} hint="qa_cnt≤0，当前仍在培训或尚未进入试标。" tone={pendingEvaluationBatchCount > 0 ? "neutral" : "success"} />
          <SummaryCard label="试标期需关注批次" value={trialAttentionBatchCount} hint="未正式上线，但已命中试标风险或试标关注。" tone={trialAttentionBatchCount > 0 ? "warning" : "success"} />
          <SummaryCard label="正式期需关注批次" value={formalAttentionBatchCount} hint="已正式上线，当前命中风险批次或关注批次。" tone={formalAttentionBatchCount > 0 ? "warning" : "success"} />
          <SummaryCard label="P0 触发批次" value={p0TriggeredBatchCount} hint="近 7 天批次内至少出现 1 位 P0 同学。" tone={p0TriggeredBatchCount > 0 ? "danger" : "success"} />
          <SummaryCard label="可晋级批次" value={canPromoteBatchCount} hint="已连续达成目标正确率和天数，可推进下一阶段。" tone={canPromoteBatchCount > 0 ? "success" : "neutral"} />
          <SummaryCard label="晋级中批次" value={notReadyBatchCount} hint="已在试标但还未连续达标，继续跟进即可。" tone={notReadyBatchCount > 0 ? "neutral" : "success"} />
        </div>
      </section>

      <div className="grid grid-4">
        <SummaryCard label="当前批次人数" value={toInteger(selectedScopePeople)} hint={`范围：${selectedBatchLabel}${selectedOwner ? ` · Owner ${selectedOwner}` : ""}${selectedTeamName ? ` · ${selectedTeamName}` : ""}`} />
        <SummaryCard label="当前质检量" value={toInteger(selectedDualStats.qa_cnt)} hint="合并了新人培训期与正式期聚合。" />
        <SummaryCard label="聚合样本正确率" value={toPercent(selectedDualStats.sample_accuracy)} hint="按质检量加权后的整体正确率。" />
        <SummaryCard label="聚合人均正确率" value={toPercent(selectedDualStats.per_capita_accuracy)} hint="先算每名审核人的正确率，再做平均。" />
        <SummaryCard label="口径差值" value={formatSignedPercent(selectedDualStats.accuracy_gap)} hint="样本口径减去人均口径，越大越说明结构差异更明显。" tone={toNumber(selectedDualStats.accuracy_gap) >= 1 ? "warning" : "neutral"} />
        <SummaryCard label="差异关注批次" value={toInteger(totalGapRisk)} hint="样本口径基地差值 ≥ 2.5% 的批次数。" tone={totalGapRisk > 0 ? "warning" : "neutral"} />
      </div>

      <div className="grid grid-3">
        {[
          ["internal", "🏫 内检样本正确率"],
          ["external", "🔍 外检样本正确率"],
          ["formal", "✅ 正式样本正确率"],
        ].map(([stageKey, label]) => {
          const stageRow = stageCardLookup.get(stageKey) || {};
          return (
            <SummaryCard
              key={stageKey}
              label={label}
              value={toPercent(getSampleAccuracy(stageRow))}
              hint={`人均 ${toPercent(stageRow.per_capita_accuracy)} · 口径差值 ${formatSignedPercent(stageRow.accuracy_gap)}`}
            />
          );
        })}
      </div>

      <div className="grid grid-2">
        <LineChartCard
          title={`培训期双口径走势 · ${selectedBatchLabel}`}
          subtitle="聚合层把培训期样本正确率和人均正确率并排看，更容易识别是否被高样本人力拉高。"
          points={trainingDualTrend}
          primaryLabel="样本正确率"
          secondaryLabel="人均正确率"
        />
        <LineChartCard
          title={`正式期双口径走势 · ${selectedBatchLabel}`}
          subtitle="正式期继续沿用双口径，看转正后整体质量和队伍稳定性是否一致。"
          points={formalDualTrend}
          primaryLabel="样本正确率"
          secondaryLabel="人均正确率"
        />
      </div>

      <DataTable
        title="阶段双口径摘要"
        subtitle="这里把内检、外检、正式三段统一到同一张表里，避免页面只剩单一平均正确率。"
        rows={buildTableRows(stageSummaryRows, {
          member_cnt: (row) => toInteger(row.member_cnt),
          qa_cnt: (row) => toInteger(row.qa_cnt),
          sample_accuracy: (row) => toPercent(row.sample_accuracy),
          per_capita_accuracy: (row) => toPercent(row.per_capita_accuracy),
          accuracy_gap: (row) => formatSignedPercent(row.accuracy_gap),
          issue_rate: (row) => toPercent(row.issue_rate),
        })}
        columns={[
          { key: "stage_label", label: "阶段" },
          { key: "member_cnt", label: "人数" },
          { key: "qa_cnt", label: "质检量" },
          { key: "sample_accuracy", label: "样本正确率" },
          { key: "per_capita_accuracy", label: "人均正确率" },
          { key: "accuracy_gap", label: "口径差值" },
          { key: "issue_rate", label: "总问题率" },
        ]}
        emptyText="当前范围内暂无阶段双口径数据。"
      />

      <div className="grid grid-2">
        <BarListCard
          title="团队人数分布"
          subtitle="看当前范围内的人力是集中在少数团队，还是整体铺开。"
          items={teamDistribution}
        />
        <BarListCard
          title="批次差异榜"
          subtitle="按样本口径基地差值排序，同时补上人均差值，避免只看一条线就下判断。"
          items={gapLeaderboard}
          suffix="%"
        />
      </div>

      {priorityBatchRows.length > 0 ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">优先处理批次</h3>
              <p className="panel-subtitle">默认按红色 → 黄色 → 暂未进入评估 → 绿色排序；同档内再按 P0/P1、团队样本差值和样本正确率继续排，先把最该看的批次顶出来。</p>
            </div>
          </div>
          <div className="comparison-card-list">
            {priorityBatchRows.map((row, index) => {
              const batchName = pickText(row.batch_name, `批次 ${index + 1}`);
              const riskTone = getBatchRiskTone(row.risk_label);
              const riskLabel = pickText(row.risk_label, "—");
              const stageLabel = formatBatchStageLabel(row.current_stage_label, row.current_stage);
              const stageColor = pickText(row.current_stage_color, "#4338ca");
              const stageBg = pickText(row.current_stage_bg, "#eef2ff");
              const promoLabel = pickText(row.promotion_label, "");
              const promoSummary = pickText(row.promotion_summary, "");
              const detailHref = buildBatchOverviewHref({
                row,
                owner: selectedOwner || undefined,
                teamName: selectedTeamName || undefined,
              });
              return (
                <article key={`${batchName}-${index}`} className={`comparison-card ${riskTone}`}>
                  <div className="focus-candidate-title-row">
                    <div className="comparison-card-title">{batchName}</div>
                    <span className={`status-pill ${riskTone}`}>{riskLabel}</span>
                    <span className="status-pill stage" style={{ background: stageBg, color: stageColor, borderColor: stageColor }}>{stageLabel}</span>
                  </div>
                  <div className="comparison-card-summary">{pickText(row.risk_reason, "当前暂无额外说明")}</div>
                  <div className="kpi-row">
                    <span className="kpi-pill">P0 {toInteger(row.p0_cnt)} / P1 {toInteger(row.p1_cnt)}</span>
                    <span className="kpi-pill">样本 {toPercent(row.sample_accuracy)}</span>
                    <span className="kpi-pill">人均 {toPercent(row.per_capita_accuracy)}</span>
                    <span className="kpi-pill">团队差值 {toPercent(row.sample_gap_pct)}</span>
                  </div>
                  {promoLabel ? (
                    <div style={{ marginTop: 8, padding: "6px 10px", background: "#f0f9ff", borderRadius: 6, borderLeft: `3px solid ${pickText(row.promotion_color, "#3b82f6")}` }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{promoLabel}</div>
                      <div style={{ fontSize: 12, color: "#475569", marginTop: 2 }}>{promoSummary}</div>
                      {pickText(row.block_reason, "") ? (
                        <div style={{ fontSize: 11.5, color: "#94a3b8", marginTop: 3 }}>阻塞：{pickText(row.block_reason, "")}</div>
                      ) : null}
                    </div>
                  ) : null}
                  <div className="comparison-card-summary">优先关注：{pickText(row.focus_people, "暂无")}</div>
                  <div className="table-action-row">
                    <a className="link-button" href={detailHref}>打开该批次详情</a>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      <DataTable
        title="批次阶段与风险总览"
        subtitle="这张表已经按优先级排好：先看当前阶段，再看风险命名、触发原因、近 7 天 P0/P1 和团队差值；每行都能直接打开该批次详情筛选。"
        rows={buildTableRows(sortedBatchWatchRows, {
          batch_name: (row) => {
            const detailHref = buildBatchOverviewHref({
              row,
              owner: selectedOwner || undefined,
              teamName: selectedTeamName || undefined,
            });
            return (
              <div className="table-cell-stack">
                <div style={{ fontWeight: 700, color: "#0f172a" }}>{pickText(row.batch_name, "—")}</div>
                <div className="table-meta">质检量 {toInteger(row.qa_cnt)} · 覆盖 {toInteger(row.member_cnt || row.total_cnt)} 人</div>
                <a className="table-link" href={detailHref}>打开该批次详情</a>
              </div>
            );
          },
          current_stage_label: (row) => (
            <div className="table-cell-stack">
              <span
                className="status-pill stage"
                style={{
                  background: pickText(row.current_stage_bg, "#eef2ff"),
                  color: pickText(row.current_stage_color, "#4338ca"),
                  borderColor: pickText(row.current_stage_color, "#4338ca"),
                }}
              >
                {formatBatchStageLabel(row.current_stage_label, row.current_stage)}
              </span>
              <div className="table-meta">成长进度 {toInteger(row.stage_progress)}%</div>
            </div>
          ),
          risk_label: (row) => {
            const tone = getBatchRiskTone(row.risk_label);
            return (
              <div className="table-cell-stack">
                <span className={`status-pill ${tone}`}>{pickText(row.risk_label, "—")}</span>
                <div className="table-meta">P0 {toInteger(row.p0_cnt)} · P1 {toInteger(row.p1_cnt)}</div>
              </div>
            );
          },
          risk_reason: (row) => (
            <div className="table-cell-stack">
              <div className="table-detail-text">{pickText(row.risk_reason, "—")}</div>
              <div className="table-meta">优先关注：{pickText(row.focus_people, "暂无")}</div>
            </div>
          ),
          promotion_label: (row) => {
            const pl = pickText(row.promotion_label, "");
            const ps = pickText(row.promotion_summary, "");
            const br = pickText(row.block_reason, "");
            if (!pl) {
              return <span style={{ color: "#94a3b8" }}>—</span>;
            }
            return (
              <div className="table-cell-stack">
                <span
                  className="status-pill"
                  style={{
                    background: pickText(row.promotion_color, "") === "#10b981" ? "#ecfdf5"
                      : pickText(row.promotion_color, "") === "#059669" ? "#f0fdf4"
                        : pickText(row.promotion_color, "") === "#dc2626" ? "#fef2f2"
                          : "#eff6ff",
                    color: pickText(row.promotion_color, "#3b82f6"),
                    borderColor: pickText(row.promotion_color, "#3b82f6"),
                  }}
                >
                  {pl}
                </span>
                {ps ? <div className="table-meta">{ps}</div> : null}
                {br ? <div className="table-meta" style={{ color: "#94a3b8" }}>阻塞：{br}</div> : null}
              </div>
            );
          },
          sample_accuracy: (row) => (
            <div className="table-cell-stack">
              <div className="table-detail-text">样本 {toPercent(row.sample_accuracy)}</div>
              <div className="table-meta">人均 {toPercent(row.per_capita_accuracy)} · 口径差值 {formatSignedPercent(row.accuracy_gap)}</div>
            </div>
          ),
          sample_gap_pct: (row) => (
            <div className="table-cell-stack">
              <div className="table-detail-text">样本 {toPercent(row.sample_gap_pct)}</div>
              <div className="table-meta">人均 {toPercent(row.per_capita_gap_pct)} · {pickText(row.best_team_name, "—")} vs {pickText(row.worst_team_name, "—")}</div>
            </div>
          ),
        })}
        columns={[
          { key: "batch_name", label: "批次" },
          { key: "current_stage_label", label: "当前阶段" },
          { key: "risk_label", label: "风险标签" },
          { key: "risk_reason", label: "命中原因" },
          { key: "promotion_label", label: "阶段晋级" },
          { key: "sample_accuracy", label: "双口径" },
          { key: "sample_gap_pct", label: "团队差值" },
        ]}
        emptyText="当前范围内暂无批次阶段与风险数据。"
      />

      <DataTable
        title="批次对比总览"
        subtitle="批次规模、样本正确率、人均正确率、口径差值和基地差值一起看，才不会被单一均值带偏。点击表头可按该列排序。"
        rows={buildTableRows(batchCompareRows, {
          training_days: (row) => toInteger(row.training_days),
          total_cnt: (row) => toInteger(row.total_cnt),
          qa_cnt: (row) => toInteger(row.qa_cnt),
          sample_accuracy: (row) => toPercent(row.sample_accuracy),
          per_capita_accuracy: (row) => toPercent(row.per_capita_accuracy),
          accuracy_gap: (row) => formatSignedPercent(row.accuracy_gap),
          sample_gap_pct: (row) => toPercent(row.sample_gap_pct),
          per_capita_gap_pct: (row) => toPercent(row.per_capita_gap_pct),
          issue_rate: (row) => toPercent(row.issue_rate),
        })}
        columns={[
          { key: "batch_name", label: "批次" },
          { key: "join_date", label: "入职日期" },
          { key: "training_days", label: "入职天数", sortable: true },
          { key: "total_cnt", label: "人数", sortable: true },
          { key: "qa_cnt", label: "质检量", sortable: true },
          { key: "sample_accuracy", label: "样本正确率", sortable: true },
          { key: "per_capita_accuracy", label: "人均正确率", sortable: true },
          { key: "accuracy_gap", label: "口径差值", sortable: true },
          { key: "sample_gap_pct", label: "样本口径基地差值", sortable: true },
          { key: "per_capita_gap_pct", label: "人均口径基地差值", sortable: true },
          { key: "issue_rate", label: "问题率", sortable: true },
          { key: "best_team_name", label: "最好基地" },
          { key: "worst_team_name", label: "待关注基地" },
          { key: "owners", label: "Owner" },
        ]}
        emptyText="当前范围内暂无批次对比数据。"
      />

      <div className="grid grid-2">
        <DataTable
          title={`成员清单 · ${selectedBatchLabel}`}
          subtitle="保留成员链路，便于继续往导师、Owner、基地管理动作下钻。"
          rows={buildTableRows(members.slice(0, 30), {
            status: (row) => formatMemberStatus(row.status),
          })}
          columns={[
            { key: "batch_name", label: "批次" },
            { key: "reviewer_name", label: "姓名" },
            { key: "reviewer_alias", label: "审核别名" },
            { key: "team_name", label: "团队" },
            { key: "team_leader", label: "联营管理" },
            { key: "delivery_pm", label: "交付PM" },
            { key: "owner", label: "质培Owner" },
            { key: "status", label: "状态" },
          ]}
          emptyText="当前范围内暂无成员数据。"
        />
        <DataTable
          title={`高频错误汇总 · ${selectedBatchLabel}`}
          subtitle="点击表头可排序。错误类型不只按团队看，也能跨批次一起看结构问题。"
          rows={buildTableRows(errorSummary.slice(0, 20), {
            error_cnt: (row) => toInteger(row.error_cnt),
          })}
          columns={[
            { key: "batch_name", label: "批次" },
            { key: "team_name", label: "团队" },
            { key: "team_leader", label: "联营管理" },
            { key: "owner_name", label: "Owner" },
            { key: "error_type", label: "错误类型" },
            { key: "error_cnt", label: "错误量", sortable: true },
          ]}
          emptyText="当前范围内暂无错误汇总。"
        />
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">培训日报预览与错误下钻</h3>
            <p className="panel-subtitle">这一块直接接了 training-daily markdown 与 error-details。现在在 Next 页也能看日报预览、培训重点和分页错误明细，不用只靠 Streamlit 页面兜底。</p>
          </div>
        </div>
        <div className="section-stack">
          <div className="kpi-row">
            <span className="kpi-pill">当前范围：{selectedBatchLabel}</span>
            {selectedOwner ? <span className="kpi-pill">Owner：{selectedOwner}</span> : null}
            {selectedTeamName ? <span className="kpi-pill">基地：{selectedTeamName}</span> : null}
            {selectedDetailStage ? <span className="kpi-pill">阶段：{formatStageLabel(selectedDetailStage)}</span> : null}
            {requestedDetailRisk ? <span className="kpi-pill">风险：{requestedDetailRisk}</span> : null}
            {requestedDetailErrorType ? <span className="kpi-pill">错误类型：{requestedDetailErrorType}</span> : null}
            {selectedDetailReviewerName ? <span className="kpi-pill">关注人：{selectedDetailReviewerName}</span> : null}
          </div>

          {!trainingDailyHasData ? (
            <div className="info-banner">
              当前范围暂无新人培训日报数据。若像 0408 这种还在标准培训阶段、已建映射但还没出现内检/外检样本，这里会正常返回空态，不再误报异常。
            </div>
          ) : null}

          <form className="section-stack">
            {selectedBatchNames.map((batchName) => (
              <input key={`detail-batch-${batchName}`} type="hidden" name="batch_names" value={batchName} />
            ))}
            {selectedOwner ? <input type="hidden" name="owner" value={selectedOwner} /> : null}
            {selectedTeamName ? <input type="hidden" name="team_name" value={selectedTeamName} /> : null}
            {selectedReviewerAlias ? <input type="hidden" name="reviewer_alias" value={selectedReviewerAlias} /> : null}
            <input type="hidden" name="detail_page" value="1" />
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="detail_stage">错误明细阶段</label>
                <select id="detail_stage" name="detail_stage" className="select" defaultValue={selectedDetailStage}>
                  <option value="">全部阶段</option>
                  <option value="internal">🏫 内检</option>
                  <option value="external">🔍 外检</option>
                  <option value="formal">✅ 正式上线</option>
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="detail_risk">风险等级</label>
                <select id="detail_risk" name="detail_risk" className="select" defaultValue={requestedDetailRisk}>
                  <option value="">全部风险等级</option>
                  {detailRiskOptions.map((risk) => (
                    <option key={risk} value={risk}>{risk}</option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="detail_error_type">错误类型</label>
                <select id="detail_error_type" name="detail_error_type" className="select" defaultValue={requestedDetailErrorType}>
                  <option value="">全部错误类型</option>
                  {detailErrorTypeOptions.map((errorType) => (
                    <option key={errorType} value={errorType}>{errorType}</option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="detail_reviewer_alias">关注人</label>
                <select id="detail_reviewer_alias" name="detail_reviewer_alias" className="select" defaultValue={selectedDetailReviewerAlias}>
                  <option value="">全部关注人</option>
                  {detailReviewerOptions.map((option) => (
                    <option key={option.key} value={option.alias}>{option.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-actions">
              <FilterActionsBar
                submitLabel="更新日报与错误明细"
                basePath="/newcomers"
                resetQueryString={(() => {
                  const keep = new URLSearchParams();
                  selectedBatchNames.forEach((batchName) => keep.append("batch_names", batchName));
                  if (selectedOwner) keep.set("owner", selectedOwner);
                  if (selectedTeamName) keep.set("team_name", selectedTeamName);
                  if (selectedReviewerAlias) keep.set("reviewer_alias", selectedReviewerAlias);
                  return keep.toString();
                })()}
                resettableFieldNames={["detail_stage", "detail_risk", "detail_error_type", "detail_reviewer_alias"]}
                extras={(
                  <>
                    <a
                      className="link-button"
                      href={shareDetailHref}
                      title={`短链分享（当前筛选已压到 ?${COMPACT_QUERY_KEY}=）。长链：${currentDetailHref}`}
                    >
                      打开当前页分享视角
                    </a>
                    {externalDetailUrl ? <a className="link-button" href={externalDetailUrl} target="_blank" rel="noreferrer">打开外部详情页</a> : null}
                  </>
                )}
              />
            </div>
            {legacyExternalDetailUrl ? (
              <div className="panel-subtitle">如果外部系统还没兼容短链接参数，可继续用旧链接：{legacyExternalDetailUrl}</div>
            ) : null}
          </form>

          <div className="grid grid-4">
            <SummaryCard label="数据可靠性" value={formatReliabilityLabel(trainingDailyReliability.status)} hint={(trainingDailyReliability.issues as string[] | undefined)?.slice(0, 2).join("；") || "当前范围下暂无额外可靠性告警。"} tone={pickText(trainingDailyReliability.status, "ok") === "error" ? "danger" : (pickText(trainingDailyReliability.status, "ok") === "warn" ? "warning" : "success")} />
            <SummaryCard label="培训重点" value={toInteger(trainingFocusRows.length)} hint="training-daily 已返回可直接对外展示的培训专题。" />
            <SummaryCard label="错误样例预览" value={toInteger(errorSamplePreviewRows.length)} hint="用于日报正文和下钻表之间快速对照。" />
            <SummaryCard label="P0 / P1 关注人" value={toInteger(recentRiskRows.length)} hint="最近 7 天风险人力数，便于对日报关注名单和明细下钻做交叉核对。" tone={recentRiskRows.length > 0 ? "warning" : "success"} />
          </div>

          <div className="grid grid-2">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h3 className="panel-title">日报 Markdown 预览</h3>
                  <p className="panel-subtitle">现在 Next 页也会直接渲染 training-daily 的 markdown 文本，方便对照企微推送内容和页面字段；日报里也会固定说明“未正式上线批次统一按试标口径展示风险”。</p>
                </div>
              </div>
              <textarea className="textarea" readOnly value={trainingDailyMarkdown || "当前暂无可预览的培训日报内容。"} style={{ minHeight: 320 }} />
            </section>
            <TrainingDailySendPanel
              batchNames={selectedBatchNames}
              owner={selectedOwner || undefined}
              teamName={selectedTeamName || undefined}
              detailStage={selectedDetailStage || undefined}
              detailRiskLevel={requestedDetailRisk || undefined}
              detailErrorType={requestedDetailErrorType || undefined}
              detailReviewerAlias={selectedDetailReviewerAlias || undefined}
              detailReviewerName={selectedDetailReviewerName || undefined}
              markdown={trainingDailyMarkdown}
              asOfDate={trainingDailyAsOfDate || undefined}
              hasData={trainingDailyHasData}
              reliabilityLabel={`${formatReliabilityLabel(trainingDailyReliability.status)} · 映射人数 ${toInteger((trainingDailyReliability.metrics as Record<string, unknown> | undefined)?.member_cnt)} · 培训样本行 ${toInteger((trainingDailyReliability.metrics as Record<string, unknown> | undefined)?.training_row_cnt)}`}
              reliabilityIssues={trainingDailyReliabilityIssues}
              currentDetailHref={currentDetailHref}
              recommendedDetailUrl={externalDetailUrl || undefined}
              legacyDetailUrl={legacyExternalDetailUrl || undefined}
            />
          </div>
        </div>
      </section>

      <div className="grid grid-2">
        <DataTable
          title="培训重点"
          subtitle="点击表头可排序。training-daily 返回的培训专题、风险等级和建议动作，便于直接对照日报正文。"
          rows={buildTableRows(trainingFocusRows, {
            qa_cnt: (row) => toInteger(row.qa_cnt),
            error_cnt: (row) => toInteger(row.error_cnt),
            sample_accuracy: (row) => toPercent(row.sample_accuracy),
          })}
          columns={[
            { key: "stage_label", label: "阶段" },
            { key: "training_topic", label: "培训专题" },
            { key: "risk_level", label: "风险等级" },
            { key: "content_type", label: "内容类型" },
            { key: "qa_cnt", label: "样本量", sortable: true },
            { key: "error_cnt", label: "错误量", sortable: true },
            { key: "sample_accuracy", label: "样本正确率", sortable: true },
            { key: "focus_reason", label: "建议动作" },
          ]}
          emptyText="当前范围内暂无可直接归纳的培训重点。"
        />
        <DataTable
          title="错误样例预览"
          subtitle="点击表头可排序。把 error-details 的最小字段集先在首页预览，方便和日报里的样例摘要逐条核对。"
          rows={buildTableRows(errorSamplePreviewRows, {
            biz_date: (row) => toDateInputValue(row.biz_date as string | undefined),
          })}
          columns={[
            { key: "biz_date", label: "日期", sortable: true },
            { key: "short_name", label: "姓名" },
            { key: "batch_name", label: "批次" },
            { key: "stage_label", label: "阶段" },
            { key: "risk_level", label: "风险等级" },
            { key: "error_type", label: "错误类型" },
            { key: "content_snippet", label: "内容摘要" },
            { key: "qa_note", label: "备注" },
          ]}
          emptyText="当前范围内暂无错误样例预览。"
        />
      </div>

      <DataTable
        title="培训错误明细下钻"
        subtitle="点击表头可排序。这里已经接到 error-details 分页接口，支持按阶段、风险、错误类型、关注人继续下钻，不再只看固定截断样本。"
        rows={buildTableRows(detailRows, {
          biz_date: (row) => toDateInputValue(row.biz_date as string | undefined),
        })}
        columns={[
          { key: "biz_date", label: "日期", sortable: true },
          { key: "stage", label: "阶段" },
          { key: "short_name", label: "姓名" },
          { key: "batch_name", label: "批次" },
          { key: "team_name", label: "基地 / 团队" },
          { key: "risk_level", label: "风险等级" },
          { key: "error_type", label: "错误类型" },
          { key: "content_snippet", label: "内容摘要" },
          { key: "qa_note", label: "备注" },
        ]}
        emptyText="当前筛选条件下暂无可下钻的培训错误明细。"
      />

      <div className="form-actions">
        <span className="panel-subtitle">当前第 {detailPage} 页 · 每页 {detailLimit} 条 · {detailHasMore ? "后面还有更多明细" : "已到当前查询结果末尾"}</span>
        {detailPrevHref ? <a className="link-button" href={detailPrevHref}>上一页</a> : null}
        {detailNextHref ? <a className="link-button primary" href={detailNextHref}>下一页</a> : null}
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">个人追踪</h3>
            <p className="panel-subtitle">个人页继续只看单人样本正确率、阶段跃迁和近期错误明细，不展示聚合层的人均正确率。</p>
          </div>
        </div>
        {selectedPersonInfo ? (
          <div className="section-stack">
            <div className="grid grid-4">
              <SummaryCard label="追踪对象" value={pickText(selectedPersonInfo.reviewer_name, selectedReviewerAlias)} hint={`${pickText(selectedPersonInfo.batch_name, "未分批")} · ${pickText(selectedPersonInfo.team_name, "未分组")}`} />
              <SummaryCard label="累计质检量" value={toInteger(totalPersonQa)} hint="合并培训期和正式期。" />
              <SummaryCard label="阶段数量" value={toInteger(personStageRows.length)} hint="内检 / 外检 / 正式期覆盖数。" />
              <SummaryCard label="近期错误数" value={toInteger(personErrorRows.length)} hint="最近 80 条新人质检明细里的错误样本。" tone={personErrorRows.length > 0 ? "warning" : "success"} />
            </div>

            <div className="grid grid-2">
              <LineChartCard
                title={`个人培训期走势 · ${pickText(selectedPersonInfo.reviewer_name, selectedReviewerAlias)}`}
                subtitle="这里只看单人样本正确率，用来判断内检到外检的训练效果是否稳定。"
                points={personStageTrend}
                primaryLabel="单人样本正确率"
              />
              <LineChartCard
                title={`个人全阶段走势 · ${pickText(selectedPersonInfo.reviewer_name, selectedReviewerAlias)}`}
                subtitle="把培训期和正式期接到一条时间线上，继续只看单人样本正确率。"
                points={personTrainingFormalTrend}
                primaryLabel="单人样本正确率"
              />
            </div>

            <DataTable
              title="个人阶段摘要"
              subtitle="个人层只展示单人样本正确率，不展示聚合口径的人均正确率。"
              rows={buildTableRows(personStageRows, {
                qa_cnt: (row) => toInteger(row.qa_cnt),
                accuracy_rate: (row) => toPercent(row.accuracy_rate),
                misjudge_rate: (row) => toPercent(row.misjudge_rate),
                missjudge_rate: (row) => toPercent(row.missjudge_rate),
              })}
              columns={[
                { key: "stage_label", label: "阶段" },
                { key: "qa_cnt", label: "质检量" },
                { key: "accuracy_rate", label: "样本正确率" },
                { key: "misjudge_rate", label: "错判率" },
                { key: "missjudge_rate", label: "漏判率" },
              ]}
              emptyText="当前追踪对象暂无阶段汇总。"
            />

            <DataTable
              title="近期错误明细"
              subtitle="直接看最近出错样本、问题标签和备注，方便快速判断当前训练重点。"
              rows={buildTableRows(personErrorRows, {
                biz_date: (row) => toDateInputValue(row.biz_date as string | undefined),
                stage: (row) => formatStageLabel(row.stage),
              })}
              columns={[
                { key: "biz_date", label: "日期" },
                { key: "stage", label: "阶段" },
                { key: "queue_name", label: "队列" },
                { key: "content_type", label: "内容类型" },
                { key: "training_topic", label: "培训专题" },
                { key: "risk_level", label: "风险等级" },
                { key: "raw_judgement", label: "一审结果" },
                { key: "final_judgement", label: "质检结果" },
                { key: "error_type", label: "错误类型" },
                { key: "qa_note", label: "质检备注" },
              ]}
              emptyText="当前追踪对象暂无错误明细。"
            />
          </div>
        ) : (
          <div className="empty-state">当前筛选范围内还没有可追踪的新人。</div>
        )}
      </section>
    </AppShell>
  );
}
