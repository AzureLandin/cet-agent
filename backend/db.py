import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from dbutils.pooled_db import PooledDB


class DB:
    def __init__(self, config: dict):
        self._pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            maxcached=5,
            blocking=True,
            host=config["host"],
            port=int(config.get("port", 3306)),
            user=config["user"],
            password=config["password"],
            database=config["name"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

    def _connect(self):
        return self._pool.connection()

    @contextmanager
    def cursor(self):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
