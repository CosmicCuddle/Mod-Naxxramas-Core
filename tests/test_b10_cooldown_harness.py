"""Contract for the #120 production-text cooldown TSAN harness (test-only).

The harness must compile #120's own cooldown code, unchanged, and refuse to
build if that code changes, so it can never silently test a substitute.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/extract_b10_cooldown_harness.py"
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"
DRIVER = ROOT / "tests/b10_cooldown_tsan_driver.cpp"
LOCK_LINE = "std::lock_guard<std::mutex> lock(\n            ConsumableCooldownLock);"


def run(source_text=None, unlocked=False):
    with tempfile.TemporaryDirectory() as tmp:
        src = SOURCE
        if source_text is not None:
            src = Path(tmp) / "BotRaidConsumables.cpp"
            src.write_text(source_text, encoding="utf-8")
        out = Path(tmp) / "harness.cpp"
        args = [sys.executable, "-I", "-B", str(SCRIPT), str(src), str(DRIVER), str(out)]
        if unlocked:
            args.append("--unlocked")
        result = subprocess.run(args, capture_output=True, text=True)
        generated = out.read_text(encoding="utf-8") if out.exists() else ""
        return result, generated


class ProductionTextHarness(unittest.TestCase):
    def test_reviewed_head_extracts_and_matches_digest(self):
        result, generated = run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: production text, 5 pieces", result.stdout)
        self.assertNotIn("@@B10_EXTRACTED", generated)

    def test_generated_code_is_the_production_text_verbatim(self):
        _, generated = run()
        source = SOURCE.read_text(encoding="utf-8")
        for signature in ("uint32 GetConsumableCooldownRemaining(",
                          "void StartConsumableCooldown(",
                          "void ResetConsumableCooldownForGroup("):
            start = source.index(signature)
            end = source.index("\n    }\n", start) + len("\n    }")
            with self.subTest(signature=signature):
                self.assertIn(source[start:end], generated)
        self.assertEqual(generated.count(LOCK_LINE), 3)

    def test_changing_a_production_lock_statement_breaks_the_contract(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count(LOCK_LINE), 3)
        mutated = source.replace(LOCK_LINE, "/* lock removed */", 1)
        result, generated = run(mutated)
        self.assertEqual(result.returncode, 3)
        self.assertIn("differs from reviewed 599d1cbb", result.stdout)
        self.assertEqual(generated, "")

    def test_changing_any_cooldown_function_body_breaks_the_contract(self):
        source = SOURCE.read_text(encoding="utf-8")
        mutated = source.replace("CONSUMABLE_COMMAND_COOLDOWN_SECONDS;\n\n        std::lock_guard",
                                 "CONSUMABLE_COMMAND_COOLDOWN_SECONDS + 1;\n\n        std::lock_guard", 1)
        self.assertNotEqual(mutated, source)
        result, _ = run(mutated)
        self.assertEqual(result.returncode, 3)

    def test_negative_control_removes_exactly_the_three_locks(self):
        result, generated = run(unlocked=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("UNLOCKED negative control", result.stdout)
        self.assertEqual(generated.count(LOCK_LINE), 0)
        self.assertEqual(generated.count("/* lock removed: negative control */"), 3)

    def test_driver_stubs_only_what_the_code_needs(self):
        driver = DRIVER.read_text(encoding="utf-8")
        self.assertEqual(driver.count("// @@B10_EXTRACTED_PRODUCTION_COOLDOWN_CODE@@"), 1)
        # The stub prelude (code, not comments) must not define or lock the
        # production state itself; only the extracted text may.
        prelude = driver.split("namespace\n{\n// @@B10")[0]
        code = "\n".join(line for line in prelude.splitlines()
                         if not line.lstrip().startswith("//"))
        for forbidden in ("ConsumableCooldownLock", "ConsumableCooldownUntil",
                          "lock_guard", "GetConsumableCooldownRemaining"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
