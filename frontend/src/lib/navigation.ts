export const NAV_ITEMS = [
  {
    key: "dashboard",
    label: "首页总览",
    href: "/",
    description: "经营总览、告警、组别概览",
  },
  {
    key: "internal",
    label: "内检看板",
    href: "/internal",
    description: "内部团队质检、队列排名、审核人分析",
  },
  {
    key: "details",
    label: "明细查询",
    href: "/details",
    description: "明细记录、审核人分析、队列分析",
  },
  {
    key: "newcomers",
    label: "新人追踪",
    href: "/newcomers",
    description: "批次、成员、阶段走势",
  },
  {
    key: "smoke",
    label: "在线冒烟",
    href: "/smoke",
    description: "一键检查四页核心接口是否正常",
  },
] as const;
