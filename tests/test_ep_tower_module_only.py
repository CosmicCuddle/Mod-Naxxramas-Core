"""Source contract and synthetic state-model tests for the unreleased EP module.

These tests are NOT evidence of compiled linkage, gameplay or DB recovery.
Full pinned Worldserver compile and disposable staging validation are required.
"""
from dataclasses import dataclass
from pathlib import Path
import sqlite3
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
        # The production wrapper will not take a new capture until the
        # existing lock expires and Update() has reset it to neutral.
        if self.expiry:
            return False
        self.value, self.owner = value, owner
        # Mirror the module's faction AND signed endpoint requirements;
        # ownership alone, or the opposite sign, must never start a lock.
        full_for_faction = (
            (owner == "alliance" and value >= 1.0) or
            (owner == "horde" and value <= -1.0)
        )
        if full_for_faction:
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
        # Mirrors the production PackLock guard: only Alliance/Horde and
        # an expiry representable in the high 31 unsigned bits may persist.
        if not self.expiry or self.owner not in ("alliance", "horde"):
            return 0
        shifted = self.expiry - EPOCH
        if shifted <= 0 or shifted > ((1 << 31) - 1):
            return 0
        return (shifted << 1) | int(self.owner == "horde")

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

    def test_restored_flags_keep_faction_artkit_when_grids_load_late(self):
        # The pinned GameObject::SetGoArtKit(uint8, GameObject*,
        # LowType) updates in-memory spawn metadata even with go=nullptr.
        # Normal vanilla ChangeState only updates currently loaded GOs.
        self.assertIn('#include "GameObject.h"', CPP)
        state = CPP.split("void ChangeState() override", 1)[1].split(
            "void RestoreFromPersistentState()", 1)[0]
        self.assertIn("OriginalTower::ChangeState();", state)
        self.assertIn("GameObject::SetGoArtKit(", state)
        self.assertIn("this->m_capturePointSpawnId", state)
        for flag in ("EP_EWT_FLAGS", "EP_NPT_FLAGS",
                     "EP_PWT_FLAGS", "EP_CGT_FLAGS"):
            self.assertIn(flag, state)
        self.assertIn("this->_objects.find(FlagSlot)", state)
        self.assertIn("artkit = 21", state)
        self.assertIn("artkit = 2", state)
        self.assertIn("artkit = 1", state)
        self.assertIn("ChangeState();\n            _pendingInitialRefresh", CPP)
        self.assertIn("ChangeState();\n\n            if constexpr", CPP)

    def test_northpass_shrine_late_spawn_uses_stock_faction(self):
        # Stock NPT::SummonGO only updates currently instantiated shrine GOs;
        # a restart can restore the tower before its grid loads.
        fn = CPP.split("void CorrectLateNorthpassShrine(GameObject* go)", 1)[1].split(
            "void ChangeState() override", 1
        )[0]
        self.assertIn("std::is_same_v<OriginalTower, OPvPCapturePointEP_NPT>", fn)
        self.assertIn("this->_team != TEAM_ALLIANCE", fn)
        self.assertIn("this->_team != TEAM_HORDE", fn)
        self.assertIn("this->_objects.find(EP_NPT_BUFF)", fn)
        self.assertIn("shrine->second != go->GetSpawnId()", fn)
        self.assertIn("go->SetUInt32Value(GAMEOBJECT_FACTION,", fn)
        self.assertIn("this->_team == TEAM_ALLIANCE ? 84 : 83", fn)
        outer = CPP.split("class NaxxramasOutdoorPvPEP final", 1)[1]
        self.assertIn("void OnGameObjectCreate(GameObject* go) override", outer)
        self.assertLess(
            outer.index("OutdoorPvP::OnGameObjectCreate(go);"),
            outer.index("_northpassTower->CorrectLateNorthpassShrine(go);")
        )
        self.assertIn("_northpassTower = npt;", outer)
        self.assertIn("NorthpassTower* _northpassTower = nullptr;", outer)

    def test_pinned_northpass_spawn_callback_and_stock_faction(self):
        core = ROOT.parents[1]
        go_path = core / "src/server/game/Entities/GameObject/GameObject.cpp"
        ep_path = core / "src/server/scripts/OutdoorPvP/OutdoorPvPEP.cpp"
        obj_path = core / "src/server/game/Entities/Object/Object.cpp"
        if not (go_path.is_file() and ep_path.is_file() and
                obj_path.is_file()):
            self.skipTest("Pinned AzerothCore source not checked out beside module")
        go = go_path.read_text()
        ep = ep_path.read_text()
        obj = obj_path.read_text()
        # GameObject::Create binds its zone script, AddToWorld dispatches it,
        # and WorldObject routes EP's zone to its registered OutdoorPvP.
        self.assertIn("SetZoneScript();", go)
        self.assertIn(
            "m_zoneScript = sOutdoorPvPMgr->GetZoneScript(zoneId);", obj
        )
        self.assertIn("m_zoneScript->OnGameObjectCreate(this);", go)
        npt = ep.split("void OPvPCapturePointEP_NPT::SummonGO", 1)[1].split(
            "// CGT", 1
        )[0]
        self.assertIn("AddObject(EP_NPT_BUFF,", npt)
        self.assertIn("(teamId == TEAM_ALLIANCE ? 84 : 83)", npt)
        self.assertIn("GetGameObjectBySpawnIdStore()", npt)

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

    def test_sql_roundtrip_updates_only_stock_ep_in_disposable_db(self):
        # Execute the actual module SQL on an IN-MEMORY SQLite table. This
        # cannot touch MySQL, credentials or production DBs. This checks the
        # narrow, portable UPDATE/WHERE semantics, not MySQL deployment.
        with sqlite3.connect(":memory:") as db:
            db.execute(
                "CREATE TABLE outdoorpvp_template "
                "(TypeId INTEGER PRIMARY KEY, ScriptName TEXT NOT NULL)"
            )
            db.executemany(
                "INSERT INTO outdoorpvp_template VALUES (?, ?)",
                [(6, "outdoorpvp_ep"),
                 (7, "another_zone_handler"),
                 (8, "outdoorpvp_naxxramas_ep_lock")]
            )
            changed = db.execute(FORWARD).rowcount
            self.assertEqual(changed, 1)
            self.assertEqual(
                db.execute("SELECT ScriptName FROM outdoorpvp_template "
                           "WHERE TypeId=6").fetchone()[0],
                "outdoorpvp_naxxramas_ep_lock"
            )
            self.assertEqual(db.execute(FORWARD).rowcount, 0)
            self.assertEqual(db.execute(BACK).rowcount, 1)
            self.assertEqual(db.execute(BACK).rowcount, 0)
            self.assertEqual(
                db.execute("SELECT TypeId, ScriptName "
                           "FROM outdoorpvp_template ORDER BY TypeId"
                ).fetchall(),
                [(6, "outdoorpvp_ep"),
                 (7, "another_zone_handler"),
                 (8, "outdoorpvp_naxxramas_ep_lock")]
            )

    def test_sql_does_not_replace_unknown_ep_handler_in_disposable_db(self):
        # Existing third-party PvP handlers are a mandatory STOP condition.
        # Neither forward migration nor rollback may overwrite a custom EP
        # script (or a stock-named handler belonging to another TypeId).
        with sqlite3.connect(":memory:") as db:
            db.execute(
                "CREATE TABLE outdoorpvp_template "
                "(TypeId INTEGER PRIMARY KEY, ScriptName TEXT NOT NULL)"
            )
            db.executemany(
                "INSERT INTO outdoorpvp_template VALUES (?, ?)",
                [(6, "outdoorpvp_custom_owner"),
                 (7, "outdoorpvp_ep")]
            )
            self.assertEqual(db.execute(FORWARD).rowcount, 0)
            self.assertEqual(db.execute(BACK).rowcount, 0)
            self.assertEqual(
                db.execute("SELECT TypeId, ScriptName "
                           "FROM outdoorpvp_template ORDER BY TypeId"
                ).fetchall(),
                [(6, "outdoorpvp_custom_owner"), (7, "outdoorpvp_ep")]
            )

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


    def test_pinned_ep_ci_uses_feature_push_without_duplicate_pr_synchronizes(self):
        # GitHub PR path filters compare against the whole PR diff, not the
        # most recent commit. Push path filters catch feature-code changes;
        # limiting PR events prevents redundant full links for docs edits.
        for filename in (
            "ep-module-pinned-compile.yml",
            "ep-module-pinned-worldserver-link.yml",
        ):
            with self.subTest(workflow=filename):
                workflow = (ROOT / ".github/workflows" / filename).read_text()
                self.assertIn("types: [opened, reopened]", workflow)
                self.assertIn("  push:\n    branches: [feature/ep-tower-lock-module-only]", workflow)
                self.assertIn("    paths:\n", workflow)
                self.assertNotIn("synchronize]", workflow)
                self.assertIn("  workflow_dispatch:", workflow)

    def test_pinned_real_core_restart_order_and_graceful_db_drain(self):
        # This is source integration: GitHub Actions checks out the exact
        # pinned core beside modules/mod-naxxramas-core. A standalone module
        # checkout cannot prove these outside-core interfaces and skips.
        core = ROOT.parents[1]
        world_path = core / "src/server/game/World/World.cpp"
        pool_path = core / "src/server/database/Database/DatabaseWorkerPool.cpp"
        state_path = core / "src/server/game/World/WorldState.cpp"
        if not all(p.is_file() for p in (
            world_path, pool_path, state_path
        )):
            self.skipTest("Pinned AzerothCore source not checked out beside module")
        world = world_path.read_text()
        pool = pool_path.read_text()
        state = state_path.read_text()
        self.assertLess(
            world.index("sWorldState->LoadWorldStates();"),
            world.index("sOutdoorPvPMgr->InitOutdoorPvP();")
        )
        self.assertLess(
            world.index("sMapMgr->Initialize();"),
            world.index("sOutdoorPvPMgr->InitOutdoorPvP();")
        )
        self.assertIn("CharacterDatabase.Execute(stmt);", state)
        self.assertIn("!sToCloud9Sidecar->IsCrossrealm()", state)
        self.assertIn("_queue->Shutdown();", pool)
        self.assertIn("_connections[IDX_ASYNC].clear();", pool)
        # Queue drain applies to graceful shutdown only, NOT power loss.
        self.assertNotIn("CharacterDatabase.DirectExecute", CPP)

    def test_pinned_real_core_late_loaded_spawn_metadata_contract(self):
        core = ROOT.parents[1]
        go_path = core / "src/server/game/Entities/GameObject/GameObject.cpp"
        outdoor_path = core / "src/server/game/OutdoorPvP/OutdoorPvP.cpp"
        ep_path = core / "src/server/scripts/OutdoorPvP/OutdoorPvPEP.h"
        if not all(p.is_file() for p in (
            go_path, outdoor_path, ep_path
        )):
            self.skipTest("Pinned AzerothCore source not checked out beside module")
        go = go_path.read_text()
        outdoor = outdoor_path.read_text()
        ep = ep_path.read_text()
        self.assertIn(
            "void GameObject::SetGoArtKit(uint8 artkit, "
            "GameObject* go, ObjectGuid::LowType lowguid)", go
        )
        self.assertIn("sObjectMgr->GetGameObjectData(lowguid)", go)
        self.assertIn("const_cast<GameObjectData*>(data)->artKit = artkit;", go)
        self.assertIn("sMapMgr->CreateBaseMap(areaTable->mapid);", outdoor)
        expected_indices = (
            "EP_EWT = 0", "EP_NPT,", "EP_PWT,", "EP_CGT,"
        )
        offsets = [ep.index(v) for v in expected_indices]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("EP_EWT_FLAGS", ep)
        self.assertIn("EP_NPT_FLAGS", ep)
        self.assertIn("EP_PWT_FLAGS", ep)
        self.assertIn("EP_CGT_FLAGS", ep)

    def test_unsigned_32bit_last_valid_expiry_and_faction_bit(self):
        limit = (1 << 31) - 1
        for side, bit in (("alliance", 0), ("horde", 1)):
            with self.subTest(owner=side):
                end = EPOCH + limit
                tower = SimTower(side, 1.0 if bit == 0 else -1.0, end)
                packed = tower.pack()
                self.assertEqual(packed, (0xfffffffe | bit))
                self.assertLessEqual(packed, 0xffffffff)
                restored = SimTower.restore(packed, end - DURATION)
                self.assertEqual(restored.owner, side)
                self.assertEqual(restored.expiry, end)
                tower.expiry = end + 1
                self.assertEqual(tower.pack(), 0)

    def test_invalid_expiry_or_neutral_faction_never_persists(self):
        for invalid_expiry in (EPOCH - 1, EPOCH, EPOCH + (1 << 31)):
            with self.subTest(expiry=invalid_expiry):
                self.assertEqual(SimTower("alliance", 1.0,
                                          invalid_expiry).pack(), 0)
                self.assertEqual(SimTower("horde", -1.0,
                                          invalid_expiry).pack(), 0)
        self.assertEqual(SimTower("neutral", 0.0,
                                  EPOCH + DURATION).pack(), 0)
        self.assertEqual(SimTower("alliance", 1.0, 0).pack(), 0)
        # This is a source contract, not a binary/runtime data-write proof.
        self.assertIn("std::numeric_limits<uint32>::max() >> 1", CPP)
        self.assertIn("team != TEAM_ALLIANCE && team != TEAM_HORDE", CPP)
        self.assertIn("return packed != 0", CPP)

    def test_endpoint_sign_matches_capturing_faction(self):
        for side, partial, wrong, full in (
            ("alliance", 0.999, -1.0, 1.0),
            ("horde", -0.999, 1.0, -1.0),
        ):
            with self.subTest(side=side):
                tower = SimTower()
                self.assertFalse(tower.capture(side, partial, EPOCH + 100))
                self.assertEqual(tower.expiry, 0)
                self.assertFalse(tower.capture(side, wrong, EPOCH + 110))
                self.assertEqual(tower.expiry, 0)
                self.assertTrue(tower.capture(side, full, EPOCH + 120))
                self.assertEqual(tower.expiry, EPOCH + 120 + DURATION)

    def test_lock_is_not_restarted_on_same_tick_as_deadline(self):
        captured = EPOCH + 1000
        tower = SimTower()
        self.assertTrue(tower.capture("horde", -1.0, captured))
        original_expiry = tower.expiry
        # Production checks expiry before allowing a new capture update.
        self.assertFalse(tower.capture("alliance", 1.0, original_expiry))
        self.assertEqual(tower.expiry, original_expiry)
        self.assertTrue(tower.update(original_expiry))
        self.assertEqual(tower.owner, "neutral")
        self.assertEqual(tower.value, 0.0)
        self.assertTrue(tower.capture("alliance", 1.0, original_expiry + 1))
        self.assertEqual(tower.expiry, original_expiry + 1 + DURATION)

    def test_unreasonably_future_persisted_state_is_rejected(self):
        now = EPOCH + 2000
        for side in (0, 1):
            with self.subTest(faction_bit=side):
                impossible_expiry = now + DURATION + 1
                value = ((impossible_expiry - EPOCH) << 1) | side
                restored = SimTower.restore(value, now)
                self.assertEqual(restored.owner, "neutral")
                self.assertEqual(restored.value, 0.0)
                self.assertEqual(restored.expiry, 0)

    def test_reset_calls_vanilla_neutral_cleanup_with_no_new_announcements(self):
        reset = CPP.split("void ResetToNeutral()", 1)[1].split(
            "uint64 _expiresAt", 1)[0]
        self.assertIn("this->_value = 0.0f", reset)
        self.assertIn("this->_team = TEAM_NEUTRAL", reset)
        self.assertIn("this->_oldState = OBJECTIVESTATE_NEUTRAL", reset)
        self.assertLess(
            reset.index("SetControlledState("),
            reset.index("ChangeState();")
        )
        self.assertIn("this->SendChangePhase()", reset)
        self.assertNotIn("SendZoneText(", reset)
        self.assertNotIn("SendObjectiveComplete(", reset)

    def test_rollback_is_outside_auto_sql_update_tree(self):
        self.assertTrue((ROOT / "docs/rollback/"
            "2026_10_13_00_ep_tower_lock_module_unbind.sql").is_file())
        updater = ROOT / "data/sql/db-world"
        self.assertEqual(
            list(updater.rglob("*ep_tower_lock*unbind*.sql")), []
        )

if __name__ == "__main__":
    unittest.main()
