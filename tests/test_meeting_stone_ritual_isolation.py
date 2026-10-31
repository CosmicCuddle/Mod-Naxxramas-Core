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
    def test_module_only_intercepts_meetingstone_or_exact_opt_in_warlock_portal(self):
        hook = hook_body()
        # The default-OFF, origin-checked exception is the ONLY early
        # override. Every other GO reaches the original IP gate.
        self.assertIn("if (!player || !go)\n            return false;", hook)
        self.assertRegex(
            hook, re.compile(
                r"go->GetGoType\(\) == GAMEOBJECT_TYPE_MEETINGSTONE\s*&&\s*"
                r"go->GetEntry\(\) == WARLOCK_SECOND_PORTAL_ENTRY\s*&&\s*"
                r"sConfigMgr->GetOption<bool>\(\s*"
                r'"NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", false',
                re.DOTALL))
        original_gate = re.compile(
            r"if\s*\(\s*go->GetGoType\(\) != GAMEOBJECT_TYPE_MEETINGSTONE\s*\|\|\s*"
            r"!sConfigMgr->GetOption<bool>\(\s*"
            r'"NaxxramasCore.MeetingStones.ClassicMode.Enabled", true',
            re.DOTALL)
        self.assertRegex(hook, original_gate)
        self.assertLess(hook.index("go->GetEntry() == WARLOCK_SECOND_PORTAL_ENTRY"),
                        hook.index("go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE"))
        # Deliberately modified default-on pilot is detected.
        altered = hook.replace(
            '"NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", false',
            '"NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", true', 1)
        self.assertNotIn(
            '"NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", false',
            altered)

    def test_progression_decision_occurs_after_type_guard(self):
        hook = hook_body()
        original = hook.split(
            "if (go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE", 1)[1]
        self.assertLess(
            hook.index("go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE"),
            hook.index("if (!IsVanillaProgression(player))"),
        )
        # Check only the unchanged *ordinary dungeon stone* path; the
        # isolated opt-in portal branch may have earlier fail-closed returns.
        self.assertLess(
            original.index("if (!IsVanillaProgression(player))"),
            original.index("return true;"),
        )
        self.assertIn("return false; // Hand off to AzerothCore", original)

    def test_disabled_mode_is_fail_open_and_default_stays_original(self):
        hook = hook_body()
        self.assertIn('"NaxxramasCore.MeetingStones.ClassicMode.Enabled", true', hook)
        # No new default-OFF setting or altered stock spell is required to
        # exempt a genuine Ritual of Summoning GO.
        self.assertNotIn("GAMEOBJECT_TYPE_SUMMONING_RITUAL", hook)
        self.assertIn("NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", hook)
        original = hook.split("if (go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE", 1)[1]
        self.assertNotIn("23598", original)

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
        # Preserve the no-cast/no-mutation contract on the ordinary
        # Meeting Stone path; the separate exact-GO pilot is tested
        # explicitly for its ONE 61994 cast.
        ordinary = hook.split(
            "if (go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE", 1)[1]
        forbidden = (
            "SetGoType(", "SetFlag(", "SetAmmo(", "Execute(",
            "WorldDatabase.", "CharacterDatabase.", "CastSpell(",
            "DoCast(", "AddAura(", "RemoveAuras",
        )
        for expression in forbidden:
            with self.subTest(expression=expression):
                self.assertNotIn(expression, ordinary)


if __name__ == "__main__":
    unittest.main()
