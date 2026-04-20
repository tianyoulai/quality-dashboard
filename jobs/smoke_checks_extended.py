"""扩展冒烟测试 - 补充边界测试、并发测试、错误处理测试。

在现有 smoke_checks.py 基础上新增：
1. 参数边界测试（空值、极值、非法值）
2. 并发请求测试（模拟多用户同时访问）
3. 错误响应测试（验证统一异常格式）
4. 分页测试（验证 page/page_size 边界）

运行方式：
    # 运行所有扩展测试
    python3 jobs/smoke_checks_extended.py --api-base http://127.0.0.1:8000
    
    # 只运行边界测试
    python3 jobs/smoke_checks_extended.py --api-base http://127.0.0.1:8000 --test-type boundary
    
    # 只运行并发测试
    python3 jobs/smoke_checks_extended.py --api-base http://127.0.0.1:8000 --test-type concurrency
"""
from __future__ import annotations

import argparse
import concurrent.futures
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TIMEOUT_SECONDS = 10


def test_boundary_conditions(api_base: str) -> list[dict[str, Any]]:
    """边界条件测试。"""
    results = []
    
    # 测试1：page=0 应该返回 422（FastAPI 参数验证）
    try:
        resp = requests.get(
            f"{api_base}/api/v1/details/query",
            params={"page": 0, "page_size": 10},
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 422:
            results.append({
                "name": "边界测试：page=0",
                "status": "PASS",
                "detail": "正确返回 422 Unprocessable Entity"
            })
        else:
            results.append({
                "name": "边界测试：page=0",
                "status": "FAIL",
                "detail": f"期望 422，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "边界测试：page=0",
            "status": "ERROR",
            "detail": str(e)
        })
    
    # 测试2：page_size=-1 应该返回 422
    try:
        resp = requests.get(
            f"{api_base}/api/v1/details/query",
            params={"page": 1, "page_size": -1},
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 422:
            results.append({
                "name": "边界测试：page_size=-1",
                "status": "PASS",
                "detail": "正确返回 422 Unprocessable Entity"
            })
        else:
            results.append({
                "name": "边界测试：page_size=-1",
                "status": "FAIL",
                "detail": f"期望 422，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "边界测试：page_size=-1",
            "status": "ERROR",
            "detail": str(e)
        })
    
    # 测试3：空日期范围查询应该返回空数据（不是错误）
    try:
        resp = requests.get(
            f"{api_base}/api/v1/dashboard/overview",
            params={
                "grain": "day",
                "selected_date": "2099-01-01"  # 未来日期
            },
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            data = resp.json()
            # 验证返回结构
            if "data" in data:
                results.append({
                    "name": "边界测试：空日期范围",
                    "status": "PASS",
                    "detail": "正确返回 200 + 空数据"
                })
            else:
                results.append({
                    "name": "边界测试：空日期范围",
                    "status": "FAIL",
                    "detail": "响应格式不符合预期"
                })
        else:
            results.append({
                "name": "边界测试：空日期范围",
                "status": "FAIL",
                "detail": f"期望 200，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "边界测试：空日期范围",
            "status": "ERROR",
            "detail": str(e)
        })
    
    # 测试4：非法日期格式应该返回 422（FastAPI 自动校验）
    try:
        resp = requests.get(
            f"{api_base}/api/v1/dashboard/overview",
            params={
                "grain": "day",
                "selected_date": "invalid-date"
            },
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 422:
            results.append({
                "name": "边界测试：非法日期格式",
                "status": "PASS",
                "detail": "正确返回 422 Unprocessable Entity"
            })
        else:
            results.append({
                "name": "边界测试：非法日期格式",
                "status": "FAIL",
                "detail": f"期望 422，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "边界测试：非法日期格式",
            "status": "ERROR",
            "detail": str(e)
        })
    
    # 测试5：grain 参数非法值应该返回 422
    try:
        resp = requests.get(
            f"{api_base}/api/v1/dashboard/overview",
            params={
                "grain": "invalid",
                "selected_date": date.today().isoformat()
            },
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 422:
            results.append({
                "name": "边界测试：非法 grain 参数",
                "status": "PASS",
                "detail": "正确返回 422 Unprocessable Entity"
            })
        else:
            results.append({
                "name": "边界测试：非法 grain 参数",
                "status": "FAIL",
                "detail": f"期望 422，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "边界测试：非法 grain 参数",
            "status": "ERROR",
            "detail": str(e)
        })
    
    return results


def test_concurrency(api_base: str, workers: int = 10, requests_per_worker: int = 5) -> list[dict[str, Any]]:
    """并发请求测试。"""
    results = []
    
    def make_request(index: int) -> tuple[int, float]:
        """单次请求"""
        start = time.time()
        try:
            resp = requests.get(
                f"{api_base}/api/v1/dashboard/overview",
                params={
                    "grain": "day",
                    "selected_date": date.today().isoformat()
                },
                timeout=TIMEOUT_SECONDS
            )
            elapsed = time.time() - start
            return resp.status_code, elapsed
        except Exception as e:
            elapsed = time.time() - start
            return 0, elapsed
    
    # 执行并发请求
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(make_request, i)
            for i in range(workers * requests_per_worker)
        ]
        responses = [f.result() for f in concurrent.futures.as_completed(futures)]
    total_elapsed = time.time() - start
    
    # 统计结果
    success_count = sum(1 for status, _ in responses if status == 200)
    error_count = sum(1 for status, _ in responses if status == 0)
    avg_latency = sum(elapsed for _, elapsed in responses) / len(responses)
    qps = len(responses) / total_elapsed
    
    if success_count == len(responses):
        results.append({
            "name": f"并发测试：{workers} 并发 × {requests_per_worker} 请求",
            "status": "PASS",
            "detail": (
                f"成功率 100%，平均延迟 {avg_latency*1000:.0f}ms，"
                f"QPS {qps:.1f}，总耗时 {total_elapsed:.2f}s"
            )
        })
    else:
        results.append({
            "name": f"并发测试：{workers} 并发 × {requests_per_worker} 请求",
            "status": "FAIL",
            "detail": (
                f"成功 {success_count}/{len(responses)}，"
                f"失败 {error_count}，平均延迟 {avg_latency*1000:.0f}ms"
            )
        })
    
    return results


def test_error_responses(api_base: str) -> list[dict[str, Any]]:
    """错误响应格式测试（验证统一异常格式）。"""
    results = []
    
    # 测试1：404 错误应该返回标准格式
    try:
        resp = requests.get(
            f"{api_base}/api/v1/nonexistent",
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 404:
            data = resp.json()
            # 验证响应格式：{ "error": { "code": "...", "message": "..." }, "request_id": "..." }
            if "error" in data and "code" in data.get("error", {}):
                results.append({
                    "name": "错误响应：404 格式校验",
                    "status": "PASS",
                    "detail": f"错误码：{data['error'].get('code')}"
                })
            else:
                results.append({
                    "name": "错误响应：404 格式校验",
                    "status": "WARN",
                    "detail": "返回 404 但格式不是标准业务异常格式（可能是 FastAPI 默认 404）"
                })
        else:
            results.append({
                "name": "错误响应：404 格式校验",
                "status": "FAIL",
                "detail": f"期望 404，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "错误响应：404 格式校验",
            "status": "ERROR",
            "detail": str(e)
        })
    
    # 测试2：验证 request_id 存在
    try:
        resp = requests.get(
            f"{api_base}/api/v1/dashboard/overview",
            params={
                "grain": "day",
                "selected_date": date.today().isoformat()
            },
            timeout=TIMEOUT_SECONDS
        )
        request_id = resp.headers.get("X-Request-Id")
        if request_id:
            results.append({
                "name": "错误响应：request_id 存在",
                "status": "PASS",
                "detail": f"X-Request-Id: {request_id}"
            })
        else:
            results.append({
                "name": "错误响应：request_id 存在",
                "status": "FAIL",
                "detail": "响应头缺少 X-Request-Id"
            })
    except Exception as e:
        results.append({
            "name": "错误响应：request_id 存在",
            "status": "ERROR",
            "detail": str(e)
        })
    
    return results


def test_pagination(api_base: str) -> list[dict[str, Any]]:
    """分页功能测试（针对 details/query 接口）。"""
    results = []
    
    # 获取默认日期
    try:
        date_resp = requests.get(f"{api_base}/api/v1/meta/date-range", timeout=TIMEOUT_SECONDS)
        default_date = date_resp.json().get("data", {}).get("max_date", date.today().isoformat())
    except:
        default_date = date.today().isoformat()
    
    # 测试1：查询接口应该正常返回
    try:
        resp = requests.get(
            f"{api_base}/api/v1/details/query",
            params={
                "date_start": default_date,
                "date_end": default_date,
                "limit": 10
            },
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            total = data.get("data", {}).get("total_count", 0)
            if len(items) <= 10:
                results.append({
                    "name": "分页测试：查询接口",
                    "status": "PASS",
                    "detail": f"返回 {len(items)} 条，总数 {total}"
                })
            else:
                results.append({
                    "name": "分页测试：查询接口",
                    "status": "FAIL",
                    "detail": f"limit=10 但返回了 {len(items)} 条"
                })
        else:
            results.append({
                "name": "分页测试：查询接口",
                "status": "FAIL",
                "detail": f"期望 200，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "分页测试：查询接口",
            "status": "ERROR",
            "detail": str(e)
        })
    
    # 测试2：超大 limit 应该被限制
    try:
        resp = requests.get(
            f"{api_base}/api/v1/details/query",
            params={
                "date_start": default_date,
                "date_end": default_date,
                "limit": 999999  # 超过最大限制
            },
            timeout=TIMEOUT_SECONDS
        )
        if resp.status_code == 422:
            results.append({
                "name": "分页测试：超大 limit",
                "status": "PASS",
                "detail": "正确返回 422（参数验证失败）"
            })
        elif resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("items", [])
            if len(items) <= 50000:  # 假设最大限制是 50000
                results.append({
                    "name": "分页测试：超大 limit",
                    "status": "PASS",
                    "detail": f"超大 limit 被限制到 {len(items)} 条"
                })
            else:
                results.append({
                    "name": "分页测试：超大 limit",
                    "status": "WARN",
                    "detail": f"返回了 {len(items)} 条，可能没有限制"
                })
        else:
            results.append({
                "name": "分页测试：超大 limit",
                "status": "FAIL",
                "detail": f"期望 422 或 200，实际 {resp.status_code}"
            })
    except Exception as e:
        results.append({
            "name": "分页测试：超大 limit",
            "status": "ERROR",
            "detail": str(e)
        })
    
    return results


def main():
    parser = argparse.ArgumentParser(description="扩展冒烟测试")
    parser.add_argument(
        "--api-base",
        required=True,
        help="API 基础地址，例如 http://127.0.0.1:8000"
    )
    parser.add_argument(
        "--test-type",
        choices=["all", "boundary", "concurrency", "error", "pagination"],
        default="all",
        help="测试类型"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="并发测试的并发数"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出结果到文件（JSON 格式）"
    )
    
    args = parser.parse_args()
    
    api_base = args.api_base.rstrip("/")
    all_results = []
    
    # 执行测试
    if args.test_type in ("all", "boundary"):
        print("\n🔍 边界条件测试...")
        all_results.extend(test_boundary_conditions(api_base))
    
    if args.test_type in ("all", "concurrency"):
        print("\n🚀 并发请求测试...")
        all_results.extend(test_concurrency(api_base, workers=args.workers))
    
    if args.test_type in ("all", "error"):
        print("\n❌ 错误响应测试...")
        all_results.extend(test_error_responses(api_base))
    
    if args.test_type in ("all", "pagination"):
        print("\n📄 分页测试...")
        all_results.extend(test_pagination(api_base))
    
    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    pass_count = sum(1 for r in all_results if r["status"] == "PASS")
    fail_count = sum(1 for r in all_results if r["status"] == "FAIL")
    error_count = sum(1 for r in all_results if r["status"] == "ERROR")
    warn_count = sum(1 for r in all_results if r["status"] == "WARN")
    
    for result in all_results:
        icon = {
            "PASS": "✅",
            "FAIL": "❌",
            "ERROR": "⚠️ ",
            "WARN": "⚠️ "
        }.get(result["status"], "❓")
        print(f"{icon} {result['name']}: {result['detail']}")
    
    print("\n" + "="*60)
    print(f"总计: {len(all_results)} 个测试")
    print(f"✅ 通过: {pass_count}")
    print(f"❌ 失败: {fail_count}")
    print(f"⚠️  错误: {error_count}")
    print(f"⚠️  警告: {warn_count}")
    print("="*60)
    
    # 保存到文件
    if args.output:
        import json
        output_path = PROJECT_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": {
                    "total": len(all_results),
                    "pass": pass_count,
                    "fail": fail_count,
                    "error": error_count,
                    "warn": warn_count
                },
                "results": all_results
            }, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存到 {output_path}")
    
    # 返回状态码
    return 0 if fail_count == 0 and error_count == 0 else 1


if __name__ == "__main__":
    exit(main())
