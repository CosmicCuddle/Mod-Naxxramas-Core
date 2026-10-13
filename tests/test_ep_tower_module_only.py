"""Source contract and synthetic state-model tests for the unreleased EP module.

These tests are NOT evidence of compiled linkage, gameplay or DB recovery.
Full pinned Worldserver compile and disposable staging validation are required.
"""
from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/EasternPlaguelandsTowerLock.cpp").read_text()
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()
FORWARD = (ROOT / "data/sql/db-world/"
    "2026_10_13_00_ep_tower_lock_module_bind.sql").read_text()
BACK = (ROOT / "docs/rollback/"
    "2026_10_13_00_ep_tower_lock_module_unbind.sql").read_text()
SECOND = 1
DURATION = 5400
EPOCH = 1577836800


@dataclass
class SimTower:
    owner: str = "neutral"
    value: float = 0.0
    expiry: int = 0

    def capture(self, owner, value, now):
        if self.expiry and now < self.expiry:
            return False
        self.value, self.owner = value, owner
        if abs(value) == 1.0 and owner in ("alliance", "horde"):
            self.expiry = now + DURATION
            return True
        return False

    def update(self, now):
        if self.expiry and now >= self.expiry:
            self.value = 0
            self.owner = "neutral"
            self.expiry = 0
            return True
        return False

    def pack(self):
        if not self.expiry:
            return 0
        return ((self.expiry - EPOCH) << 1) | int(self.owner == "horde")

    @staticmethod
    def restore(packed, now):
        if not packed:
            return SimTower()
        expiry = EPOCH + (packed >> 1)
        if expiry <= now or expiry > now + DURATION:
            return SimTower()
        owner = "horde" if packed & 1 else "alliance"
        return SimTower(owner, -1.0 if owner == "horde" else 1.0, expiry)


