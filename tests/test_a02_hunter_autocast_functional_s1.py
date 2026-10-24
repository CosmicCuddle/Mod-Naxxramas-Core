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
        if successor.bar != successor.active:
            results.append("NO_WRITE")
            continue
        if successor.active == chosen.active and successor.bar == chosen.active:
            results.append("NO_WRITE")
            continue
        results.append("RESTORE_ENABLED" if chosen.active == ACT_ENABLED else "RESTORE_DISABLED")
    return results


class SpellStores:
    """One spell's active byte, autocast vector membership, and bar slot."""

    def __init__(self, present, active, in_autospells, bar):
        self.present = present
        self.active = active
        self.in_autospells = in_autospells
        self.bar = bar


def toggle_autocast(state, apply):
    """Pet.cpp:2247-2286. A vector mismatch is a no-op and does not repair active."""
    if not state.present:
        return "absent"
    if apply:
        if state.in_autospells:
            return "noop"
        state.in_autospells = True
        if state.active != ACT_ENABLED:
            state.active = ACT_ENABLED
        return "wrote"
    if not state.in_autospells:
        return "noop"
    state.in_autospells = False
    if state.active != ACT_DISABLED:
        state.active = ACT_DISABLED
    return "wrote"


def set_spell_autocast(state, enabled):
    """CharmInfo.cpp:291-300. An absent slot stays absent."""
    if state.bar is None:
        return "noop"
    state.bar = ACT_ENABLED if enabled else ACT_DISABLED
    return "wrote"


def stores_agree(state):
    if not state.present or state.active not in CHOICE_BYTES or state.bar != state.active:
        return False
    return state.in_autospells == (state.active == ACT_ENABLED)


def restore_choice(state, want_enabled, write_bar=True):
    """Refuse splits before writing. After a write, disagreement is NO_WRITE."""
    if not state.present or state.active not in CHOICE_BYTES:
        return "NO_WRITE"
    if state.bar is None:
        return "NO_BAR"
    if state.bar != state.active:
        return "NO_WRITE"
    if state.in_autospells != (state.active == ACT_ENABLED):
        return "NO_WRITE"
    if (state.active == ACT_ENABLED) == want_enabled:
        return "NO_WRITE"
    toggle_autocast(state, want_enabled)
    if write_bar:
        set_spell_autocast(state, want_enabled)
    if not stores_agree(state):
        return "NO_WRITE"
    return "RESTORE_ENABLED" if want_enabled else "RESTORE_DISABLED"


class BaselineStore:
    def __init__(self):
        self.allocations = 0
        self.obj = None

    def get_default(self):
        if self.obj is None:
            self.allocations += 1
            self.obj = {"book": None}
        return self.obj

    def set_replace(self):
        self.allocations += 1
        self.obj = {"book": None}
        return self.obj


class CachedConfig:
    def __init__(self):
        self.load_reads = 0
        self.value = False

    def on_config_load(self, raw):
        self.load_reads += 1
        self.value = bool(raw)

    def enabled(self):
        return self.value


def hot_path_tick(config, is_pet, is_hunter_pet, store, use_set=False):
    """Cached flag, then hunter pet, then in-place GetDefault. No work before that."""
    if not config.enabled():
        return "skip"
    if not is_pet or not is_hunter_pet:
        return "skip"
    if use_set:
        slot = store.set_replace()
    else:
        slot = store.get_default()
    slot["book"] = []
    return "snap"


def authorize_write(header_present, is_real_player, owner_pet_matches):
    """IsRealPlayer runs only at write time. A missing header does not count as human."""
    if not header_present:
        return "OUT_OF_SCOPE", False
    if not is_real_player:
        return "OUT_OF_SCOPE", True
    if not owner_pet_matches:
        return "NO_WRITE", True
    return "WRITE", True


