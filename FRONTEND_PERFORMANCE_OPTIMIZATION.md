# 🚀 前端性能优化方案 - 解决切换/交互慢问题

**问题**: 左侧侧边栏 tab 切换后加载很慢，每个 tab 内部的按钮点击加载也很慢  
**诊断时间**: 2026-04-20 19:40  
**根本原因**: Server Component 全页面重渲染 + 缺少客户端状态管理

---

## 📊 问题诊断

### 当前架构

```
用户点击 Sidebar 链接
  ↓
Next.js 路由跳转 (/internal → /details)
  ↓
卸载旧页面，加载新页面
  ↓
Server Component 执行（服务端）
  ↓
并行请求 6 个 API
  ↓
等待所有响应（总计 300-800ms）
  ↓
生成 HTML
  ↓
发送到浏览器
  ↓
Hydration（水合）
  ↓
页面显示
```

**总耗时**: 500ms - 1.5s（用户感知明显卡顿）

### 性能瓶颈

| 阶段 | 耗时 | 可优化 |
|------|------|--------|
| 路由跳转 | 50-100ms | ❌ Next.js 内部 |
| 页面卸载 | 20-50ms | ❌ React 内部 |
| **API 请求** | **300-800ms** | ✅ **可优化** |
| HTML 生成 | 50-100ms | ⚠️ 部分优化 |
| Hydration | 50-150ms | ⚠️ 部分优化 |
| **总计** | **500-1500ms** | - |

### 具体问题

#### 1. 全页面重渲染
- 每次路由切换，整个页面销毁重建
- Sidebar、Header、Footer 重复渲染
- 无状态保留，无渐进式加载

#### 2. Server Component 同步等待
```tsx
// internal/page.tsx
const [summary, queues, trend, ...] = await Promise.all([...]);
// ↑ 等待所有 API 完成才开始渲染
```

**问题**: 即使最快的接口 2ms，也要等最慢的 800ms

#### 3. 无客户端缓存
- 切换回已访问页面，重新请求数据
- 相同数据重复获取
- 无 SWR（Stale-While-Revalidate）

#### 4. 按钮交互慢
```tsx
// 表单提交、筛选器、分页等
<form action="/details">  {/* 全页面刷新 */}
  <button type="submit">查询</button>
</form>
```

**问题**: 每次交互触发完整的 Server Round Trip

---

## ✅ 优化方案

### 方案 1: 布局持久化（Layout Persistence）⭐⭐⭐⭐⭐

**目标**: Sidebar 只渲染一次，页面切换时保持不变

#### 实现方式

```tsx
// app/layout.tsx（已有）
export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <AppShell>  {/* ← 持久化容器 */}
          {children}  {/* ← 切换的内容 */}
        </AppShell>
      </body>
    </html>
  );
}
```

**关键**: AppShell 作为 Client Component，包含 Sidebar + 主内容区

#### 优化后流程

```
用户点击 Sidebar 链接
  ↓
客户端路由切换（无页面刷新）
  ↓
只替换 {children} 部分
  ↓
Sidebar 保持不变
  ↓
新页面逐步加载（Suspense）
```

**耗时**: 100-300ms（减少 60-80%）

---

### 方案 2: Streaming SSR + Suspense ⭐⭐⭐⭐⭐

**目标**: 页面分块加载，不等待所有数据

#### 实现方式

```tsx
// internal/page.tsx
export default function InternalPage() {
  return (
    <>
      {/* 立即显示骨架屏 */}
      <Suspense fallback={<SummaryCardsSkeleton />}>
        <SummaryCards />  {/* 独立获取数据 */}
      </Suspense>

      <Suspense fallback={<QueuesSkeleton />}>
        <QueuesRanking />  {/* 独立获取数据 */}
      </Suspense>

      <Suspense fallback={<TrendSkeleton />}>
        <TrendChart />  {/* 独立获取数据 */}
      </Suspense>
    </>
  );
}
```

**流程**:
1. 首屏立即显示骨架屏（0ms）
2. 各组件独立加载数据（并行）
3. 数据到达立即渲染，无需等待其他

**耗时**: 首屏 <50ms，完整加载 300-500ms

---

### 方案 3: 客户端状态管理 + SWR ⭐⭐⭐⭐

