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
    e.beforeNativeOn = false;
    e.afterNativeOn = true;
    e.requestedOn = true;
    e.masterIdentityAndCommandVerified = true;
    e.masterRequestApplied = true;
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
    { auto e=good; e.version=1; reject(e); }
    { auto e=good; e.version=3; reject(e); }
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
    { auto e=good; e.masterRequestApplied=false; reject(e); }
    { auto e=good; e.beforeNativeOn=true; reject(e); }
    // An unchanged state with a false 'changed' claim is inconsistent;
    // trusted, actually accepted idempotent master intent is tested below.
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
        e.masterIdentityAndCommandVerified=false;
        e.masterRequestApplied=false; e.nativeChangeApplied=false;
        e.beforeNativeOn=e.afterNativeOn; // unchanged, source-labelled observation
        Consumer c(ValidId());
        assert(c.Review(e,now)==Verdict::AutomatedObservationOnly);
        e.masterRequestApplied=true;
        Consumer rejectApplied(ValidId());
        assert(rejectApplied.Review(e,now)==Verdict::Skip);
        e.masterRequestApplied=false; e.masterIdentityAndCommandVerified=true;
        Consumer rejectIdentity(ValidId());
        assert(rejectIdentity.Review(e,now)==Verdict::Skip);
    }
    {
        // Automatic notifications and master events must share ONE producer
        // sequence namespace per bot/Pet lifecycle, not one per ability.
        Consumer c(ValidId());
        auto bot = good; bot.origin=Origin::BotDefault;
        bot.masterIdentityAndCommandVerified=false;
        bot.masterRequestApplied=false;
        bot.nativeChangeApplied=false;
        bot.beforeNativeOn=bot.afterNativeOn;
        assert(c.Review(bot,now)==Verdict::AutomatedObservationOnly);
        auto laterMaster=good; laterMaster.operationSequence=2;
        assert(c.Review(laterMaster,now)==Verdict::MasterCandidateOnly);
        assert(c.Review(bot,now)==Verdict::Skip);
        // An alternate spell requires exact matching CURRENT spell and rank.
        auto bite=good; bite.operationSequence=3; bite.spellId=14916;
        bite.rankFamily=14916;
        Current growl=now; growl.spellId=14916; growl.rankFamily=14916;
        assert(c.Review(bite,growl)==Verdict::MasterCandidateOnly);
        assert(c.Review(laterMaster,now)==Verdict::Skip);
    }
    {
        auto bot=good; bot.origin=Origin::BotDefault;
        bot.masterIdentityAndCommandVerified=false;
        bot.masterRequestApplied=false;
        bot.nativeChangeApplied=false;
        // A bot event claiming no change, while BEFORE and AFTER differ,
        // is also an inconsistent native observation and must fail closed.
        Consumer c(ValidId());
        assert(c.Review(bot,now)==Verdict::Skip);
    }
    {
        // Already ON: a verified master request can be explicit intent.
        auto e=good; e.beforeNativeOn=true; e.nativeChangeApplied=false;
        Consumer c(ValidId());
        assert(c.Review(e,now)==Verdict::MasterCandidateOnly);
        assert(c.Review(e,now)==Verdict::Skip);
        e.operationSequence=2; e.masterRequestApplied=false;
        assert(c.Review(e,now)==Verdict::Skip);
    }
    {
        // Already OFF despite AI default ON: policy coordination required.
        auto e=good; e.beforeNativeOn=false; e.afterNativeOn=false;
        e.nativeChangeApplied=false; e.requestedOn=false;
        e.botDefaultOn=true;
        auto off=now; off.nativeOn=false;
        Consumer c(ValidId());
        assert(c.Review(e,off)==Verdict::MasterConflictNeedsBotCoordination);
        auto next=e; next.operationSequence=2;
        next.botPolicyOverrideCoordinated=true;
        assert(c.Review(next,off)==Verdict::MasterCandidateOnly);
        assert(c.Review(e,off)==Verdict::Skip);
    }
    { Consumer c(ValidId());c.Invalidate();assert(c.Review(good,now)==Verdict::Skip); }
    { Consumer c({});assert(c.Review(good,now)==Verdict::Skip); }
}
