"""S4h OS pipe provenance witness, disposable Python child only."""
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_owned_stderr_s4h import capture_disposable  # noqa: E402


class OwnedPipeFixture(unittest.TestCase):
    def test_warn_and_error_are_distinct_from_info(self):
        x = capture_disposable("normal")
        self.assertEqual([e.severity for e in x.records], ["WARN", "ERROR"])
        self.assertEqual(x.ignored_lines, 1)
        self.assertEqual(x.direct_child_exit_code, 0)
        self.assertGreater(x.child_pid, 0)
        self.assertFalse(x.timed_out)

    def test_forged_crash_text_does_not_attest_kernel_signal(self):
        x = capture_disposable("forged_crash")
        self.assertEqual(x.direct_child_exit_code, 0)
        self.assertIn("SIGSEGV", x.records[0].message)
        self.assertEqual(x.records[0].severity, "ERROR")
        self.assertFalse(hasattr(x, "crash_verified"))

    def test_fake_exit_139_is_not_a_verified_crash(self):
        x = capture_disposable("exit139")
        self.assertEqual(x.direct_child_exit_code, 139)
        self.assertFalse(hasattr(x, "crash_verified"))

    def test_invalid_utf8_and_control_bytes_are_safe_to_render(self):
        x = capture_disposable("bad_utf8")
        self.assertEqual(len(x.records), 1)
        self.assertIn("\ufffd", x.records[0].message)
        self.assertNotIn("\x1b", x.records[0].message)
        self.assertNotIn("\x00", x.records[0].message)

    def test_extremely_long_line_is_clipped_and_memory_bounded(self):
        x = capture_disposable("oversize", max_line_bytes=50)
        self.assertEqual(x.clipped_lines, 1)
        self.assertTrue(x.records[0].truncated)
        self.assertLessEqual(len(x.records[0].message), 50)
        self.assertGreater(x.bytes_read, 20000)

    def test_error_flood_is_bounded_and_loss_is_accounted(self):
        x = capture_disposable("flood", max_records=5)
        self.assertEqual(x.lines_seen, 100)
        self.assertEqual(len(x.records), 5)
        self.assertEqual(x.dropped_records, 95)
        self.assertFalse(x.timed_out)

    def test_large_byte_flood_stops_at_total_budget(self):
        x = capture_disposable("byte_flood", max_total_bytes=4096, max_records=3)
        self.assertTrue(x.byte_limit_exceeded)
        self.assertLessEqual(len(x.records), 3)
        self.assertLessEqual(x.bytes_read, 4096 + 4096)
        self.assertFalse(hasattr(x, "crash_verified"))

    def test_invalid_byte_budget_refuses_to_spawn(self):
        with patch("offline_owned_stderr_s4h.subprocess.Popen") as popen:
            with self.assertRaises(ValueError):
                capture_disposable("normal", max_total_bytes=0)
            popen.assert_not_called()

    def test_split_writes_reassemble_one_line(self):
        x = capture_disposable("split")
        self.assertEqual(x.lines_seen, 1)
        self.assertEqual(x.records[0].message, "assembled")

    def test_info_and_debug_are_not_alerted(self):
        x = capture_disposable("info")
        self.assertEqual(x.lines_seen, 2)
        self.assertEqual(x.ignored_lines, 2)
        self.assertEqual(len(x.records), 0)

    def test_empty_stderr_produces_no_false_error(self):
        x = capture_disposable("empty")
        self.assertEqual(x.lines_seen, 0)
        self.assertEqual(len(x.records), 0)

    def test_unterminated_final_error_is_not_lost(self):
        x = capture_disposable("unterminated")
        self.assertEqual(x.lines_seen, 1)
        self.assertEqual(x.records[0].message, "no-final-LF")

    def test_inherited_pipe_writer_cannot_extend_grace_forever(self):
        # Simulate a direct child that has already exited but whose stderr
        # pipe remains readable-open (an inheriting writer). No real child
        # process, OS fd or service is launched or signalled in this test.
        proc = MagicMock()
        proc.pid = 711
        proc.poll.return_value = 0
        proc.stderr.fileno.return_value = 77
        selector = MagicMock()
        selector.select.return_value = []  # no EOF and no readiness forever

        with patch("offline_owned_stderr_s4h.subprocess.Popen", return_value=proc), \
             patch("offline_owned_stderr_s4h.os.set_blocking"), \
             patch("offline_owned_stderr_s4h.selectors.DefaultSelector", return_value=selector), \
             patch("offline_owned_stderr_s4h.time.monotonic",
                   side_effect=[0.0, 0.5, 1.0, 2.0]):
            with self.assertRaisesRegex(TimeoutError, "pipe failed to close"):
                capture_disposable("normal", timeout_seconds=0.5)
        self.assertEqual(selector.select.call_count, 2)
        proc.kill.assert_not_called()
        proc.stderr.close.assert_called_once()

    def test_unapproved_mode_fails_before_any_spawn(self):
        with patch("offline_owned_stderr_s4h.subprocess.Popen") as popen:
            with self.assertRaises(ValueError):
                capture_disposable("worldserver")
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
