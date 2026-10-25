"""Source contract for the F13 Atiesh portal prototype.

Static checks of src/Systems/AtieshKarazhanPortal.cpp, AtieshPortalPolicy.h,
IndividualProgressionEra.h, the loader and conf.dist. The policy itself is
covered natively by tests/atiesh_portal_policy.cpp. Nothing here runs a
server.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/AtieshKarazhanPortal.cpp").read_text(encoding="utf-8")
POLICY = (ROOT / "src/Systems/AtieshPortalPolicy.h").read_text(encoding="utf-8")
ERA = (ROOT / "src/Systems/IndividualProgressionEra.h").read_text(encoding="utf-8")
MEETING = (ROOT / "src/Systems/MeetingStoneProgression.cpp").read_text(encoding="utf-8")
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text(encoding="utf-8")
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")


def function_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:i + 1]
    raise AssertionError("unbalanced braces for " + signature)


def normalise(code):
    code = re.sub(r"//[^\n]*", "", code)
    code = code.replace("NAXXRAMAS_MEETING_STONES_HAS_IP_HEADER", "HAS_IP")
    code = code.replace("NAXXRAMAS_IP_ERA_HAS_IP_HEADER", "HAS_IP")
    return re.sub(r"\s+", " ", code).strip()


class ConfigAndLoader(unittest.TestCase):
    def test_switch_defaults_off(self):
        self.assertRegex(CONF, r"(?m)^NaxxramasCore\.Atiesh\.VanillaOutdoorArrival\.Enabled = 0$")

    def test_code_default_matches_conf(self):
        self.assertIn('"NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled", false', CPP)

    def test_loader_declares_and_calls_once(self):
        self.assertEqual(LOADER.count("void AddAtieshKarazhanPortalScripts();"), 1)
        self.assertEqual(LOADER.count("    AddAtieshKarazhanPortalScripts();"), 1)


class Hook(unittest.TestCase):
    BODY = function_body(CPP, "bool CanGameObjectGossipHello(Player* player, GameObject* go) override")

    def test_global_gameobject_hook(self):
        self.assertIn("class NaxxramasAtieshPortalScript : public AllGameObjectScript", CPP)

    def test_entry_filter_before_any_lookup(self):
        first = self.BODY.index("go->GetEntry() != GO_ATIESH_PORTAL_TO_KARAZHAN")
        self.assertLess(first, self.BODY.index("Gather("))

    def test_only_stock_returns_false(self):
        self.assertEqual(self.BODY.count("return false;"), 2)  # entry filter + Stock
        self.assertIn("case Action::Stock:\n                return false;", self.BODY)
        self.assertIn("case Action::Ignore:\n                return true;", self.BODY)
        self.assertIn("case Action::FailClosed:\n                Tell(player);\n                return true;", self.BODY)

    def test_add_use_only_after_accepted_teleport(self):
        tail = self.BODY[self.BODY.index("player->TeleportTo("):]
        self.assertRegex(tail, r"TeleportTo\([^;]*\)\)\s*\n\s*go->AddUse\(\);\s*\n\s*else\s*\n\s*Tell\(player\);\s*\n\s*return true;")
        self.assertEqual(CPP.count("AddUse()"), 1)

    def test_mount_parity_only_when_not_usable_mounted(self):
        self.assertIn("if (!go->GetGOInfo()->IsUsableMounted())\n            player->RemoveAurasByType(SPELL_AURA_MOUNTED);", self.BODY)

    def test_teleports_to_live_row_only(self):
        self.assertIn("player->TeleportTo(row->target_mapId, row->target_X, row->target_Y,", self.BODY)
        code = re.sub(r"/\*.*?\*/", "", CPP, flags=re.S)
        code = re.sub(r"//[^\n]*", "", code)
        # No hard-coded Karazhan points or the inside map in code.
        self.assertNotRegex(code, r"-1111\d|2001\.6|\b532\b")


class StartupOnlyConfig(unittest.TestCase):
    """Same fix as #133 / #144: no ConfigMgr read from the gossip hook."""

    def test_config_manager_only_in_reader(self):
        self.assertEqual(CPP.count("sConfigMgr->"), 1)
        self.assertIn("sConfigMgr->", function_body(CPP, "bool ReadEnabled()"))
        self.assertEqual(CPP.count("ReadEnabled()"), 2)  # definition + the hook

    def test_snapshot_written_once_at_startup(self):
        hook = function_body(CPP, "void OnAfterConfigLoad(bool reload) override")
        self.assertIn("bool const loaded = ReadEnabled();", hook)
        self.assertIn("if (!reload)", hook)
        # One declaration (default OFF) and one write, in the startup branch.
        self.assertEqual(CPP.count("bool StartupEnabled = false;"), 1)
        self.assertEqual(len(re.findall(r"StartupEnabled\s*=[^=]", CPP)), 2)
        self.assertEqual(CPP.count("StartupEnabled = loaded;"), 1)
        self.assertIn('WorldScript("NaxxramasAtieshPortalConfig", { WORLDHOOK_ON_AFTER_CONFIG_LOAD })', CPP)
        self.assertNotIn("sConfigMgr", function_body(CPP, "bool Enabled()"))

    def test_era_helper_only_with_feature_on_and_ip_header(self):
        body = function_body(CPP, "Facts Gather(Player* player, GameObject* go, AreaTriggerTeleport const*& row)")
        self.assertIn("f.VanillaStage = f.Enabled && IP_HEADER_AVAILABLE &&", body)
        self.assertIn("constexpr bool IP_HEADER_AVAILABLE = NAXXRAMAS_IP_ERA_HAS_IP_HEADER != 0;", CPP)

    def test_both_scripts_registered_once(self):
        add = function_body(CPP, "void AddAtieshKarazhanPortalScripts()")
        self.assertEqual(add.count("new NaxxramasAtieshPortalConfig();"), 1)
        self.assertEqual(add.count("new NaxxramasAtieshPortalScript();"), 1)


