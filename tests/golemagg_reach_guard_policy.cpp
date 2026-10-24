#include "GolemaggActionAuditAllowlist.h"
#include "GolemaggReachGuardPolicy.h"

#include <cassert>
#include <iostream>

using namespace NaxxramasGolemaggReachGuard;

namespace
{
    // A context in which Playerbots' Golemagg back-off conditions all hold.
    ReachMeleeContext Denying()
    {
        ReachMeleeContext c;
        c.enabled = true;
        c.botAlive = true;
        c.mapId = MOLTEN_CORE_MAP;
        c.isAltBot = true;
        c.isTank = false;
        c.isDps = true;
        c.isMelee = true;
        c.nameAllowed = true;
        c.targetPresent = true;
        c.targetEntry = GOLEMAGG_ENTRY;
        c.targetAlive = true;
        c.targetInCombat = true;
        c.targetHealthPct = 55.0f;
        c.magmaSplashStacks = MAGMA_SPLASH_BACK_OFF_STACKS;
        return c;
    }

    void TestPolicy()
    {
        assert(ShouldDenyReachMelee(Denying()));

        ReachMeleeContext c = Denying();
        c.magmaSplashStacks = 25;
        assert(ShouldDenyReachMelee(c));

        // Each condition on its own releases the action.
        c = Denying(); c.enabled = false;               assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.botAlive = false;              assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.mapId = 230;                   assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.isAltBot = false;              assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.isTank = true;                 assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.isDps = false;                 assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.isMelee = false;               assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.nameAllowed = false;           assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.targetPresent = false;         assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.targetAlive = false;           assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.targetInCombat = false;        assert(!ShouldDenyReachMelee(c));

        // Core Rager (11672) or any other target is never guarded.
        c = Denying(); c.targetEntry = 11672;           assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.targetEntry = 0;               assert(!ShouldDenyReachMelee(c));

        // Stack threshold: 19 releases, 20 denies.
        c = Denying(); c.magmaSplashStacks = 19;        assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.magmaSplashStacks = 0;         assert(!ShouldDenyReachMelee(c));

        // Burn phase: 10% and below releases, just above 10% denies.
        c = Denying(); c.targetHealthPct = 10.0f;       assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.targetHealthPct = 3.0f;        assert(!ShouldDenyReachMelee(c));
        c = Denying(); c.targetHealthPct = 10.01f;      assert(ShouldDenyReachMelee(c));

        // A default-constructed context never denies.
        assert(!ShouldDenyReachMelee(ReachMeleeContext{}));
    }

    // The guard reuses the P5 observer's single exact-name gate.
    void TestBotNameGate()
    {
        using NaxxramasGolemaggActionAudit::IsAllowedBotName;
        assert(!IsAllowedBotName("Grau", ""));          // empty covers nobody
        assert(!IsAllowedBotName("Grau", "  \t "));
        assert(!IsAllowedBotName("Grau", "*"));
        assert(!IsAllowedBotName("Grau", "all"));
        assert(!IsAllowedBotName("Grau", "Grau,Krugan")); // no lists
        assert(IsAllowedBotName("Grau", "Grau"));
        assert(IsAllowedBotName("Grau", " gRaU "));
        assert(!IsAllowedBotName("GrauAlt", "Grau"));
        assert(!IsAllowedBotName("Krugan", "Grau"));
    }

    struct FakeAI { int id; };
    struct FakeEngine { int id; };

    void TestRegistration()
    {
        RegistrationRecord<FakeAI, FakeEngine> record;
        FakeAI ai1{ 1 };
        FakeAI ai2{ 2 };
        FakeEngine combat{ 10 };
        FakeEngine other{ 11 };

        // Null inputs never register.
        assert((!NeedsRegistration<FakeAI, FakeEngine>(record, nullptr, &combat)));
        assert((!NeedsRegistration<FakeAI, FakeEngine>(record, &ai1, nullptr)));

        // First sighting registers once; repeat ticks do not.
        assert(NeedsRegistration(record, &ai1, &combat));
        assert(record.alive && record.alive->load());
        LivenessToken firstToken = record.alive;
        assert(!NeedsRegistration(record, &ai1, &combat));
        assert(!NeedsRegistration(record, &ai1, &combat));
        assert(record.engines.size() == 1);

        // A different engine of the same AI gets its own listener once.
        assert(NeedsRegistration(record, &ai1, &other));
        assert(!NeedsRegistration(record, &ai1, &other));
        assert(record.alive == firstToken);

        // Listener deleted with its engine: the token clears, and the same
        // address (for example a new AI reusing it) registers afresh.
        firstToken->store(false);
        assert(NeedsRegistration(record, &ai1, &combat));
        assert(record.alive != firstToken);
        assert(record.alive->load());
        assert(record.engines.size() == 1);

        // A replaced AI object starts a fresh record with a new token.
        LivenessToken secondToken = record.alive;
        assert(NeedsRegistration(record, &ai2, &combat));
        assert(record.ai == &ai2);
        assert(record.alive != secondToken);
        assert(!NeedsRegistration(record, &ai2, &combat));

        // The old listener still holds its own token, so clearing the old
        // one does not reset the new record.
        secondToken->store(false);
        assert(!NeedsRegistration(record, &ai2, &combat));
    }

    // Playerbots creates one combat engine per PlayerbotAI and reuses it for
    // the AI's lifetime (PlayerbotAI.cpp L160-163 at d750b4b/e88cc409). The
    // update hook only offers that engine while the AI is in combat, so
    // repeated pulls, wipes, map changes and combat exits must register it
    // exactly once.
    void TestRepeatedTransitionsRegisterOnce()
    {
        RegistrationRecord<FakeAI, FakeEngine> record;
        FakeAI ai{ 7 };
        FakeEngine combat{ 70 };

        int registrations = 0;
        for (int pull = 0; pull < 50; ++pull)
        {
            bool const inMoltenCore = pull % 5 != 0;  // left MC, came back
            bool const inCombat = pull % 3 != 0;      // combat ended between pulls
            for (int tick = 0; tick < 20; ++tick)
            {
                if (!inMoltenCore || !inCombat)
                    continue;  // the hook returns before touching the record
                if (NeedsRegistration(record, &ai, &combat))
                    ++registrations;
            }
        }

        assert(registrations == 1);
        assert(record.engines.size() == 1);
        assert(record.alive && record.alive->load());
    }
}

int main()
{
    TestPolicy();
    TestBotNameGate();
    TestRegistration();
    TestRepeatedTransitionsRegisterOnce();
    std::cout << "PASS: Golemagg reach guard policy, single-name gate and registration bookkeeping\n";
    return 0;
}
