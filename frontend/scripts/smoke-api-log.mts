#!/usr/bin/env node
// 冒烟 src/lib/api.ts 的日志 / rid / ApiError 行为
// 用法：node --experimental-strip-types scripts/smoke-api-log.mts
// Node 22+ 内置 strip-types，不需要 tsx

// ---- 场景 1：成功 GET（快） ----
async function scenarioFastSuccess(api: any) {
  console.log("\n=== 场景 1: 成功 GET（快，预期 info/绿色） ===");
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ ok: true, data: { hello: "world" } }), {
      status: 200,
      headers: { "X-Request-Id": "rid-fast-001", "Content-Type": "application/json" },
    })) as any;
  const data = await api.requestApi("/api/v1/ping");
  console.log("→ 返回:", data);
}

// ---- 场景 2：慢请求（> 阈值） ----
async function scenarioSlow(api: any) {
  console.log("\n=== 场景 2: 慢请求（>800ms，预期 warn） ===");
  globalThis.fetch = (async () => {
    await new Promise((r) => setTimeout(r, 900));
    return new Response(JSON.stringify({ ok: true, data: { latency: "slow" } }), {
      status: 200,
      headers: { "X-Request-Id": "rid-slow-002" },
    });
  }) as any;
  await api.requestApi("/api/v1/dashboard/summary");
}

// ---- 场景 3：4xx（带后端错误体 + 脱敏） ----
async function scenarioBadRequest(api: any) {
  console.log("\n=== 场景 3: 4xx + 后端错误体（预期 warn，body 脱敏，错误文案含「缺少必填参数」） ===");
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({ ok: false, error: "缺少必填参数: alert_id", request_id: "rid-bad-003" }),
      {
        status: 400,
        statusText: "Bad Request",
        headers: { "X-Request-Id": "rid-bad-003", "Content-Type": "application/json" },
      },
    )) as any;
  const res = await api.safeRequestApi("/api/v1/alerts/ack", {
    method: "POST",
    body: { token: "SECRET_TOKEN_SHOULD_BE_MASKED", comment: "test" },
  });
  console.log("→ safeRequestApi 返回:", res);
}

// ---- 场景 4：网络失败 ----
async function scenarioNetworkFail(api: any) {
  console.log("\n=== 场景 4: 网络失败（预期 error + ApiError.status=0） ===");
  globalThis.fetch = (async () => {
    throw new TypeError("fetch failed: ECONNREFUSED");
  }) as any;
  try {
    await api.requestApi("/api/v1/dashboard/alerts");
  } catch (e: any) {
    console.log(
      "→ 捕获 ApiError: name=",
      e.name,
      "status=",
      e.status,
      "rid=",
      e.requestId,
      "path=",
      e.path,
    );
  }
}

// ---- 场景 5：5xx ----
async function scenario5xx(api: any) {
  console.log("\n=== 场景 5: 500 错误（预期 error） ===");
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ error: "internal" }), {
      status: 500,
      statusText: "Internal Server Error",
      headers: { "X-Request-Id": "rid-500-005" },
    })) as any;
  const res = await api.safeFetchApi("/api/v1/dashboard/kpi");
  console.log("→ safeFetchApi 错误:", res.error);
}

async function main() {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:65535";
  // 强制 DEV 模式输出 info 级
  process.env.NODE_ENV = "development";

  const api = await import("../src/lib/api.ts");
  await scenarioFastSuccess(api);
  await scenarioSlow(api);
  await scenarioBadRequest(api);
  await scenarioNetworkFail(api);
  await scenario5xx(api);

  console.log("\n✅ 冒烟完成——对照 5 段输出人工确认要点:");
  console.log("  1) 场景1 level=info（SSR 环境，纯文本一行）");
  console.log("  2) 场景2 elapsed ≥ 800ms，被判定 warn");
  console.log("  3) 场景3 body=... 里 token 被掩码为 ***，错误文案含「缺少必填参数」，返回含 rid=xxx");
  console.log("  4) 场景4 error=FAILED，ApiError.status=0，rid=-");
  console.log("  5) 场景5 level=error");
}

main().catch((e) => {
  console.error("冒烟脚本异常：", e);
  process.exit(1);
});
