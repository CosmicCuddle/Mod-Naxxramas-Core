"""P10: HonorReset.cpp differs from main only by the interval bound and guard.

Needs git history for BASE_MAIN.
"""
from pathlib import Path
import difflib
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE_MAIN = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
PATH = "src/Systems/HonorReset.cpp"


def main_source(path):
    return subprocess.run(["git", "show", f"{BASE_MAIN}:{path}"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


class HonorResetScope(unittest.TestCase):
    def test_only_additions_and_exactly_these(self):
        old = main_source(PATH).splitlines()
        new = (ROOT / PATH).read_text().splitlines()
        diff = [l for l in difflib.unified_diff(old, new, lineterm="", n=0)
                if not l.startswith(("---", "+++", "@@"))]
        removed = [l for l in diff if l.startswith("-")]
        added = [l[1:].strip() for l in diff if l.startswith("+") and l[1:].strip()]
        self.assertEqual(removed, [])
        code = [l for l in added if not l.startswith("//")]
        # difflib may align a new line with an identical existing one, so
        # compare as a multiset rather than in diff order.
        self.assertEqual(sorted(code), sorted([
            "#include <limits>",
            "constexpr uint32 MAX_INTERVAL_WEEKS =",
            "static_cast<uint32>((std::numeric_limits<int>::max() - 31) / 7);",
            "if (weeks > MAX_INTERVAL_WEEKS)",
            "return static_cast<std::time_t>(-1);",
            "if (nextReset <= scheduledReset)",
            "return scheduledReset;",
        ]))

    def test_config_and_loader_untouched(self):
        for path in ("conf/mod_naxxramas_core.conf.dist", "src/NaxxramasCore_loader.cpp"):
            with self.subTest(path=path):
                self.assertEqual((ROOT / path).read_text(), main_source(path))


if __name__ == "__main__":
    unittest.main()
