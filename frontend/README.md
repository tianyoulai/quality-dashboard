# QC统一看板前端

这不是 demo 壳子，而是当前统一看板迁移出来的第一版 Next.js 前端骨架。

## 当前已接入

- 首页首屏：`/api/v1/dashboard/overview`
- 告警列表：`/api/v1/dashboard/alerts`
- 单条告警详情：`/api/v1/dashboard/alerts/{alert_id}`
- 首页下钻：`/api/v1/dashboard/group-detail`
- 明细查询：`/api/v1/details/filters` + `/api/v1/details/query`
- 新人追踪：`/api/v1/newcomers/summary` / `members` / `qa-daily` / `error-summary`
- 元信息：`/api/v1/meta/date-range`

## 本地启动

先启动后端：

```bash
cd ..
bash start_api.sh
```

再启动前端：

```bash
cd ..
bash start_frontend.sh
```

默认访问地址：

- 前端：`http://127.0.0.1:3000`
- API：`http://127.0.0.1:8000`

## 当前定位

- 这是迁移前台，不是替换全部 Streamlit 的最终版
- 数据导入、运维、文件上传仍留在 Streamlit
- 首页、明细查询、新人追踪开始进入前后端解耦验证阶段

## 下一步

1. 继续补首页单条告警的快捷状态流转与更多联动样本
2. 优化明细查询的联动入口和筛选体验
3. 增加导入 / 运维接口
4. 接权限与环境配置
