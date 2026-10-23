"""Pin-aware NT1 compilation dispatcher tests (no real compiler invoked here).

The separate GitHub Actions job performs the actual CMake configure and
syntax-only C++ translation-unit compile from the pinned source headers.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_nt1_pinned_compile_commands.py"
WORKFLOW = (
    ROOT / ".github" / "workflows" /
    "nt1-pinned-translation-unit-compile.yml"
).read_text(encoding="utf-8")
SPEC = importlib.util.spec_from_file_location("compile_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class PinnedCompileRunnerTests(unittest.TestCase):
    def test_exact_one_module_translation_unit_is_required(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "acore"
            correct = root / "modules" / "mod-naxxramas-core" / "src" / \
                "Systems" / "BotTalentImport.cpp"
            entry = {"file": str(correct),
                     "directory": str(root),
                     "command": "c++ -c -o file.o source.cpp"}
            self.assertEqual(
                RUNNER.real_nt1_entry([entry], root)["file"], str(correct)
            )
            with self.assertRaises(ValueError):
                RUNNER.real_nt1_entry([], root)
            with self.assertRaises(ValueError):
                RUNNER.real_nt1_entry([entry, entry], root)

    def test_syntax_only_strips_output_and_dependency_side_effects(self):
        entry = {
            "file": "BotTalentImport.cpp",
            "directory": "/tmp",
            "arguments": [
                "c++", "-I", "/tmp/include", "-DTEST=1", "-MD",
                "-MF", "dep.d", "-MT", "file.o", "-o", "file.o",
                "-c", "BotTalentImport.cpp"
            ]
        }
        result = RUNNER.syntax_only_command(entry)
        self.assertEqual(result[0], "c++")
        self.assertIn("BotTalentImport.cpp", result)
        self.assertIn("-DTEST=1", result)
        self.assertIn("-fsyntax-only", result)
        for banned in ("-MD", "-MF", "-MT", "-o", "-c", "file.o",
                       "dep.d"):
            self.assertNotIn(banned, result)

    def test_command_form_from_cmake_supported(self):
        entry = {"command": 'c++ -I"/tmp/a b" -c -o output.o source.cpp'}
        argv = RUNNER.syntax_only_command(entry)
        self.assertIn("-I/tmp/a b", argv)
        self.assertNotIn("output.o", argv)

    def test_empty_invalid_command_fails_closed(self):
        for bad in ({}, {"arguments": []},
                    {"arguments": ["c++", "-o"]},
                    {"arguments": ["-c"]}):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, KeyError)):
                    RUNNER.syntax_only_command(bad)

    def test_workflow_uses_four_exact_pinned_revisions(self):
        for sha in (
            "b7f06a16ac7120b5abc2e8d3f96a94265a363224",
            "037c01418b5d01506917a3db9b44fd56ac5f965c",
            "283abe12774801e5671da746ea8bf535cc0252e0",
        ):
            self.assertIn("ref: " + sha, WORKFLOW)
        self.assertIn("path: acore/modules/mod-naxxramas-core", WORKFLOW)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", WORKFLOW)
        self.assertIn('test "$(git -C acore/modules/mod-naxxramas-core rev-parse HEAD)"', WORKFLOW)
        self.assertIn("repository: ZhengPeiRu21/mod-individual-progression", WORKFLOW)

    def test_no_worldserver_launch_or_database_changes(self):
        for forbidden in (
            "mysql -", "mysql --", "mysqldump",
            "systemctl", "worldserver --", "git push",
            ".naxxbot talents apply", "DROP TABLE",
        ):
            self.assertNotIn(forbidden, WORKFLOW)
        self.assertIn("-fsyntax-only", SCRIPT.read_text(encoding="utf-8"))
        self.assertIn("NO", WORKFLOW.upper())

    def test_generated_flags_are_required_and_configured(self):
        self.assertIn("CMAKE_EXPORT_COMPILE_COMMANDS=ON", WORKFLOW)
        self.assertIn("compile_commands.json", WORKFLOW)
        self.assertIn("USE_COREPCH=OFF", WORKFLOW)
        self.assertIn("USE_SCRIPTPCH=OFF", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
