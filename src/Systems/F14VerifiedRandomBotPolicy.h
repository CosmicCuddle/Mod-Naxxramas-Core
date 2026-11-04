#ifndef NAXXRAMAS_CORE_F14_VERIFIED_RANDOMBOT_POLICY_H
#define NAXXRAMAS_CORE_F14_VERIFIED_RANDOMBOT_POLICY_H

// F14: hide only verified, selected Blood Elf / Draenei Random Playerbots
// from ordinary Vanilla-stage observers. Everything else stays visible.
//
// This is the owner-selected rule (30 Oct, assigned in #143 6636550351).
// It replaces, for any future runtime use, both policies in
// PlayerIdentityPolicy.h:
//   - HideTbcRow policy A (hide every Blood Elf / Draenei row), and
//   - HideTbcRow policy B (hide all but positively-Human rows, which also
//     hides AltBots, SelfBots and Unknown players).
// A and B remain in PlayerIdentityPolicy.h only as historical research and
// test baselines. NEITHER IS APPROVED FOR RUNTIME ENABLEMENT.
//
// Pure standard C++. Not wired: nothing in the module includes this header,
// there is no hook, config key, /who or packet code, and F14 stays OFF.
// Observer era, the verified Random Playerbot identity and any /who or world
// callback belong to Individual Progression (IP drafts #62-#64). This model
// does not compute them; a caller would have to pass them in.
//
// Positive-only rule: every input that can lead to "hide" must be positively
// asserted, and every default (or unknown value) means "show". A missing,
// stale or contradictory fact can only ever make a row visible.

#include "PlayerIdentityPolicy.h"

#include <cstdint>

namespace NaxxramasF14VerifiedRandomBot
{
    using NaxxramasPlayerIdentity::Identity;

    enum class ObserverEra : std::uint8_t
    {
        Unknown = 0,  // not established: show everything
        Vanilla,      // positively known Vanilla-stage observer
        TbcOrLater,   // TBC or later: Blood Elf / Draenei are normal
    };

    struct Observer
    {
        ObserverEra era = ObserverEra::Unknown;
        // Positively known to be an ordinary player account (not a GM).
        // Default false, so an observer whose GM status is unknown sees all.
        bool confirmedNonGameMaster = false;
    };

    struct Row
    {
        std::uint8_t race = 0;
        // Positively known to be a different character from the observer.
        // Default false, so the observer's own row (or an unknown one) shows.
        bool confirmedNotObserver = false;
        // Classifier result for the row, e.g. IdentityBoard::Lookup. Only
        // Identity::RandomBot can hide; Unknown, Human, SelfBot and AltBot
        // never do.
        Identity identity = Identity::Unknown;
        // Separate, explicit proof that this character is a selected Random
        // Playerbot (for example IP's login-verified rndbot GUID record).
        // Headless / no-socket / config heuristics are NOT this proof: a
        // RandomBot classification without it stays visible.
        bool verifiedSelectedRandomBot = false;
    };

    constexpr bool IsTbcRace(std::uint8_t race)
    {
        return race == NaxxramasPlayerIdentity::RACE_BLOODELF ||
               race == NaxxramasPlayerIdentity::RACE_DRAENEI;
    }

    // True only when all six positive conditions hold. Any other input,
    // including any default-constructed field or out-of-range enum, shows
    // the row.
    constexpr bool HideFromVanillaObserver(Observer const& observer, Row const& row)
    {
        if (observer.era != ObserverEra::Vanilla)
            return false;
        if (!observer.confirmedNonGameMaster)
            return false;
        if (!row.confirmedNotObserver)
            return false;
        if (!IsTbcRace(row.race))
            return false;
        if (row.identity != Identity::RandomBot)
            return false;
        return row.verifiedSelectedRandomBot;
    }
}

#endif // NAXXRAMAS_CORE_F14_VERIFIED_RANDOMBOT_POLICY_H
