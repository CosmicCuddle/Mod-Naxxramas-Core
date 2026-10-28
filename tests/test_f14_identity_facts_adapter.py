"""F14 P5: the identity facts adapter is read-only, world-thread gated and unwired.

Source contract only; native behaviour is in f14_identity_facts_adapter_tests.cpp.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ADAPTER_CPP = (SRC / "Systems/PlayerIdentityFacts.cpp").read_text()
ADAPTER_H = (SRC / "Systems/PlayerIdentityFacts.h").read_text()
OWN = {"Systems/PlayerIdentityFacts.cpp", "Systems/PlayerIdentityFacts.h",
       "Systems/PlayerIdentityPolicy.h"}


def code(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def module_sources():
    for path in sorted(SRC.rglob("*")):
        if path.suffix in (".cpp", ".h") and path.relative_to(SRC).as_posix() not in OWN:
            yield path, code(path.read_text(errors="replace"))


class AdapterIsNotWired(unittest.TestCase):
    def test_no_module_source_uses_the_adapter_or_board(self):
        for path, text in module_sources():
            for name in ("PlayerIdentityFacts", "SampleFacts", "WorldThreadSampling",
                         "IdentityBoard", "NaxxramasPlayerIdentity"):
                with self.subTest(path=path.name, name=name):
                    self.assertNotIn(name, text)

    def test_grant_is_declared_but_never_defined_in_src(self):
        self.assertIn("struct WorldThreadSamplingGrant; // deliberately not defined in src/", ADAPTER_H)
        for path in SRC.rglob("*"):
            if path.suffix in (".cpp", ".h"):
                self.assertIsNone(
                    re.search(r"struct\s+WorldThreadSamplingGrant\s*\{", code(path.read_text(errors="replace"))),
                    path)

    def test_token_cannot_be_aggregate_or_subclass_built(self):
        h = code(ADAPTER_H)
        self.assertIn("class WorldThreadSampling final", h)
        self.assertIn("WorldThreadSampling() {}", h)
        self.assertNotIn("WorldThreadSampling() = default", h)
        self.assertNotRegex(h, r"public:\s*WorldThreadSampling\(")

    def test_adapter_registers_nothing(self):
        c = code(ADAPTER_CPP)
        for denied in ("ScriptMgr.h", "WorldScript", "PlayerScript", "ServerScript",
                       "AddSC_", "Add", "new ", "sScriptMgr", "RegisterHook"):
            with self.subTest(denied=denied):
                if denied == "Add":
                    self.assertIsNone(re.search(r"\bvoid\s+Add\w*Scripts\s*\(", c))
                else:
                    self.assertNotIn(denied, c)


class AdapterIsReadOnly(unittest.TestCase):
    ALLOWED_CALLS = {"GetSession", "IsInWorld", "IsSocketClosed", "instance",
                     "GetPlayerbotAI", "GetMaster", "IsRandomBot"}

    def test_only_allow_listed_calls(self):
        c = code(ADAPTER_CPP)
        calls = set(re.findall(r"(?:->|\.|::)\s*(\w+)\s*\(", c))
        self.assertEqual(calls - self.ALLOWED_CALLS, set())

    def test_no_guessing_inputs_or_remote_lookup(self):
        c = code(ADAPTER_CPP)
        for denied in ("ObjectAccessor", "FindPlayer", "FindConnectedPlayer", "GetName",
                       "getRace", "GetRace", "GetAccountId", "GetGUID", "GetCounter",
                       "GetLevel", "GetRemoteAddress", "HashMapHolder", "sWorld",
                       "sConfigMgr", "GetMap", "GetZoneId"):
            with self.subTest(denied=denied):
                self.assertNotIn(denied, c)

    def test_no_state_kept(self):
        c = code(ADAPTER_CPP)
        self.assertIsNone(re.search(r"\bstatic\b", c))
        self.assertNotIn("thread_local", c)
        # Facts holds only bools: nothing can carry a Player* out.
        policy = code((SRC / "Systems/PlayerIdentityPolicy.h").read_text())
        facts = policy[policy.index("struct Facts"):policy.index("};", policy.index("struct Facts"))]
        self.assertEqual(set(re.findall(r"^\s*(\w+)\s+\w+\s*=", facts, re.M)), {"bool"})

    def test_signature_takes_token_and_returns_by_value(self):
        self.assertIn("Facts SampleFacts(WorldThreadSampling const& onWorldThread, Player* player);",
                      ADAPTER_H)

    def test_missing_headers_fall_back_to_empty_facts(self):
        c = code(ADAPTER_CPP)
        for header in ("PlayerbotAIConfig.h", "PlayerbotMgr.h", "PlayerbotAI.h", "RandomPlayerbotMgr.h"):
            self.assertIn(f'__has_include("{header}")', c)
        tail = c[c.index("#else", c.index("Facts facts;")):]
        self.assertIn("(void)player;", tail)
        self.assertNotIn("facts.", tail[:tail.index("#endif")])

    def test_config_and_loader_untouched_for_f14(self):
        loader = (SRC / "NaxxramasCore_loader.cpp").read_text()
        self.assertNotIn("Identity", loader)
        conf = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
        self.assertNotIn("Identity", conf)
        self.assertNotIn("HideBotsOnly", conf)


if __name__ == "__main__":
    unittest.main()
