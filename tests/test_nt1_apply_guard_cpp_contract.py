"""Execute the original ApplyValidated C++ function in isolated counted fakes.

The mocked C++ harness is not a real server mutation safety proof. It must
compile the EXACT production C++ function body, not a rewritten Python model.
"""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Nt1ApplyGuardCppContract(unittest.TestCase):
    def test_extracted_cpp_apply_guard_runs_without_mutating_altbot(self):
        result = subprocess.run(
            [sys.executable,
             str(ROOT / "scripts/check_nt1_apply_guard_cpp_contract.py")],
            cwd=ROOT, text=True, capture_output=True, timeout=90,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Extracted C++ test failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("PASS: 7 source-extracted NT1 Apply guard scenarios",
                      result.stdout)
        self.assertIn("NOT a live Apply or full respec", result.stdout)


if __name__ == "__main__":
    unittest.main()
