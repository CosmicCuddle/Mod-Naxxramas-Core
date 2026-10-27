"""F15 P29 source-only: directory-inode lock prevents split cooperative lock domains.

All experiments use disposable PRIVATE fixture folders. No World/Auth server,
journal, SQL, root, systemd, installed module, or daemon identity is touched.
A cooperating lock protocol is NOT a hostile same-UID security boundary.
"""
import errno
import fcntl
import multiprocessing
import os
from pathlib import Path
import sys
import threading
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "f15"))
from offline_store import Incident, IncidentStore


def crash(index=1):
    return Incident(
        service="worldserver",
        host="offline-fixture",
        boot="fixture-boot",
        invocation=f"fixture-{index}",
        pid=10000 + index,
        start_utc="2026-10-27T12:00:00Z",
        end_utc="2026-10-27T12:01:00Z",
        verified_actual_death=True,
        unexpected_death=True,
        exit_code=1,
    )


def native_writer_holding(folder, ready, release, queue):
    """Fresh subprocess opens its own store and holds BOTH native locks."""
    store = IncidentStore(Path(folder))
    try:
        with store._locked():
            ready.set()
            if not release.wait(10):
                queue.put("release-timeout")
                return
        queue.put("released")
    except BaseException as exc:
        queue.put(type(exc).__name__)
    finally:
        store.close()


class PinnedDirectoryFlock(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private-reports"
        self.root.mkdir(mode=0o700)
        self.store = IncidentStore(self.root)
        self.addCleanup(self.store.close)

    def crash_names(self):
        return sorted(p.name for p in self.root.glob("*-crash-*.txt"))

    def test_replaced_legacy_lock_does_not_split_two_modern_writers(self):
        ready = multiprocessing.Event()
        release = multiprocessing.Event()
        outcomes = multiprocessing.Queue()
        child = multiprocessing.Process(
            target=native_writer_holding,
            args=(str(self.root), ready, release, outcomes),
        )
        child.start()
        try:
            self.assertTrue(ready.wait(3), "first fixture writer did not lock")
            named = self.root / ".f15.offline.lock"
            original_inode = named.stat().st_ino
            renamed = self.root / ".f15.offline.lock.replaced-fixture"
            named.rename(renamed)
            replacement_fd = os.open(
                named, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            os.close(replacement_fd)
            self.assertNotEqual(named.stat().st_ino, original_inode)
            # This new named lock is entirely UNHELD. Directory-inode flock
            # must prevent entry; older name-only flock would allow it.
            new_lock_fd = os.open(named, os.O_RDWR | os.O_NOFOLLOW)
            try:
                fcntl.flock(new_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(new_lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(new_lock_fd)
            with patch("offline_store.LOCK_WAIT_SECONDS", 0.08), \
                 patch("offline_store.LOCK_POLL_SECONDS", 0.004):
                with self.assertRaisesRegex(TimeoutError, "deadline"):
                    self.store.publish(crash(1))
            self.assertEqual(self.crash_names(), [])
            self.assertEqual(self.store.offline_rejections()["lock_timeout"], 1)
        finally:
            release.set()
            child.join(4)
            if child.is_alive():
                child.terminate()
                child.join(3)
        self.assertEqual(child.exitcode, 0)
        self.assertEqual(outcomes.get(timeout=2), "released")
        self.assertTrue(self.store.publish(crash(1)))
        self.assertEqual(len(self.crash_names()), 1)
        self.assertTrue(renamed.is_file())  # no silent deletion

    def test_legacy_named_lock_is_still_respected(self):
        # An older compatible F15 publisher only locks the named file.
        # The modern dual lock MUST wait for that writer, too.
        named = self.root / ".f15.offline.lock"
        fd = os.open(named, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch("offline_store.LOCK_WAIT_SECONDS", 0.06), \
                 patch("offline_store.LOCK_POLL_SECONDS", 0.004):
                with self.assertRaisesRegex(TimeoutError, "deadline"):
                    self.store.publish(crash(1))
            self.assertEqual(self.crash_names(), [])
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        self.assertTrue(self.store.publish(crash(1)))

    def test_same_instance_threads_get_distinct_directory_lock_descriptions(self):
        # os.dup(self._fd) would share an open file description, so it
        # would NOT serialize these two threads. os.open(".", dir_fd=...)
        # must instead create a new description for every acquisition.
        errors = []
        with self.store._locked():
            def competing_thread():
                try:
                    with patch("offline_store.LOCK_WAIT_SECONDS", 0.06), \
                         patch("offline_store.LOCK_POLL_SECONDS", 0.004):
                        with self.store._locked():
                            errors.append("wrongly-entered")
                except TimeoutError:
                    errors.append("deadline")

            thread = threading.Thread(target=competing_thread, daemon=True)
            thread.start()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, ["deadline"])
        self.assertEqual(self.store.offline_rejections()["lock_timeout"], 1)
        self.assertTrue(self.store.publish(crash(1)))

    def test_missing_directory_flock_support_is_not_downgraded(self):
        with patch("offline_store.fcntl.flock",
                   side_effect=OSError(errno.EOPNOTSUPP, "disposable unsupported FS")):
            with self.assertRaises(OSError) as caught:
                self.store.publish(crash(1))
            self.assertEqual(caught.exception.errno, errno.EOPNOTSUPP)
        self.assertFalse(self.crash_names())
        self.assertFalse((self.root / ".f15.offline.lock").exists())
        self.assertTrue(self.store.publish(crash(1)))

    def test_swapped_legacy_path_does_not_affect_pinned_dir_identity(self):
        a = IncidentStore(self.root)
        self.addCleanup(a.close)
        with a._locked():
            named = self.root / ".f15.offline.lock"
            rotated = self.root / ".f15.offline.lock-old"
            named.rename(rotated)
            fd = os.open(named, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            self.assertEqual(os.fstat(self.store._fd).st_ino,
                             os.fstat(a._fd).st_ino)
        self.assertTrue(self.store.publish(crash(1)))

    def test_legacy_lock_open_failure_releases_directory_flock(self):
        # After the directory lock is acquired, failure to open the old
        # named lock must close the directory FD even on exception.
        original_open = os.open

        def reject_legacy(path, flags, *args, **kwargs):
            if path == ".f15.offline.lock":
                raise OSError(errno.EACCES, "synthetic legacy lock denied")
            return original_open(path, flags, *args, **kwargs)

        with patch("offline_store.os.open", side_effect=reject_legacy):
            with self.assertRaises(OSError) as caught:
                self.store.publish(crash(1))
            self.assertEqual(caught.exception.errno, errno.EACCES)
        self.assertEqual(self.crash_names(), [])
        # A leaked directory lock would cause the next independent opener
        # to time out rather than succeeding immediately.
        other = IncidentStore(self.root)
        try:
            with patch("offline_store.LOCK_WAIT_SECONDS", 0.08):
                self.assertTrue(other.publish(crash(1)))
        finally:
            other.close()

    def test_positive_serialization_with_intact_legacy_path(self):
        with self.store._locked():
            self.assertEqual(self.crash_names(), [])
            self.assertFalse((self.root / "Crash-History.txt").exists())
        self.assertTrue(self.store.publish(crash(2)))
        self.assertFalse(self.store.publish(crash(2)))
        self.assertEqual(len(self.crash_names()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
