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
    return {ValidId(), 17261, 17261, true, true, true,
        true, true, true};
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
    { auto e=good; e.version=4; reject(e); }
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
    // Native state and spell ID can remain unchanged even after IP
    // revokes entitlement, a spell loses autocastability, or IP starts a
    // replacement reconciliation. All three must fail closed NOW,
    // regardless of the earlier event's claimed legal/ready state.
    { auto e=good; auto c=now; c.currentPetKnowsLegalRank=false; reject(e,c); }
    { auto e=good; auto c=now; c.currentNativeAutocastable=false; reject(e,c); }
    { auto e=good; auto c=now; c.currentIpReconciliationCompleted=false; reject(e,c); }
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
    {
        // Model ALL eligible ability IDs generically, never only Lightning
        // Breath. The numbers below are distinct synthetic spell/rank pairs,
        // NOT claims of learnt spells in the operator's current pet book.
        constexpr std::uint32_t spells[] = {
            10001, 10002, 10003, 10004, 10005, 10006
        };
        Consumer c(ValidId());
        std::uint64_t sequence = 1;
        for (std::uint32_t i = 0; i < 6; ++i)
        {
            bool const requestedOn = (i % 2 == 0);
            bool const botDefaultOn = (i % 3 == 0) ? requestedOn
                                                     : !requestedOn;
            Current current = Live();
            current.spellId = spells[i];
            current.rankFamily = spells[i];
            current.nativeOn = requestedOn;

            Notification owner = ValidMaster();
            owner.operationSequence = sequence++;
            owner.spellId = spells[i];
            owner.rankFamily = spells[i];
            owner.requestedOn = requestedOn;
            owner.beforeNativeOn = !requestedOn;
            owner.afterNativeOn = requestedOn;
            owner.nativeChangeApplied = true;
            owner.botDefaultOn = botDefaultOn;

            Verdict const expected = requestedOn == botDefaultOn
                ? Verdict::MasterCandidateOnly
                : Verdict::MasterConflictNeedsBotCoordination;
            assert(c.Review(owner, current) == expected);
            // Per-bot operation sequences must not be reused across spells.
            assert(c.Review(owner, current) == Verdict::Skip);

            // Normal Playerbots policy can subsequently reassert the bot's
            // default. This observation is AUTOMATED, never master intent.
            Notification ai = owner;
            ai.operationSequence = sequence++;
            ai.origin = Origin::BotDefault;
            ai.masterIdentityAndCommandVerified = false;
            ai.masterRequestApplied = false;
            ai.beforeNativeOn = requestedOn;
            ai.afterNativeOn = botDefaultOn;
            ai.nativeChangeApplied = (requestedOn != botDefaultOn);
            current.nativeOn = botDefaultOn;
            assert(c.Review(ai, current) == Verdict::AutomatedObservationOnly);

            // A hypothetical newly verified master request on this SAME
            // spell requires coordination if opposing Playerbots policy.
            Notification ownerAgain = owner;
            ownerAgain.operationSequence = sequence++;
            ownerAgain.beforeNativeOn = botDefaultOn;
            ownerAgain.afterNativeOn = requestedOn;
            ownerAgain.nativeChangeApplied = (requestedOn != botDefaultOn);
            ownerAgain.botPolicyOverrideCoordinated = true;
            current.nativeOn = requestedOn;
            assert(c.Review(ownerAgain, current) ==
                   Verdict::MasterCandidateOnly);
            // Old events cannot relabel AI action after newer master action.
            assert(c.Review(ai, current) == Verdict::Skip);

            // A previous rank or replaced spell cannot be used as evidence
            // of intent for a different legal rank on the current pet.
            Current differentRank = current;
            ++differentRank.rankFamily;
            Notification stale = owner;
            stale.operationSequence = sequence++;
            assert(c.Review(stale, differentRank) == Verdict::Skip);

            // Even an equal spell ID, family, pet and native ON/OFF may
            // have become ineligible since the earlier signed event.
            // Use fresh consumers so the test isolates current eligibility
            // rather than accidentally succeeding due to replay rejection.
            Current revoked = current;
            revoked.currentPetKnowsLegalRank = false;
            Consumer revokedConsumer(ValidId());
            assert(revokedConsumer.Review(owner, revoked) == Verdict::Skip);
            Current replacing = current;
            replacing.currentIpReconciliationCompleted = false;
            Consumer replacingConsumer(ValidId());
            assert(replacingConsumer.Review(owner, replacing) == Verdict::Skip);
            Current noAutocast = current;
            noAutocast.currentNativeAutocastable = false;
            Consumer noAutocastConsumer(ValidId());
            assert(noAutocastConsumer.Review(owner, noAutocast) == Verdict::Skip);
        }
        // Model verdicts remain advisory; no Pet toggle or DB persistence.
    }
    { Consumer c(ValidId());c.Invalidate();assert(c.Review(good,now)==Verdict::Skip); }
    { Consumer c({});assert(c.Review(good,now)==Verdict::Skip); }
}
