/*
 * Naxxramas Core — Eastern Plaguelands independently locked towers.
 *
 * MODULE-ONLY implementation: this file does NOT replace or edit AzerothCore
 * source files. The supported DB-bound OutdoorPvP factory selects this script
 * with the reviewed world DB update to outdoorpvp_template (TypeId 6).
 *
 * Keep all four original AzerothCore EP objective classes and their rewards.
 * Only wrap their capture-progress Update and reset/restart behaviour.
 * Tested against pinned Playerbots-compatible AzerothCore source; runtime
 * acceptance and actual installed-fork compatibility remain separate gates.
 */

#include "GameTime.h"
#include "GameObject.h"
#include "Map.h"
#include "OutdoorPvPScript.h"
#include "WorldState.h"

#if __has_include("OutdoorPvPEP.h")
#include "OutdoorPvPEP.h"
#elif __has_include("../../../../src/server/scripts/OutdoorPvP/OutdoorPvPEP.h")
// A standard AzerothCore modules/mod-naxxramas-core/src/Systems tree can
// include the original script declaration without altering that source.
#include "../../../../src/server/scripts/OutdoorPvP/OutdoorPvPEP.h"
#else
#error "Naxxramas EP tower lock requires AzerothCore's original OutdoorPvPEP.h"
#endif

#include <limits>
#include <string>
#include <type_traits>

namespace
{
    // A full capture adds one zone announcement when its 90-minute lock
    // starts; no countdown, replay on restart, or neutral-reset broadcast.
    constexpr uint64 TowerLockSeconds = 90 * 60;

    // EP_Towers enum order in the original OutdoorPvPEP.h.
    char const* const TowerNames[EP_TOWER_NUM] =
    {
        "Eastwall Tower", "Northpass Tower",
        "Plaguewood Tower", "Crown Guard Tower"
    };

    // One atomic per-tower packed value in acore_characters.worldstates.
    // IMPORTANT: check these IDs are absent in the owner's DB before install.
    // No owner/expiry pair can be torn by an interrupted two-row update.
    constexpr uint32 TowerStateBase = 93420020;

    // Timestamp offset allows us to store the Unix expiry SECOND plus a
    // faction bit inside a 32-bit persisted WorldState value until ~2088.
    // Bit 0 = Horde (1) or Alliance (0); all remaining bits = seconds since
    // 2020-01-01 UTC. Packed zero is the neutral/unlocked sentinel.
    constexpr uint64 TowerEpochSeconds = 1577836800;

    uint64 CurrentUnixSeconds()
    {
        return uint64(GameTime::GetGameTime().count());
    }

    bool PackLock(TeamId team, uint64 expiresAt, uint32& packed)
    {
        if ((team != TEAM_ALLIANCE && team != TEAM_HORDE) ||
            expiresAt <= TowerEpochSeconds)
            return false;

        uint64 const shifted = expiresAt - TowerEpochSeconds;
        if (shifted > (std::numeric_limits<uint32>::max() >> 1))
            return false;

        packed = uint32((shifted << 1) |
            (team == TEAM_HORDE ? uint64(1) : uint64(0)));
        return packed != 0;
    }

    template <typename OriginalTower, uint8 Index>
    class NaxxramasLockedEPTower final : public OriginalTower
    {
    public:
        explicit NaxxramasLockedEPTower(OutdoorPvP* pvp)
            : OriginalTower(pvp)
        {
        }

        bool Update(uint32 diff) override
        {
            uint64 const now = CurrentUnixSeconds();

            if (_expiresAt)
            {
                // The base updater at diff=0 only refreshes player presence.
                // No opposing numbers can move the capture bar while locked.
                OPvPCapturePoint::Update(0);

                if (now >= _expiresAt)
                {
                    ResetToNeutral();
                    return true; // Refresh zone-wide tower count and buffs.
                }

                bool const changed = _pendingInitialRefresh;
                _pendingInitialRefresh = false;
                return changed;
            }

            bool const changed = OPvPCapturePoint::Update(diff);

            // Vanilla marks objective ALLIANCE/HORDE at the neutral edge:
            // that is NOT 100%. Require the clamped endpoint of the bar.
            if (this->_maxValue > 0.0f &&
                ((this->_state == OBJECTIVESTATE_ALLIANCE &&
                  this->_team == TEAM_ALLIANCE && this->_value >= this->_maxValue) ||
                 (this->_state == OBJECTIVESTATE_HORDE &&
                  this->_team == TEAM_HORDE && this->_value <= -this->_maxValue)))
            {
                uint32 packed = 0;
                uint64 const expiresAt = now + TowerLockSeconds;
                if (PackLock(this->_team, expiresAt, packed))
                {
                    _expiresAt = expiresAt;
                    sWorldState->setWorldState(TowerStateBase + Index, packed);

                    // Ordinary AzerothCore capture text is sent earlier, at
                    // the ownership threshold. Announce actual 100% capture
                    // only after this tower successfully starts its lock.
                    // The locked Update path and restore/reset paths never
                    // pass through here, so this fires once per full capture.
                    if (Map* map = this->_pvp->GetMap())
                    {
                        std::string message = "The ";
                        message += this->_team == TEAM_HORDE ? "Horde" : "Alliance";
                        message += " has secured ";
                        message += TowerNames[Index];
                        message += "!";
                        map->SendZoneText(EP_GraveyardZone, message.c_str());
                    }
                }
                // An unrepresentable future timestamp must NOT start an
                // unpersisted lock which could silently restart at login.
            }

            return changed;
        }