class ModuleOnlySourceContract(unittest.TestCase):
    def test_original_script_is_not_overwritten_or_duplicated(self):
        self.assertIn('#include "OutdoorPvPEP.h"', CPP)
        self.assertIn("NaxxramasOutdoorPvPEP final : public OutdoorPvPEP", CPP)
        self.assertIn("class NaxxramasEasternPlaguelandsPvPScript", CPP)
        self.assertIn('OutdoorPvPScript("outdoorpvp_naxxramas_ep_lock")', CPP)
        self.assertNotIn('OutdoorPvPScript("outdoorpvp_ep")', CPP)
        self.assertIn("new NaxxramasOutdoorPvPEP()", CPP)
        self.assertNotIn("AddSC_outdoorpvp_ep", CPP)

    def test_loader_registers_unique_handler_once(self):
        self.assertEqual(
            LOADER.count("AddNaxxramasEasternPlaguelandsTowerLockScripts();"),
            2
        )

    def test_original_special_towers_and_buffs_remain_in_use(self):
        for name in ("EWT", "NPT", "PWT", "CGT"):
            with self.subTest(tower=name):
                self.assertIn(f"OPvPCapturePointEP_{name}", CPP)
                self.assertIn(f"EP_{name}>", CPP)
        self.assertIn("OutdoorPvPEP::Update(0)", CPP)
        self.assertIn("OriginalTower::ChangeState()", CPP)
        self.assertIn("LinkGraveyard(TEAM_NEUTRAL)", CPP)
        self.assertIn("m_UnitsSummonedSideId = TEAM_NEUTRAL", CPP)
        self.assertIn("SetControlledState(", CPP)
        self.assertIn("this->SendChangePhase()", CPP)

    def test_full_capture_only(self):
        self.assertIn("this->_value >= this->_maxValue", CPP)
        self.assertIn("this->_value <= -this->_maxValue", CPP)
        self.assertIn("_maxValue > 0.0f", CPP)
        self.assertIn("TowerLockSeconds = 90 * 60", CPP)
        self.assertIn("OPvPCapturePoint::Update(diff)", CPP)
        self.assertIn("OPvPCapturePoint::Update(0)", CPP)

    def test_atomic_single_row_restart_contract(self):
        self.assertIn("TowerStateBase = 93420020", CPP)
        self.assertIn("TowerEpochSeconds = 1577836800", CPP)
        self.assertIn("sWorldState->setWorldState(TowerStateBase + Index, packed)", CPP)
        self.assertIn("sWorldState->getWorldState(TowerStateBase + Index)", CPP)
        self.assertIn("expiresAt <= now || expiresAt > now + TowerLockSeconds", CPP)
        self.assertIn("CurrentUnixSeconds()", CPP)

    def test_no_extra_ui_messages_timer_or_config(self):
        self.assertNotIn("SendZoneText(", CPP)
        self.assertNotIn("sConfigMgr", CPP)
        self.assertNotIn("ChatHandler", CPP)
        self.assertNotIn("GameObjectScript", CPP)

    def test_sql_is_reversible_and_narrow(self):
        self.assertIn("WHERE `TypeId` = 6", FORWARD)
        self.assertIn("AND `ScriptName` = 'outdoorpvp_ep'", FORWARD)
        self.assertIn("= 'outdoorpvp_naxxramas_ep_lock'", FORWARD)
        self.assertIn("WHERE `TypeId` = 6", BACK)
        self.assertIn("AND `ScriptName` = 'outdoorpvp_naxxramas_ep_lock'", BACK)
        self.assertIn("= 'outdoorpvp_ep'", BACK)
        self.assertNotIn("DELETE", FORWARD)
        self.assertNotIn("DELETE", BACK)
        self.assertNotIn("INSERT", FORWARD)
        self.assertNotIn("INSERT", BACK)

    def test_partial_capture_does_not_lock(self):
        t = SimTower()
        self.assertFalse(t.capture("alliance", 0.7, EPOCH + 120))
        self.assertEqual(t.expiry, 0)
        self.assertTrue(t.capture("alliance", 1.0, EPOCH + 140))
        self.assertEqual(t.expiry, EPOCH + 140 + DURATION)

    def test_horde_or_alliance_packed_in_one_value(self):
        for side in ("alliance", "horde"):
            t = SimTower()
            t.capture(side, 1 if side == "alliance" else -1, EPOCH + 200)
            restored = SimTower.restore(t.pack(), EPOCH + 300)
            self.assertEqual(restored.owner, side)
            self.assertEqual(restored.expiry, t.expiry)

    def test_staggered_towers_expire_independently(self):
        towers = [SimTower() for _ in range(4)]
        for index, tower in enumerate(towers):
            tower.capture("horde", -1, EPOCH + 60 * (index + 1))
        self.assertTrue(towers[0].update(EPOCH + DURATION + 60))
        self.assertEqual([t.owner for t in towers],
            ["neutral", "horde", "horde", "horde"])

    def test_restart_expiry_does_not_restart_clock(self):
        start = EPOCH + 1000
        t = SimTower()
        t.capture("alliance", 1, start)
        packed = t.pack()
        after10 = SimTower.restore(packed, start + 10 * 60)
        after89 = SimTower.restore(packed, start + 89 * 60)
        after91 = SimTower.restore(packed, start + 91 * 60)
        self.assertEqual(after10.expiry - (start + 10*60), 80 * 60)
        self.assertEqual(after89.expiry - (start + 89*60), 60)
        self.assertEqual(after91.owner, "neutral")

    def test_busy_locked_tower_cannot_be_recaptured(self):
        t = SimTower()
        now = EPOCH + 1000
        self.assertTrue(t.capture("alliance", 1, now))
        self.assertFalse(t.capture("horde", -1, now + 400))
        self.assertEqual(t.owner, "alliance")
        self.assertEqual(t.expiry, now + DURATION)
        self.assertTrue(t.update(now + DURATION))
        self.assertEqual(t.owner, "neutral")


if __name__ == "__main__":
    unittest.main()
