import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tornado import web


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "k8s"))
from usage_tracker import (
    WINDOW_SECONDS, budget_overrides, estimated_cost, record_start, record_stop,
    set_budget_override, summarize,
)
import usage_tracker


class UsageTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tempdir.name) / "usage.sqlite")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_completed_and_running_sessions_and_zero_usage_user(self):
        now = 2_000_000_000.0
        record_start("alice", at=now - 7200, path=self.db)
        record_stop("alice", at=now - 3600, path=self.db)
        record_start("alice", at=now - 1800, path=self.db)
        rows = summarize(["alice", "bob"], 1.35, now=now, path=self.db)
        self.assertEqual(rows[0]["username"], "alice")
        self.assertEqual(rows[0]["active"], 1)
        self.assertEqual(rows[0]["hours_30d"], 1.5)
        self.assertEqual(rows[0]["cost_30d_usd"], 2.03)
        self.assertEqual(rows[1]["username"], "bob")
        self.assertEqual(rows[1]["cost_all_usd"], 0)

    def test_rolling_window_and_duplicate_start(self):
        now = 2_000_000_000.0
        record_start("alice", at=now - WINDOW_SECONDS - 3600, path=self.db)
        record_start("alice", at=now - 1800, path=self.db)
        rows = summarize([], 2.0, now=now, path=self.db)
        self.assertEqual(rows[0]["hours_30d"], WINDOW_SECONDS / 3600)
        self.assertEqual(rows[0]["active"], 1)
        record_stop("alice", at=now, path=self.db)
        rows = summarize([], 2.0, now=now + 3600, path=self.db)
        self.assertEqual(rows[0]["active"], 0)
        self.assertEqual(rows[0]["hours_all"], WINDOW_SECONDS / 3600 + 1)

    def test_old_session_is_excluded_from_last_30_days(self):
        now = 2_000_000_000.0
        record_start("alice", at=now - WINDOW_SECONDS - 7200, path=self.db)
        record_stop("alice", at=now - WINDOW_SECONDS - 3600, path=self.db)
        row = summarize(["alice"], 1.35, now=now, path=self.db)[0]
        self.assertEqual(row["hours_30d"], 0)
        self.assertEqual(row["hours_all"], 1)

    def test_unrounded_all_time_cost_includes_active_and_old_sessions(self):
        now = 2_000_000_000.0
        record_start("alice", at=now - WINDOW_SECONDS - 3600, path=self.db)
        record_stop("alice", at=now - WINDOW_SECONDS, path=self.db)
        record_start("alice", at=now - 149 * 3600, path=self.db)
        self.assertEqual(estimated_cost("alice", 1, now=now, path=self.db), 150)
        self.assertEqual(estimated_cost("bob", 1, now=now, path=self.db), 0)
        self.assertLess(estimated_cost("alice", 1, now=now - 1, path=self.db), 150)
        self.assertGreaterEqual(estimated_cost("alice", 1, now=now, path=self.db), 150)

    def test_individual_override_persists_and_resets(self):
        set_budget_override("alice", 200, path=self.db)
        set_budget_override("bob", 75.25, path=self.db)
        self.assertEqual(budget_overrides(path=self.db), {"alice": 200, "bob": 75.25})
        set_budget_override("alice", 250, path=self.db)
        self.assertEqual(budget_overrides(path=self.db)["alice"], 250)
        set_budget_override("alice", None, path=self.db)
        self.assertEqual(budget_overrides(path=self.db), {"bob": 75.25})

    def test_reject_invalid_overrides(self):
        for limit in (0, -1, 0.001, 1.234, float("nan"), float("inf"), True, "bad"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                set_budget_override("alice", limit, path=self.db)
        self.assertEqual(budget_overrides(path=self.db), {})

    def test_spawner_blocks_at_limit_and_uses_individual_override(self):
        class FakeSpawner:
            def __init__(self):
                self.user = types.SimpleNamespace(name="alice", admin=False)
                self.name = ""
                self.starts = 0

            async def start(self):
                self.starts += 1
                return "started"

        jupyterhub = types.ModuleType("jupyterhub")
        jupyterhub.orm = types.SimpleNamespace(User=object())
        handlers = types.ModuleType("jupyterhub.handlers")
        handler_base = types.ModuleType("jupyterhub.handlers.base")
        handler_base.BaseHandler = object
        scopes = types.ModuleType("jupyterhub.scopes")
        scopes.needs_scope = lambda scope: lambda method: method
        kubespawner = types.ModuleType("kubespawner")
        kubespawner.KubeSpawner = FakeSpawner
        modules = {
            "jupyterhub": jupyterhub, "jupyterhub.handlers": handlers,
            "jupyterhub.handlers.base": handler_base,
            "jupyterhub.scopes": scopes, "kubespawner": kubespawner,
        }
        config = types.SimpleNamespace(JupyterHub=types.SimpleNamespace())
        with patch.dict(sys.modules, modules), patch.dict("os.environ", {"TPU_HOURLY_USD": "1", "STUDENT_TPU_BUDGET_USD": "150"}):
            usage_tracker.configure(config)
        spawner = config.JupyterHub.spawner_class()
        now = 2_000_000_000.0
        record_start("alice", at=now - 150 * 3600, path=self.db)
        with patch.object(usage_tracker, "estimated_cost", side_effect=lambda name, rate: estimated_cost(name, rate, now=now, path=self.db)), \
             patch.object(usage_tracker, "budget_overrides", side_effect=lambda: budget_overrides(path=self.db)), \
             patch.object(usage_tracker, "record_start"):
            with self.assertRaises(web.HTTPError) as caught:
                asyncio.run(spawner.start())
            self.assertEqual(caught.exception.status_code, 403)
            self.assertEqual(spawner.starts, 0)
            set_budget_override("alice", 200, path=self.db)
            self.assertEqual(asyncio.run(spawner.start()), "started")
            self.assertEqual(spawner.starts, 1)


if __name__ == "__main__":
    unittest.main()
