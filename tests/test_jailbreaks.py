from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jailbreaks import JailbreakError, JailbreakStore
from prefill_proxy import apply_injection


class MemorySecrets:
    def __init__(self):
        self.values = {}

    def set(self, name, value):
        self.values[name] = value

    def get(self, name):
        return self.values.get(name, "")

    def delete(self, name):
        self.values.pop(name, None)


class JailbreakTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.secrets = MemorySecrets()
        self.store = JailbreakStore(Path(self.temp.name) / "jailbreaks.json", self.secrets)

    def tearDown(self):
        self.temp.cleanup()

    def test_write_only_public_shape_and_explicit_assignment(self):
        self.store.create("gemma-balanced", "Gemma balanced", "assistant_prefill")
        self.store.update("gemma-balanced", profile_ids=["smart-31b"])
        self.store.set_secret("gemma-balanced", "assistant_prefill", "Start here")
        public = self.store.configure(enabled=True, profile_id="smart-31b", recipe_id="gemma-balanced")
        self.assertTrue(public["recipes"][0]["configured"])
        self.assertNotIn("Start here", str(public))
        self.assertEqual(self.store.resolve("smart-31b"), {"assistant_prefill": "Start here"})
        self.assertEqual(self.store.resolve("daily-driver"), {})
        self.store.set_secret("gemma-balanced", "assistant_prefill", "")
        self.assertEqual(self.store.resolve("smart-31b"), {})

    def test_assignment_establishes_explicit_compatibility(self):
        self.store.create("gemma-balanced", "Gemma balanced", "assistant_prefill")
        state = self.store.configure(profile_id="smart-31b", recipe_id="gemma-balanced")
        self.assertEqual(state["assignments"]["smart-31b"]["assistant_prefill"], "gemma-balanced")
        self.assertEqual(state["recipes"][0]["profile_ids"], ["smart-31b"])

    def test_duplicate_generated_id_gets_numeric_suffix(self):
        self.assertEqual(self.store.create("same-name", "First", "system_framing")["id"], "same-name")
        self.assertEqual(self.store.create("same-name", "Second", "system_framing")["id"], "same-name-2")
        self.assertEqual(self.store.create("same-name", "Third", "system_framing")["id"], "same-name-3")

    def test_prompt_validation_allows_json_text_and_rejects_control_bytes(self):
        self.store.create("safe", "Safe", "system_framing")
        value = 'Keep {"tool": "value"} and quoted text.\nUnicode: cafe'
        self.store.set_secret("safe", "system_framing", value)
        self.store.configure(enabled=True, profile_id="smart-31b", recipe_id="safe")
        self.assertEqual(self.store.resolve("smart-31b")["system_framing"], value)
        with self.assertRaisesRegex(JailbreakError, "control characters"):
            self.store.set_secret("safe", "system_framing", "bad\x00value")

    def test_each_type_has_an_independent_profile_assignment(self):
        for recipe_id, kind, value in (
            ("system-one", "system_framing", "system"),
            ("thinking-one", "thinking_prefill", "thinking"),
            ("assistant-one", "assistant_prefill", "assistant"),
        ):
            self.store.create(recipe_id, recipe_id, kind)
            self.store.update(recipe_id, profile_ids=["smart-31b"])
            self.store.set_secret(recipe_id, kind, value)
            self.store.configure(profile_id="smart-31b", recipe_id=recipe_id)
        self.store.configure(enabled=True)
        self.assertEqual(self.store.resolve("smart-31b"), {
            "system_framing": "system", "thinking_prefill": "thinking", "assistant_prefill": "assistant",
        })
        self.store.configure(profile_id="smart-31b", technique="thinking_prefill")
        self.assertEqual(self.store.resolve("smart-31b"), {
            "system_framing": "system", "assistant_prefill": "assistant",
        })

    def test_assigning_same_type_replaces_only_that_type(self):
        for recipe_id, kind in (
            ("system-one", "system_framing"),
            ("system-two", "system_framing"),
            ("assistant-one", "assistant_prefill"),
        ):
            self.store.create(recipe_id, recipe_id, kind)
            self.store.configure(profile_id="smart-31b", recipe_id=recipe_id)
        assignments = self.store.list()["assignments"]["smart-31b"]
        self.assertEqual(assignments["system_framing"], "system-two")
        self.assertEqual(assignments["assistant_prefill"], "assistant-one")

    def test_injection_keeps_types_separate(self):
        payload = {"messages": [{"role": "system", "content": "base"}, {"role": "user", "content": "hello"}]}
        changed = apply_injection(payload, {
            "system_framing": "frame", "thinking_prefill": "consider", "assistant_prefill": "Certainly",
        })
        self.assertTrue(changed)
        self.assertEqual(payload["messages"][0]["content"], "base\n\nframe")
        self.assertEqual(payload["messages"][-1], {
            "role": "assistant", "content": "Certainly", "reasoning_content": "consider",
        })

    def test_tool_continuation_is_never_injected(self):
        payload = {"messages": [{"role": "tool", "content": "result"}]}
        self.assertFalse(apply_injection(payload, {"assistant_prefill": "x"}))

    def test_delete_removes_assignments_and_secrets(self):
        self.store.create("temporary", "Temporary", "thinking_prefill")
        self.store.update("temporary", profile_ids=["smart-31b"])
        self.store.set_secret("temporary", "thinking_prefill", "private")
        self.store.configure(enabled=True, profile_id="smart-31b", recipe_id="temporary")
        result = self.store.delete("temporary")
        self.assertEqual(result["recipes"], [])
        self.assertEqual(result["assignments"], {})
        self.assertEqual(self.secrets.values, {})

    def test_clone_copies_metadata_and_protected_value_without_exposing_it(self):
        self.store.create("source", "Source", "system_framing")
        self.store.set_secret("source", "system_framing", "private multiline\nvalue")
        cloned = self.store.clone("source", "copy", "Copy")
        self.assertTrue(cloned["configured"])
        self.assertNotIn("private", str(cloned))
        self.store.update("copy", profile_ids=["smart-31b"])
        self.store.configure(enabled=True, profile_id="smart-31b", recipe_id="copy")
        self.assertEqual(self.store.resolve("smart-31b")["system_framing"], "private multiline\nvalue")


if __name__ == "__main__":
    unittest.main()
