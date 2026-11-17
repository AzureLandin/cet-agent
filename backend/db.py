from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager


def _translate_sql(sql: str) -> str:
    """Translate MySQL-style %s placeholders to SQLite ? placeholders."""
    if "%s" in sql:
        return sql.replace("%s", "?")
    return sql


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return row


class _DictCursorWrapper:
    """Wraps a sqlite3.Cursor so fetchone/fetchall return dicts and %s translates to ?."""

    def __init__(self, cursor: sqlite3.Cursor):
        self._cur = cursor

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def execute(self, sql: str, args=()):
        translated = _translate_sql(sql)
        if args is None:
            args = ()
        self._cur.execute(translated, args)
        return self

    def executemany(self, sql: str, seq_of_args):
        translated = _translate_sql(sql)
        self._cur.executemany(translated, seq_of_args)
        return self

    def fetchone(self):
        return _row_to_dict(self._cur.fetchone())

    def fetchall(self):
        return [_row_to_dict(r) for r in self._cur.fetchall()]

    def close(self):
        self._cur.close()


class DB:
    IntegrityError = sqlite3.IntegrityError

    def __init__(self, config: dict | str):
        if isinstance(config, str):
            self.path = config
        else:
            self.path = config.get("path") or ":memory:"

        self._is_memory = self.path == ":memory:" or self.path.startswith("file::memory:")
        self._lock = threading.RLock()
        self._shared_conn: sqlite3.Connection | None = None

        if self._is_memory:
            self._shared_conn = self._open_connection()
        else:
            parent_dir = os.path.dirname(os.path.abspath(self.path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            conn = self._open_connection()
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.commit()
            finally:
                conn.close()

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.path,
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        if not self._is_memory:
            conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    @contextmanager
    def cursor(self):
        if self._is_memory:
            with self._lock:
                assert self._shared_conn is not None
                raw_cur = self._shared_conn.cursor()
                cur = _DictCursorWrapper(raw_cur)
                try:
                    yield cur
                    self._shared_conn.commit()
                except Exception:
                    self._shared_conn.rollback()
                    raise
                finally:
                    cur.close()
        else:
            conn = self._open_connection()
            raw_cur = conn.cursor()
            cur = _DictCursorWrapper(raw_cur)
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()

    @contextmanager
    def transaction(self):
        """Execute multiple statements atomically in one connection."""
        with self.cursor() as cur:
            yield cur

    def execute(self, sql: str, args=()):
        with self.cursor() as cur:
            cur.execute(sql, args)
            return cur.rowcount

    def fetchone(self, sql: str, args=()):
        with self.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()

    def fetchall(self, sql: str, args=()):
        with self.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()

    def health_check(self) -> bool:
        try:
            with self.cursor() as cur:
                cur.execute("SELECT 1")
                return True
        except Exception:
            return False

    def lastrowid(self, sql: str, args=()):
        with self.cursor() as cur:
            cur.execute(sql, args)
            return cur.lastrowid

    def close(self):
        if self._shared_conn is not None:
            with self._lock:
                self._shared_conn.close()
                self._shared_conn = None
