/*
 * A02 S2 adversarial source counterexamples at original CS02 PR #60 head.
 * Tests intentionally PASS when known unsafe candidate behaviour is
 * reproducible. They are falsification/regression evidence, NOT an S2 fix.
 * No real pet, core, DB, packet, instance or server is touched.
 */
#include "HunterPetAutocastRestore.h"

#include <cstdio>
#include <map>
#include <vector>

using namespace NaxxramasCore::HunterPetAutocastRestore;

namespace
{
int failures = 0;

void Check(bool condition, char const* label)
{
    if (!condition)
    {
        std::fprintf(stderr, "A02_S2_COUNTEREXAMPLE_CHANGED: %s\n", label);
        ++failures;
    }
}

BookSpell Spell(uint32_t id, uint32_t chain, bool on)
{
    BookSpell spell;
    spell.id = id;
    spell.chainFirst = chain;
    spell.autocastable = true;
    spell.removed = false;
    spell.autocastOn = on;
    return spell;
}

Preference Packet(uint32_t id, bool on, uint64_t sequence)
{
    Preference p;
    p.spellId = id;
    p.autocastOn = on;
    p.present = true;
    p.sequence = sequence;
    return p;
}
}

int main()
{
    // 1. Unknown account lookup / malformed regex is currently classified
    // "not bot"; IsHumanHunter negates that flag in the runtime C++.
    Check(!AccountIsBot(false, "RNDBOT1", "^RNDBOT.*"),
        "unknown account treated as not bot (fail-open)");
    Check(!AccountIsBot(true, "RNDBOT1", "("),
        "invalid configured regex treated as not bot (fail-open)");
    Check(!AccountIsBot(true, "RNDBOT1", ""),
        "empty configured regex treated as not bot (fail-open)");

    // 2. Packet-cache preference is not backed by a historical HasSpell
    // assertion. A newer forged/stale ON for an unowned old rank can
    // generate an ON restore for the real current rank.
    std::vector<BookSpell> current{Spell(17255u, 17253u, false)};
    std::map<uint32_t, Preference> staleOn{
        {17253u, Packet(17253u, true, 100u)}
    };
    std::vector<ChainRestore> plans =
        PlanRestores(current, {}, staleOn, false);
    Check(plans.size() == 1u && plans[0].apply &&
        plans[0].newSpellId == 17255u && plans[0].desiredOn,
        "unverified packet ON can schedule rank restore");

    // 3. An explicit, newer OFF does not impose any OFF action when the
    // replacement book happens to be ON: OFF relies on ACT_DECIDE default.
    std::vector<BookSpell> currentOn{Spell(17255u, 17253u, true)};
    std::map<uint32_t, Preference> explicitOff{
        {17253u, Packet(17253u, false, 101u)}
    };
    Check(PlanRestores(currentOn, {}, explicitOff, false).empty(),
        "explicit OFF skipped when replacement rank is ON");

    // 4. Stable pet numbers do not distinguish two summoned incarnations.
    // This pure policy knows only the number, not a live ObjectGuid.
    Check(PetNumberMatches(45u, 45u),
        "same saved pet number accepted without incarnation identity");

    // 5. Without snapshot/packet, the REMOVED fallback can be erased by a
    // save between IP rank reconcile and the eventual restore event.
    Check(PlanRestores(current, {}, {}, true).empty(),
        "after save no REMOVED fallback exists to donate ON");

    if (failures)
    {
        std::fprintf(stderr, "A02_S2_COUNTEREXAMPLE_SOURCE_CHANGED %d\n", failures);
        return 1;
    }
    std::puts("A02_S2_KNOWN_UNSAFE_COUNTEREXAMPLES_REPRODUCED");
    std::puts("NO functional signoff, pet toggle, in-game proof or rollback guarantee.");
    return 0;
}
