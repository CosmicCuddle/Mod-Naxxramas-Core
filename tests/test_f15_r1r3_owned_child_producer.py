"""R1/R3 producer tests with real child processes and real kernel facts.
Children are disposable Python stand-ins spawned by these tests; no
Worldserver/Authserver, host, service, network or report path is used."""
import os
import re
import signal
import sys
import threading
import time
import types
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "f15"))
import r1r3_owned_child_producer as m  # noqa: E402

FIXTURE = str(Path(__file__).resolve().parent / "r1r3_fixture_child.py")
ALLOW = frozenset({os.path.realpath(sys.executable)})
SOURCE = (ROOT / "tools/f15/r1r3_owned_child_producer.py").read_text()


def producer(mode, *extra, **kw):
    # The original fixtures write level-prefixed lines, i.e. they model a
    # console with flag 0x02, so they DECLARE prefix mode. Role is required.
    kw.setdefault("role", "worldserver")
    kw.setdefault("prefix_loglevel", True)
    return m.OwnedChildProducer([sys.executable, "-I", FIXTURE, mode, *extra],
                                allowed_executables=ALLOW, **kw)


def run(mode, *extra, **kw):
    p = producer(mode, *extra, **kw)
    inc = p.start()
    return p, inc, p.observe()


def assert_reaped(test, p, handoff, timeout=10.0):
    """The handed-off child was collected and every descriptor we owned is
    closed: no zombie, no fd leak. Nothing was signalled by the producer."""
    test.assertIs(handoff, p.handoff)
    test.assertTrue(handoff.finished.wait(timeout), "reaper did not finish")
    test.assertIsNotNone(handoff.raw_exit)
    test.assertFalse(os.path.exists(f"/proc/{p._proc.pid}"))    # not even a zombie
    test.assertTrue(p._proc.stderr.closed)
    test.assertIsNone(p._pidfd)
    with test.assertRaises(ChildProcessError):
        os.waitpid(p._proc.pid, os.WNOHANG)                       # already collected


def accounted(s):
    return (s.bytes_drained == s.bytes_retained + s.bytes_framing + s.bytes_dropped
            and min(s.bytes_retained, s.bytes_framing, s.bytes_dropped) >= 0)


class KernelExitFacts(unittest.TestCase):
    def test_identity_is_ours_and_bound_to_both_facts(self):
        _, inc, obs = run("exit0")
        self.assertEqual((obs.exit.incarnation, obs.stream.incarnation), (inc, inc))
        self.assertEqual(obs.exit.attestation, "owned-child-waitid")
        self.assertEqual(obs.stream.attestation, "owned-stderr-pipe")
        self.assertEqual(inc.boot_id, m.read_boot_id())
        self.assertEqual((inc.ppid, inc.pgid), (os.getpid(), inc.pid))

    def test_clean_exit_is_not_a_crash(self):
        _, _, obs = run("exit0")
        self.assertEqual((obs.exit.kind, obs.exit.exit_code, obs.exit.classification),
                         ("exited", 0, "normal_exit"))
        self.assertIsNone(obs.exit.signal_number)

    def test_startup_error_is_error_not_crash(self):
        _, _, obs = run("exit2")
        self.assertEqual(obs.exit.classification, "nonzero_exit_not_signal")
        self.assertEqual([(r.severity, r.message) for r in obs.stream.records],
                         [("ERROR", "could not connect to database")])

    def test_exit_139_is_not_sigsegv(self):
        _, _, obs = run("exit139")
        self.assertEqual((obs.exit.kind, obs.exit.exit_code, obs.exit.signal_number),
                         ("exited", 139, None))
        self.assertEqual(obs.exit.classification, "nonzero_exit_not_signal")

    def test_real_sigsegv_and_sigabrt(self):
        for mode, sig in (("sigsegv", signal.SIGSEGV), ("sigabrt", signal.SIGABRT)):
            with self.subTest(mode=mode):
                _, _, obs = run(mode)
                self.assertIn(obs.exit.kind, ("killed", "dumped"))
                self.assertEqual((obs.exit.signal_number, obs.exit.exit_code), (sig, None))
                self.assertEqual(obs.exit.classification, "fatal_signal")

    def test_forged_crash_text_is_only_text(self):
        _, _, obs = run("forged")
        self.assertEqual(obs.exit.classification, "normal_exit")
        self.assertIn("SIGSEGV", obs.stream.records[0].message)

    def test_wrapper_hiding_grandchild_crash_reports_only_what_it_saw(self):
        _, _, obs = run("masked_wrapper")
        self.assertEqual((obs.exit.exit_code, obs.exit.signal_number), (0, None))
        self.assertEqual(obs.exit.classification, "normal_exit")

    def test_unplanned_sigterm_needs_policy(self):
        _, _, obs = run("self_sigterm")
        self.assertEqual(obs.exit.signal_number, signal.SIGTERM)
        self.assertFalse(obs.exit.planned)
        self.assertEqual(obs.exit.classification, "signal_requires_policy")

    def test_plan_declared_before_start_and_delivered_by_harness(self):
        p = producer("sleep", planned_signal=signal.SIGTERM)
        inc = p.start()
        time.sleep(0.2)
        os.kill(inc.pid, signal.SIGTERM)          # the HARNESS, not the producer
        obs = p.observe()
        self.assertTrue(obs.exit.planned)
        self.assertEqual(obs.exit.classification, "planned_signal")

    def test_plan_for_one_signal_does_not_cover_another(self):
        p = producer("sleep", planned_signal=signal.SIGTERM)
        inc = p.start()
        time.sleep(0.2)
        os.kill(inc.pid, signal.SIGINT)
        obs = p.observe()
        self.assertFalse(obs.exit.planned)
        self.assertEqual(obs.exit.classification, "signal_requires_policy")

    def test_error_and_crash_are_kept_separately(self):
        _, _, obs = run("error_then_segv")
        self.assertEqual(obs.exit.classification, "fatal_signal")
        self.assertEqual([r.severity for r in obs.stream.records], ["ERROR", "WARN"])


