/*
 * Naxxramas Core — A02 human Hunter pet autocast restore policy.
 *
 * Dependency-free decision rules so tests can run without a worldserver.
 * HunterPetAutocast.cpp reads the live pet and calls these functions.
 * Design contract: docs/research/a02-hunter-autocast-functional-s1.md
 * Writer note: docs/research/a02-hunter-autocast-functional-s2.md
 *
 * The chain id is supplied by the caller. Production uses
 * SpellMgr::GetFirstSpellInChain and does not invent a link. This header
 * never learns a spell. DecideChains does not copy Cower 1742 onto
 * another spell. BuildAddonPlan applies an explicit choice when the pet
 * already has that spell.
 */

#ifndef NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_POLICY_H
#define NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_POLICY_H

#include <cstddef>
#include <cstdint>
#include <vector>

namespace NaxxramasHunterPetAutocast
{
    constexpr uint32_t COWER_SPELL_ID = 1742;
    constexpr uint8_t ACT_PASSIVE = 0x01;
    constexpr uint8_t ACT_DISABLED = 0x81;
    constexpr uint8_t ACT_ENABLED = 0xC1;

    enum class Outcome : uint8_t
    {
        OutOfScope,
        NoWrite,
        NoLearn,
        NoBar,
        RestoreEnabled,
        RestoreDisabled
    };

    enum class WriteGate : uint8_t
    {
        OutOfScope,
        NoWrite,
        Write
    };

    // ConfirmedHuman is a test seam for a classification this module can
    // already trust. The map-thread writer never produces it.
    enum class OwnerClass : uint8_t
    {
        ConfirmedHuman,
        ConfirmedNotHuman,
        Uncertain
    };

    struct ExpensiveWork
    {
        int DecideCalls = 0;
        int VectorConstructions = 0;
    };

    struct SpellView
    {
        uint32_t SpellId = 0;
        uint32_t ChainId = 0;
        uint8_t Active = 0;
        bool Autocastable = false;
        bool HasBar = false;
        uint8_t Bar = 0;
        bool InAutospells = false;
        bool BarDuplicated = false;
        bool Present = false;
    };

    struct ChainOutcome
    {
        uint32_t ChainId = 0;
        uint32_t BaselineSpellId = 0;
        uint32_t SuccessorSpellId = 0;
        Outcome Result = Outcome::NoWrite;
    };

    struct HumanGate
    {
        WriteGate Gate = WriteGate::OutOfScope;
        bool ConsultedRealPlayer = false;
    };

    struct ApplyStats
    {
        int ToggleCalls = 0;
        int BarCalls = 0;
        int LearnCalls = 0;
    };

    struct CommitResult
    {
        Outcome Claim = Outcome::NoWrite;
        SpellView State{};
        bool Agrees = false;
    };

    struct RestoreOptions
    {
        bool Enabled = true;
        bool PlayerbotsApiPresent = true;
        bool IsRealPlayer = true;
        bool OwnerPetMatches = true;
        bool HonorEnabledGuard = true;
        bool HonorHumanGuard = true;
        bool HonorCowerGuard = true;
        bool HonorSameChain = true;
        bool HonorConsistencyGuard = true;
        bool HonorPostWriteCheck = true;
        bool WriteBar = true;
        bool HonorUnchangedFastPath = true;
        OwnerClass Owner = OwnerClass::ConfirmedHuman;
        ExpensiveWork* Work = nullptr;
    };

    struct BaselineMemory
    {
        int Allocations = 0;
        bool Allocated = false;
        bool Pending = false;
        std::vector<SpellView> Book;
        std::vector<SpellView> Scratch;
        int BaselineCopies = 0;

        void GetDefault()
        {
            if (!Allocated)
            {
                Allocated = true;
                ++Allocations;
                Book.reserve(16);
                Scratch.reserve(16);
            }
        }

        // Models DataMap::Set, which is not used on the tick path.
        void SetReplace()
        {
            ++Allocations;
            Allocated = true;
            Book.clear();
            Scratch.clear();
            Book.reserve(16);
            Scratch.reserve(16);
        }
    };

