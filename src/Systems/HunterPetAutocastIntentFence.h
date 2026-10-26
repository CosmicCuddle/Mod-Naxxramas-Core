/*
 * A02 Part 26 -- isolated test-first intent fence for a future v2 receiver.
 *
 * THIS HEADER IS NOT WIRED INTO WORLD/PLAYER/PET HOOKS.  It cannot authenticate
 * anything by itself. Every trust bit MUST come from a separately reviewed,
 * real server/client integration rather than from a client-supplied field.
 *
 * It enforces one last invariant AFTER trusted transport/identity checks:
 * a current player's newest accepted manual ON/OFF cannot be replayed onto
 * another pet, incarnation, old revision, unapproved rank or unknown owner.
 * No learn, spellbook mutation, global map, Playerbots or DB access occurs.
 */
#ifndef NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_INTENT_FENCE_H
#define NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_INTENT_FENCE_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace NaxxramasHunterPetAutocast
{
namespace IntentFence
{
    enum class OwnerMode : uint8_t
    {
        Unknown,
        Human,
        BotOrSelfBot
    };

    enum class Verdict : uint8_t
    {
        NoWrite,
        AlreadyCorrect,
        ApplyOn,
        ApplyOff
    };

    struct Identity
    {
        uint64_t PlayerGuid = 0;
        uint64_t ServerEpoch = 0;
        uint32_t PetNumber = 0;
        uint64_t SummonGeneration = 0;
        std::array<uint8_t, 16> ServerToken{};
    };

    inline bool HasToken(std::array<uint8_t, 16> const& token)
    {
        for (uint8_t const byte : token)
            if (byte != 0)
                return true;
        return false;
    }

    inline bool ValidIdentity(Identity const& identity)
    {
        return identity.PlayerGuid != 0 && identity.ServerEpoch != 0
            && identity.PetNumber != 0 && identity.SummonGeneration != 0
            && HasToken(identity.ServerToken);
    }

    inline bool SameIdentity(Identity const& a, Identity const& b)
    {
        return ValidIdentity(a) && ValidIdentity(b)
            && a.PlayerGuid == b.PlayerGuid && a.ServerEpoch == b.ServerEpoch
            && a.PetNumber == b.PetNumber
            && a.SummonGeneration == b.SummonGeneration
            && a.ServerToken == b.ServerToken;
    }

    struct AcceptedManualChoice
    {
        Identity Pet;
        uint64_t Revision = 0;
        uint32_t SpellChain = 0;
        bool Enable = false;
        // Proven by receiver-side accepted manual-intent flow, NOT a client bit.
        bool TrustedManualReceipt = false;
    };

    struct CurrentObservation
    {
        Identity Pet;
        uint64_t LatestAcceptedRevision = 0;
        uint32_t AllowedSpellChain = 0;
        uint32_t AllowedSpellId = 0;
        // Incremented for an actual relevant post-IP spellbook transition.
        uint64_t BookRevision = 0;
        OwnerMode Owner = OwnerMode::Unknown;
        bool ReceiverAuthenticated = false;
        bool AddonOptIn = false;
        bool HasVerifiedClientTransport = false;
        bool NoUnresolvedNewerManualClick = false;
        bool SelectedCurrentPet = false;
        bool RankAllowedByIP = false;
        bool SpellPresent = false;
        bool SpellAutocastable = false;
        bool SpellbookConsistent = false;
        bool EnabledNow = false;
    };

    // This key is stored in per-Pet map-worker state, not a global dictionary.
    // Two retries per *same actual spellbook transition*; no time-based guess.
    struct AttemptBudget
    {
        Identity Pet;
        uint64_t IntentRevision = 0;
        uint32_t Chain = 0;
        uint64_t BookRevision = 0;
        uint8_t Attempts = 0;
    };

    inline bool SameAttemptKey(AttemptBudget const& budget,
                               AcceptedManualChoice const& choice,
                               CurrentObservation const& current)
    {
        return SameIdentity(budget.Pet, current.Pet)
            && budget.IntentRevision == choice.Revision
            && budget.Chain == choice.SpellChain
            && budget.BookRevision == current.BookRevision;
    }

    inline uint8_t AttemptsUsed(AttemptBudget const& budget,
                                AcceptedManualChoice const& choice,
                                CurrentObservation const& current)
    {
        return SameAttemptKey(budget, choice, current) ? budget.Attempts : 0;
    }

    // Caller invokes this ONLY for a real attempted toggle, not for a no-op.
    // Failing to acknowledge a write cannot be treated as success.
    inline void RecordAttempt(AttemptBudget& budget,
                              AcceptedManualChoice const& choice,
                              CurrentObservation const& current)
    {
        if (!SameAttemptKey(budget, choice, current))
        {
            budget.Pet = current.Pet;
            budget.IntentRevision = choice.Revision;
            budget.Chain = choice.SpellChain;
            budget.BookRevision = current.BookRevision;
            budget.Attempts = 0;
        }
        if (budget.Attempts < 2)
            ++budget.Attempts;
    }

    inline Verdict Decide(AcceptedManualChoice const& choice,
                          CurrentObservation const& current,
                          AttemptBudget const& budget)
    {
        if (!current.ReceiverAuthenticated || !current.HasVerifiedClientTransport
            || !current.AddonOptIn || !choice.TrustedManualReceipt
            || current.Owner != OwnerMode::Human
            || !current.NoUnresolvedNewerManualClick
            || !current.SelectedCurrentPet)
            return Verdict::NoWrite;
        if (!SameIdentity(choice.Pet, current.Pet)
            || choice.Revision == 0 || choice.Revision != current.LatestAcceptedRevision)
            return Verdict::NoWrite;
        if (choice.SpellChain == 0 || current.AllowedSpellId == 0
            || choice.SpellChain != current.AllowedSpellChain
            || !current.RankAllowedByIP || !current.SpellPresent
            || !current.SpellAutocastable || !current.SpellbookConsistent
            || current.BookRevision == 0)
            return Verdict::NoWrite;
        if (choice.Enable == current.EnabledNow)
            return Verdict::AlreadyCorrect;
        if (AttemptsUsed(budget, choice, current) >= 2)
            return Verdict::NoWrite;
        return choice.Enable ? Verdict::ApplyOn : Verdict::ApplyOff;
    }
}
}
#endif
