"""End-to-end fake-file tests for tests/f15_integrated_disposable_runner.py.

Every file lives in the runner's own tempfile.TemporaryDirectory. Nothing here
touches PM2, tmux, a launcher, a server, a database or any real log.

A "restart" closes the runner (releasing its lock, as a dead process would)
and builds a new one on the same disposable workspace.
Tests named test_BLOCKER_* pass by demonstrating a known, unfixed gap.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

_SOURCE = Path(__file__).resolve().parent / "f15_integrated_disposable_runner.py"
_spec = importlib.util.spec_from_file_location("f15_integrated_disposable_runner", _SOURCE)
R = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = R
_spec.loader.exec_module(R)

UTC = timezone.utc
D0 = datetime(2026, 11, 2, tzinfo=UTC)
OUT, ERR, AUTH = "Worldserver-out", "Worldserver-err", "Authserver-native"


def at(day, hours=0, minutes=0, seconds=0):
    return D0 + timedelta(days=day, hours=hours, minutes=minutes, seconds=seconds)


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = R.DisposableWorkspace()
        self.addCleanup(self.ws.close)
        self.runner = R.IntegratedRunner(self.ws)
        self.addCleanup(lambda: self.runner.close())

    def restart(self):
        self.runner.close()
        self.runner = R.IntegratedRunner(self.ws)

    def boot(self, *streams, when=None, history=b"HISTORY-NOT-BACKFILLED\n"):
        for stream in streams or (OUT, ERR, AUTH):
            self.ws.seed(stream, history)
            self.assertEqual(self.runner.poll(stream, when or at(0, 0, 0, 1)).events, ("bootstrap-skip",))

    def snapshot(self):
        result = {}
        for stream in (OUT, ERR, AUTH):
            path = self.ws.source_path(stream)
            if path.exists():
                meta = path.stat()
                result[stream] = (hashlib.sha256(path.read_bytes()).hexdigest(), meta.st_ino,
                                  meta.st_size, meta.st_mtime_ns)
        return result

    def archive_files(self):
        return sorted(p.name for p in self.runner.archive.iterdir())


class EndToEnd(Base):
    def test_three_streams_to_three_daily_archives(self):
        self.boot()
        self.ws.append(OUT, b"world line 1\n")
        self.ws.append(ERR, b"world error 1\n")
        self.ws.append(AUTH, b"auth line 1\n")
        for stream in (OUT, ERR, AUTH):
            self.assertEqual(self.runner.poll(stream, at(0, 6)).events, ("appended",))
        self.ws.append(OUT, b"world line 2\n")
        self.runner.poll(OUT, at(0, 23, 59, 58))
        before = self.snapshot()
        sealed = self.runner.seal_through(at(1, 0, 0, 5))
        self.assertEqual(sorted(e["stream"] for e in sealed), sorted([OUT, ERR, AUTH]))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"world line 1\nworld line 2\n")
        self.assertEqual(self.runner.archive_bytes(ERR, at(0).date()), b"world error 1\n")
        self.assertEqual(self.runner.archive_bytes(AUTH, at(0).date()), b"auth line 1\n")
        self.assertEqual(self.snapshot(), before)  # sealing never touches the originals

    def test_archive_names_use_pr249_policy(self):
        self.boot(OUT)
        self.ws.append(OUT, b"x\n")
        self.runner.poll(OUT, at(0, 1))
        self.runner.seal_through(at(1, 0, 1))
        entry = self.runner.archive_entry(OUT, at(0).date())
        role, source, closed = R.policy.parsed_filename(entry["name"])
        self.assertEqual((role, source, closed), ("Worldserver", "out", at(1)))
        self.assertEqual(entry["closed_at"], at(1).isoformat())

    def test_bootstrap_skips_history_and_says_so(self):
        self.boot(OUT, history=b"OLD" * 1000)
        self.ws.append(OUT, b"new\n")
        self.runner.poll(OUT, at(0, 1))
        self.runner.seal_through(at(1, 0, 1))
        entry = self.runner.archive_entry(OUT, at(0).date())
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"new\n")
        kinds = [n["kind"] for n in entry["notes"]]
        self.assertEqual(kinds, ["bootstrap-skip"])
        self.assertIn("3000 existing bytes not backfilled", entry["notes"][0]["detail"])

    def test_streams_stay_separate_and_labelled(self):
        self.boot()
        self.ws.append(OUT, b"OUT-ONLY\n")
        self.ws.append(ERR, b"ERR-ONLY\n")
        self.ws.append(AUTH, b"AUTH-ONLY\n")
        for stream in (OUT, ERR, AUTH):
            self.runner.poll(stream, at(0, 3))
        self.runner.seal_through(at(1, 0, 1))
        texts = {s: self.runner.archive_bytes(s, at(0).date()) for s in (OUT, ERR, AUTH)}
        self.assertEqual(texts, {OUT: b"OUT-ONLY\n", ERR: b"ERR-ONLY\n", AUTH: b"AUTH-ONLY\n"})
        files = self.archive_files()
        self.assertEqual(len([f for f in files if f.endswith(".txt")]), 3)  # no merged timeline file
        auth = self.runner.archive_entry(AUTH, at(0).date())
        self.assertIn("NOT a PTY console transcript", auth["completeness"])
        self.assertIn("not the event time", auth["time_label"])
        err = self.runner.archive_entry(ERR, at(0).date())
        self.assertIn("not a crash diagnosis", err["completeness"])
        sidecar = json.loads((self.runner.archive / err["sidecar"]).read_text())
        self.assertEqual(sidecar["sha256"], err["sha256"])

    def test_large_append_is_split_but_archived_once(self):
        self.boot(OUT)
        payload = ("é" * 5000 + "\n").encode("utf-8")  # > MAX_SEGMENT, splits never cut a codepoint
        self.ws.append(OUT, payload)
        self.assertEqual(self.runner.poll(OUT, at(0, 1)).captured, payload)
        for record in self.runner.records(OUT):
            if record.kind == "seg":
                record.path.read_bytes().decode("utf-8")
        self.runner.seal_through(at(1, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), payload)

    def test_resealing_is_idempotent(self):
        self.boot(OUT)
        self.ws.append(OUT, b"once\n")
        self.runner.poll(OUT, at(0, 1))
        self.runner.seal_through(at(1, 0, 1))
        files = self.archive_files()
        self.assertEqual(self.runner.seal_through(at(1, 0, 2)), [])
        self.restart()
        self.assertEqual(self.runner.seal_through(at(1, 0, 3)), [])
        self.assertEqual(self.archive_files(), files)


class CrashRecovery(Base):
    def _crash_and_resume(self, failpoint):
        self.boot(OUT)
        self.ws.append(OUT, b"line-A\n")
        self.runner.poll(OUT, at(0, 1))
        self.ws.append(OUT, b"line-B\n")
        with self.assertRaises(R.SyntheticCrash):
            self.runner.poll(OUT, at(0, 2), fail_at=failpoint)
        self.restart()
        self.ws.append(OUT, b"line-C\n")
        self.runner.poll(OUT, at(0, 3))
        self.runner.seal_through(at(1, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"line-A\nline-B\nline-C\n")

    def test_stop_before_record_publish(self):
        self._crash_and_resume("before-record-publish")

    def test_stop_after_record_publish_before_checkpoint(self):
        self._crash_and_resume("after-record-publish")

    def test_stop_before_checkpoint_publish(self):
        self._crash_and_resume("before-checkpoint-publish")

    def test_stop_after_checkpoint(self):
        self._crash_and_resume("after-checkpoint")

    def test_stop_during_bootstrap(self):
        self.ws.seed(OUT, b"HISTORY\n")
        with self.assertRaises(R.SyntheticCrash):
            self.runner.poll(OUT, at(0, 1), fail_at="after-record-publish")
        self.restart()
        self.ws.append(OUT, b"after\n")
        self.assertEqual(self.runner.poll(OUT, at(0, 2)).events, ("recovered", "appended"))
        self.runner.seal_through(at(1, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"after\n")

    def test_stop_between_publication_and_daily_sealing(self):
        self.boot(OUT)
        self.ws.append(OUT, b"published on day 0\n")
        self.runner.poll(OUT, at(0, 23, 59, 59))
        self.restart()  # process gone before any seal ran
        self.restart()
        self.runner.seal_through(at(1, 0, 0, 30))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"published on day 0\n")
        self.ws.append(OUT, b"day 1\n")
        self.runner.poll(OUT, at(1, 1))
        self.runner.seal_through(at(2, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(1).date()), b"day 1\n")
        self.assertEqual(len([f for f in self.archive_files() if f.endswith(".txt")]), 2)

    def test_seal_before_adoption_still_archives_each_byte_once(self):
        self.boot(OUT)
        self.ws.append(OUT, b"published, never checkpointed\n")
        with self.assertRaises(R.SyntheticCrash):
            self.runner.poll(OUT, at(0, 23), fail_at="after-record-publish")
        self.restart()
        self.runner.seal_through(at(1, 0, 1))  # sealing runs before any poll adopts it
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"published, never checkpointed\n")
        self.ws.append(OUT, b"next\n")
        self.assertEqual(self.runner.poll(OUT, at(1, 1)).captured, b"next\n")
        self.runner.seal_through(at(2, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(1).date()), b"next\n")

    def test_stop_after_archive_publish_before_manifest(self):
        self.boot(OUT)
        self.ws.append(OUT, b"sealed once\n")
        self.runner.poll(OUT, at(0, 1))
        with self.assertRaises(R.SyntheticCrash):
            self.runner.seal_through(at(1, 0, 1), fail_at="after-archive-publish")
        self.assertIsNone(self.runner.archive_entry(OUT, at(0).date()))
        self.restart()
        self.runner.seal_through(at(1, 0, 2))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"sealed once\n")
        self.assertEqual(len([f for f in self.archive_files() if f.endswith(".txt")]), 1)

    def test_stop_before_archive_publish(self):
        self.boot(OUT)
        self.ws.append(OUT, b"x\n")
        self.runner.poll(OUT, at(0, 1))
        with self.assertRaises(R.SyntheticCrash):
            self.runner.seal_through(at(1, 0, 1), fail_at="before-archive-publish")
        self.restart()
        self.assertFalse(any(f.endswith(".pending") for f in self.archive_files()))
        self.runner.seal_through(at(1, 0, 2))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"x\n")

    def test_injected_full_disk_fails_visibly_and_loses_nothing(self):
        self.boot(OUT)
        self.ws.append(OUT, b"needs space\n")
        with self.assertRaisesRegex(R.FailClosed, "No space left"):
            self.runner.poll(OUT, at(0, 1), fail_at="enospc")
        self.assertFalse(any(p.name.endswith(".pending") for p in self.runner.segments.iterdir()))
        self.assertEqual(self.runner.poll(OUT, at(0, 2)).captured, b"needs space\n")
        self.runner.seal_through(at(1, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"needs space\n")


class TimeAndEncoding(Base):
    def test_split_utf8_across_polls(self):
        self.boot(OUT)
        euro = "€".encode("utf-8")
        self.ws.append(OUT, b"price " + euro[:2])
        result = self.runner.poll(OUT, at(0, 1))
        self.assertEqual(result.captured, b"price ")
        self.assertIn("held-incomplete-utf8", result.events)
        self.ws.append(OUT, euro[2:] + b"5\n")
        self.assertEqual(self.runner.poll(OUT, at(0, 2)).captured, euro + b"5\n")
        self.runner.seal_through(at(1, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()).decode("utf-8"), "price €5\n")

    def test_split_utf8_across_midnight(self):
        self.boot(OUT)
        euro = "€".encode("utf-8")
        self.ws.append(OUT, b"before " + euro[:1])
        self.runner.poll(OUT, at(0, 23, 59, 59))
        self.ws.append(OUT, euro[1:] + b"\n")
        self.runner.poll(OUT, at(1, 0, 0, 1))
        self.runner.seal_through(at(2, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"before ")
        self.assertEqual(self.runner.archive_bytes(OUT, at(1).date()), euro + b"\n")
        self.assertTrue(self.runner.archive_entry(OUT, at(0).date())["utf8_valid"])
        self.assertTrue(self.runner.archive_entry(OUT, at(1).date())["utf8_valid"])

    def test_stale_incomplete_tail_is_kept_and_flagged(self):
        self.boot(OUT)
        self.ws.append(OUT, b"cut " + "€".encode("utf-8")[:2])
        self.runner.poll(OUT, at(0, 1))
        result = self.runner.poll(OUT, at(0, 2))  # source did not grow: publish as-is
        self.assertIn("incomplete-utf8-tail", result.events)
        self.runner.seal_through(at(1, 0, 1))
        entry = self.runner.archive_entry(OUT, at(0).date())
        self.assertFalse(entry["utf8_valid"])
        self.assertIn("never repaired", entry["encoding"])  # raw bytes kept, not "valid UTF-8"
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"cut \xe2\x82")
        self.assertIn("incomplete-utf8-tail", [n["kind"] for n in entry["notes"]])

    def test_idle_day_closes_and_delayed_append_goes_to_observation_day(self):
        self.boot(OUT)
        self.ws.append(OUT, b"day0\n")
        self.runner.poll(OUT, at(0, 5))
        self.ws.append(OUT, b"written late on day 1, first seen on day 2\n")
        self.runner.seal_through(at(2, 0, 0, 1))
        self.assertEqual(self.runner.archive_entry(OUT, at(1).date())["state"], "idle")
        self.assertIsNone(self.runner.archive_bytes(OUT, at(1).date()))
        self.runner.poll(OUT, at(2, 0, 0, 10))
        self.runner.seal_through(at(3, 0, 1))
        self.assertEqual(self.runner.archive_bytes(OUT, at(2).date()),
                         b"written late on day 1, first seen on day 2\n")

    def test_clock_moving_backwards_fails_closed(self):
        self.boot(OUT)
        before = [r.path.name for r in self.runner.records(OUT)]
        self.ws.append(OUT, b"x\n")
        with self.assertRaisesRegex(R.FailClosed, "backwards"):
            self.runner.poll(OUT, at(0, 0, 0, 0))
        self.assertEqual([r.path.name for r in self.runner.records(OUT)], before)
        with self.assertRaisesRegex(R.FailClosed, "backwards"):
            self.runner.seal_through(at(-1))
        self.restart()  # the clock is durable state, not process memory
        with self.assertRaisesRegex(R.FailClosed, "backwards"):
            self.runner.poll(OUT, at(0, 0, 0, 0))

    def test_clock_forward_jump_seals_idle_days_but_large_jump_fails_closed(self):
        self.boot(OUT)
        self.ws.append(OUT, b"x\n")
        self.runner.poll(OUT, at(0, 1))
        self.runner.seal_through(at(4, 0, 1))
        states = [self.runner.archive_entry(OUT, at(d).date())["state"] for d in range(4)]
        self.assertEqual(states, ["sealed", "idle", "idle", "idle"])
        with self.assertRaisesRegex(R.FailClosed, "too far"):
            self.runner.poll(OUT, at(4) + timedelta(days=63))


class SourceSafety(Base):
    def test_symlinked_source_fails_closed(self):
        target = self.ws.root / "sources" / "elsewhere.log"
        target.write_bytes(b"x")
        os.symlink(target, self.ws.source_path(OUT))
        with self.assertRaisesRegex(R.FailClosed, "symlink"):
            self.runner.poll(OUT, at(0, 1))
        self.assertEqual(self.runner.records(OUT), [])

    def test_hardlinked_source_fails_closed(self):
        self.ws.seed(OUT, b"x")
        os.link(self.ws.source_path(OUT), self.ws.root / "sources" / "second-name.log")
        with self.assertRaisesRegex(R.FailClosed, "hard links"):
            self.runner.poll(OUT, at(0, 1))

    def test_unsafe_source_names_rejected(self):
        for bad in ("../state/clock.json", "/etc/passwd", ".hidden", "a/b.log", "x..y"):
            names = dict(R.DEFAULT_SOURCE_NAMES, **{OUT: bad})
            self.runner.close()
            with self.assertRaises(R.FailClosed):
                R.IntegratedRunner(self.ws, names)
            self.runner = R.IntegratedRunner(self.ws)

    def test_two_streams_cannot_share_one_source_file(self):
        names = dict(R.DEFAULT_SOURCE_NAMES, **{ERR: R.DEFAULT_SOURCE_NAMES[OUT]})
        self.runner.close()
        with self.assertRaisesRegex(R.FailClosed, "its own source file"):
            R.IntegratedRunner(self.ws, names)
        self.runner = R.IntegratedRunner(self.ws)

    def test_only_world_out_err_and_auth_native(self):
        for stream in ("Authserver-pty", "Worldserver-native", "Authserver-out", "../x"):
            with self.assertRaises(R.FailClosed):
                self.runner.poll(stream, at(0, 1))

    def test_replaced_source_records_a_visible_gap(self):
        self.boot(OUT, history=b"OLD\n")
        self.ws.append(OUT, b"read\n")
        self.runner.poll(OUT, at(0, 1))
        self.ws.append(OUT, b"UNREAD-OLD-TAIL\n")
        os.rename(self.ws.source_path(OUT), self.ws.root / "sources" / "rotated.log")
        self.ws.seed(OUT, b"new file\n")
        self.assertEqual(self.runner.poll(OUT, at(0, 2)).events, ("replaced", "appended"))
        self.runner.seal_through(at(1, 0, 1))
        entry = self.runner.archive_entry(OUT, at(0).date())
        self.assertEqual(self.runner.archive_bytes(OUT, at(0).date()), b"read\nnew file\n")
        self.assertIn("replaced", [n["kind"] for n in entry["notes"]])
        self.assertIn("may be missing", [n for n in entry["notes"] if n["kind"] == "replaced"][0]["detail"])

    def test_truncated_source_records_a_visible_gap(self):
        self.boot(OUT, history=b"OLD-HISTORY\n")
        os.truncate(self.ws.source_path(OUT), 0)
        self.ws.append(OUT, b"fresh\n")
        self.assertEqual(self.runner.poll(OUT, at(0, 1)).events, ("truncated", "appended"))
        self.runner.seal_through(at(1, 0, 1))
        self.assertIn("truncated", [n["kind"] for n in self.runner.archive_entry(OUT, at(0).date())["notes"]])

    @unittest.skipIf(os.geteuid() == 0, "root can read a mode-000 file")
    def test_unreadable_source_fails_closed(self):
        self.ws.seed(OUT, b"x")
        os.chmod(self.ws.source_path(OUT), 0)
        with self.assertRaisesRegex(R.FailClosed, "unreadable"):
            self.runner.poll(OUT, at(0, 1))

    def test_restart_cleanup_removes_only_its_own_pending_files(self):
        foreign = {self.runner.archive / "Crash-History.txt.pending": b"not ours\n",
                   self.runner.segments / "random.rec.pending": b"not ours\n",
                   self.runner.state / "owner-notes.json.pending": b"not ours\n"}
        for path, data in foreign.items():
            path.write_bytes(data)
        self.restart()
        for path, data in foreign.items():
            self.assertEqual(path.read_bytes(), data)

    def test_second_writer_is_refused(self):
        with self.assertRaisesRegex(R.FailClosed, "already holds"):
            R.IntegratedRunner(self.ws)
        self.runner.close()
        self.runner = R.IntegratedRunner(self.ws)

    def test_refuses_a_root_that_is_not_its_workspace(self):
        class Fake:
            root = Path.cwd()
            token = "0" * 32
        with self.assertRaises(R.FailClosed):
            R.IntegratedRunner(Fake())
        other = R.DisposableWorkspace()
        self.addCleanup(other.close)
        class WrongToken:
            root = other.root
            token = "f" * 32
        with self.assertRaisesRegex(R.FailClosed, "marker"):
            R.IntegratedRunner(WrongToken())

    def test_corrupt_journal_record_blocks_sealing(self):
        self.boot(OUT)
        self.ws.append(OUT, b"genuine\n")
        self.runner.poll(OUT, at(0, 1))
        segment = [r for r in self.runner.records(OUT) if r.kind == "seg"][0]
        segment.path.write_bytes(b"forged!\n")
        with self.assertRaisesRegex(R.FailClosed, "corrupt"):
            self.runner.seal_through(at(1, 0, 1))
        self.assertEqual([f for f in self.archive_files() if f.endswith(".txt")], [])

    def test_missing_journal_record_blocks_sealing(self):
        self.boot(OUT)
        for n in range(3):
            self.ws.append(OUT, f"line {n}\n".encode())
            self.runner.poll(OUT, at(0, n + 1))
        [r for r in self.runner.records(OUT) if r.seq == 3][0].path.unlink()
        with self.assertRaisesRegex(R.FailClosed, "missing"):
            self.runner.seal_through(at(1, 0, 1))

    def test_tampered_checkpoint_fails_closed(self):
        self.boot(OUT)
        path = self.runner.state / (OUT + ".checkpoint.json")
        doc = json.loads(path.read_text())
        doc["doc"]["offset"] = 0
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(R.FailClosed, "checksum"):
            self.runner.poll(OUT, at(0, 1))


class Retention(Base):
    def _archive_two_days(self):
        self.boot(OUT)
        for day in (0, 1):
            self.ws.append(OUT, f"day {day}\n".encode())
            self.runner.poll(OUT, at(day, 1))
        self.runner.seal_through(at(2, 0, 1))
        return [self.runner.archive_entry(OUT, at(d).date()) for d in (0, 1)]

    def test_only_owned_closed_archives_older_than_30_days_go(self):
        old, young = self._archive_two_days()
        decoys = {
            "Crash-History.txt": b"crash history\n",
            "worldserver-crash-report.txt": b"report\n",
            "notes.txt": b"user file\n",
            # matches the archive pattern but is not in the manifest: not owned
            R.policy.archive_filename("Worldserver", "out", at(1), "0123456789ab"): b"look-alike\n",
        }
        for name, data in decoys.items():
            (self.runner.archive / name).write_bytes(data)
        sources = self.snapshot()
        # exactly 30x24h after the first archive closed: kept
        self.assertEqual(self.runner.expire(at(1) + R.policy.RETENTION), [])
        removed = self.runner.expire(at(1) + R.policy.RETENTION + timedelta(seconds=1))
        self.assertEqual(removed, [old["name"]])
        self.assertFalse((self.runner.archive / old["sidecar"]).exists())
        self.assertTrue((self.runner.archive / young["name"]).exists())
        for name, data in decoys.items():
            self.assertEqual((self.runner.archive / name).read_bytes(), data)
        self.assertEqual(self.snapshot(), sources)
        self.assertEqual(self.runner.archive_entry(OUT, at(0).date())["state"], "expired")

    def test_changed_hardlinked_or_symlinked_archives_are_not_deleted(self):
        old, _ = self._archive_two_days()
        later = at(31, 12)  # past the first archive's 30x24h, not the second's
        path = self.runner.archive / old["name"]
        # 1. content changed in place: no longer the archive we sealed
        path.write_bytes(b"edited by someone\n")
        self.assertEqual(self.runner.expire(later), [])
        self.assertEqual(path.read_bytes(), b"edited by someone\n")
        # 2. replaced by a symlink with the same name
        path.unlink()
        target = self.ws.root / "sources" / "precious.txt"
        target.write_bytes(b"precious\n")
        os.symlink(target, path)
        self.assertEqual(self.runner.expire(later), [])
        self.assertEqual(target.read_bytes(), b"precious\n")

    def test_foreign_file_at_the_sidecar_name_is_kept(self):
        old, young = self._archive_two_days()
        side = self.runner.archive / old["sidecar"]
        side.unlink()
        side.write_bytes(b"someone else's file, same name\n")  # regular, one link, not ours
        removed = self.runner.expire(at(31, 12))
        self.assertEqual(removed, [old["name"]])  # the archive itself is still provably ours
        self.assertEqual(side.read_bytes(), b"someone else's file, same name\n")
        entry = self.runner.archive_entry(OUT, at(0).date())
        self.assertIn("not the one this runner wrote", entry["sidecar_kept"])
        self.assertTrue((self.runner.archive / young["sidecar"]).exists())

    def test_foreign_sidecar_survives_interrupted_retention(self):
        old, _ = self._archive_two_days()
        side = self.runner.archive / old["sidecar"]
        side.write_bytes(b"edited in place: same inode, other bytes\n")
        with self.assertRaises(R.SyntheticCrash):
            self.runner.expire(at(31, 12), fail_at="after-unlink-before-manifest")
        self.restart()
        self.assertEqual(self.runner.expire(at(31, 13)), [])
        self.assertEqual(side.read_bytes(), b"edited in place: same inode, other bytes\n")
        self.assertEqual(self.runner.archive_entry(OUT, at(0).date())["state"], "expired")

    def test_hardlinked_archive_is_not_deleted(self):
        old, _ = self._archive_two_days()
        path = self.runner.archive / old["name"]
        os.link(path, self.ws.root / "sources" / "kept-copy.txt")
        self.assertEqual(self.runner.expire(at(31, 12)), [])
        self.assertTrue(path.exists())

    def test_interrupted_retention_resumes_without_touching_anything_else(self):
        old, young = self._archive_two_days()
        (self.runner.archive / "Crash-History.txt").write_bytes(b"keep\n")
        with self.assertRaises(R.SyntheticCrash):
            self.runner.expire(at(31, 12), fail_at="after-unlink-before-manifest")
        self.restart()
        self.assertEqual(self.runner.expire(at(31, 13)), [])
        self.assertEqual(self.runner.archive_entry(OUT, at(0).date())["state"], "expired")
        self.assertTrue((self.runner.archive / young["name"]).exists())
        self.assertTrue((self.runner.archive / "Crash-History.txt").exists())

    def test_manifest_cannot_point_retention_outside_the_archive(self):
        self._archive_two_days()
        manifest = self.runner._manifest()
        manifest["entries"].append({"stream": OUT, "day": "2026-10-01", "state": "sealed",
                                    "name": "../sources/World-out.log", "sidecar": "x",
                                    "closed_at": at(-30).isoformat(), "dev": 1, "ino": 1,
                                    "sha256": "0" * 64})
        self.runner._write_signed("archives.json", manifest)
        sources = self.snapshot()
        self.runner.expire(at(40))
        self.assertEqual(self.snapshot(), sources)

    def test_missing_archive_before_its_date_fails_closed(self):
        old, _ = self._archive_two_days()
        (self.runner.archive / old["name"]).unlink()
        with self.assertRaisesRegex(R.FailClosed, "missing before its retention date"):
            self.runner.expire(at(3))


class KnownGaps(Base):
    """Each test passes by showing a gap that is NOT solved. Release blockers."""

    def test_BLOCKER_same_inode_same_size_rewrite_is_not_detected(self):
        self.boot(OUT, history=b"AAAA\n")
        with open(self.ws.source_path(OUT), "r+b") as f:
            f.write(b"BBBB\n")  # same inode, same size, different content
        self.assertEqual(self.runner.poll(OUT, at(0, 1)).events, ("unchanged",))

    def test_BLOCKER_truncate_then_regrow_before_a_poll_reads_the_wrong_bytes(self):
        self.boot(OUT, history=b"123456789\n")
        os.truncate(self.ws.source_path(OUT), 0)
        self.ws.append(OUT, b"new content longer than before\n")
        result = self.runner.poll(OUT, at(0, 1))
        self.assertEqual(result.events, ("appended",))  # no gap noticed
        self.assertEqual(result.captured, b"new content longer than before\n"[10:])

    def test_BLOCKER_no_auth_pty_capture(self):
        with self.assertRaises(R.FailClosed):
            self.runner.poll("Authserver-pty", at(0, 1))
        self.assertIn("NOT a PTY", R.COMPLETENESS[AUTH])

    def test_BLOCKER_unread_old_inode_tail_is_lost_after_rotation(self):
        self.boot(OUT)
        self.ws.append(OUT, b"UNREAD\n")
        os.rename(self.ws.source_path(OUT), self.ws.root / "sources" / "rotated.log")
        self.ws.seed(OUT, b"")
        self.runner.poll(OUT, at(0, 1))
        self.runner.seal_through(at(1, 0, 1))
        self.assertIsNone(self.runner.archive_bytes(OUT, at(0).date()))  # UNREAD never archived


if __name__ == "__main__":
    unittest.main()
