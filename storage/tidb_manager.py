"""TiDB 连接管理器：基于 mysql-connector-python 的连接池与基础操作。

配置读取优先级：st.secrets → 环境变量 → 本地 settings.json
  - Streamlit Cloud 部署时，凭据存储在 st.secrets 中
  - 本地开发时，从 config/settings.json 读取（文件不提交 Git）
"""
from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator, Iterable

import mysql.connector
from mysql.connector import pooling
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _get_secret(key: str, default: str | None = None) -> str | None:
    """从 st.secrets / 环境变量 / settings.json 三级读取配置值。
    
    支持嵌套格式：key="tidb.host" → st.secrets["tidb"]["host"] 或 env["tidb.host"]
    """
    # 优先级 1: Streamlit Cloud Secrets（支持嵌套字典）
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            # 尝试嵌套访问：st.secrets["tidb"]["host"]
            if "." in key:
                parts = key.split(".")
                val = st.secrets
                for p in parts:
                    # Secrets 对象不支持 isinstance(val, dict)，用 try-except 更安全
                    try:
                        val = val[p]
                    except (KeyError, TypeError):
                        val = None
                        break
                if val is not None:
                    return str(val)
            # 尝试扁平访问：st.secrets["tidb.host"]
            elif key in st.secrets:
                return str(st.secrets[key])
    except Exception:
        pass
    
    # 优先级 2: 环境变量（扁平格式）
    env_val = os.environ.get(key)
    if env_val is not None:
        return env_val
    
    # 优先级 3: 本地 settings.json（嵌套格式）
    settings_path = PROJECT_ROOT / "config" / "settings.json"
    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        if "." in key:
            parts = key.split(".")
            val = settings
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p)
                else:
                    val = None
                    break
            if val is not None:
                return str(val)
        elif key in settings:
            return str(settings[key])
    return default


@dataclass
class TiDBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    pool_name: str = "tidb_pool"
    pool_size: int = 5  # TiDB Serverless 免费版限制为 ~10 并发，留余量

    @classmethod
    def from_settings(cls) -> "TiDBConfig":
        """从 st.secrets / 环境变量 / settings.json 读取 TiDB 配置。"""
        return cls(
            host=_get_secret("tidb.host", ""),
            port=int(_get_secret("tidb.port", "4000")),
            user=_get_secret("tidb.user", ""),
            password=_get_secret("tidb.password", ""),
            database=_get_secret("tidb.database") or _get_secret("tidb.db", "test"),
            charset=_get_secret("tidb.charset", "utf8mb4"),
        )


def _create_pool(config: TiDBConfig) -> pooling.MySQLConnectionPool:
    """创建 TiDB 连接池。TiDB Serverless 需要 SSL。"""
    return pooling.MySQLConnectionPool(
        pool_name=config.pool_name,
        pool_size=config.pool_size,
        autocommit=True,
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset=config.charset,
        ssl_ca=None,
        ssl_verify_cert=False,
        connect_timeout=5,          # 缩短：原 10s → 5s，TiDB Serverless 通常 1-2s
        connection_timeout=15,      # 缩短：原 30s → 15s
        pool_reset_session=False,   # 禁用 session reset，避免 TiDB 连接问题
    )


