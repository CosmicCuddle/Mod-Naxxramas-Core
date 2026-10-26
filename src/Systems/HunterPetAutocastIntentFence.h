/*
 * A02 Part 26 -- isolated test-first intent fence for a future v2 receiver.
 *
 * THIS HEADER IS NOT WIRED INTO WORLD/PLAYER/PET HOOKS.  It cannot authenticate
 * anything by itself. Every trust bit MUST come from a separately reviewed,
 * real server/client integration rather than from a client-supplied field.
 *
 * It enforces one last invariant AFTER trusted transport/identity checks:
 * a current player's newest accepted manual ON/OFF cannot be replayed onto
 * another pet birth, outdated revision, unapproved rank or unknown owner.
 * A summon is NOT a pet birth: same authenticated birth may resummon, while
 * recycled PetNumber NEVER establishes same birth across replacement/relog.
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
        // BirthToken MUST be bound server-side to the same physical pet birth
        // across sessions. No v1 packet, name, family or PetNumber proves it.
        // A missing/unverified token rejects cross-summon restore.
        std::array<uint8_t, 16> BirthToken{};
        // Below are transient incarnation details; do NOT bind the enduring
        // human preference to these or resummon would always be rejected.
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
            && HasToken(identity.BirthToken) && HasToken(identity.ServerToken);
    }

    // Policy-A preference continuity. Server-authenticated durable birth is
    // an additional MANDATORY prerequisite in Decide; comparing bytes alone
    // does not establish authenticity of an alleged persistent token.
    inline bool SameBirth(Identity const& a, Identity const& b)
    {
        return ValidIdentity(a) && ValidIdentity(b)
            && a.PlayerGuid == b.PlayerGuid && a.PetNumber == b.PetNumber
            && a.BirthToken == b.BirthToken;
    }

    // Only same in-flight summon operation. Used for retry accounting, NEVER
    // as the key of an accepted choice across dismiss/resummon/relog.
    inline bool SameIncarnation(Identity const& a, Identity const& b)
    {
        return SameBirth(a, b) && a.ServerEpoch == b.ServerEpoch
            && a.SummonGeneration == b.SummonGeneration
            && a.ServerToken == b.ServerToken;
    }

    struct AcceptedManualChoice
    {
        Identity Pet;
        uint64_t Revision = 0;
        // Scope the revision to one positively-identified authoritative
        // counter domain. Reused revision 1 in another login is NOT newer.
        uint64_t RevisionDomain = 0;
        uint32_t SpellChain = 0;
        bool Enable = false;
        // Proven by receiver-side accepted manual-intent flow, NOT a client bit.
        bool TrustedManualReceipt = false;
        // A module cannot infer this from PetNumber/name alone. Must have a
        // separately verified immutable birth identity at receipt time.
        bool TrustedBirthAtReceipt = false;
    };

    struct CurrentObservation
    {
        Identity Pet;
        uint64_t LatestAcceptedRevision = 0;
        uint64_t LatestRevisionDomain = 0;
        // True only if a separately reviewed producer has authenticated the
        // CURRENT pet's birth binding (including relog/reuse). No producer yet.
        bool TrustedCurrentBirth = false;
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
        return SameIncarnation(budget.Pet, current.Pet)
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
            || !current.SelectedCurrentPet
            || !choice.TrustedBirthAtReceipt || !current.TrustedCurrentBirth)
            return Verdict::NoWrite;
        if (!SameBirth(choice.Pet, current.Pet)
            || choice.Revision == 0 || choice.RevisionDomain == 0
            || choice.RevisionDomain != current.LatestRevisionDomain
            || choice.Revision != current.LatestAcceptedRevision)
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
