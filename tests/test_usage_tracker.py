import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "k8s"))
from usage_tracker import WINDOW_SECONDS, record_start, record_stop, summarize


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


if __name__ == "__main__":
    unittest.main()
