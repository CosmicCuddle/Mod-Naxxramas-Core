import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import f15_incident_pipeline as pipeline

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)


class SequenceRunner:
    def __init__(self, responses):
        self.responses = {tuple(k): list(v) for k, v in responses.items()}
        self.calls = []

    def __call__(self, argv):
        key = tuple(argv)
        self.calls.append(list(argv))
        queue = self.responses.get(key)
        if not queue:
            raise AssertionError(f"unexpected/exhausted command: {argv}")
        return queue.pop(0)


def pm2(pid, restarts, exit_code=0, uptime=1000):
    return json.dumps([{
        "name": "worldserver",
        "pid": pid,
        "pm_id": 0,
        "pm2_env": {
            "status": "online",
            "restart_time": restarts,
            "unstable_restarts": 0,
            "pm_uptime": uptime,
            "created_at": 900,
            "exit_code": exit_code,
            "pm_out_log_path": "/fixture/world-out.log",
            "pm_err_log_path": "/fixture/world-err.log",
        },
    }])


def proc_stat(pid, start_ticks):
    return f"{pid} (authserver) S " + " ".join(["0"] * 18 + [str(start_ticks), "0", "0"])


class FullPipelineTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.state = self.base / "state"
        self.crash = self.base / "Crash Logs"
        self.raw = self.crash / "Raw Evidence"

    def test_world_pm2_sigsegv_creates_one_bundle_report_and_history(self):
        runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 4), ""),
                (0, pm2(101, 5), ""),
                (0, pm2(101, 5), ""),
            ],
        })
        manager = (
            "2026-11-13 App [worldserver:0] exited with code [0] "
            "via signal [SIGSEGV]"
        )

        self.assertIsNone(pipeline.world_cycle(
            self.state, self.crash, self.raw, "worldserver", "", "baseline", runner, NOW,
            build_version="fixture-build", source_revision="fixture-sha",
        ))
        incident = pipeline.world_cycle(
            self.state, self.crash, self.raw, "worldserver", manager,
            "ERROR segmentation fixture\n", runner, NOW + timedelta(seconds=1),
            build_version="fixture-build", source_revision="fixture-sha",
        )
        self.assertEqual(incident["incident_id"], "worldserver-00000001")
        self.assertEqual(incident["classification"], "FATAL_SIGNAL_EXIT")
        self.assertEqual(incident["signal"], 11)

        reports = [p for p in self.crash.glob("*.txt") if p.name != "Crash-History.txt"]
        self.assertEqual(len(reports), 1)
        report = reports[0].read_text()
        self.assertIn("Classification: FATAL_SIGNAL_EXIT", report)
        self.assertIn("Signal name: SIGSEGV", report)
        self.assertIn("fixture-build", report)
        self.assertIn("Raw evidence reference:", report)

        bundles = [p for p in self.raw.iterdir() if p.is_dir()]
        self.assertEqual(len(bundles), 1)
        manifest = json.loads((bundles[0] / "manifest.json").read_text())
        self.assertEqual(manifest["incident_id"], "worldserver-00000001")
        self.assertEqual(
            {x["name"] for x in manifest["artifacts"]},
            {"pm2-jlist.json", "pm2-manager.txt", "recent-context.txt"},
        )

        history = (self.crash / "Crash-History.txt").read_text()
        self.assertIn("worldserver-00000001", history)
        self.assertIn("FATAL_SIGNAL_EXIT", history)

        self.assertIsNone(pipeline.world_cycle(
            self.state, self.crash, self.raw, "worldserver", manager,
            "same state", runner, NOW + timedelta(seconds=2),
        ))
        reports_after = [p for p in self.crash.glob("*.txt") if p.name != "Crash-History.txt"]
        self.assertEqual(len(reports_after), 1)
        self.assertEqual(len([p for p in self.raw.iterdir() if p.is_dir()]), 1)

    def test_auth_disappearance_creates_once_with_unknown_cause(self):
        runner = SequenceRunner({
            ("tmux", "display-message", "-p", "-t", "auth", "#{pane_pid}"): [
                (0, "10\n", ""),
                (0, "10\n", ""),
                (0, "10\n", ""),
            ],
            ("ps", "-eo", "pid=,ppid=,comm=,args="): [
                (0, "10 1 tmux tmux\n20 10 bash bash\n30 20 authserver /root/bin/authserver\n", ""),
                (0, "10 1 tmux tmux\n20 10 bash bash\n", ""),
                (0, "10 1 tmux tmux\n20 10 bash bash\n", ""),
            ],
        })

        def read_text(path):
            self.assertEqual(path, Path("/proc/30/stat"))
            return proc_stat(30, 777)

        self.assertIsNone(pipeline.auth_cycle(
            self.state, self.crash, self.raw, "auth", "baseline", runner, read_text, NOW,
            build_version="auth-fixture", source_revision="auth-sha",
        ))
        incident = pipeline.auth_cycle(
            self.state, self.crash, self.raw, "auth", "auth vanished fixture",
            runner, read_text, NOW + timedelta(seconds=1),
            build_version="auth-fixture", source_revision="auth-sha",
        )
        self.assertEqual(incident["incident_id"], "authserver-00000001")
        self.assertEqual(incident["classification"], "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN")
        self.assertIsNone(incident["exit_code"])

        reports = [p for p in self.crash.glob("*Authserver*.txt")]
        self.assertEqual(len(reports), 1)
        report = reports[0].read_text()
        self.assertIn("Classification: PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN", report)
        self.assertIn("Exit code: UNKNOWN", report)
        self.assertIn("Signal name: UNKNOWN", report)
        self.assertIn("tmux session still present", report)

        bundles = [p for p in self.raw.iterdir() if p.is_dir()]
        self.assertEqual(len(bundles), 1)
        meta = json.loads((bundles[0] / "manifest.json").read_text())
        self.assertEqual(meta["incident_id"], "authserver-00000001")
        self.assertEqual(
            {x["name"] for x in meta["artifacts"]},
            {"auth-process.json", "recent-context.txt"},
        )

        self.assertIsNone(pipeline.auth_cycle(
            self.state, self.crash, self.raw, "auth", "still absent",
            runner, read_text, NOW + timedelta(seconds=2),
        ))
        self.assertEqual(len([p for p in self.crash.glob("*Authserver*.txt")]), 1)

    def test_world_and_auth_have_independent_sequences(self):
        world_runner = SequenceRunner({
            ("pm2", "jlist"): [
                (0, pm2(100, 1), ""),
                (0, pm2(101, 2, exit_code=7), ""),
            ],
        })
        pipeline.world_cycle(self.state, self.crash, self.raw, "worldserver", "", "", world_runner, NOW)
        world = pipeline.world_cycle(
            self.state, self.crash, self.raw, "worldserver", "", "fatal exit 7",
            world_runner, NOW + timedelta(seconds=1),
        )
        self.assertEqual(world["incident_id"], "worldserver-00000001")

        auth_runner = SequenceRunner({
            ("tmux", "display-message", "-p", "-t", "auth", "#{pane_pid}"): [
                (0, "10\n", ""),
                (0, "10\n", ""),
            ],
            ("ps", "-eo", "pid=,ppid=,comm=,args="): [
                (0, "10 1 tmux tmux\n20 10 bash bash\n30 20 authserver authserver\n", ""),
                (0, "10 1 tmux tmux\n20 10 bash bash\n", ""),
            ],
        })
        def read_text(_path):
            return proc_stat(30, 555)
        pipeline.auth_cycle(self.state, self.crash, self.raw, "auth", "", auth_runner, read_text, NOW)
        auth = pipeline.auth_cycle(
            self.state, self.crash, self.raw, "auth", "", auth_runner, read_text,
            NOW + timedelta(seconds=1),
        )
        self.assertEqual(auth["incident_id"], "authserver-00000001")

if __name__ == "__main__":
    unittest.main()
