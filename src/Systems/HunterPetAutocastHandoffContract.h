/*
 * Hunter Pet Autocast IP handoff contract -- PURE TEST MODEL ONLY.
 *
 * This header is deliberately NOT included by a Worldserver source file.
 * No IP/core callback is installed or implemented here. The "trusted"
 * source below is HYPOTHETICAL: code that can set this enum is not thereby
 * trusted. Real provenance requires an authenticated upstream producer.
 */
#ifndef NAXXRAMAS_HUNTER_PET_AUTOCAST_HANDOFF_CONTRACT_H
#define NAXXRAMAS_HUNTER_PET_AUTOCAST_HANDOFF_CONTRACT_H

#include <cstdint>

namespace NaxxramasCore::HunterAutocastHandoff
{
    enum class Producer : std::uint8_t
    {
        Unknown,
        PetLoadFlag,
        TimerOrStableSnapshot,
        LearnedSpellPacket,
        HypotheticalTrustedIPAfterReturn
    };

    enum class Outcome : std::uint8_t
    {
        Unknown,
        Scheduled,
        RetryingWhileLoading,
        SkippedOrAborted,
        EligibleReconciliationReturned
    };

    enum class Decision : std::uint8_t
    {
        Skip,
        CandidateOnly
    };

    // All identifiers must be minted and authenticated by the same trusted
    // lifecycle. A raw PetNumber is NOT a Pet object incarnation token.
    struct InvocationStamp
    {
        std::uint64_t processEpoch = 0;
        std::uint64_t ownerGuid = 0;
        std::uint64_t ownerSessionEpoch = 0;
        std::uint64_t petInstance = 0;
        std::uint64_t petEventGeneration = 0;
    };

    [[nodiscard]] constexpr bool Matches(
        InvocationStamp const& a, InvocationStamp const& b) noexcept
    {
        return a.processEpoch && a.processEpoch == b.processEpoch &&
            a.ownerGuid && a.ownerGuid == b.ownerGuid &&
            a.ownerSessionEpoch &&
                a.ownerSessionEpoch == b.ownerSessionEpoch &&
            a.petInstance && a.petInstance == b.petInstance &&
            a.petEventGeneration &&
                a.petEventGeneration == b.petEventGeneration;
    }

    struct HandoffEvidence
    {
        InvocationStamp eventStamp;
        Producer producer = Producer::Unknown;
        Outcome outcome = Outcome::Unknown;
        bool originalEventWasEntered = false;
        bool callbackAfterReconcileReturn = false;
        bool actualIPEligibilityVerified = false;
    };

    struct CurrentState
    {
        InvocationStamp activeStamp;
        bool activePetStillSameObject = false;
        bool ownerSessionStillActive = false;
    };

    // Pure one-shot, fail-closed synthetic state machine. No pet pointers,
    // spell IDs, account data, packet events, SQL, or ToggleAutocast calls.
    class OneShotHandoff
    {
    public:
        constexpr explicit OneShotHandoff(InvocationStamp expected) noexcept
            : _expected(expected) { }

        constexpr void Invalidate() noexcept { _invalidated = true; }

        [[nodiscard]] constexpr Decision Check(
            HandoffEvidence const& signal, CurrentState const& now) noexcept
        {
            if (_invalidated || _consumed || !Matches(_expected, signal.eventStamp) ||
                !Matches(_expected, now.activeStamp) ||
                !now.activePetStillSameObject ||
                !now.ownerSessionStillActive ||
                signal.producer != Producer::HypotheticalTrustedIPAfterReturn ||
                signal.outcome != Outcome::EligibleReconciliationReturned ||
                !signal.originalEventWasEntered ||
                !signal.callbackAfterReconcileReturn ||
                !signal.actualIPEligibilityVerified)
                return Decision::Skip;

            _consumed = true;
            return Decision::CandidateOnly;
        }

    private:
        InvocationStamp _expected;
        bool _invalidated = false;
        bool _consumed = false;
    };
}

#endif
