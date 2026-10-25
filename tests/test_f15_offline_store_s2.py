"""Synthetic F15 S2 offline persistence contracts; no game processes or host adapters."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import multiprocessing
import os
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_store import Incident, IncidentStore, UNKNOWN


def event(service="worldserver", invocation="call-1", pid=210,
          start_utc="2026-10-25T01:10:00Z",
          end_utc="2026-10-25T01:11:00Z", **changes):
    values = dict(service=service, host="synthetic-host", boot="boot-99",
                  invocation=invocation, pid=pid, start_utc=start_utc,
                  end_utc=end_utc, verified_actual_death=True,
                  unexpected_death=True, planned_stop=False,
                  exit_code=1)
    values.update(changes)
    return Incident(**values)


def worker(directory: str, incident: Incident, queue):
    try:
        queue.put(("ok", IncidentStore(Path(directory)).publish(incident)))
    except Exception as exc:
        queue.put(("error", str(exc)))


class StoreTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Crash Logs"
        self.root.mkdir(mode=0o700)
        self.store = IncidentStore(self.root)

    def reports(self):
        return sorted(self.root.glob("*-crash-*.txt"))

    def history(self):
        return (self.root / "Crash-History.txt").read_text("utf-8")

    def test_one_immutable_worldserver_report_and_index(self):
        self.assertTrue(self.store.publish(event()))
        self.assertEqual(len(self.reports()), 1)
        text = self.reports()[0].read_text("utf-8")
        self.assertIn("COSMIC CORE - SERVER CRASH REPORT", text)
        self.assertIn(UNKNOWN, text)
        self.assertIn("Observed termination: exit 1", text)
        self.assertIn("Worldserver: 1", self.history())
        self.assertIn("Authserver: 0", self.history())
        self.assertEqual(self.reports()[0].stat().st_mode & 0o777, 0o600)

    def test_ten_overnight_crashes_are_ten_files(self):
        for n in range(10):
            self.assertTrue(self.store.publish(event(invocation=f"n-{n}", pid=100+n)))
        self.assertEqual(len(self.reports()), 10)
        self.assertIn("Total: 10", self.history())

    def test_same_second_and_pid_distinct_invocations_survive(self):
        for n in range(4):
            self.assertTrue(self.store.publish(event(invocation=f"same-second-{n}")))
        self.assertEqual(len(self.reports()), 4)

    def test_notice_time_is_not_event_identity(self):
        first = event(end_utc="2026-10-25T01:11:00Z")
        second = replace(first, end_utc="2026-10-25T01:11:12Z")
        self.assertEqual(first.identity(), second.identity())
        self.assertTrue(self.store.publish(first))
        self.assertFalse(self.store.publish(second))
        self.assertEqual(len(self.reports()), 1)
        self.assertIn("Total: 1", self.history())

    def test_replaying_after_reporter_restart_is_idempotent(self):
        self.assertTrue(self.store.publish(event()))
        self.assertFalse(IncidentStore(self.root).publish(event()))
        self.assertEqual(len(self.reports()), 1)

    def test_normal_exit_never_counts(self):
        self.assertFalse(self.store.publish(event(exit_code=0, unexpected_death=False)))
        self.assertEqual(self.reports(), [])

    def test_planned_code_two_never_counts(self):
        self.assertFalse(self.store.publish(event(exit_code=2, planned_stop=True,
                                                  unexpected_death=False)))
        self.assertFalse(self.store.publish(event(exit_code=2, planned_stop=False)))
        self.assertEqual(len(self.reports()), 0)

    def test_planned_termination_without_fatal_signal_not_counted(self):
        self.assertFalse(self.store.publish(event(planned_stop=True)))
        self.assertEqual(self.reports(), [])

    def test_verified_teardown_signal_after_restart_intent_is_counted(self):
        self.assertTrue(self.store.publish(event(planned_stop=True, exit_code=None,
                                                 signal="SIGSEGV")))
        self.assertIn("Total: 1", self.history())

    def test_sigsegv_and_sigabrt_independently_reported(self):
        for signal in ("SIGSEGV", "SIGABRT"):
            self.assertTrue(self.store.publish(event(invocation=signal,
                                                     exit_code=None, signal=signal)))
        self.assertEqual(len(self.reports()), 2)

    def test_status_masking_must_not_be_mistaken_for_verified_child(self):
        self.assertFalse(self.store.publish(event(verified_actual_death=False, exit_code=0)))
        self.assertFalse(self.store.publish(event(verified_actual_death=False, exit_code=None)))
        self.assertEqual(self.reports(), [])

    def test_unknown_child_status_with_independent_unexpected_proof_is_minimal(self):
        self.assertTrue(self.store.publish(event(exit_code=None)))
        self.assertIn("status unknown", self.reports()[0].read_text())

    def test_uncorrelated_notice_cannot_create_random_identity(self):
        with self.assertRaises(ValueError):
            self.store.publish(event(invocation=""))
        with self.assertRaises(ValueError):
            self.store.publish(event(boot=""))
        with self.assertRaises(ValueError):
            self.store.publish(event(invocation="../../escape"))

    def test_pid_reuse_requires_verified_start_identity(self):
        a = event(invocation="worker-1", pid=999)
        b = event(invocation="worker-2", pid=999,
                  start_utc="2026-10-25T01:10:01Z")
        self.assertNotEqual(a.identity(), b.identity())
        self.store.publish(a)
        self.store.publish(b)
        self.assertEqual(len(self.reports()), 2)

    def test_corrupt_and_partial_reports_are_not_counted_on_rebuild(self):
        self.store.publish(event())
        (self.root / "worldserver-crash-20261025T011000Z-"
         "00000000-0000-0000-0000-000000000000.txt").write_text(
             "UNFINISHED", encoding="utf-8")
        (self.root / "Crash-History.txt").write_text("CORRUPTED", encoding="utf-8")
        self.assertEqual(self.store.rebuild(), (1, 0))
        self.assertIn("Total: 1", self.history())
        self.assertEqual(len(self.reports()), 2)  # corrupt file is preserved, not erased

    def test_final_report_survives_missing_index_and_rebuilds(self):
        self.store.publish(event())
        (self.root / "Crash-History.txt").unlink()
        self.assertEqual(self.store.rebuild(), (1, 0))
        self.assertIn("Total: 1", self.history())

    def test_existing_final_never_overwritten(self):
        item = event()
        final = self.root / IncidentStore._filename(item.metadata())
        final.write_text("different owner data", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.store.publish(item)
        self.assertEqual(final.read_text(), "different owner data")

    def test_symlinked_report_not_counted_or_overwritten(self):
        item = event()
        target = self.root / "sentinel"
        target.write_text("DO NOT MODIFY")
        (self.root / IncidentStore._filename(item.metadata())).symlink_to(target)
        with self.assertRaises(FileExistsError):
            self.store.publish(item)
        self.assertEqual(target.read_text(), "DO NOT MODIFY")
        self.assertEqual(self.store.rebuild(), (0, 0))

    def test_directory_must_exist_and_be_private(self):
        with self.assertRaises(FileNotFoundError):
            IncidentStore(self.root / "not-created")
        public = Path(self.temp.name) / "public"
        public.mkdir(mode=0o777)
        public.chmod(0o777)
        with self.assertRaises(PermissionError):
            IncidentStore(public)
        link = Path(self.temp.name) / "alias"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(PermissionError):
            IncidentStore(link)

    def test_report_does_not_leak_input_or_serialize_arbitrary_logs(self):
        with self.assertRaises(ValueError):
            self.store.publish(event(host="name\nsecret"))
        with self.assertRaises(ValueError):
            self.store.publish(event(boot=";password"))
        self.store.publish(event())
        self.assertNotIn("password", self.reports()[0].read_text())

    def test_full_report_is_utc_chronological_not_local_dst_sort(self):
        self.store.publish(event(invocation="later", pid=221,
                                 end_utc="2026-10-25T02:10:00Z"))
        self.store.publish(event(invocation="earlier", pid=222,
                                 end_utc="2026-10-25T01:30:00Z"))
        text = self.history()
        self.assertLess(text.index("2026-10-25T01:30:00Z"),
                        text.index("2026-10-25T02:10:00Z"))

    def test_ancestor_symlink_is_rejected_before_any_write(self):
        alias = Path(self.temp.name) / "alias-parent"
        alias.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(PermissionError):
            IncidentStore(alias / "Crash Logs")
        self.assertEqual(self.reports(), [])

    def test_replaced_directory_path_does_not_redirect_writer(self):
        moved = Path(self.temp.name) / "original-private-directory"
        self.root.rename(moved)
        self.root.mkdir(mode=0o700)
        self.assertTrue(self.store.publish(event()))
        self.assertEqual(len(list(moved.glob("*-crash-*.txt"))), 1)
        self.assertEqual(len(self.reports()), 0)
        self.assertFalse((self.root / "Crash-History.txt").exists())
        self.assertIn("Total: 1", (moved / "Crash-History.txt").read_text())

    def test_parent_swap_to_symlink_does_not_redirect_writer(self):
        moved = Path(self.temp.name) / "old-private"
        self.root.rename(moved)
        hostile = Path(self.temp.name) / "new-target"
        hostile.mkdir(mode=0o700)
        self.root.symlink_to(hostile, target_is_directory=True)
        self.assertTrue(self.store.publish(event()))
        self.assertEqual(len(list(moved.glob("*-crash-*.txt"))), 1)
        self.assertEqual(len(list(hostile.glob("*-crash-*.txt"))), 0)

    def test_report_survives_rebuild_exception_and_recovers(self):
        from unittest.mock import patch
        with patch.object(self.store, "_rebuild_locked",
                          side_effect=OSError("injected history failure")):
            with self.assertRaisesRegex(OSError, "injected"):
                self.store.publish(event())
        self.assertEqual(len(self.reports()), 1)
        self.assertEqual(IncidentStore(self.root).rebuild(), (1, 0))
        self.assertIn("Total: 1", self.history())

    def test_index_symlink_replaced_without_touching_its_target(self):
        sentinel = Path(self.temp.name) / "unrelated.txt"
        sentinel.write_text("DO NOT REPLACE", encoding="utf-8")
        (self.root / "Crash-History.txt").symlink_to(sentinel)
        self.assertTrue(self.store.publish(event()))
        self.assertEqual(sentinel.read_text(), "DO NOT REPLACE")
        self.assertFalse((self.root / "Crash-History.txt").is_symlink())
        self.assertIn("Total: 1", self.history())

    def test_report_corruption_never_counted_even_with_matching_filename(self):
        self.assertTrue(self.store.publish(event()))
        report = self.reports()[0]
        content = report.read_bytes()
        report.write_bytes(content.replace(b"Observed termination: exit 1",
                                           b"Observed termination: exit 3"))
        self.assertEqual(self.store.rebuild(), (0, 0))
        self.assertIn("Total: 0", self.history())
        self.assertEqual(len(self.reports()), 1)

    def test_unusual_real_fatal_signals_are_preserved(self):
        # A real death cannot disappear because a signal was not named in
        # the first six-signal prototype allowlist.
        for number, name in enumerate(("SIGTERM", "SIGXFSZ", "SIGXCPU",
                                       "SIGSYS", "SIGTRAP", "SIGQUIT",
                                       "SIGPIPE", "SIGHUP")):
            item = event(invocation="signal-" + name, pid=600 + number,
                         signal=name, exit_code=None)
            self.assertTrue(self.store.publish(item))
        self.assertEqual(len(self.reports()), 8)
        self.assertIn("Total: 8", self.history())

    def test_signal_evidence_still_rejects_unsafe_text(self):
        for bad in ("SIGTERM\nsecret", "SIG" + "Z"*100, "term", "../SIG"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                self.store.publish(event(signal=bad, exit_code=None))

    def test_authserver_code_two_is_not_worldserver_restart(self):
        self.assertTrue(self.store.publish(event(service="authserver",
                                                  invocation="auth-exit2",
                                                  exit_code=2)))
        self.assertIn("Authserver: 1", self.history())
        self.assertFalse(self.store.publish(event(invocation="world-exit2",
                                                  exit_code=2)))
        self.assertEqual(len(self.reports()), 1)

    def test_verified_planned_SIGTERM_is_not_a_crash(self):
        self.assertFalse(self.store.publish(event(signal="SIGTERM",
                                                  exit_code=None, planned_stop=True)))
        self.assertFalse(self.store.publish(event(signal="SIGHUP",
                                                  exit_code=None, planned_stop=True)))
        self.assertEqual(self.reports(), [])

    def test_corrupted_report_is_visible_as_unverified_warning(self):
        self.store.publish(event())
        report = self.reports()[0]
        report.write_bytes(report.read_bytes() + b"Owner note\n")
        self.assertEqual(self.store.rebuild(), (0, 0))
        history = self.history()
        self.assertIn("Total: 0", history)
        self.assertIn("Unverified or modified report files: 1", history)
        self.assertIn("Unverified report: " + report.name, history)
        self.assertIn("Do not edit immutable reports", history)
        with self.assertRaises(FileExistsError):
            self.store.publish(event())
        self.assertIn("Unverified or modified report files: 1", self.history())

    def test_no_unverified_warning_when_all_reports_valid(self):
        self.store.publish(event())
        self.assertIn("Unverified or modified report files: 0", self.history())
        self.assertNotIn("WARNING: some named reports", self.history())

    def test_writable_ancestor_without_root_sticky_policy_is_rejected(self):
        parent = Path(self.temp.name)
        original = parent.stat().st_mode & 0o7777
        parent.chmod(0o777)
        try:
            with self.assertRaises(PermissionError):
                IncidentStore(self.root)
        finally:
            parent.chmod(original)

    def test_leaf_owned_by_other_uid_cannot_be_opened(self):
        import stat
        from unittest.mock import patch
        real_fstat = os.fstat
        target = self.root.stat()
        def altered(fd):
            old = real_fstat(fd)
            if old.st_ino == target.st_ino and old.st_dev == target.st_dev:
                vals = list(old)
                vals[4] = old.st_uid + 1000
                return os.stat_result(vals)
            return old
        with patch("offline_store.os.fstat", side_effect=altered):
            with self.assertRaises(PermissionError):
                IncidentStore(self.root)

    def test_same_name_as_parent_does_not_skip_security_check(self):
        duplicate = Path(self.temp.name) / "same"
        duplicate.mkdir(mode=0o700)
        leaf = duplicate / "same"
        leaf.mkdir(mode=0o700)
        duplicate.chmod(0o777)
        try:
            with self.assertRaises(PermissionError):
                IncidentStore(leaf)
        finally:
            duplicate.chmod(0o700)

    def test_actual_parallel_world_and_auth_writers(self):
        ctx = multiprocessing.get_context("fork")
        queue = ctx.Queue()
        entries = [event(invocation="world", pid=211),
                   event(service="authserver", invocation="auth", pid=212)]
        processes = [ctx.Process(target=worker, args=(str(self.root), ev, queue))
                     for ev in entries]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=10)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual([queue.get(timeout=5) for _ in processes],
                         [("ok", True), ("ok", True)])
        self.assertIn("Worldserver: 1", self.history())
        self.assertIn("Authserver: 1", self.history())
        self.assertIn("Total: 2", self.history())

    def test_two_parallel_collectors_one_actual_event(self):
        ctx = multiprocessing.get_context("fork")
        queue = ctx.Queue()
        item = event()
        processes = [ctx.Process(target=worker, args=(str(self.root), item, queue))
                     for _ in range(2)]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=10)
            self.assertEqual(p.exitcode, 0)
        statuses = [queue.get(timeout=5) for _ in processes]
        self.assertEqual(sorted(statuses), [("ok", False), ("ok", True)])
        self.assertEqual(len(self.reports()), 1)
        self.assertIn("Total: 1", self.history())


if __name__ == "__main__":
    unittest.main()
