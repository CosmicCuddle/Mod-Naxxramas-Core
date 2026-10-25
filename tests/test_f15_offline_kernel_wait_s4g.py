"""Tests only a child we spawn ourselves: never operator services or external PIDs."""
import os
import signal
import unittest
from offline_kernel_wait_s4g import OfflineKernelWaitFixture


class KernelWaitFixtureTests(unittest.TestCase):
    def witness(self, mode):
        f = OfflineKernelWaitFixture(mode)
        pid = f.launch()
        self.assertGreater(pid, 0)
        result = f.observe()
        self.assertEqual(result.child_pid, pid)
        self.assertGreaterEqual(result.ended_monotonic_ns,
                                result.started_monotonic_ns)
        with self.assertRaisesRegex(RuntimeError, "unconsumed"):
            f.observe()
        with self.assertRaisesRegex(RuntimeError, "already launched"):
            f.launch()
        return result

    def test_normal_exit_is_not_crash(self):
        x = self.witness("exit0")
        self.assertEqual((x.kind, x.exit_code, x.classification),
                         ("kernel_exit", 0, "normal_exit"))
        self.assertIsNone(x.signal_number)

    def test_nonzero_exit_is_not_fatal_signal(self):
        x = self.witness("exit2")
        self.assertEqual(x.classification, "nonzero_exit_not_signal")
        self.assertEqual(x.exit_code, 2)

    def test_fake_wrapper_139_is_not_signal_11(self):
        x = self.witness("exit139")
        self.assertEqual(x.kind, "kernel_exit")
        self.assertEqual(x.exit_code, 139)
        self.assertIsNone(x.signal_number)

    def test_kernel_sigsegv_is_a_real_child_signal(self):
        x = self.witness("sigsegv")
        self.assertEqual(x.signal_number, signal.SIGSEGV)
        self.assertEqual(x.classification, "fatal_child_signal")
        self.assertIsNone(x.exit_code)

    def test_kernel_sigabrt_is_a_real_child_signal(self):
        x = self.witness("sigabrt")
        self.assertEqual(x.signal_number, signal.SIGABRT)
        self.assertEqual(x.classification, "fatal_child_signal")

    def test_unplanned_sigterm_is_not_assumed_crash(self):
        x = self.witness("unplanned_sigterm")
        self.assertEqual(x.signal_number, signal.SIGTERM)
        self.assertEqual(x.classification, "signal_requires_policy")
        self.assertFalse(x.planned_by_parent)

    def test_parent_registered_planned_termination(self):
        x = self.witness("planned_sigterm")
        self.assertEqual(x.signal_number, signal.SIGTERM)
        self.assertEqual(x.classification, "planned_signal")
        self.assertTrue(x.planned_by_parent)

    def test_wrapper_zerocode_does_not_attest_grandchild(self):
        x = self.witness("masked_wrapper")
        self.assertEqual(x.classification, "normal_exit")
        self.assertEqual(x.exit_code, 0)
        self.assertIsNone(x.signal_number)

    def test_reject_foreign_mode_and_unstarted_observe(self):
        with self.assertRaises(ValueError):
            OfflineKernelWaitFixture("worldserver")
        with self.assertRaisesRegex(RuntimeError, "unconsumed"):
            OfflineKernelWaitFixture("exit0").observe()

    def test_parent_pid_guard(self):
        f = OfflineKernelWaitFixture("exit0")
        self.assertEqual(f._origin_pid, os.getpid())
        self.witness("exit0")


if __name__ == "__main__":
    unittest.main()
