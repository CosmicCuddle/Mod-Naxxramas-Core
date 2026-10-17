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
        ProcessLocalPetNumber,
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
        SameProcessAfterResummon,
        AcrossWorldserverRestart
    };

    enum class RankEligibilityProvenance : std::uint8_t
    {
        Unknown,
        AccountProgressionOnly,
        CharacterQuestStageOnly,
        VerifiedOwnerSpecificIPRules
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
        RankEligibilityProvenance rankProvenance =
            RankEligibilityProvenance::Unknown;
        LifetimeScope scope = LifetimeScope::AcrossWorldserverRestart;
        // Volatile observations have NO validity across Worldserver restarts.
        bool volatileChoiceCapturedThisProcess = false;
        bool petNumberContinuityVerified = false;
        bool ownerIsHunter = false;
        bool petIsHunterPet = false;
        bool isPlayerbot = false;
        bool sameOwner = false;
        bool stillKnowsSpell = false;
        bool spellAutocastable = false;
        bool legalUnderCurrentIP = false;
        bool exactlyOneKnownRankInFamily = false;
    };

    // The read-only audit cannot supply VerifiedExplicitHuman,
    // VerifiedDurableIncarnation or VerifiedPostReconciliation. Process-local
    // identity requires separate in-process capture AND counter continuity
    // evidence. Do not synthesize proof from packets, native flags or time.
    [[nodiscard]] constexpr Verdict Evaluate(Evidence const& evidence) noexcept
    {
        if (evidence.choice == ExplicitChoice::Unknown ||
            evidence.intent != HumanIntentProof::VerifiedExplicitHuman ||
            evidence.ipCompletion != IpCompletionProof::VerifiedPostReconciliation ||
            evidence.rankProvenance !=
                RankEligibilityProvenance::VerifiedOwnerSpecificIPRules ||
            !evidence.ownerIsHunter || !evidence.petIsHunterPet ||
            evidence.isPlayerbot || !evidence.sameOwner ||
            !evidence.stillKnowsSpell || !evidence.spellAutocastable ||
            !evidence.legalUnderCurrentIP || !evidence.exactlyOneKnownRankInFamily)
            return Verdict::Skip;

        // A volatile PetNumber cannot be trusted after a process restart.
        if (evidence.scope == LifetimeScope::AcrossWorldserverRestart)
            return evidence.identity == PetIdentityProof::VerifiedDurableIncarnation
                ? Verdict::CandidateOnly : Verdict::Skip;

        if (evidence.scope == LifetimeScope::SameProcessAfterResummon)
        {
            if (evidence.identity == PetIdentityProof::VerifiedDurableIncarnation)
                return Verdict::CandidateOnly;

            // Must be captured *after* process start in module-owned RAM.
            // A reseeded/wrapped allocator or restored cache is not safe.
            return evidence.identity == PetIdentityProof::ProcessLocalPetNumber &&
                evidence.volatileChoiceCapturedThisProcess &&
                evidence.petNumberContinuityVerified
                ? Verdict::CandidateOnly : Verdict::Skip;
        }

        // Only exact object identity works in a continuous live Pet object;
        // number-only proof cannot substitute for Pet object identity here.
        return evidence.identity == PetIdentityProof::RuntimePetObject ||
            evidence.identity == PetIdentityProof::VerifiedDurableIncarnation
            ? Verdict::CandidateOnly : Verdict::Skip;
    }
}

#endif