class TiDBManager:
    """TiDB 数据库操作封装，提供连接池、查询、执行等基础方法。
    
    连接池延迟初始化：只有在首次使用时才创建，确保 st.secrets 已就绪。
    使用单例模式：全进程共享一个连接池，避免 Streamlit 多页面各自创建连接池耗尽连接。
    """

    _instance: "TiDBManager | None" = None

    def __new__(cls, config: TiDBConfig | None = None) -> "TiDBManager":
        """单例模式：全进程共享同一个 TiDBManager 实例。"""
        if cls._instance is None:
            instance = super().__new__(cls)
            instance.config = config
            instance._pool = None
            cls._instance = instance
        return cls._instance

    def __init__(self, config: TiDBConfig | None = None):
        # __new__ 已完成初始化，避免重复覆盖
        pass

    def _ensure_pool(self) -> pooling.MySQLConnectionPool:
        """延迟初始化连接池。首次创建后立即预热一个连接，减少首次查询等待。"""
        if self._pool is None:
            config = self.config or TiDBConfig.from_settings()
            if not config.host or not config.user or not config.password:
                raise ValueError(f"TiDB 配置不完整: host={config.host}, user={config.user}, "
                                 f"password={'已设置' if config.password else '未设置'}")
            self.config = config  # 回写，确保 table_exists 等方法能读取
            self._pool = _create_pool(config)
            # 预热：立即建立并归还一个连接，让后续查询不用等 TCP 握手
            try:
                warmup_conn = self._pool.get_connection()
                warmup_conn.close()
            except Exception:
                pass  # 预热失败不阻塞，第一次查询时自然会重试
        return self._pool

    @contextmanager
    def get_connection(self) -> Generator[mysql.connector.MySQLConnection, None, None]:
        """从连接池获取一个连接，使用后自动归还。"""
        pool = self._ensure_pool()
        conn = pool.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def fetch_df(self, sql: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
        """执行 SQL 并返回 DataFrame。
        
        安全防护：对无 LIMIT 的纯行查询自动追加上限 50000，
        防止全表扫描大量数据。排除聚合/分组/子查询/UNION 等情况。
        """
        safe_sql = sql.strip().rstrip(";")
        upper = safe_sql.upper()
        
        # 只对满足全部条件的纯 SELECT 追加 LIMIT：
        # ① 以 SELECT 开头 ② 无 LIMIT/OFFSET ③ 无聚合函数/GROUP BY/UNION
        # ④ FROM 后无子查询（括号）  ⑤ 无 WITH 子句（CTE）
        needs_limit = (
            upper.startswith("SELECT")
            and " LIMIT " not in upper
            and "\nLIMIT " not in upper
            and "OFFSET" not in upper
            and not upper.startswith("WITH")
            and "GROUP BY" not in upper
            and "UNION" not in upper
            and not any(fn in upper for fn in ("COUNT(", "SUM(", "AVG(", "MAX(", "MIN("))
            and not re.search(r'\bFROM\s*\(', upper)
        )
        if needs_limit:
            safe_sql += " LIMIT 50000"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(safe_sql, tuple(params) if params else ())
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                return pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame()
            finally:
                cursor.close()

    def fetch_one(self, sql: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
        """执行 SQL 并返回第一行。直接使用 fetchone，不加 LIMIT。"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, tuple(params) if params else ())
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                return dict(zip(columns, row)) if columns else None
            finally:
                cursor.close()

    def execute_query(self, sql: str, params: Iterable[Any] | None = None) -> list[tuple]:
        """执行查询并返回结果列表（兼容层方法）。
        
        返回 list[tuple] 格式以兼容索引访问 result[0][0]。
        如果需要字典格式，请使用 fetch_df() 或 fetch_one()。
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, tuple(params) if params else ())
                rows = cursor.fetchall()
                return rows if rows else []
            finally:
                cursor.close()
    
    def close(self):
        """兼容层方法：连接池自动管理，无需手动关闭。"""
        pass

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> None:
        """执行 SQL（INSERT/UPDATE/DELETE 等）。"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, tuple(params) if params else ())
            finally:
                cursor.close()

    def execute_many(self, sql: str, params_list: list[Iterable[Any]]) -> int:
        """批量执行同一条 SQL（executemany）。返回影响的行数。"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(sql, [tuple(p) for p in params_list])
                return cursor.rowcount
            finally:
                cursor.close()

    def execute_in_transaction(self, sql_list: list[tuple[str, Iterable[Any] | None]]) -> None:
        """在事务中批量执行 SQL，失败时自动回滚。"""
        with self.get_connection() as conn:
            conn.autocommit = False
            cursor = conn.cursor()
            try:
                for sql, params in sql_list:
                    cursor.execute(sql, tuple(params) if params else ())
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.autocommit = True
                cursor.close()

    def insert_dataframe(self, table_name: str, df: pd.DataFrame,
                         batch_size: int = 10000) -> int:
        """将 DataFrame 分批插入到指定表。返回插入行数。
        
        使用向量化转换代替 iterrows，大幅提升 3 万+ 行数据的写入速度。
        batch_size=10000: TiDB Serverless 延迟高(~500ms/次)，大批次减少 roundtrip。
        """
        if df.empty:
            return 0
        columns = list(df.columns)
        placeholders = ", ".join(["%s"] * len(columns))
        col_sql = ", ".join(f"`{c}`" for c in columns)
        sql = f"INSERT INTO `{table_name}` ({col_sql}) VALUES ({placeholders})"

        # 向量化转换：统一转 object 类型，确保 pd.NA/NaT 全部变 None
        clean_df = df.copy()
        for col in clean_df.columns:
            dtype = clean_df[col].dtype
            if pd.api.types.is_datetime64_any_dtype(dtype):
                # datetime → Python datetime，NaT → None
                clean_df[col] = clean_df[col].dt.to_pydatetime()
            # 统一转 object，消除 pandas nullable 类型残留的 pd.NA
            clean_df[col] = clean_df[col].astype("object")

        # 一次性把所有 NaN/NA/NaT 替换为 None
        clean_df = clean_df.where(clean_df.notna(), other=None)

        # DataFrame → list of tuples（比 iterrows 快 50 倍以上）
        all_rows = list(clean_df.itertuples(index=False, name=None))

        # 分批提交，避免 TiDB Serverless 大事务超时
        total_inserted = 0
        for i in range(0, len(all_rows), batch_size):
            batch = all_rows[i:i + batch_size]
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.executemany(sql, batch)
                    total_inserted += cursor.rowcount
                finally:
                    cursor.close()
        return total_inserted

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在。"""
        sql = """
        SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """
        result = self.fetch_one(sql, [self.config.database, table_name])
        return bool(result and result.get("COUNT(*)", 0) > 0)
