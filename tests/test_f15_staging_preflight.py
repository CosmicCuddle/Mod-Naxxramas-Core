import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "f15_staging_preflight.py"
spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def complete():
    return {
        "log_root": "/root/cosmic_core/logs",
        "world": {
            "pm2_name": "worldserver",
            "pm2_manager_log": "/root/cosmic_core/logs/pm2.log",
            "stdout_log": "/root/cosmic_core/logs/world-out.log",
            "stderr_log": "/root/cosmic_core/logs/world-err.log",
        },
        "auth": {
            "tmux_session": "authserver",
            "process_name": "authserver",
            "log": "/root/cosmic_core/logs/auth.log",
        },
        "logging": {
            "overwrite_owner": "verified launcher/rotation owner",
            "snapshot_hook": "pre-overwrite hook",
        },
        "security": {"run_user": "verified", "log_owner": "verified"},
        "capacity": {"free_bytes": 2000, "projected_30d_bytes": 1000},
        "fingerprints": {
            "build_version_source": "verified",
            "source_revision_source": "verified",
        },
        "scheduling": {"observe_once": "proposed", "retain_once": "proposed"},
        "authorizations": {"live_install": False},
    }


class Tests(unittest.TestCase):
    def test_complete_manifest_is_review_ready_not_deployed(self):
        r = preflight.assess(complete())
        self.assertEqual(r["status"], "READY_FOR_OWNER_REVIEW")
        self.assertFalse(r["live_changes_performed"])

    def test_unknown_stays_unknown(self):
        data = complete()
        del data["auth"]["log"]
        r = preflight.assess(data)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertIn("auth.log", r["unknown"])

    def test_external_log_path_blocks(self):
        data = complete()
        data["world"]["stderr_log"] = "/tmp/world.err"
        r = preflight.assess(data)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(any("outside log_root" in x for x in r["blockers"]))

    def test_capacity_shortfall_blocks(self):
        data = complete()
        data["capacity"] = {"free_bytes": 999, "projected_30d_bytes": 1000}
        r = preflight.assess(data)
        self.assertEqual(r["status"], "BLOCKED")

    def test_manifest_cannot_authorize_install(self):
        data = complete()
        data["authorizations"]["live_install"] = True
        r = preflight.assess(data)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(any("self-authorize" in x for x in r["blockers"]))

    def test_snapshot_hook_without_owner_blocks(self):
        data = complete()
        data["logging"]["overwrite_owner"] = "UNKNOWN"
        r = preflight.assess(data)
        self.assertEqual(r["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