class Identity(unittest.TestCase):
    def test_only_the_exact_live_incarnation_matches(self):
        p = producer("sleep", planned_signal=signal.SIGTERM)
        inc = p.start()
        try:
            self.assertTrue(p.matches(inc))
            for wrong in (replace(inc, starttime=inc.starttime + 1),
                          replace(inc, boot_id="0" * 36),
                          replace(inc, pid=os.getpid()),
                          replace(inc, ppid=1)):
                self.assertFalse(p.matches(wrong))
        finally:
            os.kill(inc.pid, signal.SIGTERM)
            p.observe()
        self.assertFalse(p.matches(inc))           # pidfd released

    def test_exited_child_no_longer_matches_before_reap(self):
        p = producer("exit0")
        inc = p.start()
        time.sleep(0.5)                            # exited, still a zombie
        self.assertFalse(p.matches(inc))
        p.observe()

    def test_pinned_process_that_is_not_our_child_is_refused(self):
        real = m.read_stat
        p = producer("exit0")
        with mock.patch.object(m, "read_stat",
                               side_effect=lambda pid: (1,) + real(pid)[1:]):
            with self.assertRaisesRegex(m.StartFailed, "not our own child") as cm:
                p.start()
        assert_reaped(self, p, cm.exception.handoff)
        with self.assertRaises(RuntimeError):
            p.observe()                            # refused producer is spent

    def test_child_text_cannot_change_the_incarnation(self):
        _, inc, obs = run("spoof_identity")
        self.assertEqual(obs.stream.incarnation, inc)
        self.assertEqual(obs.exit.classification, "normal_exit")
        self.assertIn("verified=True", obs.stream.records[0].message)

    def test_missing_kernel_support_fails_closed(self):
        for missing in ("pidfd_open", "P_PIDFD", "waitid", "CLD_DUMPED"):
            fake = types.SimpleNamespace(**{k: getattr(os, k) for k in dir(os)
                                            if not k.startswith("__") and k != missing})
            with self.subTest(missing=missing), mock.patch.object(m, "os", fake):
                with self.assertRaises(m.Unsupported):
                    producer("exit0")


