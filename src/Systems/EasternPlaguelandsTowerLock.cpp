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
#include <type_traits>

namespace
{
    // The lock duration is intentionally fixed. No config switch, custom
    // countdown or extra capture/reset broadcast is requested by the owner.
    constexpr uint64 TowerLockSeconds = 90 * 60;

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
            if (_maxValue > 0.0f &&
                ((_state == OBJECTIVESTATE_ALLIANCE &&
                  _team == TEAM_ALLIANCE && _value >= _maxValue) ||
                 (_state == OBJECTIVESTATE_HORDE &&
                  _team == TEAM_HORDE && _value <= -_maxValue)))
            {
                uint32 packed = 0;
                uint64 const expiresAt = now + TowerLockSeconds;
                if (PackLock(_team, expiresAt, packed))
                {
                    _expiresAt = expiresAt;
                    sWorldState->setWorldState(TowerStateBase + Index, packed);
                }
                // An unrepresentable future timestamp must NOT start an
                // unpersisted lock which could silently restart at login.
            }

            return changed;
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
                _maxValue <= 0.0f)
            {
                // Expired, corrupted or impossible locks restart neutral.
                sWorldState->setWorldState(TowerStateBase + Index, 0);
                return;
            }

            TeamId const team = (packed & 1) ?
                TEAM_HORDE : TEAM_ALLIANCE;
            _expiresAt = expiresAt;
            _team = team;
            _value = team == TEAM_ALLIANCE ?
                _maxValue : -_maxValue;
            _state = team == TEAM_ALLIANCE ?
                OBJECTIVESTATE_ALLIANCE : OBJECTIVESTATE_HORDE;

            // Suppress vanilla re-capture / loss zone text on server restart.
            // These original scripts only broadcast capture text when the
            // state changed; no players are inside the objective at setup.
            _oldState = _state;
            OriginalTower::ChangeState();
            _pendingInitialRefresh = true;
        }

    private:
        void ResetToNeutral()
        {
            _expiresAt = 0;
            sWorldState->setWorldState(TowerStateBase + Index, 0);

            // Do not use the old faction as _oldState: vanilla ChangeState
            // would send a "lost tower" announcement. The requested reset
            // should not introduce new player-facing notifications.
            _state = OBJECTIVESTATE_NEUTRAL;
            _oldState = OBJECTIVESTATE_NEUTRAL;
            _team = TEAM_NEUTRAL;
            _value = 0.0f;

            // Original ChangeState's neutral case does not always call
            // SetControlledState. Do it explicitly for all four towers.
            static_cast<OutdoorPvPEP*>(_pvp)->SetControlledState(
                Index, TEAM_NEUTRAL);

            OriginalTower::ChangeState();

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
