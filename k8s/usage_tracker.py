"""Per-user TPU notebook time and cost estimates for the JupyterHub admin UI.

Mounted into the Hub by hub.extraFiles. The SQLite ledger lives on the Hub PVC,
separate from JupyterHub's own database schema.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections import defaultdict


DB_PATH = "/srv/jupyterhub/usage.sqlite"
WINDOW_SECONDS = 30 * 24 * 60 * 60


def _connect(path=DB_PATH):
    db = sqlite3.connect(path, timeout=10)
    db.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            server_name TEXT NOT NULL,
            started REAL NOT NULL,
            stopped REAL
        )"""
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS sessions_user_started "
        "ON sessions (username, started)"
    )
    return db


def record_start(username, server_name="", at=None, path=DB_PATH):
    at = time.time() if at is None else at
    with _connect(path) as db:
        # A second start without an observed stop closes the earlier interval.
        db.execute(
            "UPDATE sessions SET stopped = ? "
            "WHERE username = ? AND server_name = ? AND stopped IS NULL",
            (at, username, server_name),
        )
        db.execute(
            "INSERT INTO sessions (username, server_name, started) VALUES (?, ?, ?)",
            (username, server_name, at),
        )


def record_stop(username, server_name="", at=None, path=DB_PATH):
    at = time.time() if at is None else at
    with _connect(path) as db:
        db.execute(
            "UPDATE sessions SET stopped = max(started, ?) "
            "WHERE username = ? AND server_name = ? AND stopped IS NULL",
            (at, username, server_name),
        )


def open_sessions(path=DB_PATH):
    with _connect(path) as db:
        return db.execute(
            "SELECT DISTINCT username, server_name FROM sessions WHERE stopped IS NULL"
        ).fetchall()


def summarize(usernames, hourly_usd, now=None, path=DB_PATH):
    now = time.time() if now is None else now
    cutoff = now - WINDOW_SECONDS
    totals = defaultdict(lambda: {"hours_30d": 0.0, "hours_all": 0.0, "active": 0})
    with _connect(path) as db:
        for username, started, stopped in db.execute(
            "SELECT username, started, stopped FROM sessions"
        ):
            end = now if stopped is None else min(stopped, now)
            totals[username]["hours_all"] += max(0.0, end - started) / 3600
            totals[username]["hours_30d"] += max(0.0, end - max(started, cutoff)) / 3600
            if stopped is None:
                totals[username]["active"] += 1
    rows = []
    for username in sorted(set(usernames) | totals.keys()):
        row = totals[username]
        rows.append(
            {
                "username": username,
                "active": row["active"],
                "hours_30d": round(row["hours_30d"], 3),
                "cost_30d_usd": round(row["hours_30d"] * hourly_usd, 2),
                "hours_all": round(row["hours_all"], 3),
                "cost_all_usd": round(row["hours_all"] * hourly_usd, 2),
            }
        )
    rows.sort(key=lambda row: (-row["cost_30d_usd"], row["username"]))
    return rows


def configure(c):
    """Install a tracked KubeSpawner and an admin-scoped read-only JSON endpoint."""
    from jupyterhub import orm
    from jupyterhub.handlers.base import BaseHandler
    from jupyterhub.scopes import needs_scope
    from kubespawner import KubeSpawner
    from tornado import web

    hourly_usd = float(os.environ.get("TPU_HOURLY_USD", "1.35"))
    if not 0 <= hourly_usd < float("inf"):
        raise ValueError("TPU_HOURLY_USD must be a finite non-negative number")

    class UsageKubeSpawner(KubeSpawner):
        async def start(self):
            result = await super().start()
            try:
                record_start(self.user.name, self.name)
            except Exception:
                self.log.exception("Could not record TPU usage start for %s", self.user.name)
            return result

        async def stop(self, now=False):
            result = await super().stop(now=now)
            try:
                record_stop(self.user.name, self.name)
            except Exception:
                self.log.exception("Could not record TPU usage stop for %s", self.user.name)
            return result

    class UsageHandler(BaseHandler):
        @web.authenticated
        @needs_scope("admin-ui")
        def get(self):
            # Reconcile intervals left open by a Hub restart or an external pod
            # deletion. The observation time is the best stop time available.
            now = time.time()
            for username, server_name in open_sessions():
                user = self.find_user(username)
                spawner = user.spawners.get(server_name) if user else None
                if spawner is None or not spawner.active:
                    record_stop(username, server_name, at=now)
            usernames = [name for (name,) in self.db.query(orm.User.name).all()]
            self.set_header("Cache-Control", "no-store")
            self.set_header("Content-Type", "application/json")
            self.write(
                {
                    "hourly_usd": hourly_usd,
                    "rows": summarize(usernames, hourly_usd, now=now),
                }
            )

    c.JupyterHub.spawner_class = UsageKubeSpawner
    c.JupyterHub.extra_handlers = [(r"/admin/usage", UsageHandler)]
    c.JupyterHub.template_paths = ["/usr/local/share/jupyterhub/custom_templates"]
