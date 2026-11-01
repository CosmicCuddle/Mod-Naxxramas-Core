"""Disposable F15 raw-archive tests: synthetic subprocesses in temp folders only."""
import ast
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import f15_process_supervisor as supervisor  # noqa: E402
import f15_raw_archive as archive  # noqa: E402
from f15_operator_collector import Refused  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RawArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        os.chmod(base, 0o700)
        self.raw = base / "raw"
        self.captures = base / "captures"
        self.dest = base / "raw-archive"
        os.mkdir(self.dest, 0o700)  # the operator creates the destination

    def launch(self, service, text="SECRET_NOT_IN_REPORT", exit_code=0):
        command = [sys.executable, "-c",
                   "import sys; print(" + repr(text) + ", flush=True); "
                   "print('err-' + " + repr(text) + ", file=sys.stderr, flush=True); "
                   "sys.exit(" + str(exit_code) + ")"]
        run, outcome = supervisor.supervise(self.raw, self.captures, service, command,
                                            poll_seconds=0.02)
        return run

    def plan(self, runs, execute=False, days=0, **kw):
        when = (datetime.now(timezone.utc) + timedelta(days=days)).timestamp()
        return archive.plan(self.raw, self.captures, self.dest, [r.name for r in runs],
                            now=when, execute=execute, **kw)

    def originals(self, *runs):
        snap = {}
        for run in runs:
            for name in ("stdout.raw", "stderr.raw", "start.json", "exit.json"):
                p = run / name
                st = p.lstat()
                snap[p] = (p.read_bytes(), st.st_ino, st.st_mtime_ns, st.st_size, stat.S_IMODE(st.st_mode))
        return snap

    def assertUnchanged(self, snap):
        for p, (data, ino, mtime, size, mode) in snap.items():
            st = p.lstat()
            self.assertEqual((p.read_bytes(), st.st_ino, st.st_mtime_ns, st.st_size, stat.S_IMODE(st.st_mode)),
                             (data, ino, mtime, size, mode), p)

    # ------------------------------------------------------------------
    def test_dry_run_is_default_and_writes_nothing(self):
        w = self.launch("Worldserver")
        snap = self.originals(w)
        report = self.plan([w])
        self.assertEqual(report["mode"], "DRY_RUN_READ_ONLY")
        self.assertEqual(report["deletions"], 0)
        self.assertEqual(report["runs"][0]["result"], "would_archive")
        self.assertEqual(list(self.dest.iterdir()), [])
        self.assertUnchanged(snap)
        self.assertNotIn("SECRET_NOT_IN_REPORT", json.dumps(report))

    def test_world_and_auth_clean_and_nonzero_archived_byte_for_byte(self):
        w = self.launch("Worldserver", exit_code=0)
        a = self.launch("Authserver", exit_code=3)
        snap = self.originals(w, a)
        report = self.plan([w, a], execute=True)
        self.assertEqual(report["mode"], "ARCHIVE_COPY")
        self.assertEqual([r["result"] for r in report["runs"]], ["archived", "archived"])
        self.assertEqual({r["service"]: r["exit_kind"] for r in report["runs"]},
                         {"Worldserver": "clean_exit", "Authserver": "nonzero_exit"})
        for run in (w, a):
            final = self.dest / "runs" / run.name
            self.assertEqual(stat.S_IMODE(final.lstat().st_mode), 0o700)
            manifest = json.loads((final / "manifest.json").read_text())
            self.assertEqual(manifest["format"], "naxx-f15-raw-archive-v1")
            for name in ("stdout.raw", "stderr.raw", "start.json", "exit.json"):
                self.assertEqual((final / name).read_bytes(), (run / name).read_bytes())
                self.assertEqual(stat.S_IMODE((final / name).lstat().st_mode), 0o600)
                self.assertEqual((final / name).lstat().st_nlink, 1)
            for name in ("stdout.raw", "stderr.raw"):
                self.assertEqual(manifest["files"][name]["sha256"], sha(run / name))
                self.assertEqual(manifest["files"][name]["source_ino"], (run / name).lstat().st_ino)
        self.assertUnchanged(snap)
        self.assertEqual(report["stale_staging_entries"], 0)
        self.assertNotIn("SECRET_NOT_IN_REPORT", json.dumps(report))
        self.assertIn("not an engine crash", report["note"])

    def test_only_selected_runs_are_copied(self):
        w = self.launch("Worldserver")
        a = self.launch("Authserver")
        self.plan([w], execute=True)
        self.assertEqual([p.name for p in (self.dest / "runs").iterdir()], [w.name])
        self.assertTrue(a.exists())

    def test_duplicate_invocation_is_idempotent(self):
        w = self.launch("Worldserver")
        self.plan([w], execute=True)
        final = self.dest / "runs" / w.name
        before = {p.name: (p.lstat().st_ino, p.lstat().st_mtime_ns) for p in final.iterdir()}
        again = self.plan([w], execute=True)
        self.assertEqual(again["runs"][0]["result"], "already_archived")
        self.assertEqual({p.name: (p.lstat().st_ino, p.lstat().st_mtime_ns) for p in final.iterdir()}, before)
        self.assertEqual(self.plan([w])["runs"][0]["result"], "would_verify_existing")

    def test_interrupted_copy_leaves_staging_and_restart_completes(self):
        w = self.launch("Worldserver")
        snap = self.originals(w)
        with self.assertRaises(KeyboardInterrupt):
            self.plan([w], execute=True, interrupt_after=1)
        self.assertFalse((self.dest / "runs" / w.name).exists())
        self.assertEqual(len(list((self.dest / ".staging").iterdir())), 1)
        report = self.plan([w], execute=True)
        self.assertEqual(report["runs"][0]["result"], "archived")
        self.assertEqual(report["stale_staging_entries"], 1)  # reported, never removed
        self.assertUnchanged(snap)

    def test_digest_mismatch_in_archive_refused(self):
        w = self.launch("Worldserver")
        self.plan([w], execute=True)
        copy = self.dest / "runs" / w.name / "stdout.raw"
        with open(copy, "ab") as f:  # synthetic corruption of OUR temp copy
            f.write(b"tampered")
        with self.assertRaisesRegex(Refused, "digest mismatch"):
            self.plan([w], execute=True)

    def _replace_in_archive(self, run, name, data):
        """Swap one file of OUR temp archive for a new 0600 file (fixture only)."""
        final = self.dest / "runs" / run.name
        os.rename(final / name, self.dest / ("parked-" + name))
        fd = os.open(final / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, data)
        os.close(fd)

    def test_symlinked_archived_receipt_refused_before_read(self):
        w = self.launch("Worldserver")
        self.plan([w], execute=True)
        final = self.dest / "runs" / w.name
        twin = self.dest / "twin-start.json"
        os.rename(final / "start.json", twin)  # identical bytes, now behind a symlink
        os.symlink(twin, final / "start.json")
        with self.assertRaisesRegex(Refused, "symlink"):
            self.plan([w], execute=True)

    def test_hardlinked_archived_receipt_refused(self):
        w = self.launch("Worldserver")
        self.plan([w], execute=True)
        os.link(self.dest / "runs" / w.name / "exit.json", self.dest / "extra-exit-link.json")
        with self.assertRaisesRegex(Refused, "single-link"):
            self.plan([w], execute=True)

    def test_forged_manifest_exit_code_refused(self):
        w = self.launch("Authserver", exit_code=3)
        self.plan([w], execute=True)
        manifest = json.loads((self.dest / "runs" / w.name / "manifest.json").read_text())
        manifest["exit_code"] = 0
        self._replace_in_archive(w, "manifest.json", json.dumps(manifest, sort_keys=True).encode())
        with self.assertRaisesRegex(Refused, "manifest does not match"):
            self.plan([w], execute=True)

    def test_forged_manifest_exit_time_refused(self):
        w = self.launch("Worldserver")
        self.plan([w], execute=True)
        manifest = json.loads((self.dest / "runs" / w.name / "manifest.json").read_text())
        manifest["exit_time_utc"] = "2020-01-01T00:00:00+00:00"
        self._replace_in_archive(w, "manifest.json", json.dumps(manifest, sort_keys=True).encode())
        with self.assertRaisesRegex(Refused, "manifest does not match"):
            self.plan([w], execute=True)

    def test_source_changed_after_archive_refused(self):
        w = self.launch("Worldserver")
        self.plan([w], execute=True)
        with open(w / "stdout.raw", "ab") as f:  # temp fixture only
            f.write(b"late bytes")
        with self.assertRaisesRegex(Refused, "no longer matches"):
            self.plan([w], execute=True)

    def test_symlink_forged_stream_refused(self):
        w = self.launch("Worldserver")
        target = self.raw / "elsewhere.raw"
        os.rename(w / "stdout.raw", target)
        os.symlink(target, w / "stdout.raw")
        with self.assertRaises(Refused):
            self.plan([w], execute=True)
        self.assertFalse((self.dest / "runs").exists())

    def test_hardlink_forged_stream_refused(self):
        w = self.launch("Worldserver")
        os.link(w / "stderr.raw", self.raw / "extra-link.raw")
        with self.assertRaisesRegex(Refused, "single-link"):
            self.plan([w], execute=True)

    def test_replaced_stream_inode_refused(self):
        w = self.launch("Worldserver")
        data = (w / "stdout.raw").read_bytes()
        os.rename(w / "stdout.raw", self.raw / "old.raw")
        fd = os.open(w / "stdout.raw", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, data)
        os.close(fd)
        with self.assertRaisesRegex(Refused, "capture origin"):
            self.plan([w], execute=True)

    def test_incomplete_run_refused(self):
        w = self.launch("Worldserver")
        os.rename(w / "exit.json", self.raw / "parked-exit.json")  # temp fixture: unfinished run
        with self.assertRaisesRegex(Refused, "not complete"):
            self.plan([w], execute=True)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_fail_closed_capture_refused(self):
        w = self.launch("Worldserver")
        exit_receipt = json.loads((w / "exit.json").read_text())
        exit_receipt["capture"] = "fail_closed"
        exit_receipt["capture_error_type"] = "UncapturedConsoleBytes"
        os.rename(w / "exit.json", self.raw / "parked-exit.json")
        fd = os.open(w / "exit.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, json.dumps(exit_receipt, sort_keys=True).encode())
        os.close(fd)
        with self.assertRaisesRegex(Refused, "fail_closed"):
            self.plan([w], execute=True)

    def test_thirty_day_boundary_is_informational_only(self):
        w = self.launch("Worldserver")
        self.assertFalse(self.plan([w], days=29)["runs"][0]["older_than_30_days"])
        late = self.plan([w], days=31, execute=True)
        self.assertTrue(late["runs"][0]["older_than_30_days"])
        self.assertEqual(late["runs"][0]["result"], "archived")
        self.assertEqual(late["deletions"], 0)
        self.assertTrue((w / "stdout.raw").exists())

    def test_bad_selection_and_roots_refused(self):
        w = self.launch("Worldserver")
        with self.assertRaises(Refused):
            archive.plan(self.raw, self.captures, self.dest, [], execute=True)
        with self.assertRaises(Refused):
            archive.plan(self.raw, self.captures, self.dest, [w.name, w.name])
        with self.assertRaises(Refused):
            archive.plan(self.raw, self.captures, self.dest, ["../escape"])
        with self.assertRaises(Refused):  # nested destination
            archive.plan(self.raw, self.captures, self.raw / "runs", [w.name])
        missing = self.dest.parent / "not-created"
        with self.assertRaises(Refused):
            archive.plan(self.raw, self.captures, missing, [w.name])
        self.assertFalse(missing.exists())
        os.chmod(self.dest, 0o755)
        with self.assertRaises(Refused):
            archive.plan(self.raw, self.captures, self.dest, [w.name])

    def test_cli_defaults_to_dry_run(self):
        w = self.launch("Worldserver")
        rc = archive.main(["--output-root", str(self.raw), "--archive-root", str(self.captures),
                           "--raw-archive-root", str(self.dest), "--run", w.name])
        self.assertEqual(rc, 0)
        self.assertEqual(list(self.dest.iterdir()), [])
        rc = archive.main(["--output-root", str(self.raw), "--archive-root", str(self.captures),
                           "--raw-archive-root", str(self.dest), "--run", w.name,
                           "--archive-owned-completed"])
        self.assertEqual(rc, 0)
        self.assertTrue((self.dest / "runs" / w.name / "manifest.json").exists())


class NoDestructiveCalls(unittest.TestCase):
    def test_archive_script_has_no_delete_truncate_or_process_calls(self):
        source = (ROOT / "scripts" / "f15_raw_archive.py").read_text()
        tree = ast.parse(source)
        forbidden = {"unlink", "remove", "rmdir", "rmtree", "removedirs", "truncate", "ftruncate",
                     "replace", "kill", "killpg", "system", "Popen", "run", "call", "check_call",
                     "check_output", "write_text", "write_bytes", "chmod"}
        found = [(getattr(n.func, "attr", getattr(n.func, "id", None)), n.lineno)
                 for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", getattr(n.func, "id", None)) in forbidden]
        self.assertEqual(found, [])
        self.assertNotIn("O_TRUNC", source)
        imported = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                    for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(imported & {"subprocess", "shutil", "signal"}, imported)


if __name__ == "__main__":
    unittest.main()
