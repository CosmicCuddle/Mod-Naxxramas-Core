"""F15 P30: bounded S3 restart sidecars. Disposable temp directories ONLY.

No daemon, systemd, log, real report path, root or server interaction. The
limits are offline TEST FIXTURES (backpressure), NOT an owner retention
policy, and a refusal is an untrusted diagnostic, not a real daemon event.
"""
import errno
import multiprocessing
import os
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))

import offline_restart  # noqa: E402
import offline_store  # noqa: E402
from offline_error_reports import OfflineErrorReportStore  # noqa: E402
from offline_restart import RestartObservation  # noqa: E402
from offline_store import Incident  # noqa: E402

CAP = offline_restart.MAX_RESTART_SIDECARS_PER_INCIDENT


def crash(n=1, service="worldserver"):
    return Incident(
        service=service, host="synthetic-host", boot="boot-fixture",
        invocation=f"run-{n}", pid=9000 + n,
        start_utc="2026-10-25T00:00:00Z", end_utc="2026-10-25T00:01:00Z",
        verified_actual_death=True, unexpected_death=True, exit_code=1)


def restart(incident, attempt="try-1", outcome="failed"):
    return RestartObservation(incident.identity(), attempt,
                              "2026-10-25T00:02:00Z", outcome, True)


def racer(folder, attempt, gate, result):
    """Separate disposable process with its own descriptors and the shared lock."""
    store = OfflineErrorReportStore(Path(folder))
    try:
        if not gate.wait(10):
            result.put(("no-start", attempt))
            return
        try:
            done = store.publish_restart(restart(crash(1), attempt))
            result.put(("published" if done else "duplicate", attempt))
        except OverflowError:
            result.put(("at-capacity", attempt))
        except TimeoutError:
            result.put(("lock-timeout", attempt))
    except BaseException as exc:  # reported, never swallowed silently
        result.put((type(exc).__name__, attempt))
    finally:
        store.close()