class StreamSafety(unittest.TestCase):
    def test_descendant_holding_pipe_gives_source_incomplete_without_signals(self):
        start = time.monotonic()
        _, _, obs = run("descendant_holds", "4", eof_grace_seconds=0.5)
        self.assertLess(time.monotonic() - start, 3.0)   # single-shot grace
        self.assertEqual(obs.exit.classification, "normal_exit")
        self.assertTrue(obs.stream.deadline_hit and obs.stream.source_incomplete)
        self.assertFalse(obs.stream.eof)
        helper = int(re.search(r"helper (\d+)", obs.stream.records[0].message).group(1))
        os.kill(helper, 0)                          # still alive: never signalled
        # It left the group with setsid(): the scan cannot see it. Not proof.
        self.assertNotIn(helper, obs.group_members_seen_after_exit)
        os.kill(helper, signal.SIGKILL)             # test cleanup only

    def test_group_scan_reports_members_it_can_see(self):
        _, _, obs = run("group_member")
        helper = int(re.search(r"helper (\d+)", obs.stream.records[0].message).group(1))
        self.assertIn(helper, obs.group_members_seen_after_exit)
        self.assertTrue(obs.stream.eof)
        try:
            os.kill(helper, signal.SIGKILL)         # test cleanup only
        except ProcessLookupError:
            pass

    def test_flood_is_drained_and_every_byte_accounted(self):
        mib = 48
        _, _, obs = run("flood", str(mib), retain_bytes=64 * 1024,
                        max_records=16, eof_grace_seconds=1.0)
        s = obs.stream
        self.assertEqual(s.bytes_drained, mib * 1024 * 1024)
        self.assertTrue(accounted(s))
        self.assertEqual(s.bytes_framing, mib * 1024)
        self.assertLessEqual(s.bytes_retained, 64 * 1024)
        self.assertGreater(s.bytes_dropped, 0)
        self.assertEqual(len(s.records), 16)
        self.assertTrue(s.eof and not s.deadline_hit)
        # The child times its own writes and reports seconds as exit code:
        # it was never held up because the producer kept draining.
        self.assertEqual(obs.exit.kind, "exited")
        self.assertLess(obs.exit.exit_code, 10)

    def test_multiline_split_utf8_and_control_bytes(self):
        _, _, obs = run("multiline")
        s = obs.stream
        self.assertEqual([(r.severity, r.message, r.line) for r in s.records],
                         [("ERROR", "first", 1),
                          ("ERROR", "split�red", 3),   # ANSI CSI now stripped
                          ("WARN", "no newline at end", 4)])
        self.assertTrue(s.final_partial_line)
        self.assertEqual(s.lines_terminated, 3)
        self.assertTrue(accounted(s))

    def test_truncated_line_is_marked(self):
        _, _, obs = run("exit2", max_line_bytes=8)
        self.assertTrue(obs.stream.records[0].truncated)
        self.assertEqual(obs.stream.records[0].message, "co")
        self.assertTrue(accounted(obs.stream))