    struct RestoreTickResult
    {
        std::vector<ChainOutcome> Outcomes;
        bool ConsultedRealPlayer = false;
        bool Wrote = false;
        bool SkippedUnchanged = false;
        int Packets = 0;
        ApplyStats Stats{};
        std::vector<SpellView> Book;
    };

    inline bool IsChoiceByte(uint8_t active)
    {
        return active == ACT_DISABLED || active == ACT_ENABLED;
    }

    inline bool VectorMatches(SpellView const& spell)
    {
        return spell.InAutospells == (spell.Active == ACT_ENABLED);
    }

    inline bool StoresAgree(SpellView const& spell, uint8_t wantActive)
    {
        return spell.Present && spell.Autocastable && spell.HasBar && !spell.BarDuplicated
            && spell.Active == wantActive && spell.Bar == wantActive
            && spell.InAutospells == (wantActive == ACT_ENABLED);
    }

    // Every field DecideChains reads. A same-id autocast toggle changes
    // Active, Bar, and InAutospells, so it must not compare equal.
    inline bool ViewFieldsEqual(SpellView const& left, SpellView const& right)
    {
        return left.SpellId == right.SpellId
            && left.ChainId == right.ChainId
            && left.Active == right.Active
            && left.Autocastable == right.Autocastable
            && left.HasBar == right.HasBar
            && left.Bar == right.Bar
            && left.InAutospells == right.InAutospells
            && left.BarDuplicated == right.BarDuplicated
            && left.Present == right.Present;
    }

    inline bool SameBook(std::vector<SpellView> const& baseline, std::vector<SpellView> const& current)
    {
        if (baseline.size() != current.size())
            return false;
        for (std::size_t index = 0; index < baseline.size(); ++index)
            if (!ViewFieldsEqual(baseline[index], current[index]))
                return false;
        return true;
    }

    inline bool HotFilterPasses(
        bool enabled,
        bool isPet,
        bool hunterPet,
        bool loading,
        bool ownerIsHunterInWorld)
    {
        if (!enabled)
            return false;
        if (!isPet || !hunterPet)
            return false;
        if (loading)
            return false;
        if (!ownerIsHunterInWorld)
            return false;
        return true;
    }

    inline char const* OutcomeName(Outcome outcome)
    {
        switch (outcome)
        {
            case Outcome::OutOfScope:
                return "OUT_OF_SCOPE";
            case Outcome::NoWrite:
                return "NO_WRITE";
            case Outcome::NoLearn:
                return "NO_LEARN";
            case Outcome::NoBar:
                return "NO_BAR";
            case Outcome::RestoreEnabled:
                return "RESTORE_ENABLED";
            case Outcome::RestoreDisabled:
                return "RESTORE_DISABLED";
        }
        return "UNKNOWN";
    }

    inline bool WantsWrite(std::vector<ChainOutcome> const& outcomes)
    {
        for (ChainOutcome const& outcome : outcomes)
        {
            if (outcome.Result == Outcome::RestoreEnabled || outcome.Result == Outcome::RestoreDisabled)
                return true;
        }
        return false;
    }

    // IsRealPlayer is consulted only when a restore is already proposed.
    // A missing Playerbots API is not a human. A pet that is not
    // owner->GetPet() is NoWrite after that consultation.
    inline HumanGate AuthorizeRestore(bool playerbotsApiPresent, bool isRealPlayer, bool ownerPetMatches)
    {
        HumanGate gate;
        if (!playerbotsApiPresent)
        {
            gate.Gate = WriteGate::OutOfScope;
            gate.ConsultedRealPlayer = false;
            return gate;
        }

        gate.ConsultedRealPlayer = true;
        if (!isRealPlayer)
        {
            gate.Gate = WriteGate::OutOfScope;
            return gate;
        }
        if (!ownerPetMatches)
        {
            gate.Gate = WriteGate::NoWrite;
            return gate;
        }
        gate.Gate = WriteGate::Write;
        return gate;
    }