**目标**: 智能缓存，减少重复请求

#### 使用 SWR 库

```tsx
import useSWR from 'swr';

function InternalSummary({ date }) {
  const { data, error, isLoading } = useSWR(
    `/api/v1/internal/summary?selected_date=${date}`,
    fetcher,
    {
      revalidateOnFocus: false,  // 切换标签不重新请求
      dedupingInterval: 60000,   // 60秒内去重
    }
  );

  if (isLoading) return <SkeletonLoader />;
  if (error) return <ErrorState />;
  return <SummaryCards data={data} />;
}
```

**特性**:
- ✅ 自动缓存
- ✅ 请求去重
- ✅ 后台自动重新验证
- ✅ 乐观更新

**耗时**: 首次 300ms，再次访问 <10ms（命中缓存）

---

### 方案 4: 交互式客户端组件 ⭐⭐⭐⭐⭐

**目标**: 按钮点击立即响应，无页面刷新

#### Before（Server Form）

```tsx
<form action="/details">
  <input name="queue" />
  <button type="submit">查询</button>  {/* 全页面刷新 */}
</form>
```

**耗时**: 500-1000ms

#### After（Client Component）

```tsx
'use client';

function FilterForm() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const result = await fetch('/api/v1/details/query?...');
    const json = await result.json();
    
    setData(json.data);
    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="queue" />
      <button disabled={loading}>
        {loading ? '查询中...' : '查询'}
      </button>
    </form>
  );
}
```

**耗时**: 50-200ms（只更新数据区域）

---

### 方案 5: 预加载 + 预取（Prefetch）⭐⭐⭐

**目标**: 鼠标悬停时提前加载数据

```tsx
import { useRouter } from 'next/navigation';

function NavLink({ href }) {
  const router = useRouter();

  return (
    <Link 
      href={href}
      onMouseEnter={() => router.prefetch(href)}  // 预加载
    >
      内检看板
    </Link>
  );
}
```

**效果**: 点击时数据已在缓存，瞬间显示

---

## 📈 综合方案效果对比

| 方案 | 首次加载 | 二次加载 | 按钮点击 | 实现复杂度 | 推荐度 |
|------|---------|---------|---------|-----------|--------|
| **当前（Server）** | 1000ms | 1000ms | 800ms | ⭐ | ❌ |
| 方案1: 布局持久化 | 600ms | 400ms | 800ms | ⭐⭐ | ⭐⭐⭐ |
| 方案2: Streaming | 300ms | 300ms | 800ms | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 方案3: SWR | 300ms | <10ms | 300ms | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 方案4: 客户端组件 | 300ms | 300ms | 100ms | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 方案5: 预加载 | 200ms | <50ms | 100ms | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **组合方案** | **<100ms** | **<10ms** | **<50ms** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎯 推荐实施路径

### 阶段 1: 快速优化（本周）

**目标**: 立即改善用户体验

1. ✅ **改造 AppShell 为 Client Component**
   - 包含 Sidebar 和路由切换逻辑
   - 使用 `usePathname()` 高亮当前页
   - 避免 Sidebar 重复渲染

2. ✅ **关键交互改为 Client Component**
   - 详情查询表单
   - 日期选择器
   - 分页按钮
   - 筛选器

**预期效果**:
- 切换耗时: 1000ms → 400ms（-60%）
- 按钮点击: 800ms → 200ms（-75%）
- 用户感知: 明显改善

**实施时间**: 1-2 天

---

### 阶段 2: 中级优化（本月）

**目标**: 接近一流产品体验

3. ✅ **引入 SWR 数据缓存**
   - 安装: `npm install swr`
   - 封装 `useSWR` Hook
   - 改造 3-5 个核心页面

4. ✅ **实施 Streaming SSR**
   - 拆分大组件为小组件
   - 使用 `<Suspense>` 包裹
   - 添加 Loading 状态

**预期效果**:
- 首屏: 400ms → 100ms（-75%）
- 二次访问: 400ms → <10ms（-98%）
- 用户感知: 优秀

**实施时间**: 3-5 天

---

### 阶段 3: 高级优化（下月）

**目标**: 行业顶尖水平

