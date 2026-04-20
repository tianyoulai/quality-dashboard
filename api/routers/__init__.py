# 子模块按需在 api.main 中导入；这里保留显式导入 dashboard / details / meta，
# newcomers 因为依赖 services 里尚未迁完的符号，由 api.main 用 try/except 加载。
from api.routers import dashboard, details, meta

__all__ = ["dashboard", "details", "meta"]