    // No positive human classification is reachable from this module.
    // Full pin citations: docs/research/a02-hunter-autocast-functional-s2.md
    //
    // Pinned Playerbots d750b4b3a50effdf22bedc8032f0e8e5f7cb8091 has no
    // mutex on PlayerbotsMgr (PlayerbotMgr.h:111-137). The AI map is
    // :135. IsRealPlayer (PlayerbotAI.cpp:4523-4528) is
    // player && !GET_PLAYERBOT_AI. GET_PLAYERBOT_AI is Playerbots.h:31.
    // GetPlayerbotAI find()s that map at PlayerbotMgr.cpp:1868 with no
    // lock (:1858-1875). AddPlayerbotData erase/emplace is :1828-1834.
    // RemovePlayerBotData erase is :1842-1845. The AI destructor removes
    // at PlayerbotAI.cpp:247. IsSelfBot (PlayerbotAI.cpp:4531-4535) is
    // that same unlocked find, plus master == player.
    //
    // Map workers perform that find. Map::Update (Map.cpp:436) calls
    // player->Update at :489 on a MapUpdater worker when
    // MapUpdate.Threads > 0 (MapMgr.cpp:56-62; schedule and wait at
    // :273-280). Player::Update calls OnPlayerAfterUpdate
    // (PlayerUpdates.cpp:431). Playerbots.cpp:248-255 find()s and calls
    // UpdateAI (PlayerbotAI.cpp:250), which calls UpdateAIInternal at
    // :438. A queued logout command (PlayerbotAI.cpp:1138-1168) calls
    // LogoutPlayerBot (PlayerbotMgr.cpp:394), which calls LogoutPlayer
    // on that worker (:446-452). Destruction runs OnDestructPlayer
    // (Playerbots.cpp:397-402), which deletes the AI, and the destructor
    // erases the map. Another worker can be inside find() in the same
    // map phase. That is a source-reachable data race on the unlocked map.
    //
    // A world-thread find is not a proven escape. update_finished
    // (MapUpdater.cpp:161-169) uses memory_order_acquire and only the
    // last worker locks _lock. wait() (MapUpdater.cpp:124-131) therefore
    // does not happen-before a non-last worker's erase. The world-thread
    // queue mutex (PlayerbotWorldThreadProcessor.h:139) guards that queue
    // only. currentBots (RandomPlayerbotMgr.h:254) has no mutex and is
    // not a human test. No Playerbots classifier takes a lock.
    //
    // A non-headless session is not a positive human fact. _headless is
    // const !socket (WorldSession.cpp:148, WorldSession.h:1234, :1350).
    // Bots created later use a null socket (PlayerbotMgr.cpp:158-160)
    // and receive an AI from OnBotLogin (PlayerbotMgr.cpp:506-514),
    // queued by OnBotLoginOperation (PlayerbotOperations.h:493-512) and
    // run from WorldScript::OnUpdate (Playerbots.cpp:545-549,
    // World.cpp:1355). A human socket stays non-headless. SelfBot attaches
    // an AI to that socket: OnPlayerLogin adds a manager only
    // (Playerbots.cpp:148-150), SelfBotLevel > 2 calls
    // HandlePlayerbotCommand("self") directly (PlayerbotMgr.cpp:1733-1734),
    // and the self command inserts or deletes the AI
    // (PlayerbotMgr.cpp:1100-1122). OnTryExecuteCommand runs before the
    // invoker (ChatCommand.cpp:326, invoke at :333, reached from
    // Chat.cpp:238). It cannot see whether an AI was attached.
    // PlayerbotMgr.cpp:1733-1734 calls HandlePlayerbotCommand("self")
    // directly and never enters that hook.
    //
    // Publishing a per-player atomic before the next map schedule would
    // be visible on the worker. World::Update runs sessions
    // (World.cpp:1227) before MapMgr::Update (:1254), and
    // PCQueue::Push/WaitAndPop (PCQueue.h:39-46, :71-83) is that
    // happens-before. Player::CustomData is Object.h:237. DataMap is
    // itself an unlocked unordered_map (DataMap.h:73), so the node would
    // have to be inserted before publication and later stores would have
    // to be atomic. There is nothing safe to store. Playerbots does not
    // use CustomData. The pinned core has no bot bit on Player.
    // Taxi-cheater is not that bit (PlayerbotAI.cpp:148-149,
    // CharacterHandler.cpp:1055-1056). OnPlayerLogin
    // (CharacterHandler.cpp:1126) cannot freeze the answer: hook order
    // against Playerbots is not a contract, and SelfBot can attach at
    // login or later.
    //
    // This function stays Uncertain. It does not read the AI map.
    // ConfirmedHuman remains a test seam for RestoreTick only.
    // Production does not call this function. An addon opt-in is the
    // write gate. See docs/A02-ADDON-PROTOCOL.md.
    inline OwnerClass ClassifyOwnerOnMapThread()
    {
        return OwnerClass::Uncertain;
    }

