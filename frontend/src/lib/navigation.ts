export const NAV_ITEMS = [
  {
    key: "dashboard",
    label: "首页总览",
    href: "/",
    description: "经营总览、告警、组别概览",
  },
  {
    key: "details",
    label: "明细查询",
    href: "/details",
    description: "多维筛选、问题样本、导出前核对",
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
    description: "一键检查三页核心接口是否正常",
  },
] as const;
