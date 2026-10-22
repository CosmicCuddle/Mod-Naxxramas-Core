"""Source gates for opt-in Hunter ammo provisioning in Bot Consumables.

Source/model tests do NOT establish that a Worldserver build compiles or that
inventory mutation behaves correctly in the owner's actual server.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROVISION = (ROOT / "src/Systems/HunterAmmoProvision.cpp").read_text()
POLICY = (ROOT / "src/Systems/HunterAmmoSelection.h").read_text()
COMMAND = (ROOT / "src/Systems/BotRaidConsumables.cpp").read_text()
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()


class HunterAmmoSafetyContract(unittest.TestCase):
    def test_opt_in_default_off_and_bounded_amount(self):
        self.assertIn("NaxxramasCore.BotConsumables.HunterAmmo.Enabled = 0", CONFIG)
        self.assertIn('"NaxxramasCore.BotConsumables.HunterAmmo.Enabled", false', PROVISION)
        self.assertIn("NaxxramasCore.BotConsumables.HunterAmmo.TargetCount = 600", CONFIG)
        self.assertIn('"NaxxramasCore.BotConsumables.HunterAmmo.TargetCount", 600', PROVISION)
        self.assertIn("configuredTarget > 1000", POLICY)
        self.assertIn("Shortfall(before, target)", PROVISION)

    def test_actual_weapon_and_current_selected_ammo(self):
        self.assertIn("GetWeaponForAttack(RANGED_ATTACK)", PROVISION)
        self.assertIn("PLAYER_AMMO_ID", PROVISION)
        self.assertIn("weapon->IsBroken()", PROVISION)
        self.assertIn("CheckAmmoCompatibility(ammo)", PROVISION)
        self.assertIn("CanUseAmmo(chosen.itemId)", PROVISION)
        self.assertIn("ITEM_CLASS_PROJECTILE", PROVISION)
        self.assertIn("ITEM_QUALITY_UNCOMMON", PROVISION)
        self.assertIn("ammo->RequiredLevel > level", PROVISION)
        self.assertIn("ammo->ItemLevel > 60", PROVISION)

    def test_command_only_and_altbot_only(self):
        self.assertIn("ai->IsAltBot()", PROVISION)
        self.assertIn("CLASS_HUNTER", PROVISION)
        self.assertIn("SupplyHunterAmmoForBot(bot, effectiveLevel, stats);", COMMAND)
        self.assertIn("SupplyHunterAmmoForBot(\n            bot,", COMMAND)
        self.assertIn("void PrepareHunter(", COMMAND)
        self.assertIn("bool PrepareDungeonBot(", COMMAND)
        self.assertNotIn("OnPlayerUpdate", PROVISION)
        self.assertNotIn("void OnUpdate", PROVISION)

    def test_no_unapproved_equip_or_quest_minting(self):
        for denied in ["SetAmmo(", "RemoveAmmo(", "EquipItem(", "bot->StoreNewItem(",
                       "CharacterDatabase.", "WorldDatabase.", "CastSpell(",
                       "AddActionExecutionListener(", "TeleportTo(", "LearnSpell("]:
            with self.subTest(denied=denied):
                self.assertNotIn(denied, PROVISION)
        self.assertIn("selectedAmmoId", POLICY)
        self.assertIn("UnsupportedSelectedAmmo", POLICY)
        self.assertIn("vendorFallback", POLICY)

    def test_non_vendor_selected_ammo_needs_second_opt_in(self):
        self.assertIn(
            "NaxxramasCore.BotConsumables.HunterAmmo.AllowSelectedNonVendor = 0",
            CONFIG,
        )
        self.assertIn(
            '"NaxxramasCore.BotConsumables.HunterAmmo.AllowSelectedNonVendor", false',
            PROVISION,
        )
        self.assertIn("allowSelectedNonVendor", POLICY)
        self.assertIn("!item.vendorFallback && !allowSelectedNonVendor", POLICY)
        self.assertIn("allowSelectedNonVendor);", PROVISION)
        self.assertIn("UnsupportedSelectedAmmo", POLICY)

    def test_bag_preflight_and_real_delta_accounting(self):
        self.assertIn("CanStoreNewItem(", PROVISION)
        self.assertIn("capacity != EQUIP_ERR_OK || noSpace || destination.empty()", PROVISION)
        self.assertIn("bot->AddItem(chosen.itemId, needed)", PROVISION)
        self.assertIn("GetItemCount(chosen.itemId, false)", PROVISION)
        self.assertIn("after - before", POLICY)
        self.assertIn("stats.HunterAmmoAdded += result.added", COMMAND)
        self.assertIn("stats.ItemsAdded += result.added", COMMAND)

    def test_quantity_is_pure_clamped_and_counts_only_real_additions(self):
        self.assertIn("constexpr uint32_t TargetCount(", POLICY)
        self.assertIn("constexpr uint32_t Shortfall(", POLICY)
        self.assertIn("constexpr uint32_t ObservedAdded(", POLICY)
        self.assertIn("TargetCount(", PROVISION)
        self.assertIn("ObservedAdded(before, after, needed)", PROVISION)
        self.assertIn("if (!needed)", PROVISION)
        self.assertIn("return current < target ? target - current : 0u;", POLICY)
        self.assertIn("delta < attempted ? delta : attempted", POLICY)

    def test_pet_missing_does_not_block_ammunition(self):
        start = COMMAND.index("void PrepareHunter(")
        end = COMMAND.index("Pet* pet = bot->GetPet();", start)
        self.assertIn("SupplyHunterAmmoForBot(", COMMAND[start:end])

    def test_catalog_is_classic_allowlist(self):
        for item in ["2512", "2515", "3030", "11285", "18042",
                     "2516", "2519", "3033", "11284", "15997"]:
            self.assertIn(item, POLICY)
        self.assertIn("ITEM_CLASS_PROJECTILE", PROVISION)
        self.assertIn("ItemLevel > 60", PROVISION)

    def test_hallows_end_solo_fire_config_preserved(self):
        """Ammo conf merge must keep current-main Hallow's End keys once each."""
        for key in (
            "NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0",
            "NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier = 3",
            "NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 0",
            "NaxxramasCore.HallowsEnd.SoloFire.DisableSpread = 0",
        ):
            with self.subTest(key=key):
                self.assertEqual(CONFIG.count(key), 1)

    def test_workflows_use_exact_head_and_do_not_upload_artifacts(self):
        pinned = (ROOT / ".github/workflows/hunter-ammo-pinned-worldserver.yml").read_text()
        source = (ROOT / ".github/workflows/hunter-ammo-source.yml").read_text()
        for text in (pinned, source):
            self.assertNotIn("upload-artifact", text)
            self.assertNotIn("actions/upload", text)
            self.assertIn("github.event.pull_request.head.sha", text)
        self.assertIn("8daffdabe9202c228e45d833c9a1d399597a15cd", pinned)
        self.assertNotIn("a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7", pinned)
        self.assertIn("cmake --build acore-build --target worldserver", pinned)


if __name__ == "__main__":
    unittest.main()