class Lifecycle(unittest.TestCase):
    """CS01 #167 review: no child or descriptor escapes on any failure path."""

    def test_pidfd_open_failure_after_spawn_hands_off_and_reaps(self):
        p = producer("exit0")
        with mock.patch.object(m.os, "pidfd_open", side_effect=OSError(38, "ENOSYS")):
            with self.assertRaises(m.StartFailed) as cm:
                p.start()
        assert_reaped(self, p, cm.exception.handoff)
        self.assertEqual(cm.exception.handoff.raw_exit, ("exited", 0))

    def test_read_stat_failure_after_spawn_hands_off_and_reaps(self):
        p = producer("exit2")
        with mock.patch.object(m, "read_stat", side_effect=OSError(5, "EIO")):
            with self.assertRaises(m.StartFailed) as cm:
                p.start()
        h = cm.exception.handoff
        assert_reaped(self, p, h)
        self.assertEqual(h.raw_exit, ("exited", 2))
        self.assertGreater(h.bytes_discarded, 0)          # its ERROR line was drained

    def test_deadline_with_live_child_hands_off_and_keeps_its_pipe_working(self):
        p = producer("chatty")
        p.start()
        started = time.monotonic()
        with self.assertRaises(m.ObservationTimeout) as cm:
            p.observe(deadline_seconds=0.3)
        self.assertLess(time.monotonic() - started, 1.5)  # no hang
        h = cm.exception.handoff
        assert_reaped(self, p, h)
        # Exit 0 means every later stderr write succeeded: no EPIPE, no stall.
        self.assertEqual(h.raw_exit, ("exited", 0))
        self.assertGreater(h.bytes_discarded, 0)
        with self.assertRaises(RuntimeError):
            p.observe()

    @staticmethod
    def one_shot(real, exc):
        state = {"fired": False}

        def side_effect(*args, **kwargs):
            if not state["fired"]:
                state["fired"] = True
                raise exc
            return real(*args, **kwargs)
        return side_effect

    def assert_failed_but_reaped(self, p, cm):
        h = cm.exception.handoff
        assert_reaped(self, p, h)
        self.assertEqual(h.raw_exit, ("exited", 0))   # child kept writing: no EPIPE
        with self.assertRaises(RuntimeError):
            p.observe()

    def test_read_error_while_child_alive_hands_off(self):
        p = producer("chatty")
        p.start()
        time.sleep(0.1)
        with mock.patch.object(m, "_read_chunk",
                               side_effect=self.one_shot(m._read_chunk, OSError(5, "EIO"))):
            with self.assertRaisesRegex(m.ObservationFailed, "EIO") as cm:
                p.observe(deadline_seconds=5.0)
            self.assert_failed_but_reaped(p, cm)
        self.assertGreater(cm.exception.handoff.bytes_discarded, 0)

    def test_selector_register_failure_hands_off(self):
        real_cls = m.selectors.DefaultSelector
        calls = {"n": 0}

        class FlakySelector(real_cls):
            def register(self, *a, **kw):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise OSError(12, "ENOMEM")
                return super().register(*a, **kw)
        p = producer("chatty")
        p.start()
        with mock.patch.object(m.selectors, "DefaultSelector", FlakySelector):
            with self.assertRaisesRegex(m.ObservationFailed, "ENOMEM") as cm:
                p.observe(deadline_seconds=5.0)
            self.assert_failed_but_reaped(p, cm)

    def test_waitid_failure_before_collection_hands_off(self):
        p = producer("exit0")
        p.start()
        with mock.patch.object(m.os, "waitid",
                               side_effect=self.one_shot(os.waitid, OSError(4, "EINTR"))):
            with self.assertRaisesRegex(m.ObservationFailed, "EINTR") as cm:
                p.observe(deadline_seconds=5.0)
            self.assert_failed_but_reaped(p, cm)

    def test_never_pausing_writer_cannot_starve_exit_and_deadline(self):
        endless = lambda fd: b"z" * 65536                  # never EAGAIN, never EOF
        p = producer("exit0", eof_grace_seconds=0.3, retain_bytes=4096)
        p.start()
        box = {}
        with mock.patch.object(m, "_read_chunk", side_effect=endless):
            t = threading.Thread(target=lambda: box.setdefault("obs", p.observe(5.0)),
                                 daemon=True)
            t.start()
            t.join(4.0)
        self.assertFalse(t.is_alive(), "observe() starved by a busy writer")
        obs = box["obs"]
        self.assertEqual(obs.exit.classification, "normal_exit")
        self.assertTrue(obs.stream.deadline_hit and not obs.stream.eof)
        self.assertTrue(accounted(obs.stream))
        self.assertGreater(obs.stream.bytes_dropped, 0)

    def test_descendant_flooding_after_exit_respects_one_shot_grace(self):
        start = time.monotonic()
        _, _, obs = run("descendant_floods", "4", eof_grace_seconds=0.5,
                        retain_bytes=8192, max_records=4)
        self.assertLess(time.monotonic() - start, 2.5)
        s = obs.stream
        self.assertEqual(obs.exit.classification, "normal_exit")
        self.assertTrue(s.deadline_hit and s.source_incomplete)
        self.assertTrue(accounted(s))
        self.assertGreater(s.bytes_dropped, 100_000)
        helper = int(re.search(r"helper (\d+)", s.records[0].message).group(1))
        try:
            os.kill(helper, signal.SIGKILL)                # test cleanup only
        except ProcessLookupError:
            pass

    def test_group_scan_listing_failure_keeps_the_observation(self):
        p = producer("sigsegv")
        p.start()
        with mock.patch.object(m.os, "listdir", side_effect=PermissionError(13, "EACCES")):
            obs = p.observe()
        self.assertEqual(obs.exit.classification, "fatal_signal")
        self.assertFalse(obs.group_scan_complete)
        self.assertEqual(obs.group_members_seen_after_exit, ())

    def test_group_scan_unreadable_entry_marks_scan_incomplete(self):
        p = producer("exit0")
        inc = p.start()
        real = m.read_stat

        def flaky(pid):
            if pid == os.getpid():
                raise PermissionError(13, "EACCES")
            return real(pid)
        with mock.patch.object(m, "read_stat", side_effect=flaky):
            obs = p.observe()
        self.assertEqual(obs.exit.incarnation, inc)
        self.assertFalse(obs.group_scan_complete)

    def test_clean_scan_reports_complete(self):
        _, _, obs = run("exit0")
        self.assertTrue(obs.group_scan_complete)


