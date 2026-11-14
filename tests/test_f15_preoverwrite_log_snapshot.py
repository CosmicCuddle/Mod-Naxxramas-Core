import importlib.util
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "snap", ROOT / "scripts/f15_preoverwrite_log_snapshot.py"
)
snap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snap)

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.logs = self.base / "logs"
        self.logs.mkdir()
        self.archive = self.logs / "Archived Logs"

    def finals(self):
        if not self.archive.exists():
            return []
        return sorted(
            p for p in self.archive.iterdir()
            if p.suffix in {".log", ".json"} and not p.name.startswith(".")
        )

    def test_snapshot_copies_independent_bytes_and_manifest(self):
        src = self.logs / "world.log"
        src.write_bytes(b"before overwrite\n")
        data, manifest = snap.snapshot_file(src, self.archive, NOW)
        self.assertEqual(data.read_bytes(), b"before overwrite\n")
        meta = json.loads(manifest.read_text())
        self.assertEqual(meta["retention_days"], 30)
        self.assertEqual(meta["source_path"], str(src))
        self.assertEqual(src.read_bytes(), b"before overwrite\n")
        src.write_bytes(b"new contents\n")
        self.assertEqual(data.read_bytes(), b"before overwrite\n")
        self.assertNotEqual(os.stat(data).st_ino, os.stat(src).st_ino)

    def test_directory_batch_publishes_all_regular_logs_only_after_preparation(self):
        (self.logs / "world.log").write_text("w")
        (self.logs / "auth.log").write_text("a")
        (self.logs / "Crash Logs").mkdir()
        (self.logs / ".f15-state").mkdir()
        nested = self.logs / "nested"
        nested.mkdir()
        (nested / "not-recursive.log").write_text("n")

        result = snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(len(result), 2)
        self.assertEqual(len(self.finals()), 4)
        manifests = [json.loads(m.read_text()) for _, m in result]
        self.assertEqual(
            {Path(x["source_path"]).name for x in manifests},
            {"world.log", "auth.log"},
        )
        self.assertFalse(any("not-recursive" in p.name for p in self.archive.iterdir()))

    def test_root_symlink_refused(self):
        real = self.base / "real-logs"
        real.mkdir()
        link = self.base / "logs-link"
        link.symlink_to(real, target_is_directory=True)
        archive = real / "Archived Logs"
        with self.assertRaises(snap.Refused):
            snap.snapshot_log_directory(link, archive, observed_utc=NOW)

    def test_single_source_symlink_refused(self):
        target = self.logs / "target.log"
        target.write_text("x")
        link = self.logs / "link.log"
        link.symlink_to(target)
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(link, self.archive, NOW)

    def test_directory_symlink_refused_before_any_final_snapshot(self):
        (self.logs / "world.log").write_text("w")
        target = self.logs / "target.log"
        target.write_text("x")
        (self.logs / "evil.log").symlink_to(target)

        with self.assertRaises(snap.Refused):
            snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(self.finals(), [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO unsupported on this platform")
    def test_fifo_refused_before_any_final_snapshot(self):
        (self.logs / "world.log").write_text("w")
        os.mkfifo(self.logs / "pipe.log")

        with self.assertRaises(snap.Refused):
            snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(self.finals(), [])

    def test_hardlinked_source_refused_before_any_final_snapshot(self):
        src = self.logs / "world.log"
        src.write_text("x")
        os.link(src, self.logs / "other.log")

        with self.assertRaises(snap.Refused):
            snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(self.finals(), [])

    def test_excluded_f15_name_must_be_real_directory(self):
        (self.logs / "world.log").write_text("w")
        (self.logs / "Crash Logs").write_text("not a directory")

        with self.assertRaises(snap.Refused):
            snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(self.finals(), [])

    def test_excluded_f15_symlink_refused(self):
        (self.logs / "world.log").write_text("w")
        target = self.base / "real-crash"
        target.mkdir()
        (self.logs / "Crash Logs").symlink_to(target, target_is_directory=True)

        with self.assertRaises(snap.Refused):
            snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(self.finals(), [])

    def test_second_source_prepare_failure_publishes_no_final_pairs(self):
        (self.logs / "a.log").write_text("a")
        (self.logs / "b.log").write_text("b")
        real_prepare = snap._prepare_snapshot
        calls = {"n": 0}

        def fail_second(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise snap.Refused("synthetic second-source failure")
            return real_prepare(*args, **kwargs)

        with mock.patch.object(snap, "_prepare_snapshot", side_effect=fail_second):
            with self.assertRaises(snap.Refused):
                snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(self.finals(), [])
        self.assertTrue(any(".pending." in p.name for p in self.archive.iterdir()))

    def test_source_changed_after_prescan_publishes_no_final_pairs(self):
        (self.logs / "a.log").write_text("a")
        (self.logs / "b.log").write_text("b")
        real_open = snap._open_source

        def refuse_second(path, expected=None):
            if expected is not None and Path(path).name == "b.log":
                raise snap.Refused("source changed after pre-scan")
            return real_open(path, expected)

        with mock.patch.object(snap, "_open_source", side_effect=refuse_second):
            with self.assertRaises(snap.Refused):
                snap.snapshot_log_directory(self.logs, self.archive, observed_utc=NOW)

        self.assertEqual(self.finals(), [])

    def test_source_change_during_copy_refused_and_source_untouched(self):
        src = self.logs / "world.log"
        src.write_bytes(b"A" * 4096)
        real_fingerprint = snap._fingerprint
        calls = {"n": 0}

        def changed_after_copy(st):
            calls["n"] += 1
            value = real_fingerprint(st)
            if calls["n"] >= 2:
                return (value[0], value[1], value[2], value[3] + 1, value[4])
            return value

        with mock.patch.object(snap, "_fingerprint", side_effect=changed_after_copy):
            with self.assertRaises(snap.Refused):
                snap.snapshot_file(src, self.archive, NOW)

        self.assertEqual(src.read_bytes(), b"A" * 4096)
        self.assertEqual(self.finals(), [])
        self.assertTrue(any(".pending." in p.name for p in self.archive.iterdir()))

    def test_partial_os_write_is_completed(self):
        src = self.logs / "world.log"
        src.write_bytes(b"A" * 8192)
        real_write = os.write
        first = {"yes": True}

        def partial(fd, data):
            if first["yes"] and len(data) > 1:
                first["yes"] = False
                half = max(1, len(data) // 2)
                return real_write(fd, data[:half])
            return real_write(fd, data)

        with mock.patch.object(snap.os, "write", side_effect=partial):
            data, _manifest = snap.snapshot_file(src, self.archive, NOW)

        self.assertEqual(data.read_bytes(), src.read_bytes())

    def test_collision_refused_without_overwriting_existing_snapshot(self):
        src = self.logs / "world.log"
        src.write_text("x")
        first_data, first_manifest = snap.snapshot_file(src, self.archive, NOW)
        first_bytes = first_data.read_bytes()
        first_meta = first_manifest.read_bytes()

        with self.assertRaises(snap.Refused):
            snap.snapshot_file(src, self.archive, NOW)

        self.assertEqual(first_data.read_bytes(), first_bytes)
        self.assertEqual(first_manifest.read_bytes(), first_meta)

    def test_same_timestamp_concurrent_snapshot_serializes_and_never_overwrites(self):
        src = self.logs / "world.log"
        src.write_text("x")
        results = []
        errors = []

        def run():
            try:
                results.append(snap.snapshot_file(src, self.archive, NOW))
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], snap.Refused)
        self.assertEqual(len(self.finals()), 2)

    def test_insecure_archive_lock_refused(self):
        self.archive.mkdir(mode=0o700)
        lock = self.archive / ".f15-snapshot.lock"
        lock.write_text("lock")
        lock.chmod(0o644)
        src = self.logs / "world.log"
        src.write_text("x")

        with self.assertRaises(snap.Refused):
            snap.snapshot_file(src, self.archive, NOW)

        self.assertEqual(self.finals(), [])

    def test_publication_failure_propagates_and_never_returns_success(self):
        src = self.logs / "world.log"
        src.write_text("x")
        real_replace = os.replace
        calls = {"n": 0}

        def fail_second(source, destination):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("synthetic publish interruption")
            return real_replace(source, destination)

        with mock.patch.object(snap.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                snap.snapshot_file(src, self.archive, NOW)

        # Partial evidence is acceptable after interrupted publication, but a
        # successful (data, manifest) pair was never returned.
        self.assertEqual(len(list(self.archive.glob("*.json"))), 0)
        self.assertLessEqual(len(list(self.archive.glob("*.log"))), 1)

    def test_insecure_archive_directory_refused(self):
        self.archive.mkdir(mode=0o755)
        self.archive.chmod(0o755)
        src = self.logs / "world.log"
        src.write_text("x")
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(src, self.archive, NOW)

    def test_naive_observation_time_refused(self):
        src = self.logs / "world.log"
        src.write_text("x")
        with self.assertRaises(snap.Refused):
            snap.snapshot_file(
                src, self.archive, datetime(2026, 11, 13, 12, 0, 0)
            )


if __name__ == "__main__":
    unittest.main()
