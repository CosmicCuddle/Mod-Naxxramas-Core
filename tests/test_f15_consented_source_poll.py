"""Only disposable fake PM2/Auth files; never an operator/owner host test."""
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timedelta, timezone
import unittest

import f15_integrated_disposable_runner as R
from f15_consented_source_poll import ConsentedSourcePoll
from f15_source_admission import AdmissionError

T0 = datetime(2026, 10, 31, tzinfo=timezone.utc)
OUT, ERR, AUTH = "Worldserver-out", "Worldserver-err", "Authserver-native"


def at(day=0, hour=0, minute=0, second=0):
    return T0 + timedelta(days=day, hours=hour, minutes=minute, seconds=second)


class EndToEndConsentedFileBridge(unittest.TestCase):
    def setUp(self):
        self.external = tempfile.TemporaryDirectory(prefix="f15-fake-external-")
        self.addCleanup(self.external.cleanup)
        root = Path(self.external.name)
        self.pmroot = root / "pm2"
        self.authroot = root / "auth"
        self.pmroot.mkdir()
        self.authroot.mkdir()
        self.out = self.pmroot / "out.log"
        self.err = self.pmroot / "err.log"
        self.auth = self.authroot / "auth.log"
        for p in (self.out, self.err, self.auth):
            p.write_bytes(b"OLD-UNARCHIVED\n")
        self.w = R.DisposableWorkspace()
        self.addCleanup(self.w.close)
        self.runner = None

    def params(self):
        obj = [{"name": "test-world",
                "pm2_env": {"status": "online", "pm_exec_path": "/fake/worldserver",
                            "pm_out_log_path": str(self.out), "pm_err_log_path": str(self.err)}}]
        return (json.dumps(obj), "test-world", "worldserver",
                str(self.auth), str(self.pmroot), str(self.authroot))

    def start(self, params=None):
        if self.runner:
            self.runner.close()
        self.runner = ConsentedSourcePoll(self.w, *(self.params() if params is None else params))
        self.addCleanup(self.runner.close)
        return self.runner

    def boot(self):
        run = self.start()
        for stream in (OUT, ERR, AUTH):
            self.assertEqual(run.poll(stream, at(0, 0, 1)).events, ("bootstrap-skip",))
        return run

    def append(self, path, payload):
        with path.open("ab") as f:
            f.write(payload)

    def test_end_to_end_three_streams_no_cross_stream_merge(self):
        r = self.boot()
        sources = ((OUT, self.out, b"out-NEW\n"),
                   (ERR, self.err, b"err-NEW\n"),
                   (AUTH, self.auth, b"auth-NEW\n"))
        for stream, path, payload in sources:
            self.append(path, payload)
            self.assertEqual(r.poll(stream, at(0, 2)).captured, payload)
        r.seal_through(at(1, 0, 1))
        for stream, path, payload in sources:
            self.assertEqual(r.archive_bytes(stream, at().date()), payload)
            self.assertEqual(path.read_bytes(), b"OLD-UNARCHIVED\n" + payload)
        self.assertIn("NOT a PTY", r.archive_entry(AUTH, at().date())["completeness"])
        self.assertIn("not a crash diagnosis", r.archive_entry(ERR, at().date())["completeness"])

    def test_exactly_one_journal_and_one_checkpoint_per_stream(self):
        r = self.boot()
        self.append(self.out, b"a\n")
        r.poll(OUT, at(0, 2))
        self.assertEqual([x.kind for x in r.records(OUT)], ["note-bootstrap-skip", "seg"])
        ck = r._checkpoint(OUT)
        self.assertEqual(ck["seq"], 2)
        self.assertFalse(any(p.exists() for p in r.sources.iterdir()))
        r.seal_through(at(1, 0, 1))
        self.assertEqual(r.archive_bytes(OUT, at().date()), b"a\n")

    def test_default_bootstrap_never_backfills_old_bytes(self):
        r = self.boot()
        r.seal_through(at(1, 0, 1))
        self.assertIsNone(r.archive_bytes(OUT, at().date()))
        note = r.archive_entry(OUT, at().date())["notes"][0]
        self.assertIn("existing bytes not backfilled", note["detail"])

    def test_crash_after_publish_before_checkpoint_recovered_exactly_once(self):
        r = self.boot()
        self.append(self.out, b"A\n")
        with self.assertRaises(R.SyntheticCrash):
            r.poll(OUT, at(0, 2), fail_at="after-record-publish")
        r = self.start()
        self.assertIn("recovered", r.poll(OUT, at(0, 3)).events)
        self.append(self.out, b"B\n")
        self.assertEqual(r.poll(OUT, at(0, 4)).captured, b"B\n")
        r.seal_through(at(1, 0, 1))
        self.assertEqual(r.archive_bytes(OUT, at().date()), b"A\nB\n")

    def test_input_file_not_modified_by_poll_seal_or_restart(self):
        r = self.boot()
        snapshots = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                     for p in (self.out, self.err, self.auth)}
        for stream in (OUT, ERR, AUTH):
            r.poll(stream, at(0, 2))
        r.seal_through(at(1, 0, 1))
        r = self.start()
        for stream in (OUT, ERR, AUTH):
            r.poll(stream, at(1, 1))
        for p, expected in snapshots.items():
            self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns), expected)

    def test_symlink_replacement_after_admission_is_refused(self):
        r = self.boot()
        old = self.pmroot / "old-out.log"
        self.out.rename(old)
        self.out.symlink_to(old)
        with self.assertRaisesRegex(R.FailClosed, "no longer passes"):
            r.poll(OUT, at(0, 2))
        self.assertEqual(len([x for x in r.records(OUT) if x.kind == "seg"]), 0)

    def test_new_inode_at_same_name_refused_without_reading_new_file(self):
        r = self.boot()
        old = self.pmroot / "rotated.log"
        self.out.rename(old)
        self.out.write_bytes(b"NEW-PROCESS-LOG\n")
        with self.assertRaisesRegex(R.FailClosed, "replaced/rotated"):
            r.poll(OUT, at(0, 2))
        self.assertEqual([x.kind for x in r.records(OUT)], ["note-bootstrap-skip"])
        self.assertEqual(old.read_bytes(), b"OLD-UNARCHIVED\n")

    def test_reopen_after_rename_does_not_authorize_new_identity(self):
        self.boot()
        self.out.rename(self.pmroot / "rotated.log")
        self.out.write_bytes(b"DIFFERENT\n")
        with self.assertRaisesRegex(AdmissionError, "source inode changed"):
            self.start()

    def test_truncation_same_inode_has_explicit_gap_note(self):
        r = self.boot()
        self.append(self.out, b"first\n")
        r.poll(OUT, at(0, 2))
        with self.out.open("wb") as f:
            f.write(b"X")
        self.assertIn("truncated", r.poll(OUT, at(0, 3)).events)
        r.seal_through(at(1, 0, 1))
        self.assertIn("truncated", [x["kind"] for x in r.archive_entry(OUT, at().date())["notes"]])

    def test_hardlink_added_after_admission_is_refused(self):
        r = self.boot()
        os.link(self.out, self.pmroot / "other-hardlink")
        with self.assertRaisesRegex(R.FailClosed, "no longer passes"):
            r.poll(OUT, at(0, 2))

    def test_world_process_status_must_be_online(self):
        p = list(self.params())
        data = json.loads(p[0]); data[0]["pm2_env"]["status"] = "stopped"
        p[0] = json.dumps(data)
        with self.assertRaises(AdmissionError):
            self.start(p)

    def test_mismatched_executable_rejected(self):
        p = list(self.params()); p[2] = "authserver"
        with self.assertRaises(AdmissionError):
            self.start(p)

    def test_source_root_is_explicit_and_restricted(self):
        p = list(self.params()); p[4] = str(self.authroot)
        with self.assertRaises(AdmissionError):
            self.start(p)

    def test_auth_native_file_must_be_a_regular_file(self):
        self.auth.unlink(); self.auth.mkdir()
        with self.assertRaises(AdmissionError):
            self.start()

    def test_shared_inode_between_world_and_auth_rejected(self):
        self.auth.unlink()
        os.link(self.out, self.auth)
        with self.assertRaises(AdmissionError):
            self.start()

    def test_source_unchanged_on_failed_admission(self):
        self.out.unlink(); self.out.symlink_to(self.err)
        before = self.err.read_bytes()
        with self.assertRaises(AdmissionError):
            self.start()
        self.assertEqual(before, self.err.read_bytes())


if __name__ == "__main__":
    unittest.main()
