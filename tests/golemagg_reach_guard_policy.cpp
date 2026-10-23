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

    void TestNameFilter()
    {
        NameFilter all = NameFilter::Parse("");
        assert(all.AllowsAll());
        assert(all.Allows("Grau"));
        assert(NameFilter::Parse(" \t\r\n").AllowsAll());

        NameFilter one = NameFilter::Parse("Grau");
        assert(!one.AllowsAll());
        assert(one.Allows("Grau"));
        assert(one.Allows("gRAU"));
        assert(!one.Allows("Krugan"));
        assert(!one.Allows("GrauAlt"));
        assert(!one.Allows("Gra"));

        NameFilter list = NameFilter::Parse(" Grau , krugan,Kore ");
        assert(list.Size() == 3);
        assert(list.Allows("Grau"));
        assert(list.Allows("Krugan"));
        assert(list.Allows("KORE"));
        assert(!list.Allows("Emda"));

        // A non-empty value without usable names covers nobody.
        NameFilter broken = NameFilter::Parse(" , ,, ");
        assert(!broken.AllowsAll());
        assert(broken.Size() == 0);
        assert(!broken.Allows("Grau"));

        // Names ending in r/t/n keep those letters.
        NameFilter trimmed = NameFilter::Parse("  Arndor ,Rukhan  ");
        assert(trimmed.Allows("Arndor"));
        assert(trimmed.Allows("Rukhan"));
        assert(!trimmed.Allows("Arndo"));
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
}

int main()
{
    TestPolicy();
    TestNameFilter();
    TestRegistration();
    std::cout << "PASS: Golemagg reach guard policy, name filter and registration bookkeeping\n";
    return 0;
}
