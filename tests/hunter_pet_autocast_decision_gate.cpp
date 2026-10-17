/*
 * Pure, standalone C++20 test for HunterPetAutocastDecisionGate.h.
 * Synthetic evidence only. Does not create a Pet or run a Worldserver.
 */
#include "../src/Systems/HunterPetAutocastDecisionGate.h"

#include <cassert>
#include <cstdint>
#include <initializer_list>

using namespace NaxxramasCore::HunterAutocastDecision;

constexpr Evidence HypotheticalProvenCase()
{
    Evidence e;
    e.choice = ExplicitChoice::On;
    e.intent = HumanIntentProof::VerifiedExplicitHuman;
    e.nativeAcceptance = NativeAcceptanceProof::VerifiedNativeHandlerChange;
    e.identity = PetIdentityProof::VerifiedDurableIncarnation;
    e.ipCompletion = IpCompletionProof::VerifiedPostReconciliation;
    e.rankProvenance = RankEligibilityProvenance::VerifiedOwnerSpecificIPRules;
    e.scope = LifetimeScope::AcrossWorldserverRestart;
    e.ownerIsHunter = true;
    e.petIsHunterPet = true;
    e.isPlayerbot = false;
    e.sameOwner = true;
    e.stillKnowsSpell = true;
    e.spellAutocastable = true;
    e.legalUnderCurrentIP = true;
    e.exactlyOneKnownRankInFamily = true;
    return e;
}

static_assert(Evaluate(Evidence{}) == Verdict::Skip);
static_assert(Evaluate(HypotheticalProvenCase()) == Verdict::CandidateOnly);

int main()
{
    Evidence e = HypotheticalProvenCase();
    assert(Evaluate(e) == Verdict::CandidateOnly);

    // Explicit OFF is distinct from Unknown. Neither alone proves intent.
    e.choice = ExplicitChoice::Off;
    assert(Evaluate(e) == Verdict::CandidateOnly);
    e.choice = ExplicitChoice::Unknown;
    assert(Evaluate(e) == Verdict::Skip);
    e.choice = ExplicitChoice::On;

    // A packet observed before native acceptance is never an intent proof.
    e.intent = HumanIntentProof::PacketObserved;
    assert(Evaluate(e) == Verdict::Skip);
    e.intent = HumanIntentProof::Unknown;
    assert(Evaluate(e) == Verdict::Skip);
    e.intent = HumanIntentProof::VerifiedExplicitHuman;

    // Accepted native change proof is distinct from BOTH packet
    // observation and a later matching Pet::m_spells state.
    for (NativeAcceptanceProof insufficient : {
        NativeAcceptanceProof::Unknown,
        NativeAcceptanceProof::PreHandlerPacketObserved,
        NativeAcceptanceProof::PostUpdateMatchingState})
    {
        e.nativeAcceptance = insufficient;
        assert(Evaluate(e) == Verdict::Skip);
    }
    e.nativeAcceptance = NativeAcceptanceProof::VerifiedNativeHandlerChange;

    // Even a verified native change alone cannot prove HUMAN intent.
    e.intent = HumanIntentProof::Unknown;
    assert(Evaluate(e) == Verdict::Skip);
    e.intent = HumanIntentProof::VerifiedExplicitHuman;

    // Every tempting IP timing proxy is insufficient.
    for (IpCompletionProof insufficient : {
        IpCompletionProof::Unknown, IpCompletionProof::NativeLoadingCleared,
        IpCompletionProof::ElapsedTimer, IpCompletionProof::LearnedSpellPacket})
    {
        e.ipCompletion = insufficient;
        assert(Evaluate(e) == Verdict::Skip);
    }
    e.ipCompletion = IpCompletionProof::VerifiedPostReconciliation;

    // A character quest alone cannot prove the currently IP-legal rank.
    for (RankEligibilityProvenance insufficient : {
        RankEligibilityProvenance::Unknown,
        RankEligibilityProvenance::AccountProgressionOnly,
        RankEligibilityProvenance::CharacterQuestStageOnly})
    {
        e.rankProvenance = insufficient;
        assert(Evaluate(e) == Verdict::Skip);
    }
    e.rankProvenance = RankEligibilityProvenance::VerifiedOwnerSpecificIPRules;

    // Runtime Pet identity cannot survive dismissal/resummon/restart.
    e.identity = PetIdentityProof::RuntimePetObject;
    assert(Evaluate(e) == Verdict::Skip);
    e.scope = LifetimeScope::SameRuntimePetObject;
    assert(Evaluate(e) == Verdict::CandidateOnly);
    e.identity = PetIdentityProof::Unknown;
    assert(Evaluate(e) == Verdict::Skip);
    e.identity = PetIdentityProof::VerifiedDurableIncarnation;
    e.scope = LifetimeScope::AcrossWorldserverRestart;

    // Hypothetical process-local cache: ONLY valid across resummons when
    // acquired in memory this process and no allocator reset/wrap occurred.
    e.scope = LifetimeScope::SameProcessAfterResummon;
    e.identity = PetIdentityProof::ProcessLocalPetNumber;
    assert(Evaluate(e) == Verdict::Skip);
    e.volatileChoiceCapturedThisProcess = true;
    assert(Evaluate(e) == Verdict::Skip);
    e.petNumberContinuityVerified = true;
    assert(Evaluate(e) == Verdict::CandidateOnly);
    e.volatileChoiceCapturedThisProcess = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.volatileChoiceCapturedThisProcess = true;
    e.petNumberContinuityVerified = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.petNumberContinuityVerified = true;
    e.scope = LifetimeScope::AcrossWorldserverRestart;
    assert(Evaluate(e) == Verdict::Skip);

    // A runtime Pet object ID alone is invalid across separate summons.
    e.scope = LifetimeScope::SameProcessAfterResummon;
    e.identity = PetIdentityProof::RuntimePetObject;
    assert(Evaluate(e) == Verdict::Skip);
    e.scope = LifetimeScope::SameRuntimePetObject;
    assert(Evaluate(e) == Verdict::CandidateOnly);
    e.identity = PetIdentityProof::ProcessLocalPetNumber;
    assert(Evaluate(e) == Verdict::Skip);

    e.identity = PetIdentityProof::VerifiedDurableIncarnation;
    e.scope = LifetimeScope::AcrossWorldserverRestart;
    assert(Evaluate(e) == Verdict::CandidateOnly);

    e.isPlayerbot = true;
    assert(Evaluate(e) == Verdict::Skip);
    e.isPlayerbot = false;

    // Fail closed if even ONE ownership, known-rank or entitlement proof fails.
    e.ownerIsHunter = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.ownerIsHunter = true;
    e.petIsHunterPet = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.petIsHunterPet = true;
    e.sameOwner = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.sameOwner = true;
    e.stillKnowsSpell = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.stillKnowsSpell = true;
    e.spellAutocastable = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.spellAutocastable = true;
    e.legalUnderCurrentIP = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.legalUnderCurrentIP = true;
    e.exactlyOneKnownRankInFamily = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.exactlyOneKnownRankInFamily = true;
    assert(Evaluate(e) == Verdict::CandidateOnly);

    // No previous ability's ON/OFF choice influences another evaluation.
    Evidence bite = e;
    Evidence growl = e;
    bite.choice = ExplicitChoice::On;
    growl.choice = ExplicitChoice::Off;
    assert(Evaluate(bite) == Verdict::CandidateOnly);
    assert(Evaluate(growl) == Verdict::CandidateOnly);
}
