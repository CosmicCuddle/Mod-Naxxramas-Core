/*
 * A02 Part27 — isolated lifetime-choice retry-limit MODEL, NOT MODULE CODE.
 * All "trusted" bits come from UNREAL synthetic fixtures; no production
 * receipt, human-mode check, persistent birth, database, Pet or Player source.
 * Before a real toggle, the caller must reserve on an owning serialized
 * context, using an unchanged PRE-toggle observation. Failed toggles count.
 *
 * This ledger is IN-MEMORY ONLY: restart loses counts. Without a durable
 * trusted birth and latest revision across restart, automatic writes stay OFF.
 */
#ifndef NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_LIFETIME_MODEL_H
#define NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_LIFETIME_MODEL_H

#include "HunterPetAutocastIntentFence.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace NaxxramasHunterPetAutocast
{
namespace LifetimeModel
{
    using namespace IntentFence;

    constexpr std::size_t kMaxLifetimeKeys = 32;
    constexpr uint8_t kMaxAttemptsPerVerifiedChoice = 20;

    struct Entry
    {
        Identity Birth;
        uint32_t Chain = 0;
        uint64_t RevisionDomain = 0;
        uint64_t Revision = 0;
        uint8_t Attempts = 0;
        bool Occupied = false;
    };

    struct Ledger
    {
        // Caller owns a single serialized ledger across temporary unsummons,
        // mounts, teleports and map transitions; never recreate per Pet*.
        std::array<Entry, kMaxLifetimeKeys> Entries{};
    };

    inline std::size_t FindBirthChain(Ledger const& ledger,
                                      AcceptedManualChoice const& choice)
    {
        for (std::size_t i = 0; i < ledger.Entries.size(); ++i)
        {
            Entry const& entry = ledger.Entries[i];
            if (entry.Occupied && entry.Chain == choice.SpellChain
                && SameBirth(entry.Birth, choice.Pet))
                return i;
        }
        return ledger.Entries.size();
    }

    inline std::size_t FindUnused(Ledger const& ledger)
    {
        for (std::size_t i = 0; i < ledger.Entries.size(); ++i)
            if (!ledger.Entries[i].Occupied)
                return i;
        return ledger.Entries.size();
    }

    inline Verdict DecideWithLifetime(AcceptedManualChoice const& choice,
                                       CurrentObservation const& current,
                                       AttemptLedger const& perIncarnation,
                                       Ledger const& lifetime)
    {
        Verdict const verdict = DecideTracked(choice, current, perIncarnation);
        if (verdict != Verdict::ApplyOn && verdict != Verdict::ApplyOff)
            return verdict; // includes NO-WRITE for all missing trust inputs

        std::size_t const index = FindBirthChain(lifetime, choice);
        if (index == lifetime.Entries.size())
            return FindUnused(lifetime) == lifetime.Entries.size()
                ? Verdict::NoWrite : verdict;

        Entry const& entry = lifetime.Entries[index];
        bool const sameAcceptedChoice =
            entry.RevisionDomain == choice.RevisionDomain
            && entry.Revision == choice.Revision;
        return sameAcceptedChoice && entry.Attempts >= kMaxAttemptsPerVerifiedChoice
            ? Verdict::NoWrite : verdict;
    }

    inline bool ReserveWithLifetime(AcceptedManualChoice const& choice,
                                     CurrentObservation const& current,
                                     AttemptLedger& perIncarnation,
                                     Ledger& lifetime)
    {
        Verdict const verdict = DecideWithLifetime(choice, current,
                                                   perIncarnation, lifetime);
        if (verdict != Verdict::ApplyOn && verdict != Verdict::ApplyOff)
            return false;

        std::size_t index = FindBirthChain(lifetime, choice);
        if (index == lifetime.Entries.size())
            index = FindUnused(lifetime);
        if (index == lifetime.Entries.size())
            return false; // full => no eviction or budget reset

        // Caller-owned, single-thread contract: no intervening modification
        // of either ledger or the choice/current snapshot between the check
        // and these two reservations.
        if (!RecordTrackedAttempt(perIncarnation, choice, current))
            return false;

        Entry& entry = lifetime.Entries[index];
        bool const sameAcceptedChoice = entry.Occupied
            && entry.RevisionDomain == choice.RevisionDomain
            && entry.Revision == choice.Revision
            && entry.Chain == choice.SpellChain
            && SameBirth(entry.Birth, choice.Pet);
        if (!sameAcceptedChoice)
        {
            entry = Entry{};
            entry.Birth = choice.Pet;
            entry.Chain = choice.SpellChain;
            entry.RevisionDomain = choice.RevisionDomain;
            entry.Revision = choice.Revision;
            entry.Occupied = true;
        }
        if (entry.Attempts >= kMaxAttemptsPerVerifiedChoice)
            return false; // unreachable with unchanged serialized snapshot
        ++entry.Attempts;
        return true;
    }
}
}
#endif
