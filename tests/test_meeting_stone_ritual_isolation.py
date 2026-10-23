"""Read-only source contract: Warlock rituals must bypass meeting-stone gate.

This test deliberately does not simulate native Warlock portal spawning or
prove installed world DB/gameplay behavior. It checks the actual module hook.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/MeetingStoneProgression.cpp").read_text(
    encoding="utf-8"
)
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text(
    encoding="utf-8"
)


def hook_body():
    begin = "bool CanGameObjectGossipHello(Player* player, GameObject* go) override"
    if SOURCE.count(begin) != 1:
        raise AssertionError("Expected exactly one module GO gossip hook")
    return SOURCE.split(begin, 1)[1].split("\n};", 1)[0]


class MeetingStoneRitualIsolation(unittest.TestCase):
    def test_module_only_intercepts_real_meetingstone_type(self):
        hook = hook_body()
        # This early fail-open type guard excludes a Warlock ritual GO (type 18).
        guard = re.compile(
            r"if\s*\(\s*!player\s*\|\|\s*!go\s*\|\|\s*"
            r"go->GetGoType\(\)\s*!=\s*GAMEOBJECT_TYPE_MEETINGSTONE"
            r"\s*\|\|\s*!sConfigMgr->GetOption<bool>\s*\("
            r'\s*"NaxxramasCore.MeetingStones.ClassicMode.Enabled",\s*true'
            r"\s*\)\s*\)\s*\{\s*return false;\s*\}",
            re.DOTALL,
        )
        # The type/config guard must be the FIRST statement in the hook:
        # a prior injected ritual-specific return true would stop native Use.
        first_statement_guard = re.compile(
            r"^\s*\{\s*" + guard.pattern,
            re.DOTALL,
        )
        self.assertRegex(hook, first_statement_guard)
        # Prove the assertion itself rejects an accidental blocking return.
        altered = hook.replace("return false;", "return (true);", 1)
        self.assertNotRegex(altered, first_statement_guard)
        # Also reject an earlier ritual-specific override before the type guard.
        altered = hook.replace(
            "{",
            "{ if (go->GetGoType() == GAMEOBJECT_TYPE_SUMMONING_RITUAL)"
            " return true;",
            1,
        )
        self.assertNotRegex(altered, first_statement_guard)

    def test_progression_decision_occurs_after_type_guard(self):
        hook = hook_body()
        self.assertLess(
            hook.index("go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE"),
            hook.index("if (!IsVanillaProgression(player))"),
        )
        self.assertLess(
            hook.index("if (!IsVanillaProgression(player))"),
            hook.index("return true;"),
        )
        self.assertIn("return false; // Hand off to AzerothCore", hook)

    def test_disabled_mode_is_fail_open_and_default_stays_original(self):
        hook = hook_body()
        self.assertIn('"NaxxramasCore.MeetingStones.ClassicMode.Enabled", true', hook)
        # No new default-OFF setting or altered stock spell is required to
        # exempt a genuine Ritual of Summoning GO.
        self.assertNotIn("GAMEOBJECT_TYPE_SUMMONING_RITUAL", hook)
        self.assertNotIn("23598", hook)

    def test_guard_hook_is_registered_once(self):
        registration = re.compile(
            r"void\s+AddMeetingStoneProgressionScripts\s*\(\s*\)"
            r"\s*\{\s*new\s+NaxxramasCoreMeetingStoneProgression"
            r"\s*\(\s*\)\s*;\s*\}",
            re.DOTALL,
        )
        self.assertRegex(SOURCE, registration)
        calls = re.findall(
            r"^\s+AddMeetingStoneProgressionScripts\(\);\s*$",
            LOADER,
            re.MULTILINE,
        )
        self.assertEqual(len(calls), 1)
        # Mutation evidence: removing the loader call is a detected failure.
        without_call = LOADER.replace(
            "    AddMeetingStoneProgressionScripts();", "", 1
        )
        altered_calls = re.findall(
            r"^\s+AddMeetingStoneProgressionScripts\(\);\s*$",
            without_call,
            re.MULTILINE,
        )
        self.assertEqual(altered_calls, [])

    def test_vanilla_gate_retains_existing_ip_disabled_fallbacks(self):
        before = SOURCE.split("bool IsVanillaProgression(Player* player)", 1)[1]
        before = before.split("\nclass NaxxramasCoreMeetingStoneProgression", 1)[0]
        self.assertIn("if (!sIndividualProgression->enabled)", before)
        self.assertIn('"IndividualProgression.Enable", true', before)
        self.assertIn("CURRENT_IP_TBC_ENTRY_QUEST", before)
        self.assertIn("return false;", before)

    def test_no_gameplay_or_sql_mutation_in_ritual_contract(self):
        hook = hook_body()
        forbidden = (
            "SetGoType(", "SetFlag(", "SetAmmo(", "Execute(",
            "WorldDatabase.", "CharacterDatabase.", "CastSpell(",
            "DoCast(", "AddAura(", "RemoveAuras",
        )
        for expression in forbidden:
            with self.subTest(expression=expression):
                self.assertNotIn(expression, hook)


# --- Issue #84: Warlock second-stage portal exemption (source + model) ---
GO_TYPE_SUMMONING_RITUAL = 18
GO_TYPE_MEETINGSTONE = 23
WARLOCK_PORTAL_GO = 194097
WARLOCK_PORTAL_SPELL = 61993
RITUAL_GO_ENTRIES_TYPE_18 = (194108, 179944)
OTHER_MEETING_STONE = 179595  # any non-portal type-23 stone


def model_hook(go_type, entry, spell_id, classic_mode, vanilla):
    """Python model of CanGameObjectGossipHello; True means blocked."""
    if go_type != GO_TYPE_MEETINGSTONE or not classic_mode:
        return False
    if not vanilla:
        return False
    if entry == WARLOCK_PORTAL_GO and spell_id == WARLOCK_PORTAL_SPELL:
        return False
    return True


class WarlockPortalExemption(unittest.TestCase):
    def test_source_uses_named_constants_and_exact_pair(self):
        self.assertIn(
            "constexpr uint32 WARLOCK_RITUAL_PORTAL_GO_ENTRY = 194097;", SOURCE)
        self.assertIn(
            "constexpr uint32 WARLOCK_RITUAL_PORTAL_SPELL_ID = 61993;", SOURCE)
        pair = re.compile(
            r"go->GetEntry\(\)\s*==\s*WARLOCK_RITUAL_PORTAL_GO_ENTRY\s*&&"
            r"\s*go->GetSpellId\(\)\s*==\s*WARLOCK_RITUAL_PORTAL_SPELL_ID",
        )
        self.assertRegex(SOURCE, pair)
        # Mutation: dropping the spell check must be detected.
        self.assertNotRegex(
            SOURCE.replace("WARLOCK_RITUAL_PORTAL_SPELL_ID;", "0;")
            .replace("go->GetSpellId() == WARLOCK_RITUAL_PORTAL_SPELL_ID",
                     "true"), pair)
        self.assertNotIn("61994", SOURCE)

    def test_exemption_sits_after_type_config_and_progression_guards(self):
        hook = hook_body()
        self.assertLess(
            hook.index("go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE"),
            hook.index("if (!IsVanillaProgression(player))"))
        self.assertLess(
            hook.index("if (!IsVanillaProgression(player))"),
            hook.index("if (IsWarlockRitualPortal(go))"))
        self.assertLess(
            hook.index("if (IsWarlockRitualPortal(go))"),
            hook.index("return true;"))
        self.assertEqual(hook.count("IsWarlockRitualPortal(go)"), 1)

    def test_model_portal_with_spell_is_exempt(self):
        self.assertFalse(model_hook(23, WARLOCK_PORTAL_GO,
                                    WARLOCK_PORTAL_SPELL, True, True))

    def test_model_portal_with_spell_zero_stays_blocked(self):
        self.assertTrue(model_hook(23, WARLOCK_PORTAL_GO, 0, True, True))

    def test_model_other_type23_stones_stay_blocked(self):
        for spell in (0, WARLOCK_PORTAL_SPELL, 23598):
            with self.subTest(spell=spell):
                self.assertTrue(model_hook(
                    23, OTHER_MEETING_STONE, spell, True, True))

    def test_model_type18_ritual_objects_untouched(self):
        for entry in RITUAL_GO_ENTRIES_TYPE_18:
            for vanilla in (True, False):
                with self.subTest(entry=entry, vanilla=vanilla):
                    self.assertFalse(model_hook(
                        GO_TYPE_SUMMONING_RITUAL, entry, 0, True, vanilla))

    def test_model_classic_mode_off_unchanged(self):
        for entry in (WARLOCK_PORTAL_GO, OTHER_MEETING_STONE):
            for spell in (0, WARLOCK_PORTAL_SPELL):
                with self.subTest(entry=entry, spell=spell):
                    self.assertFalse(model_hook(23, entry, spell, False, True))

    def test_model_tbc_wotlk_unchanged(self):
        for entry in (WARLOCK_PORTAL_GO, OTHER_MEETING_STONE):
            for spell in (0, WARLOCK_PORTAL_SPELL):
                with self.subTest(entry=entry, spell=spell):
                    self.assertFalse(model_hook(23, entry, spell, True, False))


if __name__ == "__main__":
    unittest.main()
