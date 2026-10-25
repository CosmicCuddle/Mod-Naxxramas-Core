"""Source contract for the F14 S2 `/who` prototype (default OFF).

These checks do not run the core. The native test tests/who_listing_policy.cpp
compares wire bytes against a transcription of the stock handler, and
scripts/check_f14_who_handler_fingerprint.py pins that handler.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/WhoListing.cpp").read_text()
POLICY = (ROOT / "src/Systems/WhoListingPolicy.h").read_text()
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()


def code_only(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def body(code, signature):
    start = code.index(signature)
    brace = code.index("{", start)
    depth = 0
    for i in range(brace, len(code)):
        depth += {"{": 1, "}": -1}.get(code[i], 0)
        if depth == 0:
            return code[brace:i + 1]
    raise AssertionError(signature)


CODE = code_only(CPP)
POLICY_CODE = code_only(POLICY)


class StockWhenOff(unittest.TestCase):
    def test_other_opcodes_and_off_return_true_first(self):
        hook = body(CODE, "bool CanPacketReceive(WorldSession* session, WorldPacket const& packet)")
        first = hook.index("if (packet.GetOpcode() != CMSG_WHO)")
        off = hook.index("if (!config.hideTbcRaces || !session)")
        self.assertLess(first, off)
        self.assertEqual(hook[first:off].count("return true;"), 1)
        self.assertLess(off, hook.index("IsVanillaProgression"))
        self.assertLess(off, hook.index("WorldPacket copy(packet);"))

    def test_no_ip_header_stays_stock_before_era_helper(self):
        # CS01 #145 6398790496: the era helper's no-header fallback reads
        # ConfigMgr on this map thread, so the module must return first.
        hook = body(CODE, "bool CanPacketReceive(WorldSession* session, WorldPacket const& packet)")
        check = hook.index("if (!observer.ipHeaderAvailable)")
        self.assertLess(check, hook.index("NaxxramasIpEra::IsVanillaProgression(player)"))
        self.assertEqual(hook[check:].split("\n", 2)[1].strip(), "return true;")
        self.assertIn("constexpr bool IP_HEADER_AVAILABLE = NAXXRAMAS_IP_ERA_HAS_IP_HEADER != 0;", CODE)
        rule = body(POLICY_CODE, "inline bool InterceptWho(")
        self.assertIn("!o.ipHeaderAvailable", rule)

    def test_rules_decide_before_any_reply(self):
        hook = body(CODE, "bool CanPacketReceive(WorldSession* session, WorldPacket const& packet)")
        self.assertLess(hook.index("if (!InterceptWho(observer))"), hook.index("SendPacket"))
        self.assertIn("observer.observerAboveSecPlayer = session->GetSecurity() > SEC_PLAYER;", hook)
        self.assertIn("NaxxramasIpEra::IsVanillaProgression(player)", hook)
        self.assertEqual(hook.count("SendPacket("), 1)
        self.assertIn("return false;                                  // stock early return", CPP)

    def test_defaults_off(self):
        self.assertEqual(CONF.splitlines().count("NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0"), 1)
        self.assertEqual(CONF.splitlines().count("NaxxramasCore.ExpansionRaceVisibility.GMBypass = 1"), 1)
        self.assertIn('"NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces", false', CODE)
        self.assertIn('"NaxxramasCore.ExpansionRaceVisibility.GMBypass", true', CODE)


class StartupOnlyConfig(unittest.TestCase):
    def test_config_read_only_in_startup_hook(self):
        self.assertEqual(CODE.count("sConfigMgr->"), 2)
        self.assertEqual(body(CODE, "WhoListingConfig ReadWhoListingConfig()").count("sConfigMgr->"), 2)
        self.assertEqual(CODE.count("ReadWhoListingConfig()"), 2)
        hook = body(CODE, "void OnAfterConfigLoad(bool reload)")
        self.assertIn("if (!reload)", hook)
        self.assertEqual(len(re.findall(r"StartupWhoListingConfig\s*=[^=]", CODE)), 1)
        self.assertIn('WorldScript("NaxxramasCoreWhoListingConfig", { WORLDHOOK_ON_AFTER_CONFIG_LOAD })', CODE)

    def test_packet_path_reads_snapshot_only(self):
        hook = body(CODE, "bool CanPacketReceive(WorldSession* session, WorldPacket const& packet)")
        self.assertNotIn("sConfigMgr", hook)
        self.assertIn("WhoListingConfig const& config = StartupWhoListingConfig;", hook)


class MirrorContract(unittest.TestCase):
    def test_hide_runs_before_the_count(self):
        reply = body(POLICY_CODE, "void WriteWhoReply(")
        self.assertLess(reply.index("if (hide && HideRow("), reply.index("if ((matchCount++) >= ctx.maxReturn)"))
        self.assertEqual(reply.count("matchCount++"), 1)
        self.assertIn("data.put(0, displaycount);", reply)
        self.assertIn("data.put(4, matchCount);", reply)

    def test_stock_early_returns_are_kept(self):
        read = body(POLICY_CODE, "bool ReadWhoRequest(")
        for needle in ("if (req.zonesCount > MAX_ZONES)", "if (req.strCount > MAX_STRINGS)",
                       "Text::ToWide(packetPlayerName, req.playerName) &&",
                       "if (req.levelMax >= maxLevel)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, read)
        self.assertIn("MAX_ZONES = 10", POLICY_CODE)
        self.assertIn("MAX_STRINGS = 4", POLICY_CODE)

    def test_policy_header_is_dependency_free(self):
        includes = re.findall(r'#include [<"]([^>"]+)[>"]', POLICY)
        self.assertEqual(sorted(includes), ["array", "cstdint", "string"])

    def test_rule_is_race_10_and_11_and_own_row_kept(self):
        hide = body(POLICY_CODE, "inline bool HideRow(")
        self.assertIn("if (rowIsObserver)", hide)
        self.assertIn("race == RACE_BLOODELF || race == RACE_DRAENEI", hide)
        self.assertIn("RACE_BLOODELF = 10", POLICY_CODE)
        self.assertIn("RACE_DRAENEI = 11", POLICY_CODE)

    def test_reads_only_observer_and_who_cache(self):
        for forbidden in ("ObjectAccessor", "PlayerbotsMgr", "GetPlayerbotAI", "FindPlayer",
                          "sWorldSessionMgr", "IncludePlayerbots"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, CODE + POLICY_CODE)
        self.assertIn("sWhoListCacheMgr->GetWhoList()", CODE)


class Registration(unittest.TestCase):
    def test_loader_registers_once(self):
        self.assertEqual(LOADER.count("void AddWhoListingScripts();"), 1)
        self.assertEqual(LOADER.count("    AddWhoListingScripts();"), 1)
        add = body(CODE, "void AddWhoListingScripts()")
        self.assertEqual(add.count("new NaxxramasCoreWhoListingConfig();"), 1)
        self.assertEqual(add.count("new NaxxramasCoreWhoListing();"), 1)
        self.assertIn('ServerScript("NaxxramasCoreWhoListing", { SERVERHOOK_CAN_PACKET_RECEIVE })', CODE)


if __name__ == "__main__":
    unittest.main()
