"""Disposable F15 file-I/O integration tests, NEVER an owner-host archive tool.

Every path comes from this fixture's own tempfile.TemporaryDirectory.
The harness has no command-line interface, no external path input, no scheduler,
no runtime service adapter and no permission to touch real PM2/Auth logs.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
FILE = BASE / "tools" / "f15" / "console_archive_policy.py"
spec = importlib.util.spec_from_file_location("f15_archive_policy", FILE)
policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy
spec.loader.exec_module(policy)

UTC = timezone.utc
DAY = datetime(2026, 10, 31, tzinfo=UTC)
STREAMS = ("Worldserver-out", "Worldserver-err", "Authserver-native")
CAP = 4096


class DisposableArchiveHarness:
    """Test-only I/O. The only owned root is internally created and auto-removed."""

    def __init__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="f15-synthetic-only-")
        self.root = Path(self.temporary.name)
        self.input = self.root / "fake-sources"
        self.output = self.root / "fake-archives"
        self.input.mkdir(mode=0o700)
        self.output.mkdir(mode=0o700)
        self.checkpoints = {}
        self.records = {}

    def close(self):
        self.temporary.cleanup()

    def _parts(self, stream):
        if stream not in STREAMS:
            raise ValueError("untrusted stream")
        return stream.split("-", 1)

    def source_path(self, stream):
        self._parts(stream)
        return self.input / (stream + ".log")

    def part_path(self, stream):
        self._parts(stream)
        return self.output / (stream + ".part")

    def seed(self, stream, data):
        path = self.source_path(stream)
        if path.exists():
            raise FileExistsError(path.name)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

    def append_source(self, stream, data):
        path = self.source_path(stream)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

    def ingest(self, stream, now=DAY, max_bytes=CAP):
        """Read at most a bounded byte span, then checkpoint only written bytes."""
        if not isinstance(max_bytes, int) or not (0 < max_bytes <= CAP):
            raise ValueError("invalid per-poll budget")
        path = self.source_path(stream)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ValueError("unsafe source type or hardlink")
            prev = self.checkpoints.get(stream)
            sample = policy.StreamSample(before.st_dev, before.st_ino, before.st_size, now)
            proposed = policy.plan_increment(prev, sample)
            if proposed.event == "bootstrap-skip":
                self.checkpoints[stream] = proposed.checkpoint
                return proposed.event, b""
            end = min(proposed.stop, proposed.start + max_bytes)
            nbytes = end - proposed.start
            chunk = os.pread(fd, nbytes, proposed.start)
            if len(chunk) != nbytes:
                raise IOError("source changed while copying")
            after = os.fstat(fd)
            if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino) or after.st_size < end:
                raise IOError("source inode/size changed while copying")
        finally:
            os.close(fd)
        if chunk:
            outfd = os.open(self.part_path(stream),
                            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                outstat = os.fstat(outfd)
                if not stat.S_ISREG(outstat.st_mode) or outstat.st_nlink != 1:
                    raise ValueError("unsafe archive partial")
                # Synthetic-only append, not a crash-atomic multi-writer protocol.
                if os.write(outfd, chunk) != len(chunk):
                    raise IOError("short archive write")
                os.fsync(outfd)
            finally:
                os.close(outfd)
        self.checkpoints[stream] = policy.StreamCheckpoint(
            before.st_dev, before.st_ino, end, now)
        return proposed.event, chunk

    def seal(self, stream, closed_at, token="012345abcdef"):
        """Test-only seal. Only internally owned .part files can be published."""
        role, source = self._parts(stream)
        partial = self.part_path(stream)
        if not partial.exists():
            return None
        name = policy.archive_filename(role, source, closed_at, token)
        dest = self.output / name
        # Fail rather than overwrite an existing named archive.
        os.link(partial, dest, follow_symlinks=False)
        partial.unlink()
        metadata = dest.lstat()
        record = policy.ArchiveRecord(
            name, closed_at, True, True, stat.S_ISREG(metadata.st_mode),
            stat.S_ISLNK(metadata.st_mode), metadata.st_nlink,
            metadata.st_dev, metadata.st_ino)
        self.records[name] = record
        return dest

    def expired_candidates(self, now):
        return policy.retention_candidates(list(self.records.values()), now)

    def discard_expired_synthetic_only(self, now):
        """Can unlink only test-created files below own tempfile root."""
        planned = self.expired_candidates(now)
        deleted = []
        for name in planned:
            record = self.records[name]
            file = self.output / name
            try:
                current = file.lstat()
            except FileNotFoundError:
                continue
            if (current.st_ino, current.st_dev, current.st_nlink) != (
                    record.inode, record.device, 1):
                continue
            if not stat.S_ISREG(current.st_mode):
                continue
            # Safe inside dedicated disposable temporary fixture only;
            # NOT a production revalidation/unlink race solution.
            file.unlink()
            deleted.append(name)
            del self.records[name]
        return tuple(deleted)


class TestF15DisposableArchive(unittest.TestCase):
    def setUp(self):
        self.h = DisposableArchiveHarness()
        self.addCleanup(self.h.close)

    def bootstrap(self, stream="Worldserver-out", data=b"OLD"):
        self.h.seed(stream, data)
        return self.h.ingest(stream)

    def test_bootstrap_does_not_copy_legacy_source(self):
        event, blob = self.bootstrap(data=b"A" * 8000)
        self.assertEqual((event, blob), ("bootstrap-skip", b""))
        self.assertFalse(self.h.part_path("Worldserver-out").exists())

    def test_append_records_only_new_bytes(self):
        self.bootstrap(data=b"old")
        self.h.append_source("Worldserver-out", b"NEW\n")
        event, blob = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        self.assertEqual((event, blob), ("append", b"NEW\n"))
        self.assertEqual(self.h.part_path("Worldserver-out").read_bytes(), b"NEW\n")

    def test_repeat_poll_does_not_duplicate(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"1")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        event, blob = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=2))
        self.assertEqual((event, blob), ("unchanged", b""))
        self.assertEqual(self.h.part_path("Worldserver-out").read_bytes(), b"1")

    def test_bounded_4096_byte_poll(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"n" * 9000)
        _, first = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        _, second = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=2))
        _, third = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=3))
        self.assertEqual((len(first), len(second), len(third)), (4096, 4096, 808))
        self.assertEqual(self.h.part_path("Worldserver-out").stat().st_size, 9000)

    def test_lower_budget_throttles(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"12345")
        _, c = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1), 2)
        self.assertEqual(c, b"12")

    def test_reject_overbudget(self):
        self.bootstrap()
        with self.assertRaises(ValueError):
            self.h.ingest("Worldserver-out", DAY, CAP + 1)

    def test_reject_zero_budget(self):
        self.bootstrap()
        with self.assertRaises(ValueError):
            self.h.ingest("Worldserver-out", DAY, 0)

    def test_reject_unsupported_source(self):
        with self.assertRaises(ValueError):
            self.h.seed("../../Authserver-native", b"x")

    def test_world_out_and_err_are_isolated(self):
        for s in ("Worldserver-out", "Worldserver-err"):
            self.bootstrap(s)
        self.h.append_source("Worldserver-out", b"OUT")
        self.h.append_source("Worldserver-err", b"ERR")
        for s in ("Worldserver-out", "Worldserver-err"):
            self.h.ingest(s, DAY + timedelta(seconds=1))
        self.assertEqual(self.h.part_path("Worldserver-out").read_bytes(), b"OUT")
        self.assertEqual(self.h.part_path("Worldserver-err").read_bytes(), b"ERR")

    def test_auth_native_independent(self):
        self.bootstrap("Authserver-native")
        self.h.append_source("Authserver-native", b"AUTH")
        self.h.ingest("Authserver-native", DAY + timedelta(seconds=1))
        self.assertEqual(self.h.part_path("Authserver-native").read_bytes(), b"AUTH")

    def test_binary_contents_round_trip(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"\xff\x00\xfe\x0a")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        self.assertEqual(self.h.part_path("Worldserver-out").read_bytes(), b"\xff\x00\xfe\x0a")

    def test_truncation_detected_without_recopying_old(self):
        self.bootstrap(data=b"history")
        self.h.source_path("Worldserver-out").write_bytes(b"x")
        event, chunk = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        self.assertEqual((event, chunk), ("truncated", b"x"))

    def test_inode_replacement_detected(self):
        self.bootstrap()
        path = self.h.source_path("Worldserver-out")
        path.rename(self.h.input / "old.log")
        self.h.seed("Worldserver-out", b"fresh")
        event, chunk = self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        self.assertEqual((event, chunk), ("replaced", b"fresh"))

    def test_reject_symlink_source(self):
        target = self.h.input / "fake-target"
        target.write_bytes(b"x")
        self.h.source_path("Worldserver-out").symlink_to(target)
        with self.assertRaises(OSError):
            self.h.ingest("Worldserver-out")

    def test_reject_hardlink_source(self):
        self.h.seed("Worldserver-out", b"x")
        os.link(self.h.source_path("Worldserver-out"), self.h.input / "other")
        with self.assertRaises(ValueError):
            self.h.ingest("Worldserver-out")

    def test_partial_files_private(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"secret-synthetic")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        mode = self.h.part_path("Worldserver-out").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_seal_preserves_contents(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"PART")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        sealed = self.h.seal("Worldserver-out", DAY + timedelta(days=1))
        self.assertEqual(sealed.read_bytes(), b"PART")
        self.assertFalse(self.h.part_path("Worldserver-out").exists())

    def test_seal_no_empty_archive(self):
        self.bootstrap()
        self.assertIsNone(self.h.seal("Worldserver-out", DAY + timedelta(days=1)))

    def test_seal_duplicate_name_does_not_overwrite(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"PART")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        first = self.h.seal("Worldserver-out", DAY + timedelta(days=1))
        self.h.append_source("Worldserver-out", b"MORE")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=2))
        with self.assertRaises(FileExistsError):
            self.h.seal("Worldserver-out", DAY + timedelta(days=1))
        self.assertEqual(first.read_bytes(), b"PART")

    def test_correct_archive_not_expired_at_30_days(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"PART")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        date = DAY + timedelta(days=1)
        target = self.h.seal("Worldserver-out", date)
        self.assertFalse(self.h.discard_expired_synthetic_only(date + timedelta(days=30)))
        self.assertTrue(target.exists())

    def test_expired_synthetic_archive_removed(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"PART")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        date = DAY + timedelta(days=1)
        target = self.h.seal("Worldserver-out", date)
        name = target.name
        self.assertEqual(self.h.discard_expired_synthetic_only(
            date + timedelta(days=30, seconds=1)), (name,))
        self.assertFalse(target.exists())
        self.assertTrue(self.h.source_path("Worldserver-out").exists())

    def test_unknown_files_and_crash_history_not_removed(self):
        self.bootstrap()
        unrelated = self.h.output / "Crash-History.txt"
        unrelated.write_bytes(b"do-not-touch")
        self.h.discard_expired_synthetic_only(DAY + timedelta(days=400))
        self.assertEqual(unrelated.read_bytes(), b"do-not-touch")

    def test_unowned_manifest_does_not_remove(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"P")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        p = self.h.seal("Worldserver-out", DAY + timedelta(days=1))
        self.h.records[p.name] = replace(self.h.records[p.name], tool_owned=False)
        self.assertFalse(self.h.discard_expired_synthetic_only(DAY + timedelta(days=60)))
        self.assertTrue(p.exists())

    def test_archive_symlink_replacement_not_removed(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"P")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        p = self.h.seal("Worldserver-out", DAY + timedelta(days=1))
        p.unlink()
        target = self.h.output / "Crash-History.txt"
        target.write_bytes(b"protected")
        p.symlink_to(target)
        self.assertFalse(self.h.discard_expired_synthetic_only(DAY + timedelta(days=60)))
        self.assertEqual(target.read_bytes(), b"protected")

    def test_archive_inode_replacement_not_removed(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"P")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        p = self.h.seal("Worldserver-out", DAY + timedelta(days=1))
        substitute = self.h.output / "separate-owned-fixture"
        substitute.write_bytes(b"third-party-owned")
        substitute.replace(p)  # Moves a distinct, already allocated inode over the archive.
        self.assertFalse(self.h.discard_expired_synthetic_only(DAY + timedelta(days=60)))
        self.assertEqual(p.read_bytes(), b"third-party-owned")

    def test_archive_hardlink_not_removed(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"P")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        p = self.h.seal("Worldserver-out", DAY + timedelta(days=1))
        os.link(p, self.h.output / "other-hardlink")
        self.assertFalse(self.h.discard_expired_synthetic_only(DAY + timedelta(days=60)))
        self.assertTrue(p.exists())

    def test_appender_symlink_does_not_clobber_external_fixture(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"NEW")
        target = self.h.input / "separate-secret"
        target.write_bytes(b"protected")
        self.h.part_path("Worldserver-out").symlink_to(target)
        with self.assertRaises(OSError):
            self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        self.assertEqual(target.read_bytes(), b"protected")

    def test_failed_archive_append_checkpoint_does_not_advance(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"NEW")
        self.h.part_path("Worldserver-out").mkdir()
        with self.assertRaises(OSError):
            self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        self.assertEqual(self.h.checkpoints["Worldserver-out"].offset, 3)

    def test_utc_archive_name_with_dst_offset(self):
        self.bootstrap()
        self.h.append_source("Worldserver-out", b"N")
        self.h.ingest("Worldserver-out", DAY + timedelta(seconds=1))
        local = (DAY + timedelta(days=1)).astimezone(timezone(timedelta(hours=2)))
        p = self.h.seal("Worldserver-out", local)
        self.assertIn("2026-11-01_00-00-00Z", p.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
