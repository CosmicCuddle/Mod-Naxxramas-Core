"""A03 P4: the NT1 in-place swap fact checker must fail on any changed fact.

Each negative case mutates the REAL pinned source text (paths from the
environment) and expects the matching fact to fail. Needs:
  NT1_PIN_CORE        Grimfeather core checkout (8daffda)
  NT1_PIN_PLAYERBOTS  mod-playerbots checkout (d750b4b)
  NT1_PIN_IP          mod-individual-progression checkout (dd96f2b)
Without them the module is skipped (so a broad local discover still runs);
the dedicated workflow sets them and requires 'Ran 23' with a bare 'OK',
so a skipped run can never pass there.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_nt1_inplace_swap_facts as facts  # noqa: E402


def pin(name):
    value = os.environ.get(name)
    if not value or not Path(value).is_dir():
        raise unittest.SkipTest(f"{name} does not point at a pinned checkout")
    return Path(value)


CORE = pin("NT1_PIN_CORE")
PLAYERBOTS = pin("NT1_PIN_PLAYERBOTS")
IP = pin("NT1_PIN_IP")
PLAYER_DIR = CORE / "src/server/game/Entities/Player"
PLAYER_CPP = (PLAYER_DIR / "Player.cpp").read_text()
PLAYER_H = (PLAYER_DIR / "Player.h").read_text()


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


RESET_SIG = "bool Player::resetTalents(bool noResetCost)"


def in_function(text, signature, old, new):
    """Replace exactly one occurrence inside one function body only."""
    begin, end = facts.span(text, signature)
    return text[:begin] + replace_once(text[begin:end], old, new) + text[end:]


class RealPins(unittest.TestCase):
    def test_all_facts_hold_at_the_pins(self):
        lines = facts.run(CORE, PLAYERBOTS, IP, ROOT)
        self.assertIn("changed_build_altbot_apply_safe=false (no such path is implemented)", lines)
        self.assertIn("reset_free_swap_primitives_public=true", lines)

    def test_cli_exit_codes(self):
        args = ["--core", str(CORE), "--playerbots", str(PLAYERBOTS), "--ip", str(IP),
                "--module", str(ROOT)]
        self.assertEqual(facts.main(args), 0)
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(facts.main(["--core", empty, "--playerbots", empty,
                                         "--ip", empty, "--module", str(ROOT)]), 1)


class ResetFacts(unittest.TestCase):
    def assertFact(self, code, fn, *args):
        with self.assertRaises(facts.FactError) as caught:
            fn(*args)
        self.assertTrue(str(caught.exception).startswith(code), str(caught.exception))

    def test_f1_conditional_pet_removal(self):
        text = in_function(PLAYER_CPP, RESET_SIG, "    RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true);",
                           "    if (GetPet() && false)\n        RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true);")
        self.assertFact("F1", facts.check_reset, text)

    def test_f1_pet_removal_gone(self):
        text = in_function(PLAYER_CPP, RESET_SIG, "    RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true);", "")
        self.assertFact("F1", facts.check_reset, text)

    def test_f1_pet_removal_after_loop(self):
        text = in_function(PLAYER_CPP, RESET_SIG, "    RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true);", "")
        text = in_function(text, RESET_SIG, "    AutoUnequipOffhandIfNeed();\n\n    // pussywizard: removed saving",
                           "    AutoUnequipOffhandIfNeed();\n    RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true);\n\n    // pussywizard: removed saving")
        self.assertFact("F1", facts.check_reset, text)

    def test_f2_no_offhand_unequip(self):
        text = in_function(PLAYER_CPP, RESET_SIG, "    AutoUnequipOffhandIfNeed();\n\n    // pussywizard: removed saving",
                            "\n    // pussywizard: removed saving")
        self.assertFact("F2", facts.check_reset, text)

    def test_f3_new_capability_reset_site(self):
        game = {"src/server/game/Entities/Player/Player.cpp": PLAYER_CPP,
                "src/server/game/Spells/Other.cpp": "void X() { p->SetCanTitanGrip(false); }"}
        self.assertFact("F3", facts.check_capability_sites, game)

    def test_f3_site_removed_from_activate_spec(self):
        spec_start = PLAYER_CPP.index("void Player::ActivateSpec(uint8 spec)")
        head, tail = PLAYER_CPP[:spec_start], PLAYER_CPP[spec_start:]
        tail = tail.replace("SetCanDualWield(false);", "(void)0;", 1)
        game = {"src/server/game/Entities/Player/Player.cpp": head + tail}
        self.assertFact("F3", facts.check_capability_sites, game)

    def test_f3_baseline_passes(self):
        facts.check_capability_sites({"src/server/game/Entities/Player/Player.cpp": PLAYER_CPP})

    def test_f4_primitive_made_private(self):
        text = replace_once(PLAYER_H, "    void _removeTalentAurasAndSpells(uint32 spellId);",
                            "private:\n    void _removeTalentAurasAndSpells(uint32 spellId);\npublic:")
        self.assertFact("F4", facts.check_public_primitives, text)

    def test_f4_primitive_removed(self):
        text = replace_once(PLAYER_H, "    void _addTalentAurasAndSpells(uint32 spellId);", "")
        self.assertFact("F4", facts.check_public_primitives, text)

    def test_f5_learn_hook_removed(self):
        text = replace_once(PLAYER_CPP,
                            "    sScriptMgr->OnPlayerLearnTalents(this, talentId, talentRank, spellId);", "")
        self.assertFact("F5", facts.check_learn_talent, text)

    def test_f5_exit_after_add_talent(self):
        text = replace_once(PLAYER_CPP, "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                            "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);\n    if (!learned)\n        return;")
        self.assertFact("F5", facts.check_learn_talent, text)

    def test_f5_veto_moved_after_rule_checks(self):
        text = replace_once(PLAYER_CPP,
                            "    if (!sScriptMgr->OnPlayerCanLearnTalent(this, talentInfo, talentRank))\n        return;\n", "")
        text = replace_once(text, "    // xinef: hacking attempt, tries to learn unknown rank",
                            "    if (!sScriptMgr->OnPlayerCanLearnTalent(this, talentInfo, talentRank))\n        return;\n    // xinef: hacking attempt, tries to learn unknown rank")
        self.assertFact("F5", facts.check_learn_talent, text)

    def test_f6_new_failure_exit(self):
        text = replace_once(PLAYER_CPP, "    // xinef: add talent auras and spells\n",
                            "    if (IsInCombat())\n        return false;\n    // xinef: add talent auras and spells\n")
        self.assertFact("F6", facts.check_add_talent, text)

    def test_f6_hook_in_add_talent(self):
        text = replace_once(PLAYER_CPP, "    // xinef: add talent auras and spells\n",
                            "    sScriptMgr->OnPlayerLearnTalents(this, 0, 0, spellId);\n    // xinef: add talent auras and spells\n")
        self.assertFact("F6", facts.check_add_talent, text)


class HookAndModuleFacts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def module_copy(self):
        dest = self.base / "module"
        shutil.copytree(ROOT / "src", dest / "src")
        return dest

    def test_f7_playerbots_gains_a_veto(self):
        bots = self.base / "playerbots"
        (bots / "src").mkdir(parents=True)
        (bots / "src/NewScript.cpp").write_text(
            "bool OnPlayerCanLearnTalent(Player*, TalentEntry const*, uint32) override { return false; }")
        with self.assertRaisesRegex(facts.FactError, "^F7: Playerbots"):
            facts.check_hooks(bots / "src", IP / "src", ROOT)

    def test_f7_ip_gains_a_reset_hook(self):
        ip = self.base / "ip"
        (ip / "src").mkdir(parents=True)
        (ip / "src/X.h").write_text("void OnPlayerTalentsReset(Player* p, bool c) override;")
        with self.assertRaisesRegex(facts.FactError, "^F7: Individual Progression"):
            facts.check_hooks(PLAYERBOTS / "src", ip / "src", ROOT)

    def test_f7_commented_hook_is_ignored(self):
        bots = self.base / "playerbots"
        (bots / "src").mkdir(parents=True)
        (bots / "src/Note.cpp").write_text("// bool OnPlayerCanLearnTalent(Player*) is not used\n")
        facts.check_hooks(bots / "src", IP / "src", ROOT)

    def test_f7_module_hook_set_changes(self):
        module = self.module_copy()
        path = module / "src/Class/Shaman/ShamanRockbiter.cpp"
        path.write_text(path.read_text().replace("void OnPlayerLearnTalents(", "void OnRenamed(", 1))
        with self.assertRaisesRegex(facts.FactError, "^F7: module"):
            facts.check_hooks(PLAYERBOTS / "src", IP / "src", module)

    def test_f8_pet_guard_removed(self):
        module = self.module_copy()
        path = module / "src/Systems/BotTalentImport.cpp"
        path.write_text(replace_once(path.read_text(), "if (bot->GetPet() != nullptr)", "if (false)"))
        with self.assertRaisesRegex(facts.FactError, "^F8"):
            facts.check_module_apply(module)

    def test_f8_offhand_guard_removed(self):
        module = self.module_copy()
        path = module / "src/Systems/BotTalentImport.cpp"
        path.write_text(replace_once(
            path.read_text(), "INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND) != nullptr)\n            {\n                error = \"Alt Bot NT1 Apply blocked",
            "INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND) == reinterpret_cast<Item*>(1))\n            {\n                error = \"Alt Bot NT1 Apply blocked"))
        with self.assertRaisesRegex(facts.FactError, "^F8"):
            facts.check_module_apply(module)

    def test_f8_apply_no_longer_resets(self):
        module = self.module_copy()
        path = module / "src/Systems/BotTalentImport.cpp"
        text = path.read_text().replace("bot->resetTalents(true);", "bot->SwapTalentsInPlace();")
        path.write_text(text)
        with self.assertRaisesRegex(facts.FactError, "^F8"):
            facts.check_module_apply(module)


if __name__ == "__main__":
    unittest.main()
