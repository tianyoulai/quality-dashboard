"""负载测试脚本 - 使用 locust 进行 API 压力测试。

功能：
1. 模拟多用户并发访问
2. 测试核心 API 端点性能
3. 生成性能报告（响应时间、成功率、QPS）

安装依赖：
    pip install locust

运行方式：
    # Web UI 模式（推荐）
    locust -f jobs/load_test.py --host=http://localhost:8000
    # 然后访问 http://localhost:8089 配置用户数和启动测试
    
    # 命令行模式
    locust -f jobs/load_test.py --host=http://localhost:8000 \\
        --users 100 --spawn-rate 10 --run-time 5m --headless
    
    # 生成 HTML 报告
    locust -f jobs/load_test.py --host=http://localhost:8000 \\
        --users 100 --spawn-rate 10 --run-time 5m --headless \\
        --html deliverables/load_test_report.html
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from locust import HttpUser, TaskSet, between, task


class DashboardTaskSet(TaskSet):
    """看板页面任务集"""
    
    def on_start(self):
        """初始化：每个用户开始前执行一次"""
        # 获取可用日期范围
        response = self.client.get("/api/v1/meta/date-range")
        if response.status_code == 200:
            data = response.json().get("data", {})
            self.max_date = data.get("max_date", date.today().isoformat())
            self.min_date = data.get("min_date", (date.today() - timedelta(days=30)).isoformat())
        else:
            self.max_date = date.today().isoformat()
            self.min_date = (date.today() - timedelta(days=30)).isoformat()
    
    @task(10)  # 权重10：最常访问的接口
    def overview_day(self):
        """首页总览（日粒度）"""
        selected_date = self._random_date()
        self.client.get(
            "/api/v1/dashboard/overview",
            params={
                "grain": "day",
                "selected_date": selected_date
            },
            name="/api/v1/dashboard/overview [day]"
        )
    
    @task(3)
    def overview_week(self):
        """首页总览（周粒度）"""
        selected_date = self._random_date()
        self.client.get(
            "/api/v1/dashboard/overview",
            params={
                "grain": "week",
                "selected_date": selected_date
            },
            name="/api/v1/dashboard/overview [week]"
        )
    
    @task(2)
    def overview_month(self):
        """首页总览（月粒度）"""
        selected_date = self._random_date()
        self.client.get(
            "/api/v1/dashboard/overview",
            params={
                "grain": "month",
                "selected_date": selected_date
            },
            name="/api/v1/dashboard/overview [month]"
        )
    
    @task(8)
    def alerts_list(self):
        """告警列表"""
        selected_date = self._random_date()
        self.client.get(
            "/api/v1/dashboard/alerts",
            params={
                "grain": "day",
                "selected_date": selected_date
            },
            name="/api/v1/dashboard/alerts"
        )
    
    @task(5)
    def details_page_1(self):
        """详情列表（第1页）"""
        self.client.get(
            "/api/v1/details/query",
            params={
                "page": 1,
                "page_size": 20
            },
            name="/api/v1/details/query [page=1]"
        )
    
    @task(3)
    def details_page_random(self):
        """详情列表（随机页）"""
        page = random.randint(1, 100)
        self.client.get(
            "/api/v1/details/query",
            params={
                "page": page,
                "page_size": 20
            },
            name="/api/v1/details/query [page=random]"
        )
    
    @task(2)
    def details_export(self):
        """导出详情（小数据量）"""
        selected_date = self._random_date()
        self.client.get(
            "/api/v1/details/export-csv",
            params={
                "biz_date_min": selected_date,
                "biz_date_max": selected_date,
                "limit": 1000
            },
            name="/api/v1/details/export-csv [1k rows]"
        )
    
    @task(4)
    def meta_date_range(self):
        """元数据：日期范围"""
        self.client.get(
            "/api/v1/meta/date-range",
            name="/api/v1/meta/date-range"
        )
    
    @task(3)
    def meta_filters(self):
        """元数据：筛选选项"""
        self.client.get(
            "/api/v1/meta/filters",
            name="/api/v1/meta/filters"
        )
    
    @task(1)
    def health_check(self):
        """健康检查"""
        self.client.get(
            "/api/health",
            name="/api/health"
        )
    
    def _random_date(self) -> str:
        """生成随机日期（最近30天内）"""
        try:
            min_date = date.fromisoformat(self.min_date)
            max_date = date.fromisoformat(self.max_date)
            delta = (max_date - min_date).days
            if delta <= 0:
                return max_date.isoformat()
            random_days = random.randint(0, delta)
            return (min_date + timedelta(days=random_days)).isoformat()
        except Exception:
            return date.today().isoformat()


class InternalTaskSet(TaskSet):
    """内检看板任务集"""
    
    @task(5)
    def internal_summary(self):
        """内检总览"""
        selected_date = date.today().isoformat()
        self.client.get(
            "/api/v1/internal/summary",
            params={"selected_date": selected_date},
            name="/api/v1/internal/summary"
        )
    
    @task(3)
    def internal_queues(self):
        """内检队列明细"""
        selected_date = date.today().isoformat()
        self.client.get(
            "/api/v1/internal/queues",
            params={"selected_date": selected_date},
            name="/api/v1/internal/queues"
        )
    
    @task(2)
    def internal_trend(self):
        """内检趋势"""
        self.client.get(
            "/api/v1/internal/trend",
            params={"days": 7},
            name="/api/v1/internal/trend"
        )


class DashboardUser(HttpUser):
    """看板用户 - 模拟正常浏览行为"""
    tasks = [DashboardTaskSet]
    wait_time = between(1, 5)  # 每次请求之间等待 1-5 秒
    weight = 8  # 80% 的用户访问主看板


class InternalUser(HttpUser):
    """内检用户 - 模拟内检看板访问"""
    tasks = [InternalTaskSet]
    wait_time = between(2, 6)
    weight = 2  # 20% 的用户访问内检看板


# ============================================================
# 自定义事件处理（可选）
# ============================================================

from locust import events

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时触发"""
    print("\n" + "="*60)
    print("🚀 负载测试开始")
    print(f"Target: {environment.host}")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时触发"""
    print("\n" + "="*60)
    print("✅ 负载测试结束")
    print("="*60 + "\n")
    
    # 打印汇总统计
    stats = environment.stats.total
    print(f"📊 统计汇总:")
    print(f"  - 总请求数: {stats.num_requests}")
    print(f"  - 失败数: {stats.num_failures}")
    print(f"  - 成功率: {(1 - stats.fail_ratio) * 100:.2f}%")
    print(f"  - 平均响应时间: {stats.avg_response_time:.0f}ms")
    print(f"  - 中位数响应时间: {stats.median_response_time:.0f}ms")
    print(f"  - 95% 响应时间: {stats.get_response_time_percentile(0.95):.0f}ms")
    print(f"  - QPS: {stats.total_rps:.2f}")
    print()


# ============================================================
# 运行建议
# ============================================================

"""
## 🎯 测试场景建议