class DualStreamSeverity(unittest.TestCase):
    """CS01 #167 6418335424: stdout+stderr provenance, unknown by default."""

    def plain(self, **kw):
        return run("two_streams_plain", prefix_loglevel=False, **kw)[2]

    def test_default_severity_is_unknown_with_stream_provenance_and_hints(self):
        obs = self.plain()
        self.assertEqual(obs.stdout.attestation, "owned-stdout-pipe")
        self.assertEqual(obs.stderr.attestation, "owned-stderr-pipe")
        self.assertEqual([(r.stream, r.severity, r.message, r.severity_hint, r.hint_source)
                          for r in obs.stdout.records],
                         [("stdout", "unknown", "Map 0 loaded", "below_error_candidate",
                           "pinned_console_route"),
                          ("stdout", "unknown", "Could not find creature 1234",
                           "below_error_candidate", "pinned_console_route")])
        self.assertEqual([(r.stream, r.severity, r.severity_hint) for r in obs.stderr.records],
                         [("stderr", "unknown", "error_or_fatal_candidate")])
        self.assertEqual(obs.cross_stream_order, "unknown")
        self.assertTrue(obs.stdout_may_be_block_buffered)

    def test_hint_or_message_word_never_becomes_a_severity(self):
        obs = run("two_streams_prefixed", prefix_loglevel=False)[2]
        records = obs.stdout.records + obs.stderr.records
        self.assertTrue(records)
        self.assertTrue(all(r.severity == "unknown" and r.severity_source == "none"
                            for r in records))

    def test_declared_prefix_decodes_line_start_only_after_ansi(self):
        obs = run("two_streams_prefixed", prefix_loglevel=True)[2]
        self.assertEqual([(r.severity, r.message, r.severity_source) for r in obs.stdout.records],
                         [("WARN", "Creature missing", "declared_prefix"),
                          ("unknown", "hello ERROR not a prefix", "none")])
        self.assertEqual(obs.stdout.lines_below_warn, 1)           # INFO
        self.assertEqual([(r.severity, r.message) for r in obs.stderr.records],
                         [("ERROR", "DB down"), ("FATAL", "boom")])
        self.assertGreaterEqual(obs.stdout.ansi_sequences_stripped, 4)
        self.assertGreaterEqual(obs.stderr.ansi_sequences_stripped, 3)
        self.assertEqual(obs.stderr.lines_blank, 1)               # trailing colour reset
        for s in (obs.stdout, obs.stderr):
            self.assertTrue(accounted(s))

    def test_declared_timestamp_prefix_is_positional(self):
        obs = run("timestamped", prefix_loglevel=True, prefix_timestamp=True)[2]
        self.assertEqual([(r.severity, r.message) for r in obs.stderr.records],
                         [("ERROR", "timed")])
        self.assertEqual([(r.severity, r.message) for r in obs.stdout.records],
                         [("unknown", "ERROR missing timestamp")])

    def test_timestamp_mode_requires_declared_prefix_mode(self):
        with self.assertRaises(ValueError):
            producer("exit0", prefix_loglevel=False, prefix_timestamp=True)

    def test_stdout_flood_cannot_hide_a_stderr_error(self):
        mib = 40
        _, _, obs = run("stdout_flood_stderr_error", str(mib), prefix_loglevel=True,
                        retain_bytes=64 * 1024, max_records=8, eof_grace_seconds=1.0)
        out, err = obs.stdout, obs.stderr
        self.assertEqual(out.bytes_drained, mib * 1024 * 1024)
        self.assertGreater(out.bytes_dropped, 0)
        self.assertTrue(accounted(out) and accounted(err))
        self.assertEqual([(r.severity, r.message) for r in err.records],
                         [("ERROR", "important while stdout floods")])
        self.assertEqual(err.bytes_dropped, 0)                     # separate budget
        self.assertTrue(out.eof and err.eof)
        self.assertEqual(obs.exit.kind, "exited")
        self.assertLess(obs.exit.exit_code, 10)                    # child never stalled

    def test_buffered_stdout_tail_is_lost_on_crash_and_flagged(self):
        _, _, obs = run("buffered_then_segv")
        self.assertEqual(obs.exit.classification, "fatal_signal")
        self.assertEqual(obs.stdout.bytes_drained, 0)              # tail never written
        self.assertTrue(obs.stdout_tail_lost_on_crash_possible)
        self.assertEqual([(r.severity, r.message) for r in obs.stderr.records],
                         [("ERROR", "kept on unbuffered stderr")])

    def test_one_stream_ending_does_not_end_the_other(self):
        _, _, obs = run("stdout_late_descendant", eof_grace_seconds=2.0)
        self.assertTrue(obs.stderr.eof)
        self.assertTrue(obs.stdout.eof and not obs.stdout.deadline_hit)
        self.assertEqual([(r.severity, r.message) for r in obs.stdout.records],
                         [("WARN", "late stdout line")])

    def test_clean_exit_does_not_flag_lost_tail(self):
        _, _, obs = run("exit0")
        self.assertFalse(obs.stdout_tail_lost_on_crash_possible)


