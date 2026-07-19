"""Unit tests for GCS→NFS migration path helpers (no network)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.migrate_gcs_to_nfs import destination_path, should_skip, summarize_plan


class MigrationHelpersTests(unittest.TestCase):
    def test_destination_path(self):
        root = Path("/srv/budget-analysis")
        self.assertEqual(
            destination_path(root, "alice/configs/alice_config.json"),
            root / "alice/configs/alice_config.json",
        )

    def test_destination_path_rejects_traversal(self):
        with self.assertRaises(ValueError):
            destination_path(Path("/data"), "../etc/passwd")

    def test_should_skip_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "alice" / "uploads" / "a.csv"
            dest.parent.mkdir(parents=True)
            dest.write_text("x", encoding="utf-8")
            self.assertTrue(should_skip(dest, True))
            self.assertFalse(should_skip(dest, False))
            missing = Path(tmp) / "missing.csv"
            self.assertFalse(should_skip(missing, True))

    def test_summarize_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "bob" / "uploads" / "old.csv"
            existing.parent.mkdir(parents=True)
            existing.write_text("old", encoding="utf-8")

            to_copy, to_skip, invalid = summarize_plan(
                [
                    "bob/uploads/old.csv",
                    "bob/uploads/new.csv",
                    "bob/configs/",
                    "../bad",
                ],
                root,
                skip_existing=True,
            )
            self.assertEqual(to_copy, ["bob/uploads/new.csv"])
            self.assertIn("bob/uploads/old.csv", to_skip)
            self.assertIn("bob/configs/", to_skip)
            self.assertEqual(invalid, ["../bad"])


if __name__ == "__main__":
    unittest.main()