        void CorrectLateNorthpassShrine(GameObject* go)
        {
            if constexpr (std::is_same_v<OriginalTower, OPvPCapturePointEP_NPT>)
            {
                // Stock SummonGO assigns shrine faction only to a GO already
                // instantiated in the map. Restoring a lock on an unloaded
                // grid creates spawn data, not necessarily a live shrine.
                // Apply the SAME stock factions when that exact shrine loads.
                if (!go || (this->_team != TEAM_ALLIANCE &&
                            this->_team != TEAM_HORDE))
                    return;

                auto const shrine = this->_objects.find(EP_NPT_BUFF);
                if (shrine == this->_objects.end() ||
                    shrine->second != go->GetSpawnId())
                    return;

                go->SetUInt32Value(GAMEOBJECT_FACTION,
                    this->_team == TEAM_ALLIANCE ? 84 : 83);
            }
        }

        void ChangeState() override
        {
            // Let the original tower own all side effects, capture text,
            // buffs, shrine, NPCs, flight master and graveyard decisions.
            OriginalTower::ChangeState();

            // Vanilla's SetGoArtKit() in ChangeState only visits objects
            // currently loaded into the map. On startup the base map may
            // exist while the tower's grid has not loaded yet. Update the
            // in-memory spawn data too, so late-spawned capture points and
            // tower flags adopt the restored owner instead of looking neutral.
            uint8 artkit = 21; // Original neutral/challenge art kit.
            if (this->_state == OBJECTIVESTATE_ALLIANCE)
                artkit = 2;
            else if (this->_state == OBJECTIVESTATE_HORDE)
                artkit = 1;

            GameObject::SetGoArtKit(
                artkit, nullptr, this->m_capturePointSpawnId);

            constexpr uint32 FlagSlot =
                Index == EP_EWT ? EP_EWT_FLAGS :
                Index == EP_NPT ? EP_NPT_FLAGS :
                Index == EP_PWT ? EP_PWT_FLAGS : EP_CGT_FLAGS;

            auto const flag = this->_objects.find(FlagSlot);
            if (flag != this->_objects.end())
                GameObject::SetGoArtKit(artkit, nullptr, flag->second);
        }

        void RestoreFromPersistentState()
        {
            uint32 const packed = uint32(
                sWorldState->getWorldState(TowerStateBase + Index));
            if (!packed)
                return;

            uint64 const expiresAt =
                TowerEpochSeconds + uint64(packed >> 1);
            uint64 const now = CurrentUnixSeconds();

            if (expiresAt <= now || expiresAt > now + TowerLockSeconds ||
                this->_maxValue <= 0.0f)
            {
                // Expired, corrupted or impossible locks restart neutral.
                sWorldState->setWorldState(TowerStateBase + Index, 0);
                return;
            }

            TeamId const team = (packed & 1) ?
                TEAM_HORDE : TEAM_ALLIANCE;
            _expiresAt = expiresAt;
            this->_team = team;
            this->_value = team == TEAM_ALLIANCE ?
                this->_maxValue : -this->_maxValue;
            this->_state = team == TEAM_ALLIANCE ?
                OBJECTIVESTATE_ALLIANCE : OBJECTIVESTATE_HORDE;

            // Suppress vanilla re-capture / loss zone text on server restart.
            // These original scripts only broadcast capture text when the
            // state changed; no players are inside the objective at setup.
            this->_oldState = this->_state;
            ChangeState();
            _pendingInitialRefresh = true;
        }