class RestartSidecarQuota(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Crash Logs"
        self.root.mkdir(mode=0o700)
        self.store = OfflineErrorReportStore(self.root)
        self.addCleanup(self.store.close)
        self.assertTrue(self.store.publish(crash(1)))

    def sidecars(self):
        return sorted(p.name for p in self.root.iterdir()
                      if offline_restart.SIDECAR_PATTERN.fullmatch(p.name))

    def finals(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir()
                if "-crash-" in p.name or p.name.startswith("error-burst-")}

    def temps(self):
        return [p for p in self.root.iterdir() if p.name.startswith(".f15-s2-")]

    # --- per-incident boundary -------------------------------------------
    def test_eight_attempts_accepted_ninth_refused_without_any_write(self):
        for i in range(CAP):
            self.assertTrue(self.store.publish_restart(restart(crash(1), f"try-{i}")))
        before = sorted(os.listdir(self.root))
        with self.assertRaisesRegex(OverflowError, "restart sidecar capacity"):
            self.store.publish_restart(restart(crash(1), "try-ninth"))
        self.assertEqual(sorted(os.listdir(self.root)), before)
        self.assertEqual(len(self.sidecars()), CAP)
        self.assertEqual(self.store.offline_rejections()["capacity"], 1)

    def test_1500_distinct_attempts_keep_exactly_eight_in_bounded_time(self):
        started = time.monotonic()
        accepted = refused = 0
        for i in range(1500):
            try:
                accepted += self.store.publish_restart(restart(crash(1), f"loop-{i}"))
            except OverflowError:
                refused += 1
        elapsed = time.monotonic() - started
        self.assertEqual((accepted, refused), (CAP, 1500 - CAP))
        self.assertEqual(len(self.sidecars()), CAP)
        self.assertEqual(self.temps(), [])
        # 1,500 rescans of a bounded directory, not a growing one (was ~151 s).
        self.assertLess(elapsed, 60.0)
        self.assertEqual(self.store.offline_rejections()["capacity"], 255)

    def test_duplicate_at_capacity_is_still_idempotent(self):
        for i in range(CAP):
            self.store.publish_restart(restart(crash(1), f"try-{i}"))
        self.assertFalse(self.store.publish_restart(restart(crash(1), "try-0")))
        self.assertEqual(self.store.offline_rejections()["capacity"], 0)

    def test_conflicting_replay_at_capacity_is_still_a_conflict(self):
        for i in range(CAP):
            self.store.publish_restart(restart(crash(1), f"try-{i}"))
        with self.assertRaises(FileExistsError):
            self.store.publish_restart(restart(crash(1), "try-0", "succeeded"))

    def test_invalid_attempt_is_refused_before_any_write(self):
        before = sorted(os.listdir(self.root))
        for bad in ("../x", "", "a b", "x" * 129):
            with self.assertRaises(ValueError):
                self.store.publish_restart(restart(crash(1), bad))
        self.assertEqual(sorted(os.listdir(self.root)), before)

    def test_refusal_leaves_reports_sidecars_and_history_byte_identical(self):
        for i in range(CAP):
            self.store.publish_restart(restart(crash(1), f"try-{i}"))
        snapshot = {p.name: p.read_bytes() for p in self.root.iterdir()}
        for i in range(20):
            with self.assertRaises(OverflowError):
                self.store.publish_restart(restart(crash(1), f"late-{i}"))
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()},
                         snapshot)

    # --- fairness and shared lanes ---------------------------------------
    def test_world_flood_cannot_consume_auth_sidecar_lane(self):
        self.assertTrue(self.store.publish(crash(2)))
        self.assertTrue(self.store.publish(crash(3, "authserver")))
        with patch("offline_restart.MAX_RESTART_SIDECARS_PER_SERVICE", 4):
            for n in (1, 2):
                for i in range(2):
                    self.store.publish_restart(restart(crash(n), f"w-{i}"))
            with self.assertRaises(OverflowError):
                self.store.publish_restart(restart(crash(2), "w-extra"))
            self.assertTrue(self.store.publish_restart(
                restart(crash(3, "authserver"), "a-0")))

    def test_total_lane_counts_malformed_symlinked_and_foreign_names(self):
        outside = Path(self.tmp.name) / "outside-target.txt"
        outside.write_text("must never change", encoding="utf-8")
        (self.root / "restart-not-a-real-sidecar.txt").write_text("junk")
        foreign = restart(crash(77), "orphan")       # incident never published
        os.symlink(outside, self.root / foreign.filename())
        with patch("offline_restart.MAX_TOTAL_RESTART_SIDECARS", 3):
            self.assertTrue(self.store.publish_restart(restart(crash(1), "ok-0")))
            with self.assertRaises(OverflowError):
                self.store.publish_restart(restart(crash(1), "ok-1"))
        self.assertEqual(outside.read_text(encoding="utf-8"), "must never change")
        self.assertTrue((self.root / "restart-not-a-real-sidecar.txt").exists())
        self.assertTrue(os.path.islink(self.root / foreign.filename()))

    def test_sidecars_and_reports_share_one_byte_budget(self):
        used = sum(p.lstat().st_size for p in self.root.iterdir()
                   if p.name.endswith(".txt") and "History" not in p.name)
        sidecar = len(offline_restart.sidecar_bytes(restart(crash(1), "b-0").info()))
        report = len(offline_store.report_bytes(crash(2).metadata()))
        # Room for the sidecar, and for crash 2 ONLY if sidecar bytes were
        # ignored by the report lane: one byte short when they are counted.
        with patch("offline_store.MAX_TOTAL_REPORT_BYTES", used + sidecar + report - 1):
            self.assertTrue(self.store.publish_restart(restart(crash(1), "b-0")))
            with self.assertRaises(OverflowError):
                self.store.publish(crash(2))
        with patch("offline_store.MAX_TOTAL_REPORT_BYTES", used + sidecar - 1):
            # ...and report bytes count against the sidecar lane.
            with self.assertRaises(OverflowError):
                self.store.publish_restart(restart(crash(1), "b-1"))

    # --- concurrency -------------------------------------------------------
    def race(self, attempts):
        ctx = multiprocessing.get_context("fork")
        gate, result = ctx.Event(), ctx.Queue()
        children = [ctx.Process(target=racer, args=(str(self.root), a, gate, result))
                    for a in attempts]
        for child in children:
            child.start()
        gate.set()
        outcomes = [result.get(timeout=30) for _ in children]
        for child in children:
            child.join(10)
        self.assertTrue(all(child.exitcode == 0 for child in children))
        return [kind for kind, _ in outcomes]

    def test_concurrent_distinct_attempts_never_exceed_incident_cap(self):
        kinds = self.race([f"race-{i}" for i in range(CAP + 6)])
        self.assertEqual(kinds.count("published"), CAP)
        self.assertEqual(kinds.count("at-capacity"), 6)
        self.assertEqual(len(self.sidecars()), CAP)
        self.assertEqual(self.temps(), [])

    def test_concurrent_identical_sidecar_is_written_once(self):
        kinds = self.race(["same"] * 6)
        self.assertEqual(kinds.count("published"), 1)
        self.assertEqual(kinds.count("duplicate"), 5)
        self.assertEqual(len(self.sidecars()), 1)

    # --- disk failures and crowding ---------------------------------------
    def test_enospc_before_link_leaves_no_sidecar_or_temp(self):
        with patch("offline_restart.os.link",
                   side_effect=OSError(errno.ENOSPC, "synthetic disk full")):
            with self.assertRaises(OSError) as caught:
                self.store.publish_restart(restart(crash(1), "full"))
        self.assertEqual(caught.exception.errno, errno.ENOSPC)
        self.assertEqual((self.sidecars(), self.temps()), ([], []))
        self.assertTrue(self.store.publish_restart(restart(crash(1), "full")))

    def test_eio_on_index_rebuild_keeps_final_sidecar_and_crash(self):
        crash_files = self.finals()
        with patch("offline_store.os.replace",
                   side_effect=OSError(errno.EIO, "synthetic index failure")):
            with self.assertRaises(OSError):
                self.store.publish_restart(restart(crash(1), "eio"))
        self.assertEqual(len(self.sidecars()), 1)
        self.assertEqual(self.finals(), crash_files)
        self.store.rebuild()
        self.assertFalse(self.store.publish_restart(restart(crash(1), "eio")))

    def test_crowded_directory_fails_closed_without_removal(self):
        for i in range(6):
            (self.root / f"unrelated-{i}.bin").write_bytes(b"x")
        before = sorted(os.listdir(self.root))
        with patch("offline_store.MAX_DIRECTORY_SCAN_ENTRIES", 5):
            with self.assertRaisesRegex(OverflowError, "scan budget"):
                self.store.publish_restart(restart(crash(1), "crowded"))
        self.assertEqual(sorted(os.listdir(self.root)), before)

    # --- negative checks for review items A11 / A13 ------------------------
    def test_lock_file_owned_by_another_uid_fails_closed_without_write(self):
        real = os.geteuid()
        with patch("offline_store.os.geteuid", return_value=real + 1):
            with self.assertRaisesRegex(PermissionError, "unsafe offline"):
                self.store.publish_restart(restart(crash(1), "owner"))
        self.assertEqual(self.sidecars(), [])

    def test_quota_lane_requests_are_validated(self):
        with self.store._locked():
            for args in (("bogus", "worldserver", 1), ("crash", "nodaemon", 1),
                         ("crash", "worldserver", -1), ("crash", "worldserver", True)):
                with self.assertRaises(ValueError):
                    self.store._admit_report_locked(*args)
            incident = crash(1).identity()
            for service, size in (("nodaemon", 1), ("worldserver", -1),
                                  ("worldserver", True), ("worldserver", 1.0)):
                with self.assertRaises(ValueError):
                    self.store._admit_restart_locked(incident, service, [], size)


if __name__ == "__main__":
    unittest.main()