class Gathering(unittest.TestCase):
    BODY = function_body(CPP, "Facts Gather(Player* player, GameObject* go, AreaTriggerTeleport const*& row)")

    def test_non_portal_returns_before_config_and_era(self):
        stop = self.BODY.index("if (!IsAtieshPortal(f))")
        self.assertLess(stop, self.BODY.index("Enabled()"))
        self.assertLess(stop, self.BODY.index("IsVanillaProgression"))

    def test_party_rule_inputs_match_native(self):
        for needle in ("info->spellcaster.partyOnly", "go->GetOwnerGUID()",
                       "player->GetGUID() == owner", "group->IsMember(owner)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.BODY)
        self.assertNotIn("FindPlayer", self.BODY)  # owner need not be online

    def test_runtime_exit_row_validation(self):
        self.assertIn("GetAreaTriggerTeleport(AREATRIGGER_KARAZHAN_MAIN_EXIT)", self.BODY)
        self.assertIn("MapMgr::IsValidMapCoord(row->target_mapId,", self.BODY)

    def test_gm_and_teleport_state(self):
        self.assertIn("player->IsGameMaster()", self.BODY)
        self.assertIn("player->IsBeingTeleported()", self.BODY)


class EraHelper(unittest.TestCase):
    def test_same_rule_as_meeting_stones(self):
        ours = normalise(function_body(ERA, "inline bool IsVanillaProgression(Player* player)"))
        theirs = normalise(function_body(MEETING, "bool IsVanillaProgression(Player* player)"))
        self.assertEqual(ours, theirs)

    def test_meeting_stones_untouched_and_separate_namespace(self):
        self.assertIn("namespace NaxxramasIpEra", ERA)
        self.assertNotIn("IndividualProgressionEra.h", MEETING)

    def test_constants_match(self):
        for needle in ("CURRENT_IP_TBC_ENTRY = 8", "LEGACY_IP_TBC_ENTRY = 7",
                       "CURRENT_IP_TBC_ENTRY_QUEST = 66000 + CURRENT_IP_TBC_ENTRY"):
            with self.subTest(needle=needle):
                self.assertIn(needle, ERA)
                self.assertIn(needle, MEETING)


class Boundaries(unittest.TestCase):
    def test_no_database_spell_or_core_teleport_paths(self):
        for needle in ("Database", "Execute(", "Query(", "CastSpell", "spell_target_position",
                       "OnPlayerBeforeTeleport", "CanPrepare", "AllSpellScript"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, CPP)
                self.assertNotIn(needle, POLICY)

    def test_policy_is_dependency_free(self):
        self.assertEqual(re.findall(r'#include [<"]([^>"]+)[>"]', POLICY), ["cstdint"])

    def test_known_limit_is_documented_in_source(self):
        self.assertIn("never reaches this hook", CPP)


if __name__ == "__main__":
    unittest.main()
