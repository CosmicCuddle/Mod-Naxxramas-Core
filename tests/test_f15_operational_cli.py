import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import f15_operational_cli as cli

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=31)


class SequenceRunner:
    def __init__(self, responses):
        self.responses = {tuple(k): list(v) for k, v in responses.items()}
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        queue = self.responses.get(tuple(argv))
        if not queue:
            raise AssertionError(f"unexpected/exhausted command {argv}")
        return queue.pop(0)


def pm2(pid, restarts, out_log, err_log, exit_code=0):
    return json.dumps([{
        "name": "worldserver",
        "pid": pid,
        "pm_id": 0,
        "pm2_env": {
            "status": "online",
            "restart_time": restarts,
            "unstable_restarts": 0,
            "pm_uptime": 1000 + restarts,
            "created_at": 900,
            "exit_code": exit_code,
            "pm_out_log_path": str(out_log),
            "pm_err_log_path": str(err_log),
        },
    }])


class OperationalCliTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.logs = self.base / "logs"
        self.logs.mkdir()
        self.crash = self.logs / "Crash Logs"
        self.archive = self.logs / "Archived Logs"
        self.state = self.logs / ".f15-state"

    def test_world_observe_reads_logs_and_emits_after_restart_without_modifying_sources(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out-before\n")
        err.write_text("err-before\n")
        mgr.write_text("baseline\n")
        before = {p: p.read_bytes() for p in (out, err, mgr)}

        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        first = cli.observe_once(
            self.state, self.crash,
            world_pm2_name="worldserver",
            pm2_manager_log=mgr,
            runner=runner,
            now=NOW,
        )
        self.assertEqual(first, [])

        mgr.write_text(
            "App [worldserver:0] exited with code [0] via signal [SIGSEGV]\n"
        )
        second = cli.observe_once(
            self.state, self.crash,
            world_pm2_name="worldserver",
            pm2_manager_log=mgr,
            runner=runner,
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(second[0]["classification"], "FATAL_SIGNAL_EXIT")
        self.assertEqual(len(list(self.crash.glob("*Worldserver*.txt"))), 1)
        self.assertEqual(out.read_bytes(), before[out])
        self.assertEqual(err.read_bytes(), before[err])

    def test_observe_without_target_refused_before_commands(self):
        runner = SequenceRunner({})
        with self.assertRaises(cli.Refused):
            cli.observe_once(self.state, self.crash, runner=runner, now=NOW)
        self.assertEqual(runner.calls, [])

    def test_snapshot_before_overwrite_preserves_active_logs(self):
        world = self.logs / "world.log"
        auth = self.logs / "auth.log"
        world.write_text("world old")
        auth.write_text("auth old")
        before = {world: world.read_bytes(), auth: auth.read_bytes()}
        pairs = cli.snapshot_before_overwrite(self.logs, self.archive, NOW)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(world.read_bytes(), before[world])
        self.assertEqual(auth.read_bytes(), before[auth])
        self.assertTrue(all(data.exists() and manifest.exists() for data, manifest in pairs))

    def test_snapshot_archive_must_be_direct_child(self):
        with self.assertRaises(cli.Refused):
            cli.snapshot_before_overwrite(self.logs, self.base / "elsewhere", NOW)

    def test_retain_once_expires_owned_artifacts_not_active_log(self):
        active = self.logs / "world.log"
        active.write_text("ACTIVE")
        cli.snapshot.snapshot_file(active, self.archive, OLD)

        self.crash.mkdir(mode=0o700)
        incident = {
            "service": "Worldserver",
            "incident_id": "worldserver-00000001",
            "filename_timestamp": OLD.strftime("%Y%m%dT%H%M%SZ"),
            "observed_utc": OLD.isoformat(),
            "classification": "NONZERO_EXIT",
            "exit_code": 7,
        }
        cli.pipeline.renderer.write_report(self.crash, incident)
        raw = self.crash / "Raw Evidence"
        cli.raw_bundle.write_bundle(
            raw, incident["incident_id"], {"a.txt": "evidence"}, OLD,
            {"service": "Worldserver"},
        )

        result = cli.retain_once(self.archive, self.crash, NOW)
        self.assertEqual(result["archived_log_sets_removed"], 1)
        self.assertEqual(result["raw_evidence_bundles_removed"], 1)
        self.assertEqual(result["crash_reports_removed"], 1)
        self.assertEqual(active.read_text(), "ACTIVE")

    def test_partial_raw_bundle_blocks_all_retention_before_archive_delete(self):
        active = self.logs / "world.log"
        active.write_text("ACTIVE")
        data, manifest = cli.snapshot.snapshot_file(active, self.archive, OLD)

        self.crash.mkdir(mode=0o700)
        raw = self.crash / "Raw Evidence"
        raw.mkdir(mode=0o700)
        partial = raw / "20261101T120000Z-worldserver-00000099"
        partial.mkdir(mode=0o700)
        artifact = partial / "stderr.txt"
        artifact.write_text("partial")
        artifact.chmod(0o600)

        with self.assertRaises(cli.Refused):
            cli.retain_once(self.archive, self.crash, NOW)

        self.assertTrue(data.exists())
        self.assertTrue(manifest.exists())
        self.assertEqual(active.read_text(), "ACTIVE")

    def test_recovery_status_is_read_only(self):
        self.archive.mkdir(mode=0o700)
        self.crash.mkdir(mode=0o700)
        intent = self.archive / "retention-intent.json"
        intent.write_text('{"kind":"f15_retention_30d_snapshot"}\\n')
        intent.chmod(0o600)
        before = intent.read_bytes()

        result = cli.recovery.classify_all(self.archive, self.crash)

        self.assertEqual(
            result["snapshot_archive"]["classification"],
            "LEGACY_IDENTITY_UNPROVEN",
        )
        self.assertFalse(result["mutations_performed"])
        self.assertEqual(intent.read_bytes(), before)

    def test_parser_exposes_four_operational_modes(self):
        parser = cli._parser()
        sub_action = next(
            action for action in parser._actions
            if getattr(action, "choices", None)
        )
        self.assertEqual(
            set(sub_action.choices),
            {"observe-once", "snapshot-before-overwrite", "retain-once", "recovery-status"},
        )

if __name__ == "__main__":
    unittest.main()