class RoleAndStdin(unittest.TestCase):
    def test_role_is_recorded_on_observation_and_both_streams(self):
        for role in ("worldserver", "authserver"):
            with self.subTest(role=role):
                obs = run("two_streams_plain", role=role)[2]
                self.assertEqual((obs.role, obs.stdout.role, obs.stderr.role),
                                 (role, role, role))

    def test_role_must_be_declared_from_the_allowlist(self):
        for role in (None, "", "WorldServer", "realmd"):
            with self.subTest(role=role), self.assertRaises(ValueError):
                producer("exit0", role=role)

    def test_devnull_stdin_lets_a_console_stop_on_eof(self):
        _, _, obs = run("fake_cli", stdin_mode="devnull", prefix_loglevel=False)
        self.assertEqual(obs.exit.exit_code, 0)
        self.assertEqual(obs.stdout.records[0].message, "console EOF: shutting down")

    def test_held_open_stdin_keeps_console_running_and_is_never_written(self):
        p, _, obs = run("fake_cli", stdin_mode="held_open")
        self.assertEqual(obs.exit.exit_code, 7)        # no EOF, no data (9)
        self.assertTrue(p._proc.stdin.closed)          # closed after collection

    def test_held_open_stdin_survives_handoff_until_collection(self):
        p = producer("fake_cli", stdin_mode="held_open")
        p.start()
        with self.assertRaises(m.ObservationTimeout) as cm:
            p.observe(deadline_seconds=0.2)
        h = cm.exception.handoff
        assert_reaped(self, p, h)
        self.assertEqual(h.raw_exit, ("exited", 7))     # stdin stayed open to the end
        self.assertTrue(p._proc.stdin.closed)

    def test_reaper_drains_both_streams(self):
        p = producer("chatty_both")
        p.start()
        with self.assertRaises(m.ObservationTimeout) as cm:
            p.observe(deadline_seconds=0.3)
        h = cm.exception.handoff
        assert_reaped(self, p, h)
        self.assertEqual(h.raw_exit, ("exited", 0))     # no EPIPE on either stream
        self.assertGreater(h.discarded_by_stream["stdout"], 0)
        self.assertGreater(h.discarded_by_stream["stderr"], 0)
        self.assertTrue(p._proc.stdout.closed)

    def test_invalid_stdin_mode_refused(self):
        with self.assertRaises(ValueError):
            producer("exit0", stdin_mode="pty")


class Guards(unittest.TestCase):
    def test_unlisted_executable_is_refused_before_spawn(self):
        with self.assertRaises(ValueError):
            m.OwnedChildProducer(["/bin/sh", "-c", "true"], allowed_executables=ALLOW)

    def test_single_use(self):
        p, _, _ = run("exit0")
        with self.assertRaises(RuntimeError):
            p.start()
        with self.assertRaises(RuntimeError):
            p.observe()

    def test_module_sends_no_signals_at_all(self):
        code = "\n".join(l for l in SOURCE.splitlines() if not l.lstrip().startswith("#"))
        code = re.sub(r'"""[\s\S]*?"""', "", code)
        for call in ("pidfd_send_signal", "os.kill", "killpg", ".kill(",
                     ".terminate(", ".send_signal(", "signal.raise_signal"):
            with self.subTest(call=call):
                self.assertNotIn(call, code)


if __name__ == "__main__":
    unittest.main()
