"""Unit tests for filesystem storage_utils."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import storage_utils


class StorageUtilsTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.env_patcher = mock.patch.dict(
            os.environ, {"BUDGET_STORAGE_ROOT": str(self.root)}
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        self._tmpdir.cleanup()

    def test_write_and_read_text(self):
        key = "alice/uploads/note.txt"
        storage_utils.write_text(key, "hello")
        self.assertEqual(storage_utils.read_text(key), "hello")
        self.assertTrue(storage_utils.exists(key))

    def test_write_and_read_bytes(self):
        key = "alice/uploads/data.bin"
        storage_utils.write_bytes(key, b"\x00\x01")
        self.assertEqual(storage_utils.read_bytes(key), b"\x00\x01")

    def test_missing_returns_none(self):
        self.assertIsNone(storage_utils.read_bytes("nobody/missing.txt"))
        self.assertIsNone(storage_utils.read_text("nobody/missing.txt"))
        self.assertIsNone(storage_utils.load_json("nobody/missing.json"))
        self.assertFalse(storage_utils.exists("nobody/missing.txt"))

    def test_save_and_load_json(self):
        key = "bob/configs/bob_config.json"
        payload = {"search_strings": ["Food"]}
        storage_utils.save_json(payload, key)
        self.assertEqual(storage_utils.load_json(key), payload)

    def test_copy_file(self):
        src = self.root / "source.csv"
        src.write_text("a,b\n1,2\n", encoding="utf-8")
        key = "carol/uploads/source.csv"
        storage_utils.copy_file(str(src), key)
        self.assertEqual(storage_utils.read_bytes(key), src.read_bytes())

    def test_list_with_prefix(self):
        storage_utils.write_text("dave/uploads/a.csv", "a")
        storage_utils.write_text("dave/uploads/b.csv", "b")
        storage_utils.write_text("dave/configs/dave_config.json", "{}")
        listed = storage_utils.list_with_prefix("dave/uploads/")
        self.assertEqual(listed, ["dave/uploads/a.csv", "dave/uploads/b.csv"])

    def test_delete(self):
        key = "erin/uploads/gone.csv"
        storage_utils.write_text(key, "x")
        self.assertTrue(storage_utils.delete(key))
        self.assertFalse(storage_utils.exists(key))
        self.assertFalse(storage_utils.delete(key))

    def test_path_helpers(self):
        self.assertEqual(storage_utils.get_user_prefix("mike"), "mike/")
        self.assertEqual(storage_utils.get_config_prefix("mike"), "mike/configs/")
        self.assertEqual(storage_utils.get_uploads_prefix("mike"), "mike/uploads/")
        self.assertEqual(
            storage_utils.get_path_for_config("mike", "config"),
            "mike/configs/mike_config.json",
        )
        self.assertEqual(
            storage_utils.get_path_for_upload("mike", "t.csv"),
            "mike/uploads/t.csv",
        )

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            storage_utils.write_text("../escape.txt", "nope")
        with self.assertRaises(ValueError):
            storage_utils.read_bytes("alice/../../etc/passwd")
        with self.assertRaises(ValueError):
            storage_utils.list_with_prefix("../")

    def test_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            storage_utils.write_text("", "nope")


if __name__ == "__main__":
    unittest.main()
