"""A02 runtime quarantine, source-level structural checks only."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ADDON = (ROOT / "src/Systems/HunterPetAutocastAddon.h").read_text()
CPP = (ROOT / "src/Systems/HunterPetAutocast.cpp").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()

class LegacyRuntimeQuarantine(unittest.TestCase):
    def test_v1_snapshot_has_no_automatic_authority(self):
        self.assertRegex(ADDON, r"bool\s+VerifiedHumanManualOrigin\s*=\s*false")
        self.assertIn("bool OptedIn = false", ADDON)

    def test_legacy_assembler_does_not_promote_provenance(self):
        ingest = ADDON[ADDON.index("IngestResult Accept("):]
        self.assertIn("snapshot->OptedIn = true;", ingest)
        self.assertNotIn("snapshot->VerifiedHumanManualOrigin = true", ingest)
        self.assertNotIn("VerifiedHumanManualOrigin =", ingest)

    def test_runtime_calls_strong_gate_before_making_plan(self):
        region = CPP[CPP.index("void OnWorldObjectUpdate("):CPP.index("class NaxxramasHunterPetAutocastAddonScript")]
        self.assertIn("if (!Policy::EligibleForAutomaticRestore(optIn.get()))", region)
        self.assertLess(region.index("if (!Policy::EligibleForAutomaticRestore(optIn.get()))"),
                        region.index("Policy::BuildAddonPlan("))
        self.assertLess(region.index("if (!Policy::EligibleForAutomaticRestore(optIn.get()))"),
                        region.index("pet->ToggleAutocast("))

    def test_non_authoritative_pet_baseline_cannot_write(self):
        guard = ADDON[ADDON.index("inline bool EligibleForAutomaticRestore("):
                      ADDON.index("inline bool EligibleForAutomaticRestore(") + 245]
        self.assertIn("preference->OptedIn && preference->VerifiedHumanManualOrigin", guard)

    def test_default_flags_still_off(self):
        for key in ("RestoreHumanChain", "AddonOptIn"):
            self.assertIn("NaxxramasCore.HunterPetAutocast." + key + " = 0", CONF)

    def test_receiver_scope_did_not_regress(self):
        self.assertIn("PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT", CPP)
        self.assertIn("!player || !receiver || receiver != player", CPP)
        self.assertNotIn("PLAYERHOOK_ON_BEFORE_SEND_CHAT_MESSAGE", CPP)

if __name__ == "__main__":
    unittest.main()
