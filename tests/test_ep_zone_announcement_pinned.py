"""Synthetic negative controls for the pinned EP zone announcement source contract.

No Worldserver, persistent DB, client chat, live zone or source mutator.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

FILE = Path(__file__).resolve().parents[1] / "scripts/check_ep_zone_announcement_pinned.py"
spec = importlib.util.spec_from_file_location("ep_zone_pinned", FILE)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


def fixtures():
    header = """const uint32 EP_GraveyardZone = AREA_EASTERN_PLAGUELANDS;
    enum EP_Towers {
      EP_EWT = 0, // Eastwall
      EP_NPT, EP_PWT, EP_CGT, EP_TOWER_NUM
    };"""
    map_header = """void SendZoneText(uint32 zoneId, char const* text,
      WorldSession const* self = nullptr, TeamId teamId = TEAM_NEUTRAL) const;"""
    map_src = """bool Map::SendZoneMessage(uint32 zone, WorldPacket const* packet, WorldSession const* self, TeamId teamId) const {
      if (player->IsInWorld() && player->GetZoneId() == zone &&
          (teamId == TEAM_NEUTRAL || player->GetTeamId() == teamId)) {
        player->SendDirectMessage(packet);
      }
    }
    void Map::SendZoneText(uint32 zoneId, char const* text, WorldSession const* self, TeamId teamId) const {
      SendZoneMessage(zoneId, &data, self, teamId);
    }
    void Map::SendZoneDynamicInfo(uint32 zoneId, Player* player) const {}"""
    module = """char const* const TowerNames[EP_TOWER_NUM] = {
      "Eastwall Tower", "Northpass Tower", "Plaguewood Tower", "Crown Guard Tower"
    };
    constexpr uint64 TowerLockSeconds = 90 * 60;
    using EastwallTower = NaxxramasLockedEPTower<OPvPCapturePointEP_EWT, EP_EWT>;
    using NorthpassTower = NaxxramasLockedEPTower<OPvPCapturePointEP_NPT, EP_NPT>;
    using PlaguewoodTower = NaxxramasLockedEPTower<OPvPCapturePointEP_PWT, EP_PWT>;
    using CrownGuardTower = NaxxramasLockedEPTower<OPvPCapturePointEP_CGT, EP_CGT>;
    bool Update(uint32 diff) override {
      if (_expiresAt) { OPvPCapturePoint::Update(0); return false; }
      bool const changed = OPvPCapturePoint::Update(diff);
      if (this->_maxValue > 0.0f &&
          this->_value >= this->_maxValue &&
          this->_value <= -this->_maxValue) {
          if (PackLock(this->_team, expiresAt, packed)) {
              sWorldState->setWorldState(TowerStateBase + Index, packed);
              message += TowerNames[Index];
              map->SendZoneText(EP_GraveyardZone, message.c_str());
          }
      }
    }
    void CorrectLateNorthpassShrine(GameObject* go) {}
    void RestoreFromPersistentState() {}
    void ResetToNeutral() {}
    uint64 _expiresAt = 0;"""
    return [header, map_header, map_src, module]


class EPZoneRouteContractTests(unittest.TestCase):
    def test_pinned_positive_source_shape(self):
        tool.check(*fixtures())

    def test_enum_reordering_is_not_a_safe_name_mapping(self):
        f = fixtures()
        f[0] = f[0].replace("EP_NPT, EP_PWT, EP_CGT", "EP_PWT, EP_NPT, EP_CGT")
        with self.assertRaisesRegex(ValueError, "enum order"):
            tool.check(*f)

    def test_incorrect_tower_name_or_wrapper_is_rejected(self):
        f = fixtures()
        f[3] = f[3].replace('"Northpass Tower"', '"Plaguewood Tower"')
        with self.assertRaisesRegex(ValueError, "display names"):
            tool.check(*f)
        f = fixtures()
        f[3] = f[3].replace("OPvPCapturePointEP_NPT, EP_NPT",
                             "OPvPCapturePointEP_NPT, EP_CGT")
        with self.assertRaisesRegex(ValueError, "wrapper tower index"):
            tool.check(*f)

    def test_zone_must_be_eastern_plaguelands(self):
        f = fixtures()
        f[0] = f[0].replace("AREA_EASTERN_PLAGUELANDS", "AREA_WESTERN_PLAGUELANDS")
        with self.assertRaisesRegex(ValueError, "zone constant"):
            tool.check(*f)
        f = fixtures()
        f[3] = f[3].replace("map->SendZoneText(EP_GraveyardZone",
                             "map->SendZoneText(EP_CGT_CM")
        with self.assertRaisesRegex(ValueError, "full capture persistence"):
            tool.check(*f)

    def test_native_zone_delivery_stays_both_factions(self):
        f = fixtures()
        f[1] = f[1].replace("teamId = TEAM_NEUTRAL", "teamId = TEAM_HORDE")
        with self.assertRaisesRegex(ValueError, "default team"):
            tool.check(*f)
        f = fixtures()
        f[2] = f[2].replace("teamId == TEAM_NEUTRAL || ", "")
        with self.assertRaisesRegex(ValueError, "zone delivery"):
            tool.check(*f)

    def test_announcement_only_after_successful_persistence_call(self):
        f = fixtures()
        f[3] = f[3].replace(
            "sWorldState->setWorldState(TowerStateBase + Index, packed);\n"
            "              message += TowerNames[Index];\n"
            "              map->SendZoneText(EP_GraveyardZone, message.c_str());",
            "map->SendZoneText(EP_GraveyardZone, message.c_str());\n"
            "              sWorldState->setWorldState(TowerStateBase + Index, packed);\n"
            "              message += TowerNames[Index];")
        with self.assertRaisesRegex(ValueError, "no longer after"):
            tool.check(*f)

    def test_message_must_remain_inside_successful_pack_and_endpoint(self):
        # A simple source-order test would incorrectly permit a broadcast
        # after the persistence call but OUTSIDE the guarded success scope.
        f = fixtures()
        f[3] = f[3].replace(
            "              map->SendZoneText(EP_GraveyardZone, message.c_str());\n"
            "          }",
            "          }\n"
            "          map->SendZoneText(EP_GraveyardZone, message.c_str());")
        with self.assertRaisesRegex(ValueError, "escaped the signed endpoint or PackLock"):
            tool.check(*f)

        f = fixtures()
        f[3] = f[3].replace(
            "              map->SendZoneText(EP_GraveyardZone, message.c_str());\n"
            "          }\n"
            "      }",
            "          }\n"
            "      }\n"
            "      map->SendZoneText(EP_GraveyardZone, message.c_str());")
        with self.assertRaisesRegex(ValueError, "escaped the signed endpoint or PackLock"):
            tool.check(*f)

    def test_no_additional_notifications_on_restore_or_reset(self):
        f = fixtures()
        f[3] = f[3].replace("void RestoreFromPersistentState() {}",
                             'void RestoreFromPersistentState() { SendZoneText(0, "replay"); }')
        with self.assertRaisesRegex(ValueError, "additional zone notifications"):
            tool.check(*f)

    def test_partial_endpoint_or_no_locked_tick_is_rejected(self):
        f = fixtures()
        f[3] = f[3].replace("this->_value <= -this->_maxValue", "this->_value <= 0")
        with self.assertRaisesRegex(ValueError, "signed 100 percent endpoint"):
            tool.check(*f)
        f = fixtures()
        f[3] = f[3].replace("OPvPCapturePoint::Update(0);", "OPvPCapturePoint::Update(diff);")
        with self.assertRaisesRegex(ValueError, "no-progress locked tick"):
            tool.check(*f)


if __name__ == "__main__":
    unittest.main()