    inline bool WriteAllowed(OwnerClass ownerClass)
    {
        return ownerClass == OwnerClass::ConfirmedHuman;
    }

    inline void CollectChain(
        std::vector<SpellView> const& spells,
        uint32_t chainId,
        std::vector<SpellView>& out)
    {
        out.clear();
        for (SpellView const& spell : spells)
            if (spell.ChainId == chainId)
                out.push_back(spell);
    }

    inline void CountVector(ExpensiveWork* work)
    {
        if (work)
            ++work->VectorConstructions;
    }

    inline std::vector<ChainOutcome> DecideChains(
        std::vector<SpellView> const& baseline,
        std::vector<SpellView> const& current,
        bool honorCowerGuard = true,
        bool honorSameChain = true,
        bool honorConsistencyGuard = true,
        ExpensiveWork* work = nullptr)
    {
        if (work)
            ++work->DecideCalls;

        std::vector<SpellView> adjusted = current;
        CountVector(work);
        if (!honorSameChain && !baseline.empty())
        {
            uint32_t const forced = baseline.front().ChainId;
            for (SpellView& spell : adjusted)
                spell.ChainId = forced;
        }

        std::vector<uint32_t> order;
        CountVector(work);
        for (SpellView const& spell : baseline)
        {
            bool seen = false;
            for (uint32_t chainId : order)
                if (chainId == spell.ChainId)
                    seen = true;
            if (!seen)
                order.push_back(spell.ChainId);
        }

        std::vector<ChainOutcome> outcomes;
        CountVector(work);
        if (order.empty())
        {
            ChainOutcome only;
            only.Result = Outcome::NoWrite;
            outcomes.push_back(only);
            return outcomes;
        }

        std::vector<SpellView> base;
        CountVector(work);
        std::vector<SpellView> live;
        CountVector(work);
        for (uint32_t chainId : order)
        {
            ChainOutcome outcome;
            outcome.ChainId = chainId;
            CollectChain(baseline, chainId, base);
            CollectChain(adjusted, chainId, live);

            if (base.size() != 1)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            SpellView const& chosen = base[0];
            outcome.BaselineSpellId = chosen.SpellId;
            bool const choice = IsChoiceByte(chosen.Active);
            bool const barMatches = chosen.HasBar && !chosen.BarDuplicated && chosen.Bar == chosen.Active;
            bool const vectorOk = !honorConsistencyGuard || VectorMatches(chosen);
            if (!choice || !barMatches || !vectorOk)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            bool stillThere = false;
            for (SpellView const& spell : live)
                if (spell.SpellId == chosen.SpellId)
                    stillThere = true;

            // Cower has no pinned successor. Do not copy its byte onto a
            // spell this chain map does not actually continue, and do not
            // learn 1742. The same id, still present, stays NoWrite below.
            if (honorCowerGuard && chosen.SpellId == COWER_SPELL_ID && !stillThere)
            {
                outcome.Result = Outcome::NoLearn;
                outcomes.push_back(outcome);
                continue;
            }

            if (live.empty())
            {
                outcome.Result = Outcome::NoLearn;
                outcomes.push_back(outcome);
                continue;
            }
            if (live.size() != 1)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            SpellView const& successor = live[0];
            outcome.SuccessorSpellId = successor.SpellId;
            if (successor.SpellId == chosen.SpellId || !successor.Autocastable)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }
            if (successor.SpellId == COWER_SPELL_ID)
            {
                outcome.Result = Outcome::NoLearn;
                outcomes.push_back(outcome);
                continue;
            }
            if (!successor.HasBar)
            {
                outcome.Result = Outcome::NoBar;
                outcomes.push_back(outcome);
                continue;
            }
            if (successor.BarDuplicated || successor.Bar != successor.Active)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }
            if (honorConsistencyGuard && !VectorMatches(successor))
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }
            if (successor.Active == chosen.Active && successor.Bar == chosen.Active)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            outcome.Result = chosen.Active == ACT_ENABLED
                ? Outcome::RestoreEnabled
                : Outcome::RestoreDisabled;
            outcomes.push_back(outcome);
        }
        return outcomes;
    }

    inline std::vector<ChainOutcome> DecideCall(
        bool enabled,
        bool human,
        std::vector<SpellView> const& baseline,
        std::vector<SpellView> const& current,
        bool honorEnabledGuard = true,
        bool honorHumanGuard = true,
        bool honorCowerGuard = true,
        bool honorSameChain = true,
        bool honorConsistencyGuard = true)
    {
        if ((honorEnabledGuard && !enabled) || (honorHumanGuard && !human))
        {
            ChainOutcome outcome;
            outcome.Result = Outcome::OutOfScope;
            return {outcome};
        }
        return DecideChains(baseline, current, honorCowerGuard, honorSameChain, honorConsistencyGuard);
    }

    // Pet.cpp:2247-2286. A vector mismatch is a no-op and does not repair active.
    inline void ModelToggle(SpellView& state, bool apply, ApplyStats& stats)
    {
        ++stats.ToggleCalls;
        if (!state.Present || !state.Autocastable)
            return;

        if (apply)
        {
            if (state.InAutospells)
                return;
            state.InAutospells = true;
            if (state.Active != ACT_ENABLED)
                state.Active = ACT_ENABLED;
            return;
        }

        if (!state.InAutospells)
            return;
        state.InAutospells = false;
        if (state.Active != ACT_DISABLED)
            state.Active = ACT_DISABLED;
    }

    // CharmInfo.cpp:291-300. A missing or duplicated slot is not rewritten here.
    inline void ModelSetBar(SpellView& state, bool enabled, ApplyStats& stats)
    {
        ++stats.BarCalls;
        if (!state.HasBar || state.BarDuplicated)
            return;
        state.Bar = enabled ? ACT_ENABLED : ACT_DISABLED;
    }

    inline CommitResult CommitRestore(
        SpellView successor,
        bool wantEnabled,
        bool honorConsistencyGuard,
        bool honorPostWriteCheck,
        bool writeBar,
        ApplyStats& stats)
    {
        CommitResult result;
        result.State = successor;
        if (successor.SpellId == COWER_SPELL_ID)
        {
            result.Claim = Outcome::NoLearn;
            return result;
        }

        uint8_t const want = wantEnabled ? ACT_ENABLED : ACT_DISABLED;
        if (!successor.Present || !successor.Autocastable || !IsChoiceByte(successor.Active))
        {
            result.Claim = Outcome::NoWrite;
            return result;
        }
        if (!successor.HasBar)
        {
            result.Claim = Outcome::NoBar;
            return result;
        }
        if (honorConsistencyGuard && (successor.Bar != successor.Active || successor.BarDuplicated || !VectorMatches(successor)))
        {
            result.Claim = Outcome::NoWrite;
            return result;
        }
        if ((successor.Active == ACT_ENABLED) == wantEnabled && StoresAgree(successor, want))
        {
            result.Claim = Outcome::NoWrite;
            result.Agrees = true;
            return result;
        }

        SpellView const before = successor;
        ModelToggle(successor, wantEnabled, stats);
        if (writeBar)
            ModelSetBar(successor, wantEnabled, stats);

        bool const agrees = StoresAgree(successor, want);
        if (honorPostWriteCheck && !agrees)
        {
            successor = before;
            result.State = successor;
            result.Claim = Outcome::NoWrite;
            result.Agrees = false;
            return result;
        }

        result.State = successor;
        result.Agrees = agrees;
        result.Claim = wantEnabled ? Outcome::RestoreEnabled : Outcome::RestoreDisabled;
        return result;
    }

    inline bool SnapshotTick(
        bool enabled,
        bool isPet,
        bool hunterPet,
        bool loading,
        bool ownerIsHunterInWorld,
        std::vector<SpellView> const& live,
        BaselineMemory& memory,
        bool honorEnabledGuard = true,
        bool useSet = false,
        bool honorFastPath = true)
    {
        bool const effectiveEnabled = honorEnabledGuard ? enabled : true;
        if (!HotFilterPasses(effectiveEnabled, isPet, hunterPet, loading, ownerIsHunterInWorld))
            return false;

        if (!useSet && honorFastPath && memory.Allocated && SameBook(memory.Book, live))
        {
            memory.Pending = true;
            return true;
        }

        if (useSet)
            memory.SetReplace();
        else
            memory.GetDefault();

        memory.Book.clear();
        memory.Book.insert(memory.Book.end(), live.begin(), live.end());
        ++memory.BaselineCopies;
        memory.Pending = true;
        return true;
    }

    inline RestoreTickResult RestoreTick(
        BaselineMemory& memory,
        std::vector<SpellView> const& live,
        RestoreOptions const& options)
    {
        RestoreTickResult result;
        result.Book = live;
        if (options.HonorEnabledGuard && !options.Enabled)
            return result;
        if (!memory.Pending)
            return result;

        memory.Pending = false;
        if (options.HonorUnchangedFastPath && SameBook(memory.Book, live))
        {
            result.SkippedUnchanged = true;
            return result;
        }

        result.Outcomes = DecideChains(
            memory.Book,
            live,
            options.HonorCowerGuard,
            options.HonorSameChain,
            options.HonorConsistencyGuard,
            options.Work);

        auto remember = [&]() {
            memory.Book.clear();
            memory.Book.insert(memory.Book.end(), result.Book.begin(), result.Book.end());
            ++memory.BaselineCopies;
        };

        if (!WantsWrite(result.Outcomes))
        {
            remember();
            return result;
        }

        // Uncertain and ConfirmedNotHuman do not read the Playerbots map.
        if (!WriteAllowed(options.Owner))
        {
            result.ConsultedRealPlayer = false;
            for (ChainOutcome& outcome : result.Outcomes)
            {
                if (outcome.Result == Outcome::RestoreEnabled || outcome.Result == Outcome::RestoreDisabled)
                    outcome.Result = Outcome::OutOfScope;
            }
            remember();
            return result;
        }

        bool const consultHuman = options.HonorHumanGuard;
        HumanGate gate = AuthorizeRestore(
            consultHuman ? options.PlayerbotsApiPresent : true,
            consultHuman ? options.IsRealPlayer : true,
            options.OwnerPetMatches);
        if (!consultHuman)
            gate.ConsultedRealPlayer = false;
        result.ConsultedRealPlayer = gate.ConsultedRealPlayer;
        if (gate.Gate != WriteGate::Write)
        {
            Outcome const replacement = gate.Gate == WriteGate::NoWrite
                ? Outcome::NoWrite
                : Outcome::OutOfScope;
            for (ChainOutcome& outcome : result.Outcomes)
            {
                if (outcome.Result == Outcome::RestoreEnabled || outcome.Result == Outcome::RestoreDisabled)
                    outcome.Result = replacement;
            }
            remember();
            return result;
        }

        for (ChainOutcome& outcome : result.Outcomes)
        {
            bool const wantEnabled = outcome.Result == Outcome::RestoreEnabled;
            if (!wantEnabled && outcome.Result != Outcome::RestoreDisabled)
                continue;
            if (options.HonorCowerGuard
                && (outcome.BaselineSpellId == COWER_SPELL_ID || outcome.SuccessorSpellId == COWER_SPELL_ID))
            {
                outcome.Result = Outcome::NoLearn;
                continue;
            }

            SpellView* slot = nullptr;
            for (SpellView& spell : result.Book)
                if (spell.SpellId == outcome.SuccessorSpellId)
                    slot = &spell;
            if (!slot)
            {
                outcome.Result = Outcome::NoWrite;
                continue;
            }

            CommitResult committed = CommitRestore(
                *slot,
                wantEnabled,
                options.HonorConsistencyGuard,
                options.HonorPostWriteCheck,
                options.WriteBar,
                result.Stats);
            *slot = committed.State;
            outcome.Result = committed.Claim;
            if (committed.Claim == Outcome::RestoreEnabled || committed.Claim == Outcome::RestoreDisabled)
                result.Wrote = true;
        }

        if (result.Wrote)
            result.Packets = 1;
        remember();
        return result;
    }
}

#endif
