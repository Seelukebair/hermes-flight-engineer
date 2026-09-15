from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("flight_engineer", ROOT / "flight_engineer.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
FlightEngineer = MODULE.FlightEngineer
FlightEngineerError = MODULE.FlightEngineerError


class FlightEngineerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.profiles = Path(self.temp.name)
        (self.profiles / "daily-driver.json").write_text(json.dumps({
            "id": "daily-driver",
            "label": "Daily Driver",
            "status": "production",
            "artifacts": {"model": {"file": "daily.gguf"}},
            "runtime": {
                "context_length": 262144,
                "parallel_slots": 4,
                "gpu_layers": 999,
                "kv_cache": "q8_0",
                "mmproj_offload": True,
                "batch_size": 256,
                "ubatch_size": 256,
                "image_min_tokens": 256,
                "image_max_tokens": 512,
            },
        }), encoding="utf-8")
        self.engineer = FlightEngineer(
            manager="/manager",
            control="/control",
            profile_dir=self.profiles,
        )

    def tearDown(self):
        self.temp.cleanup()

    @patch.object(FlightEngineer, "_run")
    def test_status_adds_stable_hermes_route(self, run):
        run.return_value = json.dumps({"active_profile": "daily-driver"})
        result = self.engineer.status()
        self.assertEqual(result["stable_route"]["provider"], "gemma4-thinker-local")
        run.assert_called_once_with(["/manager", "status"], timeout=15)

    @patch.object(FlightEngineer, "_run")
    def test_profiles_reads_only_valid_manifest_names(self, run):
        run.return_value = json.dumps({"active_profile": "daily-driver"})
        (self.profiles / "mismatch.json").write_text('{"id":"other"}', encoding="utf-8")
        profiles = self.engineer.profiles()
        self.assertEqual([p["id"] for p in profiles], ["daily-driver"])
        self.assertTrue(profiles[0]["active"])
        self.assertEqual(profiles[0]["kv_cache"], "q8_0")
        self.assertEqual(profiles[0]["model_file"], "daily.gguf")

    def test_use_requires_confirmation_before_subprocess(self):
        with self.assertRaisesRegex(FlightEngineerError, "confirmation"):
            self.engineer.use("daily-driver")

    def test_profile_id_rejects_argument_injection(self):
        with self.assertRaisesRegex(FlightEngineerError, "invalid profile"):
            self.engineer.use("daily-driver --force", confirm_interrupt=True)

    @patch.object(FlightEngineer, "status")
    @patch.object(FlightEngineer, "_run")
    def test_use_calls_only_constrained_control(self, run, status):
        status.return_value = {"active_profile": "daily-driver"}
        result = self.engineer.use("daily-driver", confirm_interrupt=True)
        run.assert_called_once_with(
            ["sudo", "-n", "/control", "use", "daily-driver"],
            timeout=900,
        )
        self.assertEqual(result["active_profile"], "daily-driver")

    @patch("subprocess.run")
    def test_failed_command_is_bounded(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="x" * 2000)
        with self.assertRaises(FlightEngineerError) as caught:
            FlightEngineer._run(["false"])
        self.assertLessEqual(len(str(caught.exception)), 1000)

    @patch.object(FlightEngineer, "profiles")
    @patch.object(FlightEngineer, "_run")
    def test_update_uses_bounded_stdin_json(self, run, profiles):
        profiles.return_value = [{"id": "daily-driver", "label": "Renamed"}]
        result = self.engineer.update("daily-driver", label="Renamed")
        args, kwargs = run.call_args
        self.assertEqual(["sudo", "-n", "/control", "update", "daily-driver"], args[0])
        self.assertEqual({"label": "Renamed"}, json.loads(kwargs["input_text"]))
        self.assertEqual("Renamed", result["label"])

    @patch.object(FlightEngineer, "status")
    @patch.object(FlightEngineer, "_run")
    def test_set_default_is_non_interrupting(self, run, status):
        status.return_value = {"default_profile": "daily-driver"}
        result = self.engineer.set_default("daily-driver")
        run.assert_called_once_with(["sudo", "-n", "/control", "set-default", "daily-driver"], timeout=30)
        self.assertEqual("daily-driver", result["default_profile"])

    @patch.object(FlightEngineer, "_run")
    def test_runtime_update_uses_only_bounded_control_action(self, run):
        run.return_value = json.dumps({"stage": "staged", "tested": False})
        result = self.engineer.runtime_update("daily-driver", "stage")
        run.assert_called_once_with(
            ["sudo", "-n", "/control", "runtime-stage", "daily-driver"],
            timeout=3600,
        )
        self.assertEqual("staged", result["stage"])

    def test_runtime_update_rejects_unknown_action(self):
        with self.assertRaisesRegex(FlightEngineerError, "invalid runtime update action"):
            self.engineer.runtime_update("daily-driver", "latest")

    def test_slot_context_tokens_combines_prompt_and_generation(self):
        slot = {
            "n_prompt_tokens": 6400,
            "next_token": [{"n_decoded": 900}],
        }
        self.assertEqual(7300, self.engineer._slot_context_tokens(slot))

    def test_slot_context_tokens_prefers_runtime_occupancy(self):
        slot = {
            "n_past": 8100,
            "n_prompt_tokens": 6400,
            "next_token": [{"n_decoded": 900}],
        }
        self.assertEqual(8100, self.engineer._slot_context_tokens(slot))


if __name__ == "__main__":
    unittest.main()
