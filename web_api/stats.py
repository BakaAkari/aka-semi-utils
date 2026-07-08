"""SQLite-based stats database for the aka-semi-utils Web API."""

from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from web_api.settings import settings

_DB_PATH: Path = settings.data_dir / "stats.db"
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def _init_db() -> None:
    conn = _get_conn()
    conn.executescript(
        """
        create table if not exists daily_stats (
            date text primary key,
            unique_visitors integer default 0,
            new_visitors integer default 0,
            processed_images integer default 0,
            api_calls integer default 0,
            avg_batch_size real default 0,
            p50_latency_ms integer default 0,
            p99_latency_ms integer default 0
        );

        create table if not exists visitors (
            visitor_id text primary key,
            first_seen date,
            last_seen date,
            visit_count integer default 0
        );

        create table if not exists ops_log (
            id integer primary key autoincrement,
            created_at datetime default current_timestamp,
            operation text,
            latency_ms integer,
            batch_count integer default 0,
            visitor_id text,
            preset_name text default ''
        );

        create index if not exists ops_log_date on ops_log(created_at);
        """
    )
    conn.commit()


# Ensure tables exist on first import
_init_db()


def record_visit(visitor_id: str) -> bool:
    """Record a visit and return whether this visitor is new."""
    conn = _get_conn()
    today = date.today().isoformat()
    cursor = conn.execute(
        "select first_seen, last_seen, visit_count from visitors where visitor_id = ?",
        (visitor_id,),
    )
    row = cursor.fetchone()
    if row is None:
        conn.execute(
            "insert into visitors (visitor_id, first_seen, last_seen, visit_count) values (?, ?, ?, ?)",
            (visitor_id, today, today, 1),
        )
        _bump_daily(today, unique_visitors=1, new_visitors=1)
        conn.commit()
        return True
    else:
        conn.execute(
            "update visitors set last_seen = ?, visit_count = visit_count + 1 where visitor_id = ?",
            (today, visitor_id),
        )
        if row["last_seen"] != today:
            _bump_daily(today, unique_visitors=1)
        conn.commit()
        return False


def record_process(
    operation: str,
    latency_ms: int,
    *,
    batch_count: int = 0,
    visitor_id: str = "",
    preset_name: str = "",
) -> None:
    """Record a process/preview operation and update daily stats."""
    conn = _get_conn()
    today = date.today().isoformat()
    conn.execute(
        """
        insert into ops_log (created_at, operation, latency_ms, batch_count, visitor_id, preset_name)
        values (current_timestamp, ?, ?, ?, ?, ?)
        """,
        (operation, latency_ms, batch_count, visitor_id, preset_name),
    )
    _bump_daily(today, processed_images=1 if batch_count == 0 else batch_count, api_calls=1)
    conn.commit()


def _bump_daily(
    today: str,
    *,
    unique_visitors: int = 0,
    new_visitors: int = 0,
    processed_images: int = 0,
    api_calls: int = 0,
) -> None:
    conn = _get_conn()
    conn.execute(
        """
        insert into daily_stats (date, unique_visitors, new_visitors, processed_images, api_calls)
        values (?, ?, ?, ?, ?)
        on conflict(date) do update set
            unique_visitors = unique_visitors + excluded.unique_visitors,
            new_visitors = new_visitors + excluded.new_visitors,
            processed_images = processed_images + excluded.processed_images,
            api_calls = api_calls + excluded.api_calls
        """,
        (today, unique_visitors, new_visitors, processed_images, api_calls),
    )


def get_stats() -> dict[str, Any]:
    """Return full stats payload for the dev panel."""
    conn = _get_conn()
    today = date.today().isoformat()

    # Today
    today_row = conn.execute(
        """
        select unique_visitors, new_visitors, processed_images, api_calls
        from daily_stats where date = ?
        """,
        (today,),
    ).fetchone()
    today_stats = dict(today_row) if today_row else {"unique_visitors": 0, "new_visitors": 0, "processed_images": 0, "api_calls": 0}

    # Lifetime totals
    lifetime = conn.execute(
        """
        select
            coalesce(count(*), 0) as total_visitors,
            coalesce((select sum(processed_images) from daily_stats), 0) as total_processed_images,
            coalesce((select sum(api_calls) from daily_stats), 0) as total_api_calls
        from visitors
        """
    ).fetchone()

    # Last 7 days
    seven_ago = (date.today() - timedelta(days=6)).isoformat()
    last_7 = [
        dict(row)
        for row in conn.execute(
            """
            select date, unique_visitors, new_visitors, processed_images, api_calls
            from daily_stats where date >= ? order by date
            """,
            (seven_ago,),
        )
    ]

    # Last 15 days
    fifteen_ago = (date.today() - timedelta(days=14)).isoformat()
    last_15 = [
        dict(row)
        for row in conn.execute(
            """
            select date, unique_visitors, new_visitors, processed_images, api_calls
            from daily_stats where date >= ? order by date
            """,
            (fifteen_ago,),
        )
    ]

    # Last 30 days
    thirty_ago = (date.today() - timedelta(days=29)).isoformat()
    last_30 = [
        dict(row)
        for row in conn.execute(
            """
            select date, unique_visitors, new_visitors, processed_images, api_calls
            from daily_stats where date >= ? order by date
            """,
            (thirty_ago,),
        )
    ]

    # Latency percentiles from last 7 days
    seven_ago_dt = datetime.now() - timedelta(days=7)
    latency_row = conn.execute(
        """
        select
            latency_ms
        from ops_log
        where created_at >= ? and operation in ('process', 'preview')
        order by latency_ms
        """,
        (seven_ago_dt.isoformat(),),
    ).fetchall()
    p50 = 0
    p99 = 0
    if latency_row:
        latencies = [r["latency_ms"] for r in latency_row]
        n = len(latencies)
        p50 = latencies[n // 2] if n > 0 else 0
        p99_idx = int(n * 0.99)
        p99 = latencies[min(p99_idx, n - 1)] if n > 0 else 0

    # Average batch size from last 7 days
    avg_batch = conn.execute(
        """
        select coalesce(avg(batch_count), 0) as avg_batch
        from ops_log
        where created_at >= ? and operation = 'process' and batch_count > 0
        """,
        (seven_ago_dt.isoformat(),),
    ).fetchone()

    # Active visitor ratio (visited in last 7 days / total visitors)
    active_visitors = conn.execute(
        "select count(*) as c from visitors where last_seen >= ?",
        (seven_ago,),
    ).fetchone()["c"]
    total_visitors = lifetime["total_visitors"]
    active_ratio = round(active_visitors / max(total_visitors, 1), 2)

    return {
        "ok": True,
        "today": today_stats,
        "lifetime": {
            "total_visitors": lifetime["total_visitors"] or 0,
            "total_processed_images": lifetime["total_processed_images"] or 0,
            "total_api_calls": lifetime["total_api_calls"] or 0,
        },
        "trend": {
            "last_7_days": last_7,
            "last_15_days": last_15,
            "last_30_days": last_30,
        },
        "latency": {
            "p50_ms": p50,
            "p99_ms": p99,
        },
        "extra": {
            "avg_batch_size": round(avg_batch["avg_batch"] or 0, 1),
            "active_ratio": active_ratio,
        },
    }


def health_check() -> dict[str, Any]:
    """Check database connectivity."""
    try:
        conn = _get_conn()
        conn.execute("select 1")
        return {"ok": True, "db": "connected"}
    except Exception:
        return {"ok": False, "db": "disconnected"}
