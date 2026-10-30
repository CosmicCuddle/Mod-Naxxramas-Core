"""Synthetic OFFLINE tests: no host paths, daemons, credentials or deletion."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools" / "f15" / "console_archive_policy.py"
spec = importlib.util.spec_from_file_location("console_archive_policy", PATH)
policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy
spec.loader.exec_module(policy)

T = datetime(2026, 10, 31, 0, 0, 0, tzinfo=timezone.utc)
BASE = "Worldserver-Console-2026-10-31_00-00-00Z-out-012345abcdef.txt"


def archive(**kw):
    args = dict(name=BASE, closed_at=T, tool_owned=True, closed=True,
                regular=True, symlink=False, link_count=1, device=7, inode=88)
    args.update(kw)
    return policy.ArchiveRecord(**args)


class Filenames(unittest.TestCase):
    def test_utc_filename_and_parse(self):
        n = policy.archive_filename("Worldserver", "out", T, "012345abcdef")
        self.assertEqual(n, BASE)
        self.assertEqual(policy.parsed_filename(n), ("Worldserver", "out", T))

    def test_auth_err_and_native(self):
        for source in ("out", "err", "native"):
            with self.subTest(source=source):
                n = policy.archive_filename("Authserver", source, T, "abc456789123")
                self.assertEqual(policy.parsed_filename(n), ("Authserver", source, T))

    def test_convert_explicit_offset_to_utc(self):
        local = datetime(2026, 10, 31, 1, tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(policy.archive_filename("Authserver", "native", local, "abc456789123"),
                         "Authserver-Console-2026-10-31_00-00-00Z-native-abc456789123.txt")

    def test_invalid_role(self):
        with self.assertRaises(ValueError):
            policy.archive_filename("Worldserver/../../", "out", T, "012345abcdef")

    def test_invalid_source(self):
        with self.assertRaises(ValueError):
            policy.archive_filename("Worldserver", "stdout/../", T, "012345abcdef")

    def test_invalid_token(self):
        for token in ("123", "../012345abcdef", "ABCDEF012345", "123456789abg"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                policy.archive_filename("Worldserver", "out", T, token)

    def test_reject_naive_time(self):
        with self.assertRaises(ValueError):
            policy.archive_filename("Worldserver", "out", datetime(2026, 10, 31), "012345abcdef")

    def test_disallow_paths(self):
        for n in ("../" + BASE, "/tmp/" + BASE, "dir\\" + BASE, BASE + "/suffix"):
            with self.subTest(n=n):
                self.assertIsNone(policy.parsed_filename(n))

    def test_bad_calendar_date(self):
        self.assertIsNone(policy.parsed_filename(BASE.replace("10-31", "02-31")))

    def test_do_not_match_crash_reports(self):
        self.assertIsNone(policy.parsed_filename("Crash-History.txt"))
        self.assertIsNone(policy.parsed_filename(
            "Worldserver-Crash-2026-10-31_00-00-00Z-out-012345abcdef.txt"))


class Retention(unittest.TestCase):
    def test_just_older_than_thirty_days(self):
        self.assertEqual(policy.retention_candidates([archive()], T + timedelta(days=30, seconds=1)), (BASE,))

    def test_exactly_thirty_days_is_kept(self):
        self.assertEqual(policy.retention_candidates([archive()], T + timedelta(days=30)), ())

    def test_29_days_23_hours_kept(self):
        self.assertEqual(policy.retention_candidates([archive()], T + timedelta(days=29, hours=23)), ())

    def test_future_timestamp_kept(self):
        self.assertEqual(policy.retention_candidates([archive()], T - timedelta(seconds=1)), ())

    def test_never_delete_open_file(self):
        self.assertFalse(policy.retention_candidates([archive(closed=False)], T + timedelta(days=40)))

    def test_never_delete_unowned_file(self):
        self.assertFalse(policy.retention_candidates([archive(tool_owned=False)], T + timedelta(days=40)))

    def test_never_delete_symlinks(self):
        self.assertFalse(policy.retention_candidates([archive(symlink=True)], T + timedelta(days=40)))

    def test_never_delete_non_regular(self):
        self.assertFalse(policy.retention_candidates([archive(regular=False)], T + timedelta(days=40)))

    def test_never_delete_multilink(self):
        self.assertFalse(policy.retention_candidates([archive(link_count=2)], T + timedelta(days=40)))

    def test_reject_nonpositive_identity(self):
        self.assertFalse(policy.retention_candidates([archive(inode=0)], T + timedelta(days=40)))
        self.assertFalse(policy.retention_candidates([archive(device=0)], T + timedelta(days=40)))

    def test_reject_manifest_name_timestamp_disagreement(self):
        self.assertFalse(policy.retention_candidates(
            [archive(closed_at=T + timedelta(seconds=5))], T + timedelta(days=40)))

    def test_duplicate_name_fail_closed(self):
        self.assertFalse(policy.retention_candidates(
            [archive(), archive(inode=89)], T + timedelta(days=40)))

    def test_do_not_delete_unrelated_files(self):
        self.assertFalse(policy.retention_candidates(
            [archive(name="Crash-History.txt")], T + timedelta(days=40)))

    def test_timezone_aware_retention(self):
        local = (T + timedelta(days=30, seconds=1)).astimezone(timezone(timedelta(hours=2)))
        self.assertEqual(policy.retention_candidates([archive()], local), (BASE,))

    def test_sorted_archive_candidates(self):
        extra = archive(name=policy.archive_filename("Authserver", "native", T, "012345abcdef"))
        self.assertEqual(policy.retention_candidates([archive(), extra], T + timedelta(days=31)),
                         tuple(sorted([BASE, extra.name])))


class IncrementalCapture(unittest.TestCase):
    def test_first_observation_skips_historical_eight_gig(self):
        p = policy.plan_increment(None, policy.StreamSample(7, 88, 7_700_000_000, T))
        self.assertEqual((p.event, p.start, p.stop),
                         ("bootstrap-skip", 7_700_000_000, 7_700_000_000))
        self.assertIsNotNone(p.warning)

    def test_append_only_new_bytes(self):
        old = policy.StreamCheckpoint(7, 88, 100, T)
        p = policy.plan_increment(old, policy.StreamSample(7, 88, 130, T + timedelta(seconds=1)))
        self.assertEqual((p.event, p.start, p.stop), ("append", 100, 130))
        self.assertIsNone(p.warning)

    def test_no_change_no_copy(self):
        old = policy.StreamCheckpoint(7, 88, 100, T)
        p = policy.plan_increment(old, policy.StreamSample(7, 88, 100, T + timedelta(seconds=1)))
        self.assertEqual((p.event, p.start, p.stop), ("unchanged", 100, 100))

    def test_detect_same_inode_shrink(self):
        old = policy.StreamCheckpoint(7, 88, 100, T)
        p = policy.plan_increment(old, policy.StreamSample(7, 88, 60, T + timedelta(seconds=1)))
        self.assertEqual((p.event, p.start, p.stop), ("truncated", 0, 60))
        self.assertIsNotNone(p.warning)

    def test_detect_inode_replacement(self):
        old = policy.StreamCheckpoint(7, 88, 100, T)
        p = policy.plan_increment(old, policy.StreamSample(7, 89, 60, T + timedelta(seconds=1)))
        self.assertEqual((p.event, p.start, p.stop), ("replaced", 0, 60))
        self.assertIsNotNone(p.warning)

    def test_detect_device_replacement(self):
        old = policy.StreamCheckpoint(7, 88, 100, T)
        p = policy.plan_increment(old, policy.StreamSample(8, 88, 60, T + timedelta(seconds=1)))
        self.assertEqual(p.event, "replaced")

    def test_repeated_checkpoints_no_recopy(self):
        p1 = policy.plan_increment(None, policy.StreamSample(7, 88, 100, T))
        p2 = policy.plan_increment(p1.checkpoint,
                                   policy.StreamSample(7, 88, 200, T + timedelta(seconds=1)))
        p3 = policy.plan_increment(p2.checkpoint,
                                   policy.StreamSample(7, 88, 200, T + timedelta(seconds=2)))
        self.assertEqual((p2.start, p2.stop, p3.start, p3.stop), (100, 200, 200, 200))

    def test_reject_backwards_time(self):
        old = policy.StreamCheckpoint(7, 88, 100, T)
        with self.assertRaises(ValueError):
            policy.plan_increment(old, policy.StreamSample(7, 88, 101, T - timedelta(seconds=1)))

    def test_reject_negative_sample_size(self):
        with self.assertRaises(ValueError):
            policy.plan_increment(None, policy.StreamSample(7, 88, -1, T))

    def test_reject_zero_inode(self):
        with self.assertRaises(ValueError):
            policy.plan_increment(None, policy.StreamSample(7, 0, 0, T))

    def test_reject_naive_sample_clock(self):
        with self.assertRaises(ValueError):
            policy.plan_increment(None, policy.StreamSample(7, 88, 0, datetime(2026, 10, 31)))

    def test_reject_invalid_checkpoint(self):
        old = policy.StreamCheckpoint(7, 88, -1, T)
        with self.assertRaises(ValueError):
            policy.plan_increment(old, policy.StreamSample(7, 88, 1, T + timedelta(seconds=1)))

    def test_midnight_no_historical_backfill(self):
        prev = policy.StreamCheckpoint(7, 88, 100, T - timedelta(seconds=1))
        p = policy.plan_increment(prev, policy.StreamSample(7, 88, 120, T))
        self.assertEqual((p.start, p.stop), (100, 120))
        self.assertEqual("2026-10-31", p.checkpoint.recorded_at.strftime("%Y-%m-%d"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