    private:
        void ResetToNeutral()
        {
            _expiresAt = 0;
            sWorldState->setWorldState(TowerStateBase + Index, 0);

            // Do not use the old faction as this->_oldState: vanilla ChangeState
            // would send a "lost tower" announcement. The requested reset
            // should not introduce new player-facing notifications.
            this->_state = OBJECTIVESTATE_NEUTRAL;
            this->_oldState = OBJECTIVESTATE_NEUTRAL;
            this->_team = TEAM_NEUTRAL;
            this->_value = 0.0f;

            // Original ChangeState's neutral case does not always call
            // SetControlledState. Do it explicitly for all four towers.
            static_cast<OutdoorPvPEP*>(this->_pvp)->SetControlledState(
                Index, TEAM_NEUTRAL);

            ChangeState();

            if constexpr (std::is_same_v<OriginalTower, OPvPCapturePointEP_EWT>)
            {
                // The ordinary EWT neutral branch does not despawn support.
                for (uint8 i = 0; i < EP_EWT_NUM_CREATURES; ++i)
                    this->DelCreature(i);
                this->m_UnitsSummonedSideId = TEAM_NEUTRAL;
            }
            else if constexpr (std::is_same_v<
                OriginalTower, OPvPCapturePointEP_CGT>)
            {
                // The ordinary CGT neutral branch does not unlink graveyard.
                this->LinkGraveyard(TEAM_NEUTRAL);
            }
            // NPT shrine and PWT flight master use vanilla neutral cleanup.
            this->SendChangePhase();
        }

        uint64 _expiresAt = 0;
        bool _pendingInitialRefresh = false;
    };

    using EastwallTower = NaxxramasLockedEPTower<
        OPvPCapturePointEP_EWT, EP_EWT>;
    using NorthpassTower = NaxxramasLockedEPTower<
        OPvPCapturePointEP_NPT, EP_NPT>;
    using PlaguewoodTower = NaxxramasLockedEPTower<
        OPvPCapturePointEP_PWT, EP_PWT>;
    using CrownGuardTower = NaxxramasLockedEPTower<
        OPvPCapturePointEP_CGT, EP_CGT>;

    class NaxxramasOutdoorPvPEP final : public OutdoorPvPEP
    {
    public:
        void OnGameObjectCreate(GameObject* go) override
        {
            OutdoorPvP::OnGameObjectCreate(go);
            if (_northpassTower)
                _northpassTower->CorrectLateNorthpassShrine(go);
        }

        bool SetupOutdoorPvP() override
        {
            // Recreate the vanilla four-tower setup with subclasses rather
            // than registering a second OutdoorPvP manager or modifying core.
            for (uint8 i = 0; i < EPBuffZonesNum; ++i)
                RegisterZone(EPBuffZones[i]);
            SetMapFromZone(EPBuffZones[0]);

            auto* ewt = new EastwallTower(this);
            auto* npt = new NorthpassTower(this);
            auto* pwt = new PlaguewoodTower(this);
            auto* cgt = new CrownGuardTower(this);

            _northpassTower = npt;

            AddCapturePoint(ewt);
            AddCapturePoint(pwt);
            AddCapturePoint(cgt);
            AddCapturePoint(npt);

            // Independently recover each unexpired lock with its real
            // remaining time. Never reset 90 minutes on server restart.
            ewt->RestoreFromPersistentState();
            pwt->RestoreFromPersistentState();
            cgt->RestoreFromPersistentState();
            npt->RestoreFromPersistentState();

            // The vanilla zone implementation owns a PRIVATE count cache.
            // One harmless diff=0 pass registers the restored owners and
            // computes the faction buffs before accepting normal updates.
            OutdoorPvPEP::Update(0);
            return true;
        }

    private:
        NorthpassTower* _northpassTower = nullptr;
    };

    class NaxxramasEasternPlaguelandsPvPScript final
        : public OutdoorPvPScript
    {
    public:
        NaxxramasEasternPlaguelandsPvPScript()
            : OutdoorPvPScript("outdoorpvp_naxxramas_ep_lock")
        {
        }

        OutdoorPvP* GetOutdoorPvP() const override
        {
            return new NaxxramasOutdoorPvPEP();
        }
    };
}

// Registered once by the module loader. AzerothCore still compiles its stock
// outdoorpvp_ep, but outdoorpvp_template.TypeId=6 selects THIS unique name.
void AddNaxxramasEasternPlaguelandsTowerLockScripts()
{
    new NaxxramasEasternPlaguelandsPvPScript();
}
