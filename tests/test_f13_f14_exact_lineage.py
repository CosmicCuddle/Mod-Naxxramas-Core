"""F13 current-head + exact F14 source transfer acceptance, offline-only.

Hashes are Git *blob* SHA-1 identifiers verified by GitHub's contents API.
This is an integration provenance check, NOT a live WoW 3.3.5a acceptance.
"""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
F14 = {
    ".github/workflows/f14-who-listing-s1.yml": "4fe45aff6b6c7b688890161dc7e30475b93eaee1",
    ".github/workflows/f14-who-listing-s2.yml": "e00bb63188846d5354b93c0e3ca99c1ca3b21cac",
    "docs/F14-WHO-LISTING-S2.md": "77d366509c1e63b32fba5fdc55035b259067c9ec",
    "docs/research/F14-WHO-LISTING-S1.md": "767aa33d9e145fd20ba1352aa544034351536cb5",
    "scripts/check_f14_who_handler_fingerprint.py": "d4bc8b77ceac29cc6b3f0e190551cc1c436ac031",
    "src/Systems/WhoListing.cpp": "d2926b23a1de87514a7b736298f9c50d8220dc31",
    "src/Systems/WhoListingPolicy.h": "e66f72c374af179945508addcd71c0525271f837",
    "tests/test_f14_who_listing_model.py": "f574813ea0d9082d343d5a90b95f2877c5e5100a",
    "tests/test_f14_who_listing_s2.py": "4d8f64d0a382d800694e55939ccc0e05dfc2cf14",
    "tests/who_listing_policy.cpp": "0dc9c0f7847ffe824c20bffea701445175fd2e3b",
    "src/NaxxramasCore_loader.cpp": "950ac6efe6fc00f24d41aaa5c148be34e07715ab",
    "conf/mod_naxxramas_core.conf.dist": "0401e4b7f0c72fa12edc0595a5f0772e44977fc3",
}
F13 = {
    "src/Systems/AtieshKarazhanPortal.cpp": "d37c25e6d2d825bc738b07a025ffc4f485948ae1",
    "src/Systems/AtieshPortalPolicy.h": "bc3b51dcf01271f4d13795263d5a4278e3ab897e",
    "src/Systems/IndividualProgressionEra.h": "9f73ec1499e8d1f6839586a68df75c829f5e38dc",
    "docs/ATIESH-KARAZHAN-PORTAL.md": "f0967734dc78785ae6fd53875cc4dbe8dddea4d7",
}


def git_blob(path):
    value = (ROOT / path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(value)).encode() + b"\x00" + value).hexdigest()


class F13F14ExactSourceIntegration(unittest.TestCase):
    def test_exact_f14_source_and_shared_changes(self):
        for path, blob in F14.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(path), blob)

    def test_exact_f13_runtime_and_docs_preserved(self):
        for path, blob in F13.items():
            with self.subTest(path=path):
                self.assertEqual(git_blob(path), blob)

    def test_both_registration_paths_present_once(self):
        code = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()
        for script in ("AddAtieshKarazhanPortalScripts", "AddWhoListingScripts"):
            with self.subTest(script=script):
                self.assertEqual(code.count("void " + script + "();"), 1)
                self.assertEqual(code.count("    " + script + "();"), 1)

    def test_both_features_remain_default_off(self):
        config = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text().splitlines()
        for entry in (
            "NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled = 0",
            "NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0",
            "NaxxramasCore.ExpansionRaceVisibility.GMBypass = 1",
        ):
            with self.subTest(entry=entry):
                self.assertEqual(config.count(entry), 1)


if __name__ == "__main__":
    unittest.main()
