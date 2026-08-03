"""Unit tests for category editor validation and path-based mutations."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ui.category_editor import (
    add_category,
    add_keyword,
    delete_item,
    get_children_list,
    normalize_search_strings,
    rename_category,
    update_keyword,
    validate_search_strings,
)


_ASSETS = Path(__file__).resolve().parents[1] / "src" / "assets"


class ValidateSearchStringsTests(unittest.TestCase):
    def test_accepts_flat_and_nested(self):
        data = [
            {"Gas": ["SUNOCO"]},
            "AMAZON",
            {
                "Transportation": [
                    {"Gas": ["SHELL"]},
                    {"Car": [{"Tolls": ["EZPASS"]}]},
                ]
            },
        ]
        ok, msg = validate_search_strings(data)
        self.assertTrue(ok, msg)
        self.assertEqual(msg, "")

    def test_rejects_non_list_root(self):
        ok, msg = validate_search_strings({"Gas": ["SUNOCO"]})
        self.assertFalse(ok)
        self.assertIn("list", msg.lower())

    def test_rejects_multi_key_category(self):
        ok, msg = validate_search_strings([{"A": [], "B": []}])
        self.assertFalse(ok)
        self.assertIn("exactly one", msg.lower())

    def test_rejects_empty_category_name(self):
        ok, msg = validate_search_strings([{"": ["x"]}])
        self.assertFalse(ok)
        self.assertIn("non-empty", msg.lower())

    def test_rejects_non_list_children(self):
        ok, msg = validate_search_strings([{"Gas": "SUNOCO"}])
        self.assertFalse(ok)
        self.assertIn("list", msg.lower())

    def test_rejects_invalid_item_type(self):
        ok, msg = validate_search_strings([123])
        self.assertFalse(ok)

    def test_example_nested_config(self):
        payload = json.loads((_ASSETS / "example_nested_config.json").read_text(encoding="utf-8"))
        ok, msg = validate_search_strings(payload["search_strings"])
        self.assertTrue(ok, msg)


class MutationHelperTests(unittest.TestCase):
    def setUp(self):
        self.root = [
            {
                "Transportation": [
                    {"Gas": ["SUNOCO", "SHELL"]},
                    "MISC",
                ]
            },
            "AMAZON",
        ]

    def test_get_children_list_root_and_nested(self):
        self.assertIs(get_children_list(self.root, []), self.root)
        children = get_children_list(self.root, [0])
        self.assertEqual(len(children), 2)
        gas_children = get_children_list(self.root, [0, 0])
        self.assertEqual(gas_children, ["SUNOCO", "SHELL"])

    def test_add_category_and_keyword_at_paths(self):
        add_category(self.root, [], "Pets")
        self.assertEqual(self.root[-1], {"Pets": []})
        add_keyword(self.root, [2], "CHEWY")
        self.assertEqual(get_children_list(self.root, [2]), ["CHEWY"])
        add_category(self.root, [0], "Parking")
        self.assertEqual(get_children_list(self.root, [0])[-1], {"Parking": []})

    def test_rename_category(self):
        rename_category(self.root, [0], 0, "Fuel")
        self.assertEqual(list(get_children_list(self.root, [0])[0].keys()), ["Fuel"])
        self.assertEqual(get_children_list(self.root, [0, 0]), ["SUNOCO", "SHELL"])

    def test_update_and_delete_keyword(self):
        update_keyword(self.root, [0, 0], 0, "EXXON")
        self.assertEqual(get_children_list(self.root, [0, 0])[0], "EXXON")
        delete_item(self.root, [0, 0], 1)
        self.assertEqual(get_children_list(self.root, [0, 0]), ["EXXON"])

    def test_delete_category(self):
        delete_item(self.root, [0], 0)
        self.assertEqual(get_children_list(self.root, [0]), ["MISC"])

    def test_add_rejects_empty_names(self):
        with self.assertRaises(ValueError):
            add_category(self.root, [], "  ")
        with self.assertRaises(ValueError):
            add_keyword(self.root, [], "")

    def test_normalize_strips_and_drops_empty_keywords(self):
        messy = [{" Gas ": [" SUNOCO ", "  ", "SHELL "]}, " AMAZON "]
        normalized = normalize_search_strings(messy)
        self.assertEqual(
            normalized,
            [{"Gas": ["SUNOCO", "SHELL"]}, "AMAZON"],
        )

    def test_mutations_preserve_example_round_trip_shape(self):
        payload = json.loads((_ASSETS / "example_nested_config.json").read_text(encoding="utf-8"))
        draft = copy.deepcopy(payload["search_strings"])
        add_keyword(draft, [], "NEW_ROOT_KW")
        delete_item(draft, [], len(draft) - 1)
        self.assertEqual(draft, payload["search_strings"])
        ok, msg = validate_search_strings(draft)
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
