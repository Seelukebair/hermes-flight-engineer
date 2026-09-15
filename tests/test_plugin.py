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

    def test_tool_and_cli_expose_default_selection(self):
        context = FakeContext()
        PLUGIN.register(context)
        actions = context.tool["schema"]["parameters"]["properties"]["action"]["enum"]
        self.assertIn("set_default", actions)
        self.assertIn("list_jailbreaks", actions)
        self.assertIn("assign_jailbreak", actions)
        content = (ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('commands.add_parser("set-default"', content)

    def test_dashboard_and_wrapper_keep_bounded_controls(self):
        dashboard = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")
        wrapper = (ROOT / "deploy" / "flight-engineer-control").read_text(encoding="utf-8")
        self.assertIn("Max concurrent inference", dashboard)
        self.assertIn("Live inference", dashboard)
        self.assertIn("Make default", dashboard)
        self.assertIn("Jailbreak methods", dashboard)
        self.assertIn("Think formats are not standardized", dashboard)
        self.assertIn("Enter the actual injection text", dashboard)
        self.assertIn("Save to library", dashboard)
        self.assertIn("onAssignJailbreak", dashboard)
        self.assertIn("flight-engineer-type-tag", dashboard)
        self.assertIn("Search saved methods", dashboard)
        self.assertIn("flight-engineer-method-filters", dashboard)
        self.assertIn("flight-engineer-method-results", dashboard)
        self.assertIn("visibleTypes", dashboard)
        self.assertIn('"aria-pressed": String(enabled)', dashboard)
        self.assertIn("Saved library entries", dashboard)
        self.assertNotIn("activeType", dashboard)
        self.assertIn("function EditableText", dashboard)
        self.assertIn('ariaLabel: "profile name"', dashboard)
        self.assertIn("Cancel edit", dashboard)
        self.assertIn("Create editable tuning copy", dashboard)
        self.assertIn("Internal profile id", dashboard)
        self.assertIn("Make default after reboot", dashboard)
        self.assertIn("Reload active profile", dashboard)
        self.assertIn("Check & stage", dashboard)
        self.assertIn("Test candidate", dashboard)
        self.assertIn("Promote tested", dashboard)
        self.assertNotIn("Duplicate for tuning", dashboard)
        self.assertNotIn('}, "Save name")', dashboard)
        self.assertNotIn('profile.active ? "active" : profile.status', dashboard)
        self.assertIn('exec "$MANAGER" update "$profile"', wrapper)
        self.assertIn("runtime-status|runtime-stage|runtime-test|runtime-promote", wrapper)
        self.assertNotIn("eval ", wrapper)


if __name__ == "__main__":
    unittest.main()
