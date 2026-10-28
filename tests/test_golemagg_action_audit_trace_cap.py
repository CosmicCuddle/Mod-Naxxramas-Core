"""A01 P2: the Golemagg audit bounds its action tail before caching it.

Source-order contract only; no AzerothCore compile and no in-game claim.
tests/golemagg_action_audit_trace.cpp tests the helper natively.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/BotGolemaggActionAudit.cpp").read_text()
HELPER = (ROOT / "src/Systems/GolemaggActionAuditTrace.h").read_text()
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()

CALL = "NaxxramasGolemaggActionAudit::BoundActionTrace(trace, MAX_ACTION_TEXT);"


class TraceBoundedBeforeCache(unittest.TestCase):
    def test_helper_is_included_and_called_once(self):
        self.assertIn('#include "GolemaggActionAuditTrace.h"', SOURCE)
        self.assertEqual(SOURCE.count("BoundActionTrace("), 1)
        self.assertEqual(SOURCE.count(CALL), 1)

    def test_bound_runs_after_sentinel_and_before_compare_cache_and_log(self):
        order = [
            'std::string trace = ai->HandleRemoteCommand("action");',
            'trace = "(no recent action)";',
            CALL,
            "trace == state->lastTrace",
            "state->lastTrace = trace;",
            'LOG_INFO("module",',
        ]
        positions = [SOURCE.index(token) for token in order]
        self.assertEqual(positions, sorted(positions))

    def test_cache_written_once_and_trace_not_changed_after_it(self):
        self.assertEqual(len(re.findall(r"state->lastTrace\s*=", SOURCE)), 1)
        start = SOURCE.index("state->lastTrace = trace;")
        end = SOURCE.index('LOG_INFO("module",')
        self.assertIsNone(re.search(r"\btrace\s*(=[^=]|\.|\+=)", SOURCE[start + 1:end]))

    def test_no_second_unbounded_cut_left_in_the_source(self):
        self.assertNotIn("trace.erase(", SOURCE)
        self.assertNotIn("std::replace(trace.", SOURCE)
        self.assertNotIn("trace.resize(", SOURCE)

    def test_limits_and_default_off_unchanged(self):
        self.assertRegex(SOURCE, r"MAX_ACTION_TEXT\s*=\s*320;")
        self.assertRegex(SOURCE, r"MAX_SAMPLES_PER_BOT\s*=\s*24;")
        self.assertRegex(SOURCE, r"SAMPLE_INTERVAL_MS\s*=\s*2500;")
        self.assertIn("NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled = 0", CONFIG)
        self.assertIn('NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName = ""', CONFIG)
        for denied in ("MoveAway(", "MoveTo(", "DoSpecificAction(", "CastSpell("):
            self.assertNotIn(denied, SOURCE)

    def test_helper_is_pure_standard_cpp(self):
        includes = re.findall(r"#include\s+(\S+)", HELPER)
        self.assertEqual(includes, ["<algorithm>", "<cstddef>", "<string>"])
        code = re.sub(r"//[^\n]*", "", HELPER)
        for name in ("Player", "sConfigMgr", "LOG_", "Playerbot"):
            self.assertNotIn(name, code)
        # Keeps the newest bytes, then normalises line breaks.
        self.assertLess(HELPER.index("trace.erase(0, trace.size() - maxBytes);"),
                        HELPER.index("'\\n', ' '"))


if __name__ == "__main__":
    unittest.main()
