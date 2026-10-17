/*
 * Naxxramas Core - Hunter pet autocast proof gate (HPA-G3).
 *
 * PURE, STANDALONE, NOT REGISTERED WITH WORLD SERVER. No pet operations,
 * player packets, SQL, spell mutation, or persistence are available here.
 * A successful result means a hypothetical candidate is eligible for
 * FURTHER REVIEW only. It is NOT permission to call ToggleAutocast.
 */
#ifndef NAXXRAMAS_HUNTER_PET_AUTOCAST_DECISION_GATE_H
#define NAXXRAMAS_HUNTER_PET_AUTOCAST_DECISION_GATE_H

#include <cstdint>

namespace NaxxramasCore::HunterAutocastDecision
{
    enum class ExplicitChoice : std::uint8_t
    {
        Unknown,
        On,
        Off
    };

    enum class HumanIntentProof : std::uint8_t
    {
        Unknown,
        PacketObserved,
        VerifiedExplicitHuman
    };

    enum class PetIdentityProof : std::uint8_t
    {
        Unknown,
        RuntimePetObject,
        VerifiedDurableIncarnation
    };

    enum class IpCompletionProof : std::uint8_t
    {
        Unknown,
        NativeLoadingCleared,
        ElapsedTimer,
        LearnedSpellPacket,
        VerifiedPostReconciliation
    };

    enum class LifetimeScope : std::uint8_t
    {
        SameRuntimePetObject,
        AcrossPetObjectOrRestart
    };

    enum class Verdict : std::uint8_t
    {
        Skip,
        CandidateOnly
    };

    struct Evidence
    {
        ExplicitChoice choice = ExplicitChoice::Unknown;
        HumanIntentProof intent = HumanIntentProof::Unknown;
        PetIdentityProof identity = PetIdentityProof::Unknown;
        IpCompletionProof ipCompletion = IpCompletionProof::Unknown;
        LifetimeScope scope = LifetimeScope::AcrossPetObjectOrRestart;
        bool ownerIsHunter = false;
        bool petIsHunterPet = false;
        bool isPlayerbot = false;
        bool sameOwner = false;
        bool stillKnowsSpell = false;
        bool spellAutocastable = false;
        bool legalUnderCurrentIP = false;
        bool exactlyOneKnownRankInFamily = false;
    };

    // The currently available read-only audit cannot supply VerifiedExplicitHuman,
    // VerifiedDurableIncarnation or VerifiedPostReconciliation. Do not synthesize
    // those proofs from packets, PetNumber, timeouts or current native flags.
    [[nodiscard]] constexpr Verdict Evaluate(Evidence const& evidence) noexcept
    {
        if (evidence.choice == ExplicitChoice::Unknown ||
            evidence.intent != HumanIntentProof::VerifiedExplicitHuman ||
            evidence.ipCompletion != IpCompletionProof::VerifiedPostReconciliation ||
            !evidence.ownerIsHunter || !evidence.petIsHunterPet ||
            evidence.isPlayerbot || !evidence.sameOwner ||
            !evidence.stillKnowsSpell || !evidence.spellAutocastable ||
            !evidence.legalUnderCurrentIP || !evidence.exactlyOneKnownRankInFamily)
            return Verdict::Skip;

        // A current object identity is useful within the *same* Pet lifetime,
        // but proves nothing about a different Pet object after resummon.
        if (evidence.scope == LifetimeScope::AcrossPetObjectOrRestart)
            return evidence.identity == PetIdentityProof::VerifiedDurableIncarnation
                ? Verdict::CandidateOnly : Verdict::Skip;

        if (evidence.identity == PetIdentityProof::Unknown)
            return Verdict::Skip;

        return Verdict::CandidateOnly;
    }
}

#endif
