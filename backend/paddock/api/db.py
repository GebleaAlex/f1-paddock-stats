"""Read-only access to the DuckDB file built by the pipeline.

One connection is shared by the process; every query runs on its own cursor, which is how DuckDB supports
concurrent reads from several threads. When the pipeline swaps in a new database file the connection is reopened
on the next query.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import duckdb
from fastapi import HTTPException

from .. import config


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.fixed = Path(path) if path else None
        self._con: duckdb.DuckDBPyConnection | None = None
        self._open: tuple[Path, float] | None = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self.fixed or config.current_db_path()

    def _connection(self) -> duckdb.DuckDBPyConnection:
        path = self.path
        try:
            mtime = os.stat(path).st_mtime
        except FileNotFoundError as e:
            raise RuntimeError(f"No database at {path}. Run `paddock update` first.") from e
        with self._lock:
            if self._con is None or self._open != (path, mtime):
                if self._con is not None:
                    self._con.close()
                self._con = duckdb.connect(str(path), read_only=True)
                self._open = (path, mtime)
            return self._con

    def rows(self, sql: str, params: list[Any] | dict[str, Any] | None = None) -> list[dict[str, Any]]:
        cur = self._connection().cursor()
        try:
            cur.execute(sql, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        finally:
            cur.close()

    def one(self, sql: str, params: list[Any] | dict[str, Any] | None = None) -> dict[str, Any] | None:
        result = self.rows(sql, params)
        return result[0] if result else None

    def one_or_404(self, sql: str, params: list[Any] | dict[str, Any] | None = None, what: str = "Item") -> dict:
        if (row := self.one(sql, params)) is None:
            raise HTTPException(status_code=404, detail=f"{what} not found")
        return row

    def scalar(self, sql: str, params: list[Any] | dict[str, Any] | None = None) -> Any:
        row = self.one(sql, params)
        return next(iter(row.values())) if row else None


db = Database()
