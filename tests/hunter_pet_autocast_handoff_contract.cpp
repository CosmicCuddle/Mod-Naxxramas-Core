/*
 * Synthetic trusted-IP-return handoff contract tests; standalone C++20.
 * The model never runs a real IP event or changes a Pet's autocast state.
 */
#include "../src/Systems/HunterPetAutocastHandoffContract.h"
#include <cassert>
#include <initializer_list>

using namespace NaxxramasCore::HunterAutocastHandoff;

constexpr InvocationStamp Original()
{
    return {0x1234, 77, 5, 9001, 1};
}
constexpr HandoffEvidence Valid()
{
    return {Original(), Producer::HypotheticalTrustedIPAfterReturn,
        Outcome::EligibleReconciliationReturned, true, true, true};
}
constexpr CurrentState Current()
{
    return {Original(), true, true};
}
constexpr bool HypotheticalHappyPath()
{
    OneShotHandoff gate(Original());
    return gate.Check(Valid(), Current()) == Decision::CandidateOnly &&
        gate.Check(Valid(), Current()) == Decision::Skip;
}
static_assert(HypotheticalHappyPath());

int main()
{
    auto expected = Original();
    auto proof = Valid();
    auto now = Current();

    for (Producer insufficient : {
        Producer::Unknown, Producer::PetLoadFlag,
        Producer::TimerOrStableSnapshot, Producer::LearnedSpellPacket})
    {
        proof.producer = insufficient;
        OneShotHandoff gate(expected);
        assert(gate.Check(proof, now) == Decision::Skip);
    }
    proof = Valid();

    for (Outcome outcome : {
        Outcome::Unknown, Outcome::Scheduled,
        Outcome::RetryingWhileLoading, Outcome::SkippedOrAborted})
    {
        proof.outcome = outcome;
        OneShotHandoff gate(expected);
        assert(gate.Check(proof, now) == Decision::Skip);
    }
    proof = Valid();

    proof.originalEventWasEntered = false;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    proof = Valid();
    proof.callbackAfterReconcileReturn = false;  // IP's private pending=false is before call
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    proof = Valid();
    proof.actualIPEligibilityVerified = false;   // IP may early-return
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    proof = Valid();

    // No stale queue item may certify an owner who has relogged.
    now.activeStamp.ownerSessionEpoch += 1;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    now = Current();

    // Pet replaced while delayed IP event was queued: reject both
    // the old event's token and a new pet's different live object.
    now.activeStamp.petInstance += 1;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    now = Current();
    proof.eventStamp.petInstance += 1;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    proof = Valid();

    // Old event generation, new process, and wrong owner must all skip.
    proof.eventStamp.petEventGeneration += 1;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    proof = Valid();
    now.activeStamp.processEpoch += 1;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    now = Current();
    proof.eventStamp.ownerGuid += 1;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    proof = Valid();

    now.activePetStillSameObject = false;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    now = Current();
    now.ownerSessionStillActive = false;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }
    now = Current();

    // Handoff may be used at most once per event; revocation is permanent.
    OneShotHandoff once(expected);
    assert(once.Check(proof, now) == Decision::CandidateOnly);
    assert(once.Check(proof, now) == Decision::Skip);

    OneShotHandoff revoked(expected);
    revoked.Invalidate();
    assert(revoked.Check(proof, now) == Decision::Skip);

    // Missing / synthetic zero token is not a valid incarnation proof.
    expected.petInstance = 0;
    { OneShotHandoff gate(expected);
      assert(gate.Check(proof, now) == Decision::Skip); }

    // CandidateOnly is a pure review verdict, not restoration permission.
}
