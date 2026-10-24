"""Source contract for the A02 S2 default-OFF Hunter autocast writer.

Native behaviour of the decision policy is tests/hunter_pet_autocast_policy.cpp.
These checks lock the C++ guards. Mutating a guard in memory makes the
checker fail. Nothing here starts a worldserver or writes a database.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/HunterPetAutocast.cpp").read_text(encoding="utf-8")
POLICY = (ROOT / "src/Systems/HunterPetAutocastPolicy.h").read_text(encoding="utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")
DOC = (ROOT / "docs/research/a02-hunter-autocast-functional-s2.md").read_text(encoding="utf-8")
WORKFLOW = ROOT / ".github/workflows/hunter-pet-autocast-pinned-worldserver.yml"
CONFIG_LINE = "NaxxramasCore.HunterPetAutocast.RestoreHumanChain = 0"
OFF_GUARD = "if (!RestoreHumanChainEnabled.load(std::memory_order_acquire))\n"


def function_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:index + 1]
    raise AssertionError("unbalanced braces for " + signature)


def off_guard_is_first(body):
    guard = body.find(OFF_GUARD)
    if guard < 0:
        return False
    rest = body[guard + len(OFF_GUARD):]
    if not rest.lstrip().startswith("return;"):
        return False
    pet = body.find("InScope(")
    allocation = body.find("CustomData")
    return 0 <= guard < pet and guard < allocation


def human_check_is_write_time(body):
    wants = body.find("WantsWrite(")
    human = body.find("OwnerIsRealHuman(")
    toggle = body.find("ToggleAutocast(")
    return 0 <= wants < human < toggle


def cower_write_is_blocked(source):
    return (
        "outcome.BaselineSpellId == Policy::COWER_SPELL_ID" in source
        and "outcome.SuccessorSpellId == Policy::COWER_SPELL_ID" in source
        and "learnSpell" not in source
        and "unlearnSpell" not in source
    )


def post_write_before_claim(body):
    agree = body.find("if (!Policy::StoresAgree(after, wantByte))")
    claimed = body.find("claimed = true;")
    packet = body.find("PetSpellInitialize()")
    return 0 <= agree < claimed < packet


def same_chain_uses_spell_mgr(source):
    call = "Policy::DecideChains(state->Book, state->Scratch)"
    return source.count(call) == 1 and "GetFirstSpellInChain" in source


SNAPSHOT = function_body(CPP, "void OnUnitUpdate(Unit* unit, uint32 /*diff*/) override")
RESTORE = function_body(CPP, "void OnWorldObjectUpdate(WorldObject* object, uint32 /*diff*/) override")
CONFIG = function_body(CPP, "void OnBeforeConfigLoad(bool /*reload*/) override")


class ConfigAndLoader(unittest.TestCase):
    def test_conf_defaults_off_and_cpp_fallback_is_false(self):
        self.assertEqual(CONF.count(CONFIG_LINE), 1)
        self.assertNotIn("NaxxramasCore.HunterPetAutocast.RestoreHumanChain = 1", CONF)
        self.assertIn(
            'GetOption<bool>("NaxxramasCore.HunterPetAutocast.RestoreHumanChain", false)',
            CONFIG)
        self.assertIn("RestoreHumanChainEnabled{false}", CPP)
        self.assertNotIn("GetOption", SNAPSHOT)
        self.assertNotIn("GetOption", RESTORE)
        self.assertNotIn("sConfigMgr", SNAPSHOT)
        self.assertNotIn("sConfigMgr", RESTORE)

    def test_loader_registers_once(self):
        self.assertEqual(LOADER.count("void AddHunterPetAutocastScripts();"), 1)
        self.assertEqual(LOADER.count("    AddHunterPetAutocastScripts();"), 1)

    def test_hooks_are_the_enabled_list_only(self):
        self.assertEqual(CPP.count("UNITHOOK_ON_UNIT_UPDATE"), 1)
        self.assertEqual(CPP.count("WORLDOBJECTHOOK_ON_WORLD_OBJECT_UPDATE"), 1)
        self.assertEqual(CPP.count("WORLDHOOK_ON_BEFORE_CONFIG_LOAD"), 1)
        self.assertNotIn("WORLDHOOK_ON_UPDATE", CPP)


class HotPath(unittest.TestCase):
    def test_off_returns_before_scope_and_allocation(self):
        self.assertTrue(off_guard_is_first(SNAPSHOT))
        self.assertTrue(off_guard_is_first(RESTORE))
        self.assertIn("GetDefault<Baseline>", SNAPSHOT)
        self.assertNotIn("GetDefault", RESTORE)
        self.assertIn("CustomData.Get<Baseline>", RESTORE)
        self.assertNotIn("CustomData.Set", CPP)
        self.assertNotIn("DataMap::Set", CPP)

    def test_removing_the_off_guard_fails_the_contract(self):
        self.assertTrue(off_guard_is_first(SNAPSHOT))
        mutated = SNAPSHOT.replace(OFF_GUARD + "                return;\n", "", 1)
        self.assertNotEqual(mutated, SNAPSHOT)
        self.assertFalse(off_guard_is_first(mutated))
        self.assertTrue(off_guard_is_first(RESTORE))
        restore_mutated = RESTORE.replace(OFF_GUARD + "                return;\n", "", 1)
        self.assertFalse(off_guard_is_first(restore_mutated))

    def test_snapshot_does_not_write_or_classify_bots(self):
        for needle in ("ToggleAutocast", "SetSpellAutocast", "PetSpellInitialize",
                       "IsRealPlayer", "OwnerIsRealHuman", "learnSpell"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, SNAPSHOT)


class HumanAndChainGuards(unittest.TestCase):
    def test_real_player_runs_only_when_a_write_is_proposed(self):
        self.assertTrue(human_check_is_write_time(RESTORE))
        self.assertIn("IsRealPlayer(owner)", CPP)
        self.assertEqual(CPP.count("IsRealPlayer("), 1)
        self.assertIn('#if __has_include("Playerbots.h")', CPP)
        self.assertIn("return false;", function_body(CPP, "bool OwnerIsRealHuman(Player* owner)"))
        self.assertIn("owner->GetPet() == pet", RESTORE)
        self.assertNotIn("RNDBOT", CPP)
        self.assertNotIn("BotAccountsRegex", CPP)

    def test_removing_the_write_time_return_fails_the_contract(self):
        self.assertTrue(human_check_is_write_time(RESTORE))
        mutated = RESTORE.replace(
            "if (!Policy::WantsWrite(outcomes))\n                return;\n",
            "",
            1)
        self.assertNotEqual(mutated, RESTORE)
        self.assertFalse(human_check_is_write_time(mutated))

    def test_cower_is_not_learned_and_the_guard_is_load_bearing(self):
        self.assertTrue(cower_write_is_blocked(CPP))
        self.assertTrue(cower_write_is_blocked(RESTORE))
        self.assertNotIn("learnSpell", CPP)
        self.assertNotIn("learnSpell", POLICY)
        self.assertNotIn("unlearnSpell", CPP)
        self.assertNotIn("AddSpellToActionBar", CPP)
        mutated = CPP.replace(
            "outcome.BaselineSpellId == Policy::COWER_SPELL_ID\n"
            "                    || outcome.SuccessorSpellId == Policy::COWER_SPELL_ID\n"
            "                    || ",
            "",
            1)
        self.assertNotEqual(mutated, CPP)
        self.assertFalse(cower_write_is_blocked(mutated))

    def test_chain_key_is_spell_mgr_and_not_a_hardcoded_rank_table(self):
        self.assertTrue(same_chain_uses_spell_mgr(CPP))
        for invented in ("52471", "52472", "52473", "52474", "64495"):
            with self.subTest(spell=invented):
                self.assertNotIn(invented, CPP)
                self.assertNotIn(invented, POLICY)
        mutated = CPP.replace(
            "Policy::DecideChains(state->Book, state->Scratch)",
            "Policy::DecideChains(state->Book, state->Scratch, true, false)",
            1)
        self.assertFalse(same_chain_uses_spell_mgr(mutated))

    def test_post_write_agreement_is_required_before_the_packet(self):
        self.assertTrue(post_write_before_claim(RESTORE))
        self.assertEqual(CPP.count("PetSpellInitialize()"), 1)
        mutated = RESTORE.replace(
            "if (!Policy::StoresAgree(after, wantByte))\n",
            "if (false)\n",
            1)
        self.assertFalse(post_write_before_claim(mutated))

    def test_no_process_global_pet_dictionary(self):
        for source in (CPP, POLICY):
            self.assertNotIn("std::unordered_map", source)
            self.assertNotIn("std::map<", source)
        self.assertIn("does not keep a process-global map", RESTORE)
        self.assertIn("Later OnWorldObjectUpdate subscribers are UNKNOWN", RESTORE)


class ModuleSurface(unittest.TestCase):
    def test_these_are_the_only_update_hooks_in_the_module(self):
        sources = []
        for path in (ROOT / "src").rglob("*"):
            if path.suffix in {".cpp", ".h"}:
                sources.append((path, path.read_text(encoding="utf-8")))
        unit = [path for path, text in sources if "OnUnitUpdate" in text]
        world = [path for path, text in sources if "OnWorldObjectUpdate" in text]
        self.assertEqual(unit, [ROOT / "src/Systems/HunterPetAutocast.cpp"])
        self.assertEqual(world, [ROOT / "src/Systems/HunterPetAutocast.cpp"])

    def test_doc_does_not_claim_an_in_game_pass(self):
        for phrase in (
            "NOT TESTED",
            "UNKNOWN",
            "POTENTIAL ISSUE",
            "VERIFIED",
            "1742",
            "IsRealPlayer",
            "PR #69",
            "default",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DOC)
        self.assertNotIn("passed in game", DOC.lower())
        self.assertNotIn("gameplay passed", DOC.lower())

    def test_workflow_links_exact_head_and_does_not_upload(self):
        self.assertTrue(WORKFLOW.is_file())
        text = WORKFLOW.read_text(encoding="utf-8")
        for needle in (
            "8daffdabe9202c228e45d833c9a1d399597a15cd",
            "dd96f2b77e3ebfa2a4726bf785525ba133f1ab61",
            "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091",
            "github.event.pull_request.head.sha",
            "contents: read",
            "AddHunterPetAutocastScripts()",
            "NaxxramasHunterPetAutocastSnapshotScript",
            "NaxxramasHunterPetAutocastRestoreScript",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn("upload-artifact", text)
        self.assertNotIn("actions/upload", text)
        self.assertLess(text.index("packages.microsoft.com"), text.index("sudo apt-get update"))
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            body = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertNotIn("upload-artifact", body)
                self.assertNotIn("actions/upload", body)


if __name__ == "__main__":
    unittest.main()
