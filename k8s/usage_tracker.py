"""Per-user TPU notebook time and cost estimates for JupyterHub.

Mounted into the Hub by hub.extraFiles. The SQLite ledger lives on the Hub PVC,
separate from JupyterHub's own database schema.
"""

from __future__ import annotations

import json
import math
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
    db.execute(
        """CREATE TABLE IF NOT EXISTS budget_overrides (
            username TEXT PRIMARY KEY,
            limit_usd REAL NOT NULL CHECK (limit_usd > 0)
        )"""
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


def open_sessions(path=DB_PATH, username=None):
    with _connect(path) as db:
        if username is not None:
            return db.execute(
                "SELECT DISTINCT username, server_name FROM sessions "
                "WHERE stopped IS NULL AND username = ?", (username,)
            ).fetchall()
        return db.execute(
            "SELECT DISTINCT username, server_name FROM sessions WHERE stopped IS NULL"
        ).fetchall()


def estimated_cost(username, hourly_usd, now=None, path=DB_PATH):
    """Return the unrounded all-time estimate, including running sessions."""
    now = time.time() if now is None else now
    with _connect(path) as db:
        intervals = db.execute(
            "SELECT started, stopped FROM sessions WHERE username = ?", (username,)
        ).fetchall()
    seconds = sum(max(0.0, (now if stopped is None else min(stopped, now)) - started)
                  for started, stopped in intervals)
    return seconds * hourly_usd / 3600


def budget_overrides(path=DB_PATH):
    with _connect(path) as db:
        return dict(db.execute("SELECT username, limit_usd FROM budget_overrides"))


def set_budget_override(username, limit_usd, path=DB_PATH):
    if not isinstance(username, str) or not username:
        raise ValueError("username is required")
    with _connect(path) as db:
        if limit_usd is None:
            db.execute("DELETE FROM budget_overrides WHERE username = ?", (username,))
            return
        if isinstance(limit_usd, bool):
            raise ValueError("limit_usd must be a positive dollar amount")
        try:
            limit = float(limit_usd)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit_usd must be a positive dollar amount") from exc
        if not math.isfinite(limit) or limit < 0.01 or round(limit, 2) < 0.01:
            raise ValueError("limit_usd must be at least $0.01")
        if abs(limit - round(limit, 2)) > 1e-8:
            raise ValueError("limit_usd must have at most two decimal places")
        db.execute(
            "INSERT INTO budget_overrides (username, limit_usd) VALUES (?, ?) "
            "ON CONFLICT(username) DO UPDATE SET limit_usd = excluded.limit_usd",
            (username, round(limit, 2)),
        )


def summarize(usernames, hourly_usd, now=None, path=DB_PATH, only_username=None):
    now = time.time() if now is None else now
    cutoff = now - WINDOW_SECONDS
    totals = defaultdict(lambda: {"hours_30d": 0.0, "hours_all": 0.0, "active": 0})
    with _connect(path) as db:
        if only_username is None:
            intervals = db.execute("SELECT username, started, stopped FROM sessions")
        else:
            intervals = db.execute(
                "SELECT username, started, stopped FROM sessions WHERE username = ?",
                (only_username,),
            )
        for username, started, stopped in intervals:
            end = now if stopped is None else min(stopped, now)
            totals[username]["hours_all"] += max(0.0, end - started) / 3600
            totals[username]["hours_30d"] += max(0.0, end - max(started, cutoff)) / 3600
            if stopped is None:
                totals[username]["active"] += 1
    rows = []
    included_users = {only_username} if only_username is not None else set(usernames) | totals.keys()
    for username in sorted(included_users):
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
    """Install tracked spawning, a student budget, and usage endpoints."""
    from jupyterhub import orm
    from jupyterhub.handlers.base import BaseHandler
    from jupyterhub.scopes import needs_scope
    from kubespawner import KubeSpawner
    from tornado import web

    hourly_usd = float(os.environ.get("TPU_HOURLY_USD", "1.35"))
    if not math.isfinite(hourly_usd) or hourly_usd < 0:
        raise ValueError("TPU_HOURLY_USD must be a finite non-negative number")
    default_budget = float(os.environ.get("STUDENT_TPU_BUDGET_USD", "150"))
    if not math.isfinite(default_budget) or default_budget <= 0:
        raise ValueError("STUDENT_TPU_BUDGET_USD must be a finite positive number")

    class UsageKubeSpawner(KubeSpawner):
        async def start(self):
            if not self.user.admin:
                try:
                    spent = estimated_cost(self.user.name, hourly_usd)
                    limit = budget_overrides().get(self.user.name, default_budget)
                except Exception as exc:
                    self.log.exception("Could not check TPU budget for %s", self.user.name)
                    raise web.HTTPError(503, "TPU budget check is unavailable; please try again later") from exc
                if spent >= limit:
                    raise web.HTTPError(
                        403,
                        f"Your estimated TPU usage has reached your ${limit:.2f} limit. "
                        "Please contact course staff to request an increase.",
                    )
            result = await super().start()
            try:
                record_start(self.user.name, self.name)
            except Exception as exc:
                self.log.exception("Could not record TPU usage start for %s", self.user.name)
                if not self.user.admin:
                    try:
                        await super().stop(now=True)
                    except Exception:
                        self.log.exception("Could not stop untracked TPU server for %s", self.user.name)
                    raise web.HTTPError(503, "TPU usage tracking is unavailable; please try again later") from exc
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
            if not self.current_user.admin:
                raise web.HTTPError(403)
            # Reconcile intervals left open by a Hub restart or an external pod
            # deletion. The observation time is the best stop time available.
            now = time.time()
            for username, server_name in open_sessions():
                user = self.find_user(username)
                spawner = user.spawners.get(server_name) if user else None
                if spawner is None or not spawner.active:
                    record_stop(username, server_name, at=now)
            users = self.db.query(orm.User.name, orm.User.admin).all()
            overrides = budget_overrides()
            rows = summarize([name for name, _ in users], hourly_usd, now=now)
            admins = {name for name, admin in users if admin}
            for row in rows:
                name = row["username"]
                limit = overrides.get(name, default_budget)
                row["budget_exempt"] = name in admins
                row["budget_override_usd"] = overrides.get(name)
                row["budget_limit_usd"] = limit
                row["budget_remaining_usd"] = round(max(0.0, limit - estimated_cost(name, hourly_usd, now=now)), 2)
            self.set_header("Cache-Control", "no-store")
            self.set_header("Content-Type", "application/json")
            self.write(
                {
                    "hourly_usd": hourly_usd,
                    "budget_usd": default_budget,
                    "rows": rows,
                }
            )

    class MyUsageHandler(BaseHandler):
        @web.authenticated
        def get(self):
            username = self.current_user.name
            now = time.time()
            # Reconcile only this user's stale intervals before calculating usage.
            for _, server_name in open_sessions(username=username):
                spawner = self.current_user.spawners.get(server_name)
                if spawner is None or not spawner.active:
                    record_stop(username, server_name, at=now)
            row = summarize([username], hourly_usd, now=now, only_username=username)[0]
            if self.current_user.admin:
                row["budget_exempt"] = True
            else:
                limit = budget_overrides().get(username, default_budget)
                row["budget_exempt"] = False
                row["budget_limit_usd"] = limit
                row["budget_remaining_usd"] = round(
                    max(0.0, limit - estimated_cost(username, hourly_usd, now=now)), 2
                )
            self.set_header("Cache-Control", "no-store")
            self.set_header("Content-Type", "application/json")
            self.write({"usage": row})

    class UsageLimitHandler(BaseHandler):
        @web.authenticated
        @needs_scope("admin:users")
        def post(self):
            if not self.current_user.admin:
                raise web.HTTPError(403)
            try:
                payload = json.loads(self.request.body)
            except (ValueError, TypeError) as exc:
                raise web.HTTPError(400, "Invalid JSON") from exc
            if not isinstance(payload, dict):
                raise web.HTTPError(400, "Expected a JSON object")
            username = payload.get("username")
            if not isinstance(username, str) or not username:
                raise web.HTTPError(400, "username is required")
            user = self.db.query(orm.User).filter_by(name=username).one_or_none()
            if user is None:
                raise web.HTTPError(404, "Hub user does not exist")
            if user.admin:
                raise web.HTTPError(400, "Administrators are exempt")
            try:
                set_budget_override(username, payload["limit_usd"])
            except KeyError as exc:
                raise web.HTTPError(400, "limit_usd is required") from exc
            except ValueError as exc:
                raise web.HTTPError(400, str(exc)) from exc
            self.set_header("Cache-Control", "no-store")
            self.write({"username": username, "budget_limit_usd": budget_overrides().get(username, default_budget)})

    c.JupyterHub.spawner_class = UsageKubeSpawner
    c.JupyterHub.extra_handlers = [
        (r"/admin/usage/limit", UsageLimitHandler),
        (r"/admin/usage", UsageHandler),
        (r"/usage/me", MyUsageHandler),
    ]
    c.JupyterHub.template_paths = ["/usr/local/share/jupyterhub/custom_templates"]
