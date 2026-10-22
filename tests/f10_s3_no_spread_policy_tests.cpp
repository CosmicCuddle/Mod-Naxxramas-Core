/* F10 post-pilot no-spread decision test. No core, SQL or runtime required.
 * The runtime owner census is checked separately by source/Worldserver CI.
 */
#include "HallowsEndSoloFire.h"
#include <cstdio>
#include <cstdlib>

using namespace NaxxramasCore::HallowsEndSoloFire;
int main()
{
    auto require = [](bool cond, char const* message)
    {
        if (!cond)
        {
            std::fprintf(stderr, "FAIL: %s\n", message);
            std::exit(1);
        }
    };

    SpreadGuardFacts f;
    f.soloEnabled = 1;
    f.disableSpread = 1;
    f.playerbotsApiPresent = true;
    f.sourceIsNormalFire = true;
    f.hasBaseFireAura = true;
    f.livingOwnerShadeCount = 1;
    f.activeOwnerShadeCount = 1;
    f.realPlayersNearOwner = 1;

    require(ShouldBlockFireSpread(f), "exactly one human blocks spread (any bot count ignored)");

    auto x = f;
    x.realPlayersNearOwner = 0;
    require(!ShouldBlockFireSpread(x), "zero humans: stock spread");
    x = f; x.realPlayersNearOwner = 2;
    require(!ShouldBlockFireSpread(x), "two humans: stock spread");
    x = f; x.soloEnabled = 0;
    require(!ShouldBlockFireSpread(x), "solo disabled: stock spread");
    x = f; x.disableSpread = 0;
    require(!ShouldBlockFireSpread(x), "no-spread option disabled: stock spread");
    x = f; x.playerbotsApiPresent = false;
    require(!ShouldBlockFireSpread(x), "unknown playerbot API: fail closed");
    x = f; x.sourceIsNormalFire = false;
    require(!ShouldBlockFireSpread(x), "training/other source: stock spread");
    x = f; x.hasBaseFireAura = false;
    require(!ShouldBlockFireSpread(x), "fire aura absent: stock spread");
    x = f; x.livingOwnerShadeCount = 0;
    require(!ShouldBlockFireSpread(x), "no owning Shade: stock spread");
    x = f; x.livingOwnerShadeCount = 2;
    require(!ShouldBlockFireSpread(x), "two owners: stock spread");
    x = f; x.activeOwnerShadeCount = 0;
    require(!ShouldBlockFireSpread(x), "owner did not ignite this fire: stock spread");
    x = f; x.activeOwnerShadeCount = 2;
    require(!ShouldBlockFireSpread(x), "ambiguous active owners: stock spread");

    require(DisableSpreadFromRaw("1") == 1, "exact switch ON");
    require(DisableSpreadFromRaw("0") == 0, "exact switch OFF");
    require(DisableSpreadFromRaw("2") == 0, "non-1 rejected");
    require(DisableSpreadFromRaw("-1") == 0, "negative rejected");
    require(DisableSpreadFromRaw("abc") == 0, "malformed rejected");
    require(DisableSpreadFromRaw("1oops") == 0, "partial token rejected");
    require(DisableSpreadFromRaw("  1  ") == 1, "whitespace accepted");

    std::puts("PASS: F10 solo spread suppression policy and fail-closed cases");
    return 0;
}
