"""Design and source-contract tests for the unreleased EP core patch.

All logic tests below are synthetic, NOT evidence of in-game behaviour.
The CI job separately checks 'git apply --check' on the exact pinned core.
Never deploy this patch without a backed-up, restored staging test.
"""
from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = (ROOT / "patches/azerothcore" /
    "0001-ep-full-capture-per-tower-90min-lock.patch").read_text(
        encoding="utf-8"
    )
SECONDS = 90 * 60


@dataclass
class Tower:
    owner: str = "neutral"
    slider: float = 0.0
    expires: int = 0

    def capture(self, side, slider, now):
        if self.expires and now < self.expires:
            return False
        self.owner = side
        self.slider = slider
        if abs(slider) == 1 and side in ("alliance", "horde"):
            self.expires = now + SECONDS
            return True
        return False

    def tick(self, now):
        if self.expires and now >= self.expires:
            self.expires = 0
            self.owner = "neutral"
            self.slider = 0.0
            return True
        return False

    def restore(self, side, expires, now):
        if side not in ("alliance", "horde") or not (
            now < expires <= now + SECONDS
        ):
            return Tower()
        return Tower(side, 1.0 if side == "alliance" else -1.0, expires)


class TowerLockSourceSafety(unittest.TestCase):
    def test_only_pinned_core_scripts_are_patched(self):
        self.assertEqual(PATCH.count("diff --git "), 2)
        self.assertIn(
            "a/src/server/scripts/OutdoorPvP/OutdoorPvPEP.cpp", PATCH
        )
        self.assertIn(
            "a/src/server/scripts/OutdoorPvP/OutdoorPvPEP.h", PATCH
        )
        self.assertNotIn("OutdoorPvPTF.cpp", PATCH)
        self.assertNotIn("BotTalentImport.cpp", PATCH)

    def test_capture_maximum_not_ordinary_faction_change(self):
        self.assertIn("_value >= _maxValue", PATCH)
        self.assertIn("_value <= -_maxValue", PATCH)
        self.assertIn("EP_TOWER_LOCK_SECONDS = 90 * 60", PATCH)
        self.assertIn("OPvPCapturePoint::Update(diff)", PATCH)
        self.assertNotIn("ChangeState()\n+{\n+    m_LockExpiresAt", PATCH)

    def test_each_tower_inherits_shared_lock_logic(self):
        for name in ("EWT", "NPT", "PWT", "CGT"):
            with self.subTest(tower=name):
                self.assertIn(
                    f"OPvPCapturePointEP_Lockable(pvp, EP_{name})", PATCH
                )
        self.assertIn("m_TowerIndex", PATCH)

    def test_capture_progress_frozen_but_players_still_tracked(self):
        self.assertIn("OPvPCapturePoint::Update(0)", PATCH)
        self.assertIn("now < m_LockExpiresAt", PATCH)
        self.assertIn("ResetToNeutral();", PATCH)

    def test_restart_expiry_uses_persisted_unix_time(self):
        self.assertIn("sWorldState->setWorldState(", PATCH)
        self.assertIn("sWorldState->getWorldState(", PATCH)
        self.assertIn("GameTime::GetGameTime().count()", PATCH)
        self.assertIn("void OPvPCapturePointEP_Lockable::RestoreTowerLock()", PATCH)
        self.assertIn("expiry <= now", PATCH)
        self.assertIn("expiry > now + EP_TOWER_LOCK_SECONDS", PATCH)

    def test_worldstate_owner_written_before_expiry_for_crash_safety(self):
        # Alliance's valid numeric TeamId is zero: writing expiry first
        # can make an interrupted Horde capture look like Alliance.
        block = PATCH.split(
            "void OPvPCapturePointEP_Lockable::SaveTowerLock(", 1
        )[1].split("void OPvPCapturePointEP_Lockable::ResetToNeutral()", 1)[0]
        self.assertLess(
            block.index("EP_TOWER_LOCK_OWNER_STATE_BASE + m_TowerIndex, uint32(team)"),
            block.index("EP_TOWER_LOCK_EXPIRY_STATE_BASE + m_TowerIndex, expiresAt"),
        )

    def test_neutral_reset_cleans_special_objectives(self):
        self.assertIn("m_UnitsSummonedSideId = TEAM_NEUTRAL", PATCH)
        self.assertIn("LinkGraveyard(TEAM_NEUTRAL)", PATCH)
        # NPT and PWT already contain neutral cleanup in pinned core;
        # the patch preserves their ChangeState branches unchanged.
        self.assertIn("ResetToNeutral();", PATCH)
        self.assertIn("ChangeState();", PATCH)
        self.assertIn("RefreshTowerCounts(true)", PATCH)

    def test_no_unrequested_new_ui_or_announcements(self):
        self.assertNotIn("TimerCommand", PATCH)
        self.assertNotIn("EP_LOCK_UI", PATCH)
        self.assertNotIn("ConfigMgr", PATCH)
        self.assertIn("IsSilentLockTransition", PATCH)
        self.assertIn("m_SilentLockTransition = true", PATCH)

    def test_preexisting_control_at_partial_progress_no_lock(self):
        t = Tower()
        self.assertFalse(t.capture("alliance", 0.7, 1000))
        self.assertEqual(t.expires, 0)
        self.assertTrue(t.capture("alliance", 1, 1020))
        self.assertEqual(t.expires, 6420)

    def test_each_tower_independent(self):
        towers = [Tower() for _ in range(4)]
        for i, t in enumerate(towers):
            self.assertTrue(t.capture("horde", -1, 1000 + 100 * i))
        self.assertTrue(towers[0].tick(6400))
        self.assertEqual(towers[1].owner, "horde")
        self.assertEqual(towers[2].owner, "horde")
        self.assertEqual(towers[3].owner, "horde")

    def test_90_minute_expiry_boundary(self):
        t = Tower()
        self.assertTrue(t.capture("alliance", 1, 500))
        self.assertFalse(t.tick(5899))
        self.assertEqual(t.owner, "alliance")
        self.assertTrue(t.tick(5900))
        self.assertEqual(t.owner, "neutral")
        self.assertEqual(t.slider, 0.0)

    def test_restart_at_ten_or_eighty_nine_minutes(self):
        t = Tower().restore("alliance", 6400, 1600)
        self.assertEqual(t.expires - 1600, 4800)
        t = Tower().restore("horde", 6400, 6340)
        self.assertEqual(t.expires - 6340, 60)

    def test_expired_during_downtime_returns_neutral(self):
        t = Tower().restore("horde", 6400, 6400)
        self.assertEqual(t.owner, "neutral")
        self.assertEqual(t.expires, 0)

    def test_corrupt_expiry_or_owner_cannot_be_restored(self):
        self.assertEqual(Tower().restore("unknown", 6400, 6000).owner, "neutral")
        self.assertEqual(Tower().restore("alliance", 999999, 6000).owner, "neutral")
        self.assertEqual(Tower().restore("horde", 0, 6000).owner, "neutral")

    def test_locked_attacker_cannot_overwrite_owner_or_timer(self):
        t = Tower()
        self.assertTrue(t.capture("alliance", 1, 1000))
        self.assertFalse(t.capture("horde", -1, 2000))
        self.assertEqual((t.owner, t.slider, t.expires),
            ("alliance", 1, 6400))


if __name__ == "__main__":
    unittest.main()
