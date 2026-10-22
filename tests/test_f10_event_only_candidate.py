"""Narrow F10 source-only pilot invariants; no SQL/DBC/server access."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EventPilotInvariant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conf = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
        cls.shade = (ROOT / "src/Events/HallowsEndShadeOfTheHorseman.cpp").read_text()
        cls.header = (ROOT / "src/Events/HallowsEndSoloFire.h").read_text()
        cls.cfg = (ROOT / "src/Events/HallowsEndSoloFireConfig.cpp").read_text()
        cls.sql = (ROOT / "data/sql/db-world/2026_09_21_00_event_script_overrides.sql").read_text()
        cls.loader = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()

    def test_both_switches_off_by_default(self):
        self.assertEqual(self.conf.count("NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0"), 1)
        self.assertEqual(self.conf.count("NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 0"), 1)
        self.assertEqual(self.conf.count("NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier = 3"), 1)
        self.assertEqual(self.conf.count("NaxxramasCore.HallowsEnd.SoloFire.DisableSpread = 0"), 1)

    def test_single_registration_from_existing_loader(self):
        self.assertEqual(self.loader.count("AddHallowsEndShadeOfTheHorsemanScripts();"), 2)
        self.assertEqual(self.shade.count("new spell_naxxramas_hallows_end_one_bucket();"), 1)
        self.assertIn("ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE", self.shade)
        self.assertEqual(self.shade.count("new spell_naxxramas_hallows_end_no_solo_spread();"), 1)
        self.assertIn("ALLSPELLHOOK_ON_SPELL_CHECK_CAST", self.shade)
        self.assertIn("ShouldStopSoloFireSpread", self.shade)

    def test_only_target_fire_aura_removed_by_feature(self):
        self.assertIn("target->RemoveAurasDueToSpell(FireAuraSpellId);", self.shade)
        self.assertIn("target->GetEntry() != FireTriggerEntry", self.shade)
        self.assertIn("BucketLandSpellId", self.shade)
        self.assertIn("BucketLandEffectIndex", self.shade)
        self.assertIn("CollectOneBucketOwnerCensus", self.shade)
        self.assertIn("FireAuraSpellId = 42074", self.header)
        self.assertIn("BucketLandSpellId = 42339", self.header)

    def test_config_readers_fail_closed(self):
        self.assertEqual(self.cfg.count("GetOption<std::string>"), 4)
        self.assertIn("ReadHallowsEndSoloFireEnabledSetting()", self.cfg)
        self.assertIn("ReadHallowsEndSoloFireOneBucketSetting()", self.cfg)
        self.assertIn("ReadHallowsEndSoloFireDisableSpreadSetting()", self.cfg)
        self.assertIn("ShouldBlockFireSpread", self.header)
        self.assertIn("SpreadFireSpellId = 42079", self.header)

    def test_mixed_legacy_sql_is_blocked_for_deployment(self):
        self.assertIn("WHERE `entry` = 23703", self.sql)
        self.assertIn("WHERE `entry` = 23543", self.sql)
        self.assertEqual(self.sql.count("UPDATE `creature_template`"), 2)
        self.assertIn("npc_naxxramas_hallows_end_soh", self.sql)


if __name__ == "__main__":
    unittest.main()
