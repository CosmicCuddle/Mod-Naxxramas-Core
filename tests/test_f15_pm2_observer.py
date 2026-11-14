"""F15 disposable tests for read-only existing PM2 observer; no real PM2/server."""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import f15_pm2_observer as obs


class ExistingPM2ObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "private"
        self.out = self.home / "world.out"
        self.err = self.home / "world.err"
        self.out.write_bytes(b"initial stdout\n")
        self.err.write_bytes(b"initial stderr\n")

    def payload(self, pid=12345, status="online", out=None, err=None):
        return [{
            "name": "world-private",
            "pid": pid,
            "pm2_env": {
                "status": status,
                "pm_out_log_path": str(out or self.out),
                "pm_err_log_path": str(err or self.err),
                "private_secret_that_must_never_be_saved": "CREDENTIAL_SENTINEL"
            }
        }]

    def poll(self, payload=None, **kwargs):
        return obs.observe_once(self.root, "world-private", "Worldserver",
                                snapshot=self.payload() if payload is None else payload,
                                now=1720000000, **kwargs)

    def archive(self):
        return self.root / "capture" / "archives" / "Worldserver-out" / "20240703.txt"

    def test_exact_identity_and_fail_closed_invalid_pm2_data(self):
        result = obs.select_process(self.payload(), "world-private", "Worldserver")
        self.assertEqual(result["pid"], 12345)
        self.assertEqual(set(result), obs.STATE_KEYS)
        with self.assertRaises(obs.Refused):
            obs.select_process(self.payload() * 2, "world-private", "Worldserver")
        with self.assertRaises(obs.Refused):
            obs.select_process(self.payload(), "wrong-name", "Worldserver")
        with self.assertRaises(obs.Refused):
            obs.select_process(self.payload(pid=0), "world-private", "Worldserver")
        with self.assertRaises(obs.Refused):
            obs.select_process(self.payload(status="mystery"), "world-private", "Worldserver")
        with self.assertRaises(obs.Refused):
            obs.select_process({}, "world-private", "Worldserver")

    def test_default_eof_capture_and_bounded_followup(self):
        state = self.poll()
        self.assertTrue(state["changed"])
        self.assertFalse(state["crash_proven"])
        self.assertFalse(self.archive().exists())
        with self.out.open("ab") as file:
            file.write(b"appended stdout\n")
        self.poll()
        self.assertEqual(self.archive().read_bytes(), b"appended stdout\n")
        self.assertEqual(self.out.read_bytes(), b"initial stdout\nappended stdout\n")

    def test_explicit_backfill_and_secret_redaction(self):
        state = self.poll(include_existing=True)
        self.assertTrue(state["changed"])
        self.assertEqual(self.archive().read_bytes(), self.out.read_bytes())
        self.assertEqual(len(list((self.root / "events").glob("*.json"))), 1)
        for output in (self.root / "events").glob("*.json"):
            event = json.loads(output.read_text("utf-8"))
            self.assertEqual(event["kind"], "initial_observation")
            self.assertFalse(event["crash_proven"])
            self.assertNotIn("CREDENTIAL_SENTINEL", output.read_text("utf-8"))
        self.assertNotIn("CREDENTIAL_SENTINEL",
                         (self.root / "pm2-observation.json").read_text("utf-8"))

    def test_pid_change_observed_not_misclassified_as_crash(self):
        self.poll()
        result = self.poll(self.payload(pid=22222, status="online"))
        self.assertTrue(result["changed"])
        self.assertFalse(result["crash_proven"])
        events = sorted((self.root / "events").glob("*.json"))
        self.assertEqual(len(events), 2)
        record = json.loads(events[-1].read_text("utf-8"))
        self.assertEqual(record["kind"], "unclassified_process_change")
        self.assertEqual((record["before_pid"], record["after_pid"]), (12345, 22222))
        self.assertFalse(record["crash_proven"])
        self.assertFalse(self.poll(self.payload(pid=22222))["changed"])

    def test_rotation_and_symlinks_refuse_without_source_deletion(self):
        original = self.out.read_bytes()
        self.poll()
        # Keep an FD to the removed inode alive until after the replacement
        # check: otherwise Linux can immediately reuse the same inode and
        # make the rotation fixture spuriously pass as an unchanged source.
        with self.out.open("rb") as former_source:
            previous_ino = os.fstat(former_source.fileno()).st_ino
            self.out.unlink()
            self.out.write_bytes(b"replacement source\n")
            self.assertNotEqual(previous_ino, self.out.stat().st_ino)
            with self.assertRaises(obs.Refused):
                self.poll()
        self.assertEqual(self.out.read_bytes(), b"replacement source\n")
        link = self.home / "linked.out"
        link.symlink_to(self.out)
        # O_NOFOLLOW rejects the path at os.open with ELOOP on Linux;
        # an explicit preflight may instead raise the module's Refused.
        # Do not accept an arbitrary OSError (e.g., a disk failure) as a
        # passing symlink-specific negative test.
        try:
            self.poll(self.payload(out=link))
        except obs.Refused:
            pass
        except OSError as exc:
            self.assertEqual(exc.errno, errno.ELOOP)
        else:
            self.fail("symlinked source was unexpectedly accepted")
        self.assertEqual(self.out.read_bytes(), b"replacement source\n")
        self.assertFalse(self.archive().exists())
        self.assertNotEqual(original, self.out.read_bytes())

    def test_default_off_cli_and_untrusted_root(self):
        with self.assertRaises(SystemExit):
            obs.main(["--root", str(self.root), "--pm2-name", "world-private",
                      "--service", "Worldserver", "--once"])
        self.poll()
        other_name = self.payload()
        other_name[0]["name"] = "auth-other"
        with self.assertRaises(obs.Refused):
            obs.observe_once(self.root, "auth-other", "Authserver",
                             snapshot=other_name, now=1720000000)
        self.assertEqual(self.out.read_bytes(), b"initial stdout\n")

    def test_cli_refusal_never_exposes_private_paths_or_source_bytes(self):
        before_out = self.out.read_bytes()
        before_err = self.err.read_bytes()
        path_sentinel = str(self.out)
        for failure in (
            FileNotFoundError(2, "missing private source", path_sentinel),
            obs.Refused("confidential diagnostic " + path_sentinel),
            ValueError("unsafe private data " + path_sentinel),
        ):
            with self.subTest(exception=type(failure).__name__):
                stdout, stderr = io.StringIO(), io.StringIO()
                with mock.patch.object(obs, "observe_once", side_effect=failure):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        code = obs.main([
                            "--root", str(self.root), "--pm2-name", "world-private",
                            "--service", "Worldserver", "--observe", "--once",
                        ])
                self.assertEqual(code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("F15 PM2 OBSERVER REFUSED:", stderr.getvalue())
                self.assertNotIn(path_sentinel, stderr.getvalue())
                self.assertNotIn("confidential diagnostic", stderr.getvalue())
                self.assertNotIn("unsafe private data", stderr.getvalue())
                self.assertNotIn("initial stdout", stderr.getvalue())
                self.assertFalse(self.root.exists())
                self.assertEqual(self.out.read_bytes(), before_out)
                self.assertEqual(self.err.read_bytes(), before_err)

    def test_reject_duplicate_and_nonregular_source(self):
        with self.assertRaises(obs.Refused):
            self.poll(self.payload(err=self.out))
        self.out.unlink()
        os.mkdir(self.out)
        with self.assertRaises((obs.Refused, OSError)):
            self.poll()


if __name__ == "__main__":
    unittest.main()
