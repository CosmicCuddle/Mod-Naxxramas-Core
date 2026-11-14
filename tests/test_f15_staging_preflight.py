import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "f15_staging_preflight.py"
EXAMPLE = HERE.parent / "examples" / "f15_staging_manifest.example.json"
spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def ev(value, status="VERIFIED", source="operator-read-only-evidence"):
    return {"status": status, "value": value, "source": source}


def complete():
    return {
        "log_root": "/root/cosmic_core/logs",
        "world": {
            "pm2_name": ev("worldserver"),
            "pm2_manager_log": ev("/root/cosmic_core/logs/pm2.log"),
            "stdout_log": ev("/root/cosmic_core/logs/world-out.log"),
            "stderr_log": ev("/root/cosmic_core/logs/world-err.log"),
        },
        "auth": {
            "tmux_session": ev("authserver"),
            "process_name": ev("authserver"),
            "log": ev("/root/cosmic_core/logs/auth.log"),
        },
        "logging": {
            "overwrite_owner": ev("launcher/rotation owner"),
            "snapshot_hook": ev("pre-overwrite hook"),
        },
        "security": {"run_user": ev("root"), "log_owner": ev("root")},
        "capacity": {
            "free_bytes": ev(2000),
            "projected_30d_bytes": ev(1000),
        },
        "fingerprints": {
            "build_version_source": ev("binary --version output"),
            "source_revision_source": ev("checkout HEAD"),
        },
        "scheduling": {
            "observe_once": ev("daily", "PROPOSED", "staging-plan"),
            "retain_once": ev("daily", "PROPOSED", "staging-plan"),
        },
        "authorizations": {"live_install": False},
    }


class Tests(unittest.TestCase):
    def test_complete_manifest_is_review_ready_not_deployed(self):
        r = preflight.assess(complete())
        self.assertEqual(r["status"], "READY_FOR_OWNER_REVIEW")
        self.assertFalse(r["live_changes_performed"])

    def test_plain_string_is_malformed(self):
        data = complete()
        data["auth"]["log"] = "/root/cosmic_core/logs/auth.log"
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_missing_source_is_malformed(self):
        data = complete()
        data["world"]["pm2_name"] = {"status": "VERIFIED", "value": "worldserver"}
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_host_fact_proposed_is_unknown(self):
        data = complete()
        data["world"]["pm2_name"] = ev("worldserver", "PROPOSED")
        r = preflight.assess(data)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertIn("world.pm2_name", r["unknown"])

    def test_bool_is_not_capacity_integer(self):
        data = complete()
        data["capacity"]["free_bytes"] = ev(True)
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_negative_capacity_blocks(self):
        data = complete()
        data["capacity"]["free_bytes"] = ev(-1)
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_capacity_shortfall_blocks(self):
        data = complete()
        data["capacity"]["free_bytes"] = ev(999)
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_external_log_path_blocks(self):
        data = complete()
        data["auth"]["log"] = ev("/tmp/auth.log")
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_relative_log_path_blocks(self):
        data = complete()
        data["auth"]["log"] = ev("auth.log")
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_noncanonical_log_paths_block(self):
        for path in (
            "/root//cosmic_core/logs/auth.log",
            "/root/cosmic_core/./logs/auth.log",
            "/root/cosmic_core/logs//auth.log",
        ):
            with self.subTest(path=path):
                data = complete()
                data["auth"]["log"] = ev(path)
                self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_noncanonical_log_root_blocks(self):
        data = complete()
        data["log_root"] = "/root//cosmic_core/logs"
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_manifest_cannot_broaden_log_root_to_filesystem_root(self):
        data = complete()
        data["log_root"] = "/"
        data["auth"]["log"] = ev("/tmp/auth.log")
        r = preflight.assess(data)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(any("owner-approved" in x for x in r["blockers"]))

    def test_alternate_log_root_requires_separate_owner_decision(self):
        data = complete()
        data["log_root"] = "/srv/cosmic/logs"
        for section, key in (
            ("world", "pm2_manager_log"),
            ("world", "stdout_log"),
            ("world", "stderr_log"),
            ("auth", "log"),
        ):
            data[section][key] = ev(f"/srv/cosmic/logs/{key}.log")
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_daemon_log_path_equal_to_root_blocks(self):
        for section, key in (
            ("world", "pm2_manager_log"),
            ("world", "stdout_log"),
            ("world", "stderr_log"),
            ("auth", "log"),
        ):
            with self.subTest(section=section, key=key):
                data = complete()
                data[section][key] = ev("/root/cosmic_core/logs")
                self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_strict_descendant_log_path_remains_valid(self):
        data = complete()
        r = preflight.assess(data)
        self.assertEqual(r["status"], "READY_FOR_OWNER_REVIEW")

    def test_unknown_stays_unknown(self):
        data = complete()
        data["auth"]["log"] = {"status": "UNKNOWN", "value": None, "source": ""}
        r = preflight.assess(data)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertIn("auth.log", r["unknown"])

    def test_manifest_cannot_authorize_install(self):
        data = complete()
        data["authorizations"]["live_install"] = True
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_bad_authorizations_shape_blocks(self):
        data = complete()
        data["authorizations"] = "yes"
        self.assertEqual(preflight.assess(data)["status"], "BLOCKED")

    def test_shipped_example_stays_unknown(self):
        with open(EXAMPLE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        r = preflight.assess(data)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertEqual(set(r["unknown"]), set(preflight.REQUIRED))
        self.assertFalse(r["blockers"])


if __name__ == "__main__":
    unittest.main()
