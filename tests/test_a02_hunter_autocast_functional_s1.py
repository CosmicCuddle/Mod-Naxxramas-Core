"""Source contract for the A02 S1 human Hunter autocast feasibility note.

The decision table in the note is normative. These tests execute it.
They do not compile C++, link a worldserver, or read a live pet row.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "docs/research/a02-hunter-autocast-functional-s1.md"
CONF = ROOT / "conf/mod_naxxramas_core.conf.dist"
WORKFLOWS = ROOT / ".github/workflows"

ACT_DISABLED = 0x81
ACT_ENABLED = 0xC1
ACT_PASSIVE = 0x01
CHOICE_BYTES = {ACT_DISABLED, ACT_ENABLED}

CORE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
IP = "dd96f2b77e3ebfa2a4726bf785525ba133f1ab61"
PLAYERBOTS_CI = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"
PLAYERBOTS_OWNER = "e88cc4099e69f35126b28942a412ca702d20453b"
MODULE_BASE = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
TRACE_121 = "3bfa2ce900ca2436ed5769a9c8024827e92327ac"
TRACE_103 = "ec73fc77b33e185e46e7684a03a3cecd7bad770c"
PR_69 = "7fcdaf70f86ce0c8352c129c39e08e82e8a4a66d"
CONFIG_KEY = "NaxxramasCore.HunterPetAutocast.RestoreHumanChain = 0"


class SpellView:
    def __init__(self, spell_id, chain_id, active, autocastable, bar):
        self.spell_id = spell_id
        self.chain_id = chain_id
        self.active = active
        self.autocastable = autocastable
        self.bar = bar


def parse_spell(token):
    spell_id, chain_id, active, autocastable, bar = token.split(",")
    return SpellView(
        int(spell_id),
        int(chain_id),
        int(active, 16),
        autocastable == "1",
        None if bar == "NONE" else int(bar, 16),
    )


def parse_book(text):
    if text == "-":
        return []
    return [parse_spell(part) for part in text.split("+")]


def decide(enabled, human, baseline, current):
    """One token per baseline chain, or OUT_OF_SCOPE for the whole call.

    Check order matches docs/research/a02-hunter-autocast-functional-s1.md.
    """
    if not enabled or not human:
        return ["OUT_OF_SCOPE"]

    chains = []
    for spell in baseline:
        if spell.chain_id not in chains:
            chains.append(spell.chain_id)
    if not chains:
        return ["NO_WRITE"]

    results = []
    for chain_id in chains:
        base = [spell for spell in baseline if spell.chain_id == chain_id]
        live = [spell for spell in current if spell.chain_id == chain_id]
        if len(base) != 1:
            results.append("NO_WRITE")
            continue
        chosen = base[0]
        if chosen.active not in CHOICE_BYTES or chosen.bar != chosen.active:
            results.append("NO_WRITE")
            continue
        if not live:
            results.append("NO_LEARN")
            continue
        if len(live) != 1:
            results.append("NO_WRITE")
            continue
        successor = live[0]
        if successor.spell_id == chosen.spell_id or not successor.autocastable:
            results.append("NO_WRITE")
            continue
        if successor.bar is None:
            results.append("NO_BAR")
            continue
        if successor.active == chosen.active and successor.bar == chosen.active:
            results.append("NO_WRITE")
            continue
        results.append("RESTORE_ENABLED" if chosen.active == ACT_ENABLED else "RESTORE_DISABLED")
    return results


def decision_rows(note):
    begin = note.index("<!-- DECISION-TABLE-BEGIN -->")
    end = note.index("<!-- DECISION-TABLE-END -->")
    rows = []
    for line in note[begin:end].splitlines():
        if not line.startswith("|") or line.startswith("| case") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        name, enabled, human, baseline, current, expect = cells
        rows.append((name, enabled == "1", human == "1", parse_book(baseline), parse_book(current), expect))
    return rows


class HunterAutocastFunctionalDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.note = NOTE.read_text()
        cls.conf = CONF.read_text()

    def test_decision_table_matches_the_writer_contract(self):
        rows = decision_rows(self.note)
        self.assertGreaterEqual(len(rows), 16)
        seen = set()
        for name, enabled, human, baseline, current, expect in rows:
            self.assertNotIn(name, seen)
            seen.add(name)
            with self.subTest(case=name):
                self.assertEqual(decide(enabled, human, baseline, current), [expect])
        for required in (
            "switch-off",
            "not-human",
            "rank-swap-on",
            "rank-swap-off-already",
            "rank-swap-off-bar-on",
            "removal-no-successor",
            "same-spell-on",
            "chain-mismatch",
            "missing-bar",
            "already-enabled",
        ):
            self.assertIn(required, seen)

    def test_restore_tokens_are_the_only_writes(self):
        self.assertIn("Pet::ToggleAutocast(spellInfo, true)", self.note)
        self.assertIn("Pet::ToggleAutocast(spellInfo, false)", self.note)
        self.assertIn("CharmInfo::SetSpellAutocast(spellInfo, true)", self.note)
        self.assertIn("CharmInfo::SetSpellAutocast(spellInfo, false)", self.note)
        self.assertIn("Player::PetSpellInitialize()", self.note)
        self.assertIn("The table does not call `learnSpell` or `unlearnSpell`.", self.note)
        for token in ("OUT_OF_SCOPE", "NO_WRITE", "NO_LEARN", "NO_BAR", "RESTORE_ENABLED", "RESTORE_DISABLED"):
            self.assertIn(token, self.note)

    def test_empty_baseline_writes_nothing(self):
        self.assertEqual(decide(True, True, [], []), ["NO_WRITE"])

    def test_passive_byte_is_not_a_choice(self):
        self.assertEqual(ACT_PASSIVE, 0x01)
        self.assertNotIn(ACT_PASSIVE, CHOICE_BYTES)

    def test_pins_and_prior_heads_are_recorded(self):
        for sha in (CORE, IP, PLAYERBOTS_CI, PLAYERBOTS_OWNER, MODULE_BASE, TRACE_121, TRACE_103, PR_69):
            with self.subTest(sha=sha):
                self.assertIn(sha, self.note)
        self.assertIn("6385633108", self.note)
        self.assertIn("80e9de1c39a6dc995188a80c31a5e785d0f2a6f9", self.note)

    def test_chosen_seam_is_the_unit_update_bracket(self):
        for phrase in (
            "UnitScript::OnUnitUpdate",
            "WorldObjectScript::OnWorldObjectUpdate",
            "m_Events.Update",
            "Pet.cpp:659-660",
            "Unit.cpp:510-517",
            "Object.cpp:1074-1085",
            "World.cpp:1227",
            "World.cpp:1254",
            "IndividualProgressionSpells.cpp:91-111",
            "IndividualProgressionSpells.cpp:445",
            "Pet.cpp:1853-1860",
            "PetHandler.cpp:696-834",
            "SpellMgr.cpp:603-608",
            "Object.h:237",
            "Object.h:749",
            "PlayerbotAI.cpp:4523-4528",
            "PetsAction.cpp:395",
            "PET_COWER = 1742",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.note)
        self.assertIn("OnPetAddToWorld", self.note)
        self.assertIn("before `_LoadSpells`", self.note)

    def test_config_key_is_proposed_and_absent_from_the_live_conf(self):
        self.assertEqual(self.note.count(CONFIG_KEY), 1)
        self.assertNotIn("NaxxramasCore.HunterPetAutocast", self.conf)
        self.assertNotIn("HunterPetAutocast", "\n".join(
            path.read_text() for path in (ROOT / "src").rglob("*.cpp")
        ))
        self.assertNotIn("HunterPetAutocast", "\n".join(
            path.read_text() for path in (ROOT / "src").rglob("*.h")
        ))

    def test_scope_thread_safety_and_blocked_pr_69(self):
        for phrase in (
            "MapUpdate.Threads = 8",
            "Pet::CustomData",
            "WorldScript::OnUpdate",
            "IsRealPlayer",
            "^RNDBOT.*",
            "PR #69",
            "still blocked",
            "NOT TESTED",
            "UNKNOWN",
            "VERIFIED",
            "POTENTIAL ISSUE",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.note)
        self.assertIn("process-global", self.note)

    def test_no_new_workflow_and_existing_workflows_do_not_upload_artifacts(self):
        self.assertFalse(list(WORKFLOWS.glob("*a02*hunter*autocast*")))
        self.assertIn("This PR adds no workflow.", self.note)
        scanned = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text()
            scanned += 1
            with self.subTest(workflow=path.name):
                self.assertNotIn("upload-artifact", text)
                self.assertNotIn("actions/upload", text)
                self.assertIn("permissions:", text)
                self.assertIn("contents: read", text)
        self.assertGreater(scanned, 20)
        self.assertNotIn("docs/research/a02-hunter-autocast-functional-s1.md", "\n".join(
            path.read_text() for path in WORKFLOWS.glob("*.yml")
        ))
        self.assertNotIn("test_a02_hunter_autocast_functional_s1.py", "\n".join(
            path.read_text() for path in WORKFLOWS.glob("*.yml")
        ))


if __name__ == "__main__":
    unittest.main()
