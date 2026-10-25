"""Part 25 isolated FOUR-source workstream exact-lineage contract.

P0 #120 + physical F12 + exterior F13 + WHO F14, NOT A02 or A04.
Git blob hashes anchor reviewed C++ / policy / tests and docs exactly.
This does not perform gameplay, imply approval, or replace native builds.
"""
from pathlib import Path
import hashlib
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FEATURE_BLOBS = {
    "src/Systems/ScarletExitPolicy.h": "8ba43cf1128608bd6a9904f70e8bdbd6bd9b3303",
    "src/Systems/ScarletMonasteryExits.cpp": "736055b81b8f29e5eeed0d5871e9b44cb9ccc901",
    "tests/scarlet_exit_policy.cpp": "669b32a878e1510fa46ff7b5735bdbf67ee8f978",
    "tests/test_scarlet_monastery_exits.py": "3574229d7693752c9a3970928e202596d5984a10",
    "docs/SCARLET-MONASTERY-EXITS.md": "d74737b1bde710ae6a881af1650e89be36c09835",
    "src/Systems/AtieshKarazhanPortal.cpp": "d37c25e6d2d825bc738b07a025ffc4f485948ae1",
    "src/Systems/AtieshPortalPolicy.h": "bc3b51dcf01271f4d13795263d5a4278e3ab897e",
    "src/Systems/IndividualProgressionEra.h": "9f73ec1499e8d1f6839586a68df75c829f5e38dc",
    "tests/atiesh_portal_policy.cpp": "d2feb08fc6817ff7e6e2a0952c66070214350096",
    "tests/test_atiesh_karazhan_portal.py": "c2fc2d35fb767cff5ab556908009d37761de420e",
    "docs/ATIESH-KARAZHAN-PORTAL.md": "f0967734dc78785ae6fd53875cc4dbe8dddea4d7",
    "src/Systems/WhoListing.cpp": "d2926b23a1de87514a7b736298f9c50d8220dc31",
    "src/Systems/WhoListingPolicy.h": "e66f72c374af179945508addcd71c0525271f837",
    "tests/test_f14_who_listing_model.py": "f574813ea0d9082d343d5a90b95f2877c5e5100a",
    "tests/test_f14_who_listing_s2.py": "4d8f64d0a382d800694e55939ccc0e05dfc2cf14",
    "tests/who_listing_policy.cpp": "0dc9c0f7847ffe824c20bffea701445175fd2e3b",
    "scripts/check_f14_who_handler_fingerprint.py": "d4bc8b77ceac29cc6b3f0e190551cc1c436ac031",
    "docs/F14-WHO-LISTING-S2.md": "77d366509c1e63b32fba5fdc55035b259067c9ec",
    "docs/research/F14-WHO-LISTING-S1.md": "767aa33d9e145fd20ba1352aa544034351536cb5",
}
P0_BLOBS = {
    "src/Systems/BotRaidConsumables.cpp": "fcc6e7e4c5f8b7fbe11adbac723abf69b5ea0920",
    "src/Systems/CrossMapAuraQueue.h": "a92d974ee4ac865a92e68eae333cb52438979058",
    "src/Systems/BotGolemaggReachGuard.cpp": "0d36278104126820142b83328ebd55773196b4b0",
    "src/Systems/HonorOverflow.cpp": "812037978847d3977bfdb1f0d3a3e7da4b6405ca",
    "src/Class/Warrior/WarriorRendFlurryBots.cpp": "1ab8e540f890c54a339565df796bb70b6c717fbb",
}
P0_CONF_BLOB = "f8bd75fc96a68c28dcfa7ae157215616c2988eba"
P0_CONF_BYTES = 19381
P0_LOADER_BLOB = "d0da207a2dcaeea1f55109051ae1b2a2a14677db"
ADDED = (
    "AddScarletMonasteryExitScripts",
    "AddAtieshKarazhanPortalScripts",
    "AddWhoListingScripts",
)


def git_blob(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\x00" + content).hexdigest()


def read(path):
    return (ROOT / path).read_bytes()


class FourSourceAssembly(unittest.TestCase):
    def test_all_19_feature_blobs_identical_to_reviewed_drafts(self):
        for path, expected in FEATURE_BLOBS.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(read(path)), expected)

    def test_canonical_p0_source_blobs_not_rewritten(self):
        for path, expected in P0_BLOBS.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(read(path)), expected)
        self.assertIn(b"NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS}", read("src/Systems/BotRaidConsumables.cpp"))

    def test_p0_config_prefix_and_all_default_off_options(self):
        conf = read("conf/mod_naxxramas_core.conf.dist")
        self.assertEqual(git_blob(conf[:P0_CONF_BYTES]), P0_CONF_BLOB)
        keys = [
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled = 0",
            "NaxxramasCore.ScarletExits.Enabled = 0",
            "NaxxramasCore.ScarletExits.UseVanillaDoorTargets = 1",
            "NaxxramasCore.ScarletExits.RouteDungeonFinderExits = 0",
            "NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled = 0",
            "NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0",
            "NaxxramasCore.ExpansionRaceVisibility.GMBypass = 1",
        ]
        lines = conf.decode("utf-8").splitlines()
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(lines.count(key), 1)

    def test_loader_additions_only_and_all_four_registration_calls(self):
        loader = read("src/NaxxramasCore_loader.cpp").decode("utf-8")
        for fn in (*ADDED, "AddBotGolemaggReachGuardScripts", "AddBotRaidConsumablesScripts"):
            with self.subTest(function=fn):
                self.assertEqual(loader.count(f"void {fn}();"), 1)
                self.assertEqual(loader.count(f"    {fn}();"), 1)
        stripped = loader
        for fn in ADDED:
            stripped = stripped.replace(f"void {fn}();\n", "")
            stripped = stripped.replace(f"    {fn}();\n", "")
        self.assertEqual(git_blob(stripped.encode("utf-8")), P0_LOADER_BLOB)

    def test_no_pseudo_production_config_or_playerbot_patch(self):
        body = read("src/Systems/WhoListing.cpp").decode("utf-8")
        self.assertIn("if (!config.hideTbcRaces || !session)", body)
        self.assertIn("if (!observer.ipHeaderAvailable)", body)
        self.assertNotIn("sConfigMgr", body[body.index("bool CanPacketReceive("):body.index("bool CanPacketReceive(")+850])


if __name__ == "__main__":
    unittest.main()
