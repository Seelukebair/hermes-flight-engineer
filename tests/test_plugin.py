from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "flight_engineer_plugin",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
PLUGIN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PLUGIN
assert SPEC.loader is not None
SPEC.loader.exec_module(PLUGIN)


class FakeContext:
    def __init__(self):
        self.tool = None
        self.skill = None
        self.hook = None
        self.cli = None

    def register_tool(self, **kwargs):
        self.tool = kwargs

    def register_skill(self, *args):
        self.skill = args

    def register_hook(self, *args):
        self.hook = args

    def register_cli_command(self, **kwargs):
        self.cli = kwargs


class PluginTests(unittest.TestCase):
    def test_backend_language_surfaces_flight_engineer_context(self):
        result = PLUGIN._profile_intent_context("Switch to our smarter backend profile")
        self.assertIn("flight_engineer", result["context"])
        self.assertIsNone(PLUGIN._profile_intent_context("Turn on the kitchen lights"))

    def test_registers_documented_surfaces(self):
        context = FakeContext()
        PLUGIN.register(context)
        self.assertEqual(context.tool["name"], "flight_engineer")
        self.assertEqual(context.skill[0], "flight-engineer")
        self.assertEqual(context.hook[0], "pre_llm_call")
        self.assertEqual(context.cli["name"], "flight-engineer")


if __name__ == "__main__":
    unittest.main()

