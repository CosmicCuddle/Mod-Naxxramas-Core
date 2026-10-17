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
    e.identity = PetIdentityProof::VerifiedDurableIncarnation;
    e.ipCompletion = IpCompletionProof::VerifiedPostReconciliation;
    e.scope = LifetimeScope::AcrossPetObjectOrRestart;
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

    // Every tempting IP timing proxy is insufficient.
    for (IpCompletionProof insufficient : {
        IpCompletionProof::Unknown, IpCompletionProof::NativeLoadingCleared,
        IpCompletionProof::ElapsedTimer, IpCompletionProof::LearnedSpellPacket})
    {
        e.ipCompletion = insufficient;
        assert(Evaluate(e) == Verdict::Skip);
    }
    e.ipCompletion = IpCompletionProof::VerifiedPostReconciliation;

    // Runtime Pet identity cannot survive dismissal/resummon/restart.
    e.identity = PetIdentityProof::RuntimePetObject;
    assert(Evaluate(e) == Verdict::Skip);
    e.scope = LifetimeScope::SameRuntimePetObject;
    assert(Evaluate(e) == Verdict::CandidateOnly);
    e.identity = PetIdentityProof::Unknown;
    assert(Evaluate(e) == Verdict::Skip);
    e.identity = PetIdentityProof::VerifiedDurableIncarnation;
    e.scope = LifetimeScope::AcrossPetObjectOrRestart;

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
