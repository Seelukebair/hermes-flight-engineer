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
            "runtime": {
                "context_length": 262144,
                "parallel_slots": 4,
                "gpu_layers": 999,
                "kv_cache": "q8_0",
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


if __name__ == "__main__":
    unittest.main()

