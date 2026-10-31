"""All inputs are disposable fake files, NOT owner/PM2/Auth logs."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest

import f15_integrated_disposable_runner as R
from f15_retained_old_inode_poll import RetainedOldInodePoll
from f15_manual_old_inode_recovery import ManualOldInodeRecovery
from f15_source_admission import AdmissionError

START = datetime(2026, 10, 31, tzinfo=timezone.utc)
OUT, ERR, AUTH = "Worldserver-out", "Worldserver-err", "Authserver-native"


def at(minutes):
    return START + timedelta(minutes=minutes)


class ManualOldInodeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="f15-manual-old-fake-")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.worldroot = base / "pm2-test"
        self.authroot = base / "auth-test"
        self.worldroot.mkdir()
        self.authroot.mkdir()
        self.paths = {
            OUT: self.worldroot / "out.log",
            ERR: self.worldroot / "err.log",
            AUTH: self.authroot / "native.log",
        }
        for path in self.paths.values():
            path.write_bytes(b"BEFORE-BOOTSTRAP\n")
        self.workspace = R.DisposableWorkspace()
        self.addCleanup(self.workspace.close)
        self.runner = None

    def base_args(self):
        env = [{"name": "fake-world", "pm2_env": {
            "status": "online", "pm_exec_path": "/fake/worldserver",
            "pm_out_log_path": str(self.paths[OUT]),
            "pm_err_log_path": str(self.paths[ERR])}}]
        return (json.dumps(env), "fake-world", "worldserver",
                str(self.paths[AUTH]), str(self.worldroot), str(self.authroot))

    def initial(self, capture=True):
        self.runner = RetainedOldInodePoll(self.workspace, *self.base_args())
        self.addCleanup(self.runner.close)
        for stream in (OUT, ERR, AUTH):
            self.assertEqual(self.runner.poll(stream, at(1)).events,
                             ("bootstrap-skip",))
        if capture:
            for stream, path in self.paths.items():
                with path.open("ab") as f:
                    f.write((stream + "-ANCHOR\n").encode())
                self.runner.poll(stream, at(2))
        return self.runner

    def candidates(self, replaced=None):
        ans = {
            name: (str(path), str(self.worldroot if name != AUTH else self.authroot))
            for name, path in self.paths.items()
        }
        if replaced:
            ans.update(replaced)
        return ans

    def close_initial(self):
        if self.runner is not None:
            self.runner.close()
            self.runner = None

    def restart(self, candidates=None, quarantined_quiet_streams=()):
        self.close_initial()
        new = ManualOldInodeRecovery(
            self.workspace,
            self.candidates() if candidates is None else candidates,
            quarantined_quiet_streams=quarantined_quiet_streams)
        self.runner = new
        self.addCleanup(new.close)
        return new

    def rotate(self):
        old = self.worldroot / "out.log.1"
        self.paths[OUT].rename(old)
        self.paths[OUT].write_bytes(b"NEW-INODE-DONT-READ\n")
        return old

    def test_named_renamed_old_inode_recovery_preserves_tail_without_new_file(self):
        self.initial()
        rotated = self.rotate()
        with rotated.open("ab") as f:
            f.write(b"OLD-TAIL-RECOVERABLE\n")
        new = self.restart(self.candidates({OUT: (str(rotated), str(self.worldroot))}))
        self.assertEqual(new.poll(OUT, at(3)).captured, b"OLD-TAIL-RECOVERABLE\n")
        self.assertEqual(new.poll(OUT, at(4)).captured, b"")
        new.seal_through(at(24 * 60 + 1))
        self.assertEqual(new.archive_bytes(OUT, START.date()),
                         b"Worldserver-out-ANCHOR\nOLD-TAIL-RECOVERABLE\n")
        self.assertEqual(self.paths[OUT].read_bytes(), b"NEW-INODE-DONT-READ\n")
        self.assertEqual([x.kind for x in new.records(OUT)],
                         ["note-bootstrap-skip", "seg", "seg"])
        self.assertIn("NOT proven", new.recovery_label(OUT))

    def test_unchanged_three_streams_reopened_with_single_existing_journal(self):
        self.initial()
        r = self.restart()
        for name, path in self.paths.items():
            with path.open("ab") as f:
                f.write(b"FOLLOWUP\n")
            self.assertEqual(r.poll(name, at(4)).captured, b"FOLLOWUP\n")
            self.assertEqual(r._checkpoint(name)["seq"], 3)
        r.seal_through(at(24 * 60 + 1))
        for name in self.paths:
            self.assertEqual(r.archive_bytes(name, START.date()),
                             (name + "-ANCHOR\n").encode() + b"FOLLOWUP\n")

    def test_reject_replacement_name_new_inode(self):
        self.initial()
        self.rotate()
        with self.assertRaisesRegex(AdmissionError, "inode does not match"):
            self.restart()

    def test_reject_unlinked_old_path_not_findable_after_restart(self):
        self.initial()
        old = self.rotate()
        old.unlink()
        with self.assertRaises(AdmissionError):
            self.restart(self.candidates({OUT: (str(old), str(self.worldroot))}))

    def test_reject_symlink_to_original_old_inode(self):
        self.initial()
        old = self.rotate()
        alias = self.worldroot / "alias.log"
        alias.symlink_to(old)
        with self.assertRaises(AdmissionError):
            self.restart(self.candidates({OUT: (str(alias), str(self.worldroot))}))

    def test_reject_added_hard_link_to_rotated_file(self):
        self.initial()
        old = self.rotate()
        os.link(old, self.worldroot / "hardlink.log")
        with self.assertRaises(AdmissionError):
            self.restart(self.candidates({OUT: (str(old), str(self.worldroot))}))

    def test_reject_changed_bytes_with_original_inode_at_checkpoint_anchor(self):
        self.initial()
        with self.paths[OUT].open("r+b") as f:
            f.seek(len(b"BEFORE-BOOTSTRAP\n"))
            f.write(b"Worldserver-out-XNCHOR\n")
        with self.assertRaisesRegex(AdmissionError, "last journalled source bytes differ"):
            self.restart()

    def test_reject_truncated_source_below_last_recorded_offset(self):
        self.initial()
        self.paths[OUT].write_bytes(b"")
        with self.assertRaisesRegex(AdmissionError, "truncated"):
            self.restart()

    def test_bootstrap_only_no_proven_segment_must_refuse(self):
        self.initial(capture=False)
        with self.assertRaisesRegex(AdmissionError, "no recorded byte segment"):
            self.restart()

    def test_reject_outside_explicit_root(self):
        self.initial()
        with self.assertRaises(AdmissionError):
            self.restart(self.candidates({OUT: (str(self.paths[OUT]), str(self.authroot))}))

    def test_reject_missing_or_extra_stream_mapping(self):
        self.initial()
        omitted = self.candidates()
        del omitted[ERR]
        with self.assertRaisesRegex(AdmissionError, "three streams must have old candidates or explicit quiet quarantine"):
            self.restart(omitted)

    def test_reject_invalid_candidate_pair(self):
        self.initial()
        p = self.candidates()
        p[OUT] = (str(self.paths[OUT]),)
        with self.assertRaisesRegex(AdmissionError, "exact filename"):
            self.restart(p)

    def test_prior_source_files_remain_byte_and_mtime_unchanged(self):
        self.initial()
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.paths.values()}
        r = self.restart()
        for name in (OUT, ERR, AUTH):
            r.poll(name, at(3))
        r.seal_through(at(24 * 60 + 1))
        for path, record in before.items():
            self.assertEqual(record, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_recovery_never_auto_handoffs_even_after_multiple_empty_polls(self):
        self.initial()
        old = self.rotate()
        r = self.restart(self.candidates({OUT: (str(old), str(self.worldroot))}))
        self.assertEqual(r.poll(OUT, at(3)).captured, b"")
        with self.paths[OUT].open("ab") as f:
            f.write(b"NEW-PATH-BYTES\n")
        self.assertEqual(r.poll(OUT, at(4)).captured, b"")
        with old.open("ab") as f:
            f.write(b"VERY-LATE-OLD-WRITER\n")
        self.assertEqual(r.poll(OUT, at(5)).captured, b"VERY-LATE-OLD-WRITER\n")


    def mixed_quiet_and_anchored(self, active=(OUT, AUTH)):
        """Establish actual signed bootstrap notes for all; bytes only for active."""
        r = self.initial(capture=False)
        for stream in active:
            with self.paths[stream].open("ab") as f:
                f.write((stream + "-ANCHOR\n").encode())
            r.poll(stream, at(2))
        return r

    def test_one_quiet_stream_explicit_quarantine_recovers_two_anchored(self):
        self.mixed_quiet_and_anchored()
        old = self.rotate()
        with old.open("ab") as f:
            f.write(b"OLD-OUT-AFTER-RESTART\n")
        p = self.candidates({OUT: (str(old), str(self.worldroot))})
        del p[ERR]  # no proof that stderr remained quiet
        fresh = self.restart(p, quarantined_quiet_streams=(ERR,))
        self.assertEqual(fresh.quarantined_streams(), (ERR,))
        self.assertIn("no evidence of silence", fresh.recovery_label(ERR))
        self.assertEqual(fresh.poll(OUT, at(3)).captured, b"OLD-OUT-AFTER-RESTART\n")
        with self.assertRaisesRegex(R.FailClosed, "closed retained stream"):
            fresh.poll(ERR, at(4))
        with self.paths[AUTH].open("ab") as f:
            f.write(b"AUTH-MORE\n")
        self.assertEqual(fresh.poll(AUTH, at(5)).captured, b"AUTH-MORE\n")
        fresh.seal_through(at(24 * 60 + 1))
        self.assertEqual(fresh.archive_bytes(OUT, START.date()),
                         b"Worldserver-out-ANCHOR\nOLD-OUT-AFTER-RESTART\n")
        self.assertIsNone(fresh.archive_bytes(ERR, START.date()))

    def test_two_quiet_explicit_quarantines_do_not_prevent_stdout_tail(self):
        self.mixed_quiet_and_anchored(active=(OUT,))
        old = self.rotate()
        with old.open("ab") as f:
            f.write(b"OUT-OLD\n")
        p = {OUT: (str(old), str(self.worldroot))}
        fresh = self.restart(p, quarantined_quiet_streams=(ERR, AUTH))
        self.assertEqual(fresh.quarantined_streams(), tuple(sorted((ERR, AUTH))))
        self.assertEqual(fresh.poll(OUT, at(4)).captured, b"OUT-OLD\n")
        for stream in (ERR, AUTH):
            with self.assertRaisesRegex(R.FailClosed, "closed retained stream"):
                fresh.poll(stream, at(5))

    def test_no_silent_quiet_skip_when_mapping_is_missing(self):
        self.mixed_quiet_and_anchored()
        p = self.candidates()
        del p[ERR]
        with self.assertRaisesRegex(AdmissionError, "three streams must"):
            self.restart(p)

    def test_quarantine_cannot_suppress_previously_anchored_journal(self):
        self.initial()
        p = self.candidates()
        del p[ERR]
        with self.assertRaisesRegex(AdmissionError, "exact bootstrap-only"):
            self.restart(p, quarantined_quiet_streams=(ERR,))

    def test_quarantine_rejects_unadopted_segment_after_publish_crash(self):
        r = self.mixed_quiet_and_anchored(active=(OUT, AUTH))
        with self.paths[ERR].open("ab") as f:
            f.write(b"ERR-PUBLISHED-NOT-CHECKPOINTED\n")
        with self.assertRaises(R.SyntheticCrash):
            r.poll(ERR, at(3), fail_at="after-record-publish")
        p = self.candidates()
        del p[ERR]
        with self.assertRaisesRegex(AdmissionError, "exact bootstrap-only"):
            self.restart(p, quarantined_quiet_streams=(ERR,))

    def test_unknown_duplicate_or_overlapping_quiet_list_rejected(self):
        self.mixed_quiet_and_anchored()
        p = self.candidates()
        del p[ERR]
        for excluded in ((ERR, ERR), ("random-stream",), (ERR, OUT)):
            with self.subTest(excluded=excluded):
                with self.assertRaises(AdmissionError):
                    self.restart(p, quarantined_quiet_streams=excluded)



if __name__ == "__main__":
    unittest.main()
