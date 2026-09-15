from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime_maintenance", ROOT / "deploy" / "runtime-maintenance.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RuntimeMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.profiles = root / "profiles"
        self.profiles.mkdir()
        self.state = root / "runtime-update.json"
        self.backups = root / "backups"
        self.profile = {
            "schema_version": 1,
            "id": "daily-driver",
            "label": "Daily Driver",
            "status": "production",
            "image": "ghcr.io/ggml-org/llama.cpp@sha256:" + "1" * 64,
            "runtime_update_channel": "ghcr.io/ggml-org/llama.cpp:server-cuda13",
            "artifacts": {},
            "runtime": {},
        }
        (self.profiles / "daily-driver.json").write_text(json.dumps(self.profile), encoding="utf-8")
        self.old_values = (MODULE.PROFILE_DIR, MODULE.STATE_FILE, MODULE.BACKUP_DIR, MODULE.MANAGER)
        MODULE.PROFILE_DIR, MODULE.STATE_FILE, MODULE.BACKUP_DIR, MODULE.MANAGER = self.profiles, self.state, self.backups, "/manager"

    def tearDown(self):
        MODULE.PROFILE_DIR, MODULE.STATE_FILE, MODULE.BACKUP_DIR, MODULE.MANAGER = self.old_values
        self.temp.cleanup()

    @staticmethod
    def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    def test_stage_resolves_digest_and_checks_required_flags(self):
        candidate = "ghcr.io/ggml-org/llama.cpp@sha256:" + "2" * 64
        metadata = {"RepoDigests": [candidate], "Config": {"Labels": {"org.opencontainers.image.version": "b12000"}}}
        help_text = " ".join(MODULE.REQUIRED_FLAGS)

        def fake_run(argv, **_kwargs):
            if argv[:2] == ["docker", "pull"]:
                return self._completed()
            if "image" in argv and "inspect" in argv:
                return self._completed(json.dumps(metadata))
            return self._completed(help_text)

        with patch.object(MODULE, "_run", side_effect=fake_run):
            result = MODULE.stage("daily-driver")
        self.assertEqual("staged", result["stage"])
        self.assertEqual(candidate, result["candidate"]["image"])
        self.assertFalse(result["tested"])

    def test_promote_requires_test_and_backs_up_profile(self):
        candidate = "ghcr.io/ggml-org/llama.cpp@sha256:" + "2" * 64
        MODULE._atomic_json(self.state, {
            "profile_id": "daily-driver",
            "profile_fingerprint": MODULE._fingerprint(self.profile),
            "candidate": {"image": candidate, "version": "b12000"},
            "stage": "staged",
            "tested": True,
        })
        with patch.object(MODULE, "_image_metadata", return_value={"image": candidate, "version": "b12000"}):
            result = MODULE.promote("daily-driver")
        saved = json.loads((self.profiles / "daily-driver.json").read_text(encoding="utf-8"))
        self.assertEqual(candidate, saved["image"])
        self.assertEqual("promoted", result["stage"])
        self.assertEqual(1, len(list(self.backups.glob("*.json"))))

    def test_live_test_uses_temporary_profile_and_restores_original(self):
        candidate = "ghcr.io/ggml-org/llama.cpp@sha256:" + "2" * 64
        MODULE._atomic_json(self.state, {
            "profile_id": "daily-driver",
            "profile_fingerprint": MODULE._fingerprint(self.profile),
            "candidate": {"image": candidate, "version": "b12000"},
            "stage": "staged",
            "tested": False,
        })
        with patch.object(MODULE, "_run", return_value=self._completed()) as run, \
                patch.object(MODULE, "_image_metadata", return_value={"image": self.profile["image"], "version": "old"}):
            result = MODULE.test("daily-driver")
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(["/manager", "use", MODULE.TEST_PROFILE], calls[0])
        self.assertEqual(["/manager", "use", "daily-driver"], calls[1])
        self.assertFalse((self.profiles / f"{MODULE.TEST_PROFILE}.json").exists())
        self.assertTrue(result["tested"])


if __name__ == "__main__":
    unittest.main()
