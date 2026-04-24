"""新人追踪 — 视图模块包。

每个子模块对应一个页面 Tab，均暴露 render_xxx(ctx) 函数：
  - ctx 是一个 dict，包含主页面准备好的所有 DataFrame 和配置。
  - 各子模块只负责渲染 UI，不直接执行 SQL 查询。

目录结构：
  _shared.py    共享工具函数、常量、数据类型定义
  _data.py      所有 SQL 数据加载函数（由主页面调用并传入 ctx）
  overview.py   📊 批次概览
  growth.py     📈 成长曲线
  compare.py    🔄 阶段对比
  person.py     👤 个人追踪
  dimension.py  📊 维度分析
  alert.py      ⚠️ 异常告警
"""
from views.newcomer.overview import render_overview
from views.newcomer.growth import render_growth
from views.newcomer.compare import render_compare
from views.newcomer.person import render_person
from views.newcomer.dimension import render_dimension
from views.newcomer.alert import render_alert

__all__ = [
    "render_overview",
    "render_growth",
    "render_compare",
    "render_person",
    "render_dimension",
    "render_alert",
]
