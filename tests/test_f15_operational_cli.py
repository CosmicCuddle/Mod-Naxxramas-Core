import json
import os
import sys
import tempfile
import unittest
from unittest import mock
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

    def test_expected_restart_waits_for_confirmation_then_consumes_without_crash(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out\n")
        err.write_text("err\n")
        mgr.write_text("manager\n")
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW,
        ), [])

        store = cli.pipeline.expected_maintenance.ExpectedMaintenanceStore(self.state, "Worldserver")
        store.arm("maint-1", "restart", NOW, NOW + timedelta(minutes=5))

        with self.assertRaises(cli.pipeline.checkpoint.Refused):
            cli.observe_once(
                self.state, self.crash, world_pm2_name="worldserver",
                pm2_manager_log=mgr, runner=runner, now=NOW + timedelta(seconds=10),
            )
        self.assertEqual(list(self.crash.glob("*Worldserver*.txt")), [])
        self.assertEqual(store.read()["status"], "armed")

        store.confirm("maint-1", NOW + timedelta(seconds=15))
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW + timedelta(seconds=20),
        ), [])
        self.assertIsNone(store.read())
        audit = json.loads((self.state / "Worldserver.last-expected-maintenance.json").read_text())
        self.assertEqual(audit["operation_id"], "maint-1")
        self.assertEqual(audit["result"], "EXPECTED_TRANSITION_CONFIRMED")
        self.assertEqual(list(self.crash.glob("*Worldserver*.txt")), [])

    def test_confirmed_marker_does_not_hide_explicit_fatal_signal(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out\n")
        err.write_text("err\n")
        mgr.write_text("baseline\n")
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW,
        ), [])
        store = cli.pipeline.expected_maintenance.ExpectedMaintenanceStore(self.state, "Worldserver")
        store.arm("maint-fatal", "restart", NOW, NOW + timedelta(minutes=5))
        store.confirm("maint-fatal", NOW + timedelta(seconds=5))
        mgr.write_text("App [worldserver:0] exited with code [0] via signal [SIGSEGV]\n")

        result = cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW + timedelta(seconds=10),
        )
        self.assertEqual(result[0]["classification"], "FATAL_SIGNAL_EXIT")
        self.assertTrue(store.path.exists(), "mismatched fatal evidence must not consume maintenance marker")


    def test_invalid_marker_does_not_block_real_restart_incident(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out\n")
        err.write_text("err\n")
        mgr.write_text("manager\n")
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW,
        ), [])

        store = cli.pipeline.expected_maintenance.ExpectedMaintenanceStore(
            self.state, "Worldserver"
        )
        target = self.state / "foreign-marker.json"
        target.write_text("{}")
        target.chmod(0o600)
        store.path.symlink_to(target)

        result = cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW + timedelta(seconds=10),
        )
        self.assertEqual(result[0]["classification"], "PM2_RESTART_OBSERVED")
        self.assertEqual(len(list(self.crash.glob("*Worldserver*.txt"))), 1)
        self.assertTrue(store.path.is_symlink())
        self.assertEqual(
            store.classify_recovery()["status"],
            "MARKER_INVALID_OR_UNSAFE",
        )

    def test_confirmed_clean_sigterm_restart_is_expected(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out\n")
        err.write_text("err\n")
        mgr.write_text("baseline\n")
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW,
        ), [])
        store = cli.pipeline.expected_maintenance.ExpectedMaintenanceStore(
            self.state, "Worldserver"
        )
        store.arm("maint-term", "restart", NOW, NOW + timedelta(minutes=5))
        store.confirm("maint-term", NOW + timedelta(seconds=5))
        mgr.write_text(
            "App [worldserver:0] exited with code [0] via signal [SIGTERM]\n"
        )

        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW + timedelta(seconds=10),
        ), [])
        self.assertEqual(list(self.crash.glob("*Worldserver*.txt")), [])
        self.assertIsNone(store.read())

    def test_sigkill_during_confirmed_maintenance_is_reported(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out\n")
        err.write_text("err\n")
        mgr.write_text("baseline\n")
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW,
        ), [])
        store = cli.pipeline.expected_maintenance.ExpectedMaintenanceStore(
            self.state, "Worldserver"
        )
        store.arm("maint-kill", "restart", NOW, NOW + timedelta(minutes=5))
        store.confirm("maint-kill", NOW + timedelta(seconds=5))
        mgr.write_text(
            "App [worldserver:0] exited with code [0] via signal [SIGKILL]\n"
        )

        result = cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW + timedelta(seconds=10),
        )
        self.assertEqual(
            result[0]["classification"],
            "SIGNAL_EXIT_CAUSE_UNPROVEN",
        )
        self.assertTrue(store.path.exists())

    def test_checkpoint_advanced_audit_failure_is_recoverable_without_duplicate_crash(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out\n")
        err.write_text("err\n")
        mgr.write_text("manager\n")
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW,
        ), [])
        store = cli.pipeline.expected_maintenance.ExpectedMaintenanceStore(
            self.state, "Worldserver"
        )
        store.arm("maint-audit-fail", "restart", NOW, NOW + timedelta(minutes=5))
        store.confirm("maint-audit-fail", NOW + timedelta(seconds=5))

        real_atomic = cli.pipeline.checkpoint._atomic_json

        def fail_audit(path, obj):
            if Path(path).name == "Worldserver.last-expected-maintenance.json":
                raise cli.pipeline.expected_maintenance.Refused("synthetic audit write failure")
            return real_atomic(path, obj)

        with mock.patch.object(
            cli.pipeline.checkpoint, "_atomic_json", side_effect=fail_audit
        ):
            with self.assertRaises(cli.pipeline.expected_maintenance.Refused):
                cli.observe_once(
                    self.state, self.crash, world_pm2_name="worldserver",
                    pm2_manager_log=mgr, runner=runner,
                    now=NOW + timedelta(seconds=10),
                )

        checkpoint_state = cli.pipeline.checkpoint.IncidentCheckpoint(
            self.state, "Worldserver"
        ).state()
        self.assertEqual(checkpoint_state["identity"]["restart_time"], 2)
        self.assertEqual(
            store.classify_recovery()["status"],
            "STALE_CONFIRMED_MARKER_AFTER_CHECKPOINT",
        )
        self.assertEqual(list(self.crash.glob("*Worldserver*.txt")), [])

        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner,
            now=NOW + timedelta(seconds=20),
        ), [])
        self.assertEqual(list(self.crash.glob("*Worldserver*.txt")), [])

    def test_checkpoint_and_audit_advanced_unlink_failure_is_recoverable_without_duplicate_crash(self):
        out = self.logs / "world-out.log"
        err = self.logs / "world-err.log"
        mgr = self.logs / "pm2.log"
        out.write_text("out\n")
        err.write_text("err\n")
        mgr.write_text("manager\n")
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
                (0, pm2(101, 2, out, err), ""),
            ],
        })
        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner, now=NOW,
        ), [])
        store = cli.pipeline.expected_maintenance.ExpectedMaintenanceStore(
            self.state, "Worldserver"
        )
        store.arm("maint-unlink-fail", "restart", NOW, NOW + timedelta(minutes=5))
        store.confirm("maint-unlink-fail", NOW + timedelta(seconds=5))

        real_unlink = Path.unlink

        def fail_marker_unlink(path, *args, **kwargs):
            if path == store.path:
                raise OSError("synthetic marker unlink failure")
            return real_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", new=fail_marker_unlink):
            with self.assertRaises(cli.pipeline.expected_maintenance.Refused):
                cli.observe_once(
                    self.state, self.crash, world_pm2_name="worldserver",
                    pm2_manager_log=mgr, runner=runner,
                    now=NOW + timedelta(seconds=10),
                )

        self.assertEqual(
            store.classify_recovery()["status"],
            "STALE_MARKER_WITH_MATCHING_AUDIT",
        )
        self.assertTrue(store.path.exists())
        self.assertEqual(list(self.crash.glob("*Worldserver*.txt")), [])

        self.assertEqual(cli.observe_once(
            self.state, self.crash, world_pm2_name="worldserver",
            pm2_manager_log=mgr, runner=runner,
            now=NOW + timedelta(seconds=20),
        ), [])
        self.assertEqual(list(self.crash.glob("*Worldserver*.txt")), [])

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

    def test_parser_exposes_only_three_operational_modes(self):
        parser = cli._parser()
        sub_action = next(
            action for action in parser._actions
            if getattr(action, "choices", None)
        )
        self.assertEqual(
            set(sub_action.choices),
            {"observe-once", "snapshot-before-overwrite", "retain-once"},
        )

if __name__ == "__main__":
    unittest.main()