def a02_pet_in_scope(pet_type, owner_class):
    return pet_type == "HUNTER_PET" and owner_class == "HUNTER"


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
        self.assertGreaterEqual(len(rows), 18)
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
            "successor-split-row-off",
            "successor-split-row-on",
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

    def test_config_key_is_recorded_once_in_the_s1_note(self):
        self.assertEqual(self.note.count(CONFIG_KEY), 1)
        # S2 adds the same key at default 0. The S1 note still records it once.
        self.assertEqual(self.conf.count(CONFIG_KEY), 1)

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

    def test_pinned_spell_ranks_identity_is_recorded(self):
        rows = {
            17253: [17253, 17255, 17256, 17257, 17258, 17259, 17260, 17261, 27050, 52473, 52474],
            16827: [16827, 16828, 16829, 16830, 16831, 16832, 3010, 3009, 27049, 52471, 52472],
            24604: [24604, 64491, 64492, 64493, 64494, 64495],
            24450: [24450, 24452, 24453],
        }
        self.assertEqual([len(rows[17253]), len(rows[16827]), len(rows[24604]), len(rows[24450])], [11, 11, 6, 3])
        self.assertEqual(sum(len(spells) for spells in rows.values()), 31)
        self.assertEqual(len({spell for spells in rows.values() for spell in spells}), 31)
        for first, spells in rows.items():
            self.assertIn(str(first), self.note)
            for spell in spells:
                self.assertIn(str(spell), self.note)
        for phrase in (
            "ca2ca5916cca570d219ff11088688eb4c80d24a6",
            "11 + 11 + 6 + 3 = 31",
            "58147 bytes, 3552 lines, 3502",
            "Source chain identity is **VERIFIED** at the pin.",
            "The owner's live `acore_world.spell_ranks` is **UNKNOWN**.",
            "SELECT first_spell_id, spell_id, `rank` FROM spell_ranks",
            "WHERE first_spell_id IN (17253, 16827, 24604, 24450)",
            "ORDER BY first_spell_id, `rank`;",
            "Cower stays `NO_LEARN`.",
            "This design does not call `learnSpell` to put it back.",
            "does not name `52471`, `52472`, `52473`, `52474`, or `64495`",
            "SpellMgr.cpp:1287",
            "IndividualProgressionSpells.cpp:56-469",
            "Object.h:233",
            "Pet.cpp:1909-1915",
            "CharmInfo.h:54-55",
            "ACTION_BAR_INDEX_PET_SPELL_START",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.note)
        for absent in (1753, 1754, 1755, 1756, 16697, 27048):
            self.assertIn(str(absent), self.note)

    def test_post_write_consistency_rejects_noop_splits(self):
        learned_off = SpellStores(True, ACT_DISABLED, False, ACT_DISABLED)
        self.assertEqual(restore_choice(learned_off, True), "RESTORE_ENABLED")
        self.assertTrue(stores_agree(learned_off))
        self.assertEqual(learned_off.active, ACT_ENABLED)
        self.assertTrue(learned_off.in_autospells)
        self.assertEqual(learned_off.bar, ACT_ENABLED)

        already_on = SpellStores(True, ACT_ENABLED, True, ACT_ENABLED)
        self.assertEqual(restore_choice(already_on, True), "NO_WRITE")

        turn_off = SpellStores(True, ACT_ENABLED, True, ACT_ENABLED)
        self.assertEqual(restore_choice(turn_off, False), "RESTORE_DISABLED")
        self.assertEqual(turn_off.active, ACT_DISABLED)
        self.assertFalse(turn_off.in_autospells)
        self.assertEqual(turn_off.bar, ACT_DISABLED)

        split_row = SpellStores(True, ACT_DISABLED, False, ACT_ENABLED)
        self.assertEqual(restore_choice(split_row, False), "NO_WRITE")
        self.assertEqual(split_row.bar, ACT_ENABLED)
        self.assertFalse(split_row.in_autospells)

        split_vector_on = SpellStores(True, ACT_DISABLED, True, ACT_DISABLED)
        self.assertEqual(toggle_autocast(split_vector_on, True), "noop")
        self.assertEqual(split_vector_on.active, ACT_DISABLED)
        fresh_vector = SpellStores(True, ACT_DISABLED, True, ACT_DISABLED)
        self.assertEqual(restore_choice(fresh_vector, True), "NO_WRITE")
        self.assertTrue(fresh_vector.in_autospells)

        split_vector_off = SpellStores(True, ACT_ENABLED, False, ACT_ENABLED)
        self.assertEqual(toggle_autocast(split_vector_off, False), "noop")
        self.assertEqual(split_vector_off.active, ACT_ENABLED)
        self.assertEqual(restore_choice(SpellStores(True, ACT_ENABLED, False, ACT_ENABLED), False), "NO_WRITE")

        missing = SpellStores(True, ACT_DISABLED, False, None)
        self.assertEqual(set_spell_autocast(missing, True), "noop")
        self.assertIsNone(missing.bar)
        self.assertEqual(restore_choice(SpellStores(True, ACT_DISABLED, False, None), True), "NO_BAR")

        bar_left_behind = SpellStores(True, ACT_DISABLED, False, ACT_DISABLED)
        self.assertEqual(restore_choice(bar_left_behind, True, write_bar=False), "NO_WRITE")
        self.assertFalse(stores_agree(bar_left_behind))

    def test_hot_path_caches_config_and_avoids_per_tick_allocation(self):
        config = CachedConfig()
        config.on_config_load(False)
        store = BaselineStore()
        for _ in range(8):
            self.assertEqual(hot_path_tick(config, True, True, store), "skip")
        self.assertEqual(store.allocations, 0)
        self.assertEqual(config.load_reads, 1)

        config.on_config_load(True)
        self.assertEqual(config.load_reads, 2)
        for _ in range(8):
            self.assertEqual(hot_path_tick(config, False, False, store), "skip")
            self.assertEqual(hot_path_tick(config, True, False, store), "skip")
        self.assertEqual(store.allocations, 0)

        for _ in range(8):
            self.assertEqual(hot_path_tick(config, True, True, store), "snap")
        self.assertEqual(store.allocations, 1)
        self.assertEqual(config.load_reads, 2)
        self.assertIs(store.get_default(), store.obj)

        replacing = BaselineStore()
        for _ in range(8):
            hot_path_tick(config, True, True, replacing, use_set=True)
        self.assertEqual(replacing.allocations, 8)

    def test_human_check_is_write_time_and_fail_closed(self):
        self.assertEqual(authorize_write(False, True, True), ("OUT_OF_SCOPE", False))
        self.assertEqual(authorize_write(True, False, True), ("OUT_OF_SCOPE", True))
        self.assertEqual(authorize_write(True, True, False), ("NO_WRITE", True))
        self.assertEqual(authorize_write(True, True, True), ("WRITE", True))

    def test_pet_guard_competing_hooks_and_warlock_scope(self):
        self.assertTrue(a02_pet_in_scope("HUNTER_PET", "HUNTER"))
        self.assertFalse(a02_pet_in_scope("SUMMON_PET", "WARLOCK"))
        self.assertFalse(a02_pet_in_scope("HUNTER_PET", "WARLOCK"))
        for phrase in (
            "The S2 writer is not started.",
            "successor-split-vector",
            "cached config bool",
            "DataMap.h:50-59",
            "DataMap::Set",
            "DataMap.h:65",
            "only when a restore is about to be written",
            "`_playerbotsAIMap` without a lock",
            "b5a5d7236af6e71312c8c89c10d0d1008ece4d86a3373eab8ab6fa06a9750610",
            "HallowsEndShadeOfTheHorseman.cpp:57",
            "A missing header is not a human.",
            "owner->GetPet() == pet",
            "IndividualProgressionSpells.cpp:1344",
            "Pet.cpp:656-657",
            "does not make this module the last writer",
            "owner's other modules",
            "Warlock pets are out of A02 scope.",
            "19505",
            "54049",
            "19244",
            "24259",
            "30151",
            "30154",
            "30213",
            "30214",
            "UnitScript.h:57",
            "WorldObjectScript.h:37",
            "UnitScript.cpp:109",
            "WorldObjectScript.cpp:54",
            "Pet.cpp:2247-2286",
            "CharmInfo.cpp:291-300",
            "src/Bot/PlayerbotMgr.cpp:1858-1875",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.note)


if __name__ == "__main__":
    unittest.main()