### 1. 烟雾测试（快速验证）
```bash
locust -f jobs/load_test.py --host=http://localhost:8000 \\
    --users 10 --spawn-rate 2 --run-time 1m --headless
```

### 2. 正常负载测试
```bash
locust -f jobs/load_test.py --host=http://localhost:8000 \\
    --users 50 --spawn-rate 5 --run-time 5m --headless \\
    --html deliverables/load_test_normal.html
```

### 3. 高负载测试
```bash
locust -f jobs/load_test.py --host=http://localhost:8000 \\
    --users 200 --spawn-rate 20 --run-time 10m --headless \\
    --html deliverables/load_test_stress.html
```

### 4. 峰值测试（模拟突发流量）
```bash
locust -f jobs/load_test.py --host=http://localhost:8000 \\
    --users 500 --spawn-rate 50 --run-time 2m --headless \\
    --html deliverables/load_test_spike.html
```

## 📈 性能基准

基于 TiDB Serverless（免费版）+ FastAPI (4 workers)：

- **正常负载**: 50 并发用户，QPS ~30，平均响应 200ms
- **高负载**: 200 并发用户，QPS ~80，平均响应 500ms
- **峰值**: 500 并发用户，QPS ~100，平均响应 1000ms

如果响应时间超过 2s 或失败率超过 1%，需要优化。
"""
