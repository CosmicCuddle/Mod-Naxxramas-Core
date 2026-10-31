"""A04/P4 extracted-pinned-source native C++ harness tests.

Requires A04_CORE: a checkout of Grimfeather/azerothcore-wotlk at
8daffdabe9202c228e45d833c9a1d399597a15cd (see the workflow for the paths).
The test FAILS (it does not skip) when A04_CORE is missing.

This is not a Worldserver run and not a native Core regression: the original
loot/quest function bodies are compiled with test-only collaborator stubs.
See docs/research/A04-NATIVE-QUEST-LOOT-FIXTURE.md.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent / "a04_native"
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import prepare_pinned  # noqa: E402

EXPECTED_CHECKS = 71
EXPECTED_DEFINITIONS = 28

# Each listed check must be present and PASS.
REQUIRED = [
    "T0.A_store_awards_exactly_one", "T0.B_sees_no_row", "T0.H1neg_B_direct_store_gets_nothing",
    "H1neg.complete_B_direct_store_gets_nothing",
    "T1.WITNESS_B_view_marks_shared_item_looted", "T1.WITNESS_A_stale_row_store_denied",
    "T1.WITNESS_A_denial_is_silent", "T1.WITNESS_corpse_never_reaches_isLooted",
    "T2.WITNESS_A_sees_no_row_despite_need", "T2.WITNESS_A_store_denied",
    "T3.WITNESS_H2_B_sees_locked_row", "T3.WITNESS_H2_B_store_denied_with_release", "T3.A_right_preserved",
    "T4a.STOCK_first_eligible_taker_gets_single_copy", "T4b.STOCK_first_eligible_taker_gets_single_copy",
    "O1.DIRECT_API_banked_B_store_without_view_is_awarded", "C2.O2_API_B_store_of_hidden_slot_succeeds",
    "T0.A_award_runs_quest_counter_to_complete", "T4a.taker_complete_other_still_incomplete",
    "T4b.taker_complete_other_still_incomplete", "C1b.both_quest_counters_complete",
    "T5.WITNESS_whole_slot_move_double_subtracts",
    "C1a.ffa_not_marked_looted_by_view", "C1b.B_awarded_own_copy", "C3.master_self_store_denied", "C3.A_awarded",
]


def core_dir() -> Path:
    value = os.environ.get("A04_CORE")
    if not value:
        raise AssertionError("A04_CORE is not set: point it at the pinned Grimfeather 8daffda checkout")
    return Path(value)


class ExtractionAndProvenance(unittest.TestCase):
    def test_pins_facts_and_byte_for_byte_bodies(self):
        core = core_dir()
        with tempfile.TemporaryDirectory(prefix="a04-prep-") as tmp:
            out = Path(tmp)
            log = build.prepare(core, out)
            self.assertIn("17 pinned blobs verified, 11 pinned facts, 3 call orders, 28 original definitions extracted", log)
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["pin"], "8daffdabe9202c228e45d833c9a1d399597a15cd")
            self.assertEqual(len(manifest["bodies"]), EXPECTED_DEFINITIONS)
            generated = (out / "pinned_bodies.cpp").read_text()
            # Every body in the generated file is a verbatim slice of the pinned file.
            for body in manifest["bodies"]:
                source = (core / body["file"]).read_text().split("\n")
                start = body["line"] - 1
                self.assertEqual(source[start], body["signature"])
                self.assertIn(f'#line {body["line"]} "{body["file"]}"\n{body["signature"]}\n', generated)

    def test_mutant_anchors_each_match_once(self):
        core = core_dir()
        with tempfile.TemporaryDirectory(prefix="a04-prep-") as tmp:
            build.prepare(core, Path(tmp))
            generated = (Path(tmp) / "pinned_bodies.cpp").read_text()
        for name, (old, _new) in prepare_pinned.MUTANTS.items():
            self.assertEqual(generated.count(old), 1, name)


class HarnessHasNoLootLogic(unittest.TestCase):
    """The driver and stubs must not define or write the loot state under test."""

    def setUp(self):
        self.sources = {p.name: p.read_text() for p in (HERE / "harness.cpp", HERE / "harness_env.h",
                                                        HERE / "stubs" / "ConditionMgr.h")}

    def test_no_definitions_of_tested_members(self):
        allowed = {"LootTemplate::Process", "LootStore::GetLootFor", "LootStore::Clear", "LootTemplate::~LootTemplate",
                   "Player::CanCompleteQuest", "ObjectAccessor::FindPlayer", "Acore::Assert"}
        for name, text in self.sources.items():
            for m in re.finditer(r"^[A-Za-z_][\w:<>*& ]*?\b(\w+::~?\w+)\s*\(", text, re.M):
                self.assertIn(m.group(1), allowed, f"{name} defines {m.group(1)}")

    def test_no_writes_to_loot_state(self):
        pattern = re.compile(r"\b(is_looted|is_counted|unlootedCount|is_blocked|is_underthreshold|roundRobinPlayer|"
                             r"freeforall|allowedGUIDs|PlayerQuestItems|quest_items|items)\s*(=[^=]|\+\+|--|\.push_back|\.clear)")
        for name, text in self.sources.items():
            code = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)  # ignore string literals
            code = re.sub(r"//[^\n]*", "", code)                 # and comments
            self.assertIsNone(pattern.search(code), f"{name} writes loot state")


class NativeRun(unittest.TestCase):
    def test_original_bodies_run_and_all_checks_pass(self):
        core = core_dir()
        with tempfile.TemporaryDirectory(prefix="a04-run-") as tmp:
            out = Path(tmp)
            build.prepare(core, out)
            compiled, rc, output = build.compile_and_run(core, out)
        print(output)
        self.assertTrue(compiled, output[-4000:])
        checks = build.parse_checks(output)
        ids = [cid for _verdict, cid in checks]
        if len(checks) != EXPECTED_CHECKS:
            self.fail(f"COUNT DRIFT: {len(checks)} checks, expected {EXPECTED_CHECKS}")
        self.assertEqual(len(ids), len(set(ids)), "duplicate check id")
        failed = [cid for verdict, cid in checks if verdict == "FAIL"]
        self.assertEqual(failed, [])
        self.assertEqual(rc, 0)
        for cid in REQUIRED:
            self.assertIn(("PASS", cid), checks)
        self.assertIn(f"CHECKS {EXPECTED_CHECKS} passed, 0 failed", output)


if __name__ == "__main__":
    unittest.main()
