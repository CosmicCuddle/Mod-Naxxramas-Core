/*
 * C++20 executable of the completely unregistered, read-only review model.
 * Hypothetical proof values are constructed only inside this test.
 */
#include "../src/Systems/HunterPetAutocastBotPrecedence.h"
#include <cassert>
using namespace NaxxramasCore::HunterAutocastBotPrecedence;

constexpr Evidence Baseline()
{
    Evidence e;
    e.hunterBotVerified = true;
    e.correctActivePet = true;
    e.legalKnownRankUnderIP = true;
    e.nativeAutocastable = true;
    e.postIPReconciliationVerified = true;
    e.botDefaultPolicyKnown = true;
    e.botDefaultOn = true;
    e.observedNativeOn = false;
    return e;
}
static_assert(Evaluate(Evidence{}) == Verdict::Skip);
static_assert(Evaluate(Baseline()) == Verdict::ObserveBotPolicyMismatch);
int main()
{
    Evidence e = Baseline();
    assert(Evaluate(e) == Verdict::ObserveBotPolicyMismatch);
    e.observedNativeOn = true;
    assert(Evaluate(e) == Verdict::ObserveBotPolicyMatch);

    e.command = CommandSource::PreHandlerPacket;
    assert(Evaluate(e) == Verdict::Skip);
    e.command = CommandSource::HypotheticalVerifiedMasterCommand;
    e.requestedOn = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.masterActorAuthenticated = true;
    assert(Evaluate(e) == Verdict::Skip);
    e.commandAppliedToExactPetAndSpell = true;
    assert(Evaluate(e) == Verdict::Skip); // observed ON disagrees with OFF request
    e.observedNativeOn = false;
    assert(Evaluate(e) == Verdict::MasterConflictNeedsCoordination);

    e.requestedOn = true;
    assert(Evaluate(e) == Verdict::Skip); // observed OFF disagrees with ON request
    e.observedNativeOn = true;
    assert(Evaluate(e) == Verdict::MasterMatchesBotPolicy);
    e.botDefaultOn = false;
    assert(Evaluate(e) == Verdict::MasterConflictNeedsCoordination);

    e.correctActivePet = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.correctActivePet = true;
    e.postIPReconciliationVerified = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.postIPReconciliationVerified = true;
    e.legalKnownRankUnderIP = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.legalKnownRankUnderIP = true;
    e.nativeAutocastable = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.nativeAutocastable = true;
    e.botDefaultPolicyKnown = false;
    assert(Evaluate(e) == Verdict::Skip);
    e.botDefaultPolicyKnown = true;
    e.hunterBotVerified = false;
    assert(Evaluate(e) == Verdict::Skip);
    // No verdict authorizes an autocast toggle or a persisted preference.
}
