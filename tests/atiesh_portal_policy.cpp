// Native tests for src/Systems/AtieshPortalPolicy.h (F13).
// Build: g++ -std=c++17 -Wall -Wextra -Werror -pedantic -Isrc/Systems
//        tests/atiesh_portal_policy.cpp -o /tmp/atiesh && /tmp/atiesh
#include "AtieshPortalPolicy.h"

#include <cstdio>

using namespace NaxxramasAtieshPortalPolicy;

namespace
{
    int failures = 0;

    void Check(bool ok, char const* what)
    {
        if (!ok)
        {
            ++failures;
            std::printf("FAIL: %s\n", what);
        }
    }

    // Eligible Vanilla owner clicking a baseline portal with a valid row.
    Facts Eligible()
    {
        Facts f;
        f.Entry = GO_ATIESH_PORTAL_TO_KARAZHAN;
        f.GoType = GO_TYPE_SPELLCASTER;
        f.TemplateSpell = SPELL_TELEPORT_KARAZHAN;
        f.Enabled = true;
        f.VanillaStage = true;
        f.PartyOnly = true;
        f.HasOwner = true;
        f.ClickerIsOwner = true;
        f.ExitRowExists = true;
        f.ExitRowMap = OUTSIDE_MAP;
        f.ExitRowCoordValid = true;
        return f;
    }
}

int main()
{
    // N06 owner, Vanilla -> outside.
    Check(Decide(Eligible()) == Action::Teleport, "N06 Vanilla owner -> teleport outside");

    // N01 flag off; N04/N17g IP disabled (helper says not Vanilla); N05 later era; N15 GM.
    {
        Facts f = Eligible(); f.Enabled = false;
        Check(Decide(f) == Action::Stock, "N01 flag off -> stock");
        f = Eligible(); f.VanillaStage = false;
        Check(Decide(f) == Action::Stock, "N04/N05/N17g not Vanilla -> stock");
        f = Eligible(); f.GameMaster = true;
        Check(Decide(f) == Action::Stock, "N15 GM -> stock");
    }

    // N02/N03 other objects and edited templates.
    {
        Facts f = Eligible(); f.Entry = 194097;
        Check(Decide(f) == Action::Stock, "N02 other entry -> stock");
        f = Eligible(); f.GoType = 23;
        Check(Decide(f) == Action::Stock, "N02 other type -> stock");
        f = Eligible(); f.TemplateSpell = 0;
        Check(Decide(f) == Action::Stock, "N03 template spell changed -> stock");
        f = Eligible(); f.TemplateSpell = 28148;
        Check(Decide(f) == Action::Stock, "N03 template spell 28148 -> stock");
    }

    // Party rule, mirroring GameObject.cpp L1920-1934.
    {
        Facts f = Eligible(); f.ClickerIsOwner = false; f.ClickerGroupHasOwner = true;
        Check(Decide(f) == Action::Teleport, "N07/N08 group member (owner may be offline) -> outside");
        f.ClickerGroupHasOwner = false;
        Check(Decide(f) == Action::Stock, "N09 stranger with owned portal -> stock refusal");
        f = Eligible(); f.HasOwner = false; f.ClickerIsOwner = false;
        Check(Decide(f) == Action::Teleport, "N10 ownerless portal -> stock parity, outside");
        f = Eligible(); f.PartyOnly = false; f.ClickerIsOwner = false;
        Check(Decide(f) == Action::Teleport, "partyOnly 0 in live template -> anyone");
    }

    // N14 already teleporting.
    {
        Facts f = Eligible(); f.BeingTeleported = true;
        Check(Decide(f) == Action::Ignore, "N14 already teleporting -> ignore");
    }

    // N12 row checks: fail closed, never stock.
    {
        Facts f = Eligible(); f.ExitRowExists = false;
        Check(Decide(f) == Action::FailClosed, "N12 row missing -> fail closed");
        f = Eligible(); f.ExitRowMap = 532;
        Check(Decide(f) == Action::FailClosed, "N12 row on map 532 -> fail closed");
        f = Eligible(); f.ExitRowCoordValid = false;
        Check(Decide(f) == Action::FailClosed, "N12 invalid coordinates -> fail closed");
        f = Eligible(); f.ExitRowExists = false; f.Enabled = false;
        Check(Decide(f) == Action::Stock, "row missing but flag off -> stock");
        f = Eligible(); f.ExitRowExists = false; f.VanillaStage = false;
        Check(Decide(f) == Action::Stock, "row missing but later era -> stock");
    }

    // Order: an ineligible stranger is refused natively even if the row is bad.
    {
        Facts f = Eligible(); f.ClickerIsOwner = false; f.ExitRowExists = false;
        Check(Decide(f) == Action::Stock, "stranger + bad row -> stock refusal first");
    }

    // N17e/N17f: era is per clicker.
    {
        Facts vanillaBot = Eligible(); vanillaBot.ClickerIsOwner = false;
        vanillaBot.ClickerGroupHasOwner = true;
        Check(Decide(vanillaBot) == Action::Teleport, "N17e Vanilla bot in post-TBC master's group -> outside");
        Facts lateBot = vanillaBot; lateBot.VanillaStage = false;
        Check(Decide(lateBot) == Action::Stock, "N17f post-TBC bot in Vanilla master's group -> stock");
    }

    if (failures)
    {
        std::printf("%d failure(s)\n", failures);
        return 1;
    }

    std::printf("OK (0 failures)\n");
    return 0;
}
