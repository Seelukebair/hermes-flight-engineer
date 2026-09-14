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
        self.store.create("gemma-balanced", "Gemma balanced")
        self.store.update("gemma-balanced", profile_ids=["smart-31b"])
        self.store.set_secret("gemma-balanced", "assistant_prefill", "Start here")
        public = self.store.configure(enabled=True, profile_id="smart-31b", recipe_id="gemma-balanced")
        self.assertTrue(public["recipes"][0]["techniques"]["assistant_prefill"])
        self.assertNotIn("Start here", str(public))
        self.assertEqual(self.store.resolve("smart-31b"), {"assistant_prefill": "Start here"})
        self.assertEqual(self.store.resolve("daily-driver"), {})
        self.store.set_secret("gemma-balanced", "assistant_prefill", "")
        self.assertEqual(self.store.resolve("smart-31b"), {})

    def test_assignment_requires_compatibility(self):
        self.store.create("gemma-balanced", "Gemma balanced")
        with self.assertRaisesRegex(JailbreakError, "compatible"):
            self.store.configure(profile_id="smart-31b", recipe_id="gemma-balanced")

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
        self.store.create("temporary", "Temporary")
        self.store.update("temporary", profile_ids=["smart-31b"])
        self.store.set_secret("temporary", "thinking_prefill", "private")
        self.store.configure(enabled=True, profile_id="smart-31b", recipe_id="temporary")
        result = self.store.delete("temporary")
        self.assertEqual(result["recipes"], [])
        self.assertEqual(result["assignments"], {})
        self.assertEqual(self.secrets.values, {})


if __name__ == "__main__":
    unittest.main()