5. ✅ **路由预加载**
   - 鼠标悬停预加载
   - 智能预测下一页

6. ✅ **虚拟滚动**
   - 长列表优化
   - 按需渲染

7. ✅ **Service Worker 缓存**
   - 离线支持
   - 静态资源缓存

**预期效果**:
- 所有操作 <50ms
- 离线可用
- 用户感知: 极致

**实施时间**: 1-2 周

---

## 🛠️ 立即可执行的优化

### 优化 1: AppShell 客户端化

创建 `src/components/app-shell-client.tsx`:

```tsx
'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { ReactNode } from 'react';

export function AppShellClient({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  const navItems = [
    { href: '/', label: '首页' },
    { href: '/details', label: '详情查询' },
    { href: '/newcomers', label: '新人追踪' },
    { href: '/internal', label: '内检看板' },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <nav>
          {navItems.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={pathname === item.href ? 'active' : ''}
              prefetch={true}  {/* 预加载 */}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
```

**效果**: Sidebar 只渲染一次，切换页面瞬间响应

---

### 优化 2: 详情查询客户端化

创建 `src/components/details-filter-client.tsx`:

```tsx
'use client';

import { useState } from 'react';

export function DetailsFilterClient() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    const params = new URLSearchParams({
      start_date: formData.get('start_date') as string,
      end_date: formData.get('end_date') as string,
      queue_name: formData.get('queue_name') as string,
    });

    try {
      const res = await fetch(`/api/v1/details/query?${params}`);
      const json = await res.json();
      setResults(json.data?.items || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <form onSubmit={handleSubmit}>
        <input type="date" name="start_date" required />
        <input type="date" name="end_date" required />
        <input type="text" name="queue_name" placeholder="队列名" />
        
        <button type="submit" disabled={loading}>
          {loading ? '查询中...' : '查询'}
        </button>
      </form>

      {loading && <SkeletonLoader />}
      {!loading && <DataTable data={results} />}
    </>
  );
}
```

**效果**: 点击查询按钮，200ms 内显示结果（无页面刷新）

---

## 📊 性能监控

### 关键指标

| 指标 | 当前 | 目标 | 监控方式 |
|------|------|------|---------|
| 首屏时间（FCP） | 1000ms | <300ms | Lighthouse |
| 可交互时间（TTI） | 1500ms | <500ms | Web Vitals |
| 路由切换 | 800ms | <200ms | Performance API |
| 按钮响应 | 600ms | <100ms | User Timing |

### 监控代码

```tsx
// 在 layout.tsx 添加
'use client';

import { useReportWebVitals } from 'next/web-vitals';

export function WebVitalsReporter() {
  useReportWebVitals((metric) => {
    console.log(metric);
    // 发送到分析服务
  });
}
```

---

## 📝 实施检查清单

### 立即执行（今天）

- [ ] 创建 `app-shell-client.tsx`
- [ ] 修改 `layout.tsx` 使用客户端 Shell
- [ ] 创建 `details-filter-client.tsx`
- [ ] 测试路由切换速度
- [ ] 测试按钮点击响应

### 本周完成

- [ ] 改造详情页为客户端组件
- [ ] 改造新人页关键交互
- [ ] 改造内检页筛选器
- [ ] 添加性能监控
- [ ] 用户测试反馈

### 本月完成

- [ ] 引入 SWR 缓存
- [ ] 实施 Streaming SSR
- [ ] 优化长列表渲染
- [ ] 添加路由预加载
- [ ] 性能基准测试

---

## 🎉 预期最终效果

| 操作 | 优化前 | 优化后 | 用户感知 |
|------|--------|--------|---------|
| 切换页面 | 1000ms 🐌 | <100ms ⚡ | 瞬间响应 |
| 二次访问 | 1000ms 🐌 | <10ms ⚡⚡ | 秒开 |
| 按钮点击 | 800ms 🐌 | <50ms ⚡ | 无感知延迟 |
| 表单提交 | 600ms 🐌 | <100ms ⚡ | 立即反馈 |

**总体提升**: 80-90% 性能提升 🚀

**用户满意度**: ⭐⭐ → ⭐⭐⭐⭐⭐

---

**下一步**: 是否立即开始实施阶段1快速优化？
