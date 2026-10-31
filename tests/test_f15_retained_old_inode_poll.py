"""Fake source rotation only; no real process, PM2, Auth or owner log."""
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timedelta, timezone
import unittest

import f15_integrated_disposable_runner as R
from f15_retained_old_inode_poll import RetainedOldInodePoll
from f15_source_admission import AdmissionError

T0 = datetime(2026, 10, 31, tzinfo=timezone.utc)
OUT, ERR, AUTH = "Worldserver-out", "Worldserver-err", "Authserver-native"


def at(minute=0, day=0):
    return T0 + timedelta(minutes=minute, days=day)


class RetainedOldTail(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="f15-fake-rotation-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.pmroot = root / "fake-pm2"
        self.authroot = root / "fake-auth"
        self.pmroot.mkdir()
        self.authroot.mkdir()
        self.out = self.pmroot / "out.log"
        self.err = self.pmroot / "err.log"
        self.auth = self.authroot / "auth.log"
        for p in (self.out, self.err, self.auth):
            p.write_bytes(b"OLDER-NEVER-CAPTURED\n")
        self.workspace = R.DisposableWorkspace()
        self.addCleanup(self.workspace.close)
        self.runner = None

    def params(self):
        process = [{"name": "fake-world", "pm2_env": {
            "status": "online", "pm_exec_path": "/fake/worldserver",
            "pm_out_log_path": str(self.out), "pm_err_log_path": str(self.err)}}]
        return (json.dumps(process), "fake-world", "worldserver",
                str(self.auth), str(self.pmroot), str(self.authroot))

    def start(self):
        if self.runner is not None:
            self.runner.close()
        self.runner = RetainedOldInodePoll(self.workspace, *self.params())
        self.addCleanup(self.runner.close)
        return self.runner

    def boot(self):
        r = self.start()
        for stream in (OUT, ERR, AUTH):
            self.assertEqual(r.poll(stream, at(1)).events, ("bootstrap-skip",))
        return r

    @staticmethod
    def append(path, data):
        with path.open("ab") as f:
            f.write(data)

    def rotate(self):
        old = self.pmroot / "rotated-out.log"
        self.out.rename(old)
        self.out.write_bytes(b"UNRELATED-NEW-INODE\n")
        return old

    def test_held_descriptors_are_three_distinct_original_files(self):
        r = self.boot()
        self.assertEqual(set(r._retained), {OUT, ERR, AUTH})
        self.assertEqual(len({(os.fstat(fd).st_dev, os.fstat(fd).st_ino)
                              for fd in r._retained.values()}), 3)
        self.assertEqual(r.source_name_status(OUT),
                         "same-original-inode; no completeness guarantee")

    def test_rename_then_old_writer_append_is_read_exactly_once(self):
        r = self.boot()
        self.append(self.out, b"before-rename\n")
        r.poll(OUT, at(2))
        old = self.rotate()
        self.append(old, b"old-inode-tail\n")
        self.assertEqual(r.source_name_status(OUT),
                         "name-replaced; old fd still retained")
        self.assertEqual(r.poll(OUT, at(3)).captured, b"old-inode-tail\n")
        self.assertEqual(r.poll(OUT, at(4)).captured, b"")
        r.seal_through(at(1, 1))
        self.assertEqual(r.archive_bytes(OUT, T0.date()),
                         b"before-rename\nold-inode-tail\n")
        self.assertEqual(self.out.read_bytes(), b"UNRELATED-NEW-INODE\n")
        self.assertIn("OLDER-NEVER-CAPTURED", old.read_text())
        self.assertEqual([x.kind for x in r.records(OUT)],
                         ["note-bootstrap-skip", "seg", "seg"])

    def test_new_inode_never_adopted_automatically(self):
        r = self.boot()
        self.rotate()
        self.append(self.out, b"NEW-LINES-DO-NOT-COUNT\n")
        self.assertEqual(r.poll(OUT, at(2)).captured, b"")
        r.seal_through(at(1, 1))
        self.assertIsNone(r.archive_bytes(OUT, T0.date()))

    def test_old_file_unlinked_but_held_reader_can_drain_writer_fd(self):
        r = self.boot()
        writer = os.open(self.out, os.O_WRONLY | os.O_APPEND)
        try:
            self.out.unlink()
            self.assertEqual(r.source_name_status(OUT),
                             "name-missing-or-unsafe; old fd still retained")
            os.write(writer, b"still-open-writer\n")
            self.assertEqual(r.poll(OUT, at(2)).captured, b"still-open-writer\n")
        finally:
            os.close(writer)

    def test_symlink_replaces_name_but_never_followed(self):
        r = self.boot()
        old = self.pmroot / "old-original.log"
        self.out.rename(old)
        self.out.symlink_to(self.err)
        self.append(old, b"old-only\n")
        self.assertEqual(r.source_name_status(OUT),
                         "name-missing-or-unsafe; old fd still retained")
        self.assertEqual(r.poll(OUT, at(2)).captured, b"old-only\n")
        self.assertNotIn(b"OLDER-NEVER-CAPTURED", r.poll(OUT, at(3)).captured)

    def test_after_rename_missing_old_fd_on_restart_must_refuse_rebind(self):
        self.boot()
        self.rotate()
        with self.assertRaisesRegex(AdmissionError, "source inode changed"):
            self.start()

    def test_crash_after_old_tail_publish_and_before_checkpoint_recovers(self):
        r = self.boot()
        old = self.rotate()
        self.append(old, b"old-tail-published\n")
        with self.assertRaises(R.SyntheticCrash):
            r.poll(OUT, at(2), fail_at="after-record-publish")
        self.assertEqual(r.poll(OUT, at(3)).events, ("recovered", "unchanged"))
        self.assertEqual(r.poll(OUT, at(4)).captured, b"")
        r.seal_through(at(1, 1))
        self.assertEqual(r.archive_bytes(OUT, T0.date()), b"old-tail-published\n")

    def test_parent_inherited_sealing_uses_original_single_journal(self):
        r = self.boot()
        old = self.rotate()
        self.append(old, b"read-one\n")
        r.poll(OUT, at(2))
        self.assertEqual(r._checkpoint(OUT)["seq"], 2)
        self.assertEqual([v.seq for v in r.records(OUT)], [1, 2])
        r.seal_through(at(1, 1))
        self.assertEqual(r.archive_bytes(OUT, T0.date()), b"read-one\n")

    def test_fresh_append_on_other_stream_still_independent(self):
        r = self.boot()
        old = self.rotate()
        self.append(old, b"OUT-T\n")
        self.append(self.err, b"ERR-T\n")
        self.append(self.auth, b"AUTH-T\n")
        for stream in (OUT, ERR, AUTH):
            r.poll(stream, at(2))
        r.seal_through(at(1, 1))
        self.assertEqual(r.archive_bytes(OUT, T0.date()), b"OUT-T\n")
        self.assertEqual(r.archive_bytes(ERR, T0.date()), b"ERR-T\n")
        self.assertEqual(r.archive_bytes(AUTH, T0.date()), b"AUTH-T\n")

    def test_hardlink_created_on_pinned_old_inode_fails_closed(self):
        r = self.boot()
        old = self.rotate()
        os.link(old, self.pmroot / "foreign-alias")
        with self.assertRaisesRegex(R.FailClosed, "multiple hard links"):
            r.poll(OUT, at(2))

    def test_close_drops_original_fd_and_refuses_subsequent_poll(self):
        r = self.boot()
        r.close()
        self.assertEqual(r._retained, {})
        with self.assertRaisesRegex(R.FailClosed, "closed retained stream"):
            r.poll(OUT, at(2))

    def test_original_sources_not_modified_by_reader(self):
        r = self.boot()
        snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in (self.out, self.err, self.auth)}
        for stream in (OUT, ERR, AUTH):
            r.poll(stream, at(2))
        for p, record in snapshot.items():
            self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns), record)

    def test_pinned_writer_still_active_after_first_drain_no_end_claim(self):
        r = self.boot()
        old = self.rotate()
        self.append(old, b"one\n")
        self.assertEqual(r.poll(OUT, at(2)).captured, b"one\n")
        self.append(old, b"two-after-idle\n")
        self.assertEqual(r.poll(OUT, at(3)).captured, b"two-after-idle\n")
        self.assertIn("old fd still retained", r.source_name_status(OUT))
        r.seal_through(at(1, 1))
        self.assertEqual(r.archive_bytes(OUT, T0.date()), b"one\ntwo-after-idle\n")


if __name__ == "__main__":
    unittest.main()
