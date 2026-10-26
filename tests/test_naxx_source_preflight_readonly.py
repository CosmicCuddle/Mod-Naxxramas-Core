"""Offline safety tests for a READ-ONLY git checkout preflight.

These fixtures use disposable temp repositories, never the operator's server.
"""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_naxx_source_preflight_readonly.py"
spec = importlib.util.spec_from_file_location("naxx_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        text=True, capture_output=True, check=True,
    ).stdout.strip()


def init_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=CI",
         "-c", "user.email=ci@example.invalid",
         "commit", "--allow-empty", "-qm", "fixture"],
        check=True, capture_output=True, text=True,
    )
    return git(path, "rev-parse", "HEAD")


class ReadOnlySourcePreflight(unittest.TestCase):
    def test_clean_exact_sha_and_missing_expected_are_not_confused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "acore"
            sha = init_repo(path)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exact = preflight.check_checkout("AzerothCore", path, sha)
                not_certified = preflight.check_checkout("Naxx Core", path, None)
            self.assertEqual(exact, 0)
            self.assertEqual(not_certified, 0)
            self.assertIn("MATCH: requested source revision", stdout.getvalue())
            self.assertIn("NOT certified".lower(), stdout.getvalue().lower())

    def test_wrong_revision_fails_even_on_clean_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "acore"
            sha = init_repo(path)
            alternate = "0" * 40 if sha != "0" * 40 else "1" * 40
            with contextlib.redirect_stdout(io.StringIO()):
                result = preflight.check_checkout("AzerothCore", path, alternate)
            self.assertEqual(result, preflight.MISMATCH)

    def test_old_pins_stay_default_and_new_core_can_be_selected(self):
        default = preflight.selected_pins()
        self.assertEqual(default, preflight.PINS)
        new_core = "8daffdabe9202c228e45d833c9a1d399597a15cd"
        selected = preflight.selected_pins(core=new_core)
        self.assertEqual(selected["AzerothCore"], new_core)
        self.assertEqual(selected["Playerbots"], default["Playerbots"])
        self.assertEqual(selected["Individual Progression"],
                         default["Individual Progression"])
        self.assertEqual(default, preflight.PINS)

    def test_independent_exact_overrides_do_not_change_global_defaults(self):
        playerbots = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"
        ip = "84818a195bd02107f13c261eea11c9e14cb3f1a0"
        selected = preflight.selected_pins(
            playerbots=playerbots.upper(), ip=ip.upper())
        self.assertEqual(selected["AzerothCore"],
                         preflight.PINS["AzerothCore"])
        self.assertEqual(selected["Playerbots"], playerbots)
        self.assertEqual(selected["Individual Progression"], ip)
        self.assertEqual(preflight.selected_pins(), preflight.PINS)

    def test_invalid_or_short_overrides_are_refused_not_autofilled(self):
        for field in ("core", "playerbots", "ip"):
            for value in ("8daffda", "x" * 40, "", "abcd", " " * 40):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, "40-character"):
                        preflight.selected_pins(**{field: value})

    def test_new_core_checkout_matches_only_explicit_chosen_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "core"
            real = init_repo(path)
            wrong = "0" * 40 if real != "0" * 40 else "1" * 40
            selected = preflight.selected_pins(core=real)
            with contextlib.redirect_stdout(io.StringIO()):
                good = preflight.check_checkout("AzerothCore", path,
                                                selected["AzerothCore"])
                bad = preflight.check_checkout("AzerothCore", path, wrong)
            self.assertEqual(good, 0)
            self.assertEqual(bad, preflight.MISMATCH)

    def test_modified_tracked_source_blocks_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "acore"
            _ = init_repo(path)
            source = path / "tracked.cpp"
            source.write_text("int example = 1;\n")
            git(path, "add", "tracked.cpp")
            subprocess.run(
                ["git", "-C", str(path), "-c", "user.name=CI",
                 "-c", "user.email=ci@example.invalid",
                 "commit", "-qm", "tracked"],
                check=True, capture_output=True, text=True,
            )
            sha = git(path, "rev-parse", "HEAD")
            source.write_text("int example = 2;\n")
            with contextlib.redirect_stdout(io.StringIO()):
                result = preflight.check_checkout("AzerothCore", path, sha)
            self.assertEqual(result, preflight.DIRTY)

    def test_missing_checkout_and_nested_parent_checkout_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "acore"
            init_repo(root)
            (root / "modules/mod-playerbots").mkdir(parents=True)
            with contextlib.redirect_stdout(io.StringIO()):
                missing = preflight.check_checkout(
                    "IP", root / "modules/mod-individual-progression", None
                )
                nested = preflight.check_checkout(
                    "Playerbots", root / "modules/mod-playerbots", None
                )
            self.assertEqual(missing, preflight.INVALID)
            self.assertEqual(nested, preflight.INVALID)

    def test_optional_binary_hash_uses_file_contents_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "worldserver"
            path.write_bytes(b"disposable-not-a-real-worldserver")
            self.assertEqual(
                preflight.sha256_file(path),
                hashlib.sha256(b"disposable-not-a-real-worldserver").hexdigest(),
            )

    def test_procfs_pid_hash_reads_only_matching_executable(self):
        # Fake /proc tree, never query a real service or private process.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "worldserver"
            binary.write_bytes(b"disposable-test-worldserver")
            proc = root / "proc"
            directory = proc / "123"
            directory.mkdir(parents=True)
            (directory / "comm").write_text("worldserver\n")
            (directory / "exe").symlink_to(binary)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status, digest = preflight.check_running_worldserver_pid(
                    123, proc_root=proc)
            self.assertEqual(status, 0)
            self.assertEqual(digest, hashlib.sha256(binary.read_bytes()).hexdigest())
            self.assertIn("Running-process executable SHA-256", stdout.getvalue())
            self.assertNotIn(str(root), stdout.getvalue())

    def test_procfs_pid_rejects_wrong_process_and_missing_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary) / "proc"
            directory = proc / "123"
            directory.mkdir(parents=True)
            (directory / "comm").write_text("python3\n")
            with contextlib.redirect_stdout(io.StringIO()):
                wrong, digest = preflight.check_running_worldserver_pid(
                    123, proc_root=proc)
            self.assertEqual(wrong, preflight.BINARY_ERROR)
            self.assertIsNone(digest)
            (directory / "comm").write_text("worldserver\n")
            with contextlib.redirect_stdout(io.StringIO()):
                missing, digest = preflight.check_running_worldserver_pid(
                    123, proc_root=proc)
            self.assertEqual(missing, preflight.BINARY_ERROR)
            self.assertIsNone(digest)

    def test_procfs_pid_rejects_invalid_and_deleted_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary) / "proc"
            directory = proc / "123"
            directory.mkdir(parents=True)
            (directory / "comm").write_text("worldserver\n")
            # Simulate the Linux (deleted) suffix; a running process with
            # a removed executable must not be mistaken for current on-disk.
            binary = Path(temporary) / "worldserver (deleted)"
            binary.write_bytes(b"old-binary")
            (directory / "exe").symlink_to(binary)
            with contextlib.redirect_stdout(io.StringIO()):
                deleted, digest = preflight.check_running_worldserver_pid(
                    123, proc_root=proc)
                invalid, bad_hash = preflight.check_running_worldserver_pid(
                    0, proc_root=proc)
            self.assertEqual(deleted, preflight.BINARY_ERROR)
            self.assertEqual(invalid, preflight.BINARY_ERROR)
            self.assertIsNone(digest)
            self.assertIsNone(bad_hash)

    def test_pid_checker_does_not_open_private_proc_process_data(self):
        contents = SCRIPT.read_text()
        for forbidden in ("/environ", "/cmdline", "/mem", "os.kill(", "signal.SIG",
                          "subprocess.Popen", "os.system(", "sudo "):
            # A descriptive stderr/log sentence may mention a path. Check
            # actual file access syntax in source when warranted.
            if forbidden == "/cmdline":
                continue
            self.assertNotIn(forbidden, contents)
        self.assertIn('directory / "comm"', contents)
        self.assertIn('directory / "exe"', contents)

    def test_script_has_no_mutation_commands(self):
        text = SCRIPT.read_text()
        for forbidden in (
            "git pull", "git fetch", "git checkout", "systemctl ",
            "mysql ", "mysqldump ", "CREATE TABLE", "UPDATE world",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("GIT_OPTIONAL_LOCKS", text)
        self.assertIn("untracked files NOT inspected", text)


if __name__ == "__main__":
    unittest.main()
