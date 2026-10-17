#include "../src/Systems/HunterPetAutocastPlayerbotBridgeContract.h"
#include <cassert>
#include <initializer_list>
using namespace NaxxramasCore::HunterAutocastPlayerbotBridge;
constexpr Identity ValidId() { return {11, 22, 33, 44, 55}; }
constexpr Notification ValidMaster()
{
    Notification e;
    e.version = ContractVersion;
    e.identity = ValidId();
    e.operationSequence = 1;
    e.spellId = 17261;
    e.rankFamily = 17261;
    e.origin = Origin::HypotheticalAuthenticatedMaster;
    e.trustedProducer = true;
    e.nativeOperationAttempted = true;
    e.nativeChangeApplied = true;
    e.petKnowsLegalRank = true;
    e.nativeAutocastable = true;
    e.ipReconciliationCompleted = true;
    e.afterNativeOn = true;
    e.requestedOn = true;
    e.masterIdentityAndCommandVerified = true;
    e.botDefaultKnown = true;
    e.botDefaultOn = true;
    return e;
}
constexpr Current Live()
{
    return {ValidId(), 17261, 17261, true, true, true};
}
constexpr bool OneShot()
{
    Consumer c(ValidId());
    return c.Review(ValidMaster(), Live()) == Verdict::MasterCandidateOnly &&
        c.Review(ValidMaster(), Live()) == Verdict::Skip;
}
static_assert(OneShot());
int main()
{
    const auto good = ValidMaster();
    const auto now = Live();
    {
        Consumer c(ValidId());
        assert(c.Review(good, now) == Verdict::MasterCandidateOnly);
        auto newer = good; newer.operationSequence = 2;
        assert(c.Review(newer, now) == Verdict::MasterCandidateOnly);
        assert(c.Review(good, now) == Verdict::Skip);
    }
    auto reject = [&](Notification e, Current state = Live()) {
        Consumer c(ValidId());
        assert(c.Review(e, state) == Verdict::Skip);
    };
    { auto e=good; e.version=2; reject(e); }
    { auto e=good; e.identity.petIncarnation++; reject(e); }
    { auto e=good; e.identity.processEpoch++; reject(e); }
    { auto e=good; e.identity.ownerSessionEpoch++; reject(e); }
    { auto e=good; e.identity.petEventGeneration++; reject(e); }
    { auto e=good; e.identity.botGuid++; reject(e); }
    { auto e=good; e.operationSequence=0; reject(e); }
    { auto e=good; e.spellId=0; reject(e); }
    { auto e=good; e.rankFamily=0; reject(e); }
    { auto e=good; e.spellId++; reject(e); }
    { auto e=good; e.rankFamily++; reject(e); }
    { auto e=good; e.origin=Origin::Unknown; reject(e); }
    { auto e=good; e.trustedProducer=false; reject(e); }
    { auto e=good; e.nativeOperationAttempted=false; reject(e); }
    { auto e=good; e.nativeChangeApplied=false; reject(e); }
    { auto e=good; e.petKnowsLegalRank=false; reject(e); }
    { auto e=good; e.nativeAutocastable=false; reject(e); }
    { auto e=good; e.ipReconciliationCompleted=false; reject(e); }
    { auto e=good; e.afterNativeOn=false; reject(e); }
    { auto e=good; e.requestedOn=false; reject(e); }
    { auto e=good; e.masterIdentityAndCommandVerified=false; reject(e); }
    { auto e=good; e.botDefaultKnown=false; reject(e); }
    { auto e=good; auto c=now; c.identity.petIncarnation++; reject(e,c); }
    { auto e=good; auto c=now; c.stillSameActivePet=false; reject(e,c); }
    { auto e=good; auto c=now; c.ownerSessionActive=false; reject(e,c); }
    { auto e=good; auto c=now; c.nativeOn=false; reject(e,c); }
    {
        auto e=good; e.botDefaultOn=false;
        Consumer c(ValidId());
        assert(c.Review(e,now)==Verdict::MasterConflictNeedsBotCoordination);
        assert(c.Review(e,now)==Verdict::Skip);
        auto next=e; next.operationSequence=2;
        next.botPolicyOverrideCoordinated=true;
        assert(c.Review(next,now)==Verdict::MasterCandidateOnly);
    }
    for (auto origin: {Origin::BotDefault,Origin::FactoryOrTame,Origin::OtherAI})
    {
        auto e=good; e.origin=origin;
        e.masterIdentityAndCommandVerified=false; e.nativeChangeApplied=false;
        Consumer c(ValidId());
        assert(c.Review(e,now)==Verdict::AutomatedObservationOnly);
    }
    { Consumer c(ValidId());c.Invalidate();assert(c.Review(good,now)==Verdict::Skip); }
    { Consumer c({});assert(c.Review(good,now)==Verdict::Skip); }
}
