#include "HunterPetAutocastIntentFence.h"
#include <iostream>
#include <string>

using namespace NaxxramasHunterPetAutocast::IntentFence;

namespace
{
    int failed = 0;
    int checked = 0;

    void Check(bool condition, char const* label)
    {
        ++checked;
        if (!condition)
        {
            ++failed;
            std::cerr << "FAIL " << label << "\n";
        }
    }

    Identity Pet(uint32_t number = 42, uint64_t generation = 9)
    {
        Identity p;
        p.PlayerGuid = 1234;
        p.ServerEpoch = 777;
        p.PetNumber = number;
        p.SummonGeneration = generation;
        p.ServerToken[0] = 0xA7;
        p.ServerToken[15] = 0xD4;
        return p;
    }

    AcceptedManualChoice Manual(bool enabled = true)
    {
        AcceptedManualChoice x;
        x.Pet = Pet();
        x.Revision = 21;
        x.SpellChain = 17253; // synthetic Bite chain, NOT a DBC assertion
        x.Enable = enabled;
        x.TrustedManualReceipt = true; // fixture input, not real attestation
        return x;
    }

    CurrentObservation Current(bool enabled = false)
    {
        CurrentObservation c;
        c.Pet = Pet();
        c.LatestAcceptedRevision = 21;
        c.AllowedSpellChain = 17253;
        c.AllowedSpellId = 17260; // illustrative IP-permitted rank
        c.BookRevision = 6;
        c.Owner = OwnerMode::Human;
        c.ReceiverAuthenticated = true;
        c.AddonOptIn = true;
        c.HasVerifiedClientTransport = true;
        c.NoUnresolvedNewerManualClick = true;
        c.SelectedCurrentPet = true;
        c.RankAllowedByIP = true;
        c.SpellPresent = true;
        c.SpellAutocastable = true;
        c.SpellbookConsistent = true;
        c.EnabledNow = enabled;
        return c;
    }
}

int main()
{
    auto yes = Manual();
    auto no = Manual(false);
    auto c = Current();
    AttemptBudget budget;

    Check(Decide(yes, c, budget) == Verdict::ApplyOn, "accepted ON on allowed existing rank");
    c.EnabledNow = true;
    Check(Decide(no, c, budget) == Verdict::ApplyOff, "accepted OFF overrides ON");
    Check(Decide(yes, c, budget) == Verdict::AlreadyCorrect, "idempotent matching state");
    c = Current();

    auto trial = [&](char const* name, auto mutate) {
        auto x = c;
        auto pref = yes;
        mutate(pref, x);
        Check(Decide(pref, x, budget) == Verdict::NoWrite, name);
    };

    trial("different pet number", [](auto&, auto& x) { x.Pet.PetNumber = 43; });
    trial("different summon generation", [](auto&, auto& x) { x.Pet.SummonGeneration++; });
    trial("recycled server epoch", [](auto&, auto& x) { x.Pet.ServerEpoch++; });
    trial("different player", [](auto&, auto& x) { x.Pet.PlayerGuid++; });
    trial("different server token", [](auto&, auto& x) { x.Pet.ServerToken[15]++; });
    trial("missing server token", [](auto&, auto& x) { x.Pet.ServerToken = {}; });
    trial("zero current pet number", [](auto&, auto& x) { x.Pet.PetNumber = 0; });
    trial("old accepted revision", [](auto&, auto& x) { x.LatestAcceptedRevision++; });
    trial("missing accepted revision", [](auto& x, auto&) { x.Revision = 0; });
    trial("no authoritative client receipt", [](auto& x, auto&) { x.TrustedManualReceipt = false; });
    trial("untrusted transport", [](auto&, auto& x) { x.HasVerifiedClientTransport = false; });
    trial("receiver unauthenticated", [](auto&, auto& x) { x.ReceiverAuthenticated = false; });
    trial("manual first-click pending", [](auto&, auto& x) { x.NoUnresolvedNewerManualClick = false; });
    trial("wrong current pet", [](auto&, auto& x) { x.SelectedCurrentPet = false; });
    trial("unknown owner", [](auto&, auto& x) { x.Owner = OwnerMode::Unknown; });
    trial("SelfBot or Playerbot", [](auto&, auto& x) { x.Owner = OwnerMode::BotOrSelfBot; });
    trial("opt-in disabled", [](auto&, auto& x) { x.AddonOptIn = false; });
    trial("IP rank not allowed", [](auto&, auto& x) { x.RankAllowedByIP = false; });
    trial("missing spell", [](auto&, auto& x) { x.SpellPresent = false; });
    trial("not autocastable", [](auto&, auto& x) { x.SpellAutocastable = false; });
    trial("inconsistent book", [](auto&, auto& x) { x.SpellbookConsistent = false; });
    trial("different chain", [](auto&, auto& x) { x.AllowedSpellChain++; });
    trial("no selected spell rank", [](auto&, auto& x) { x.AllowedSpellId = 0; });
    trial("no book revision", [](auto&, auto& x) { x.BookRevision = 0; });

    // Repeated IP rank reconciliation: a new real book transition allows
    // another bounded attempt, without a guessed 200ms timer.
    c = Current();
    RecordAttempt(budget, yes, c);
    Check(Decide(yes, c, budget) == Verdict::ApplyOn, "first retry for same book");
    RecordAttempt(budget, yes, c);
    Check(Decide(yes, c, budget) == Verdict::NoWrite, "two-attempt ceiling");
    c.BookRevision++;
    c.AllowedSpellId = 17259; // different synthetic allowed rank
    Check(Decide(yes, c, budget) == Verdict::ApplyOn, "new IP transition separate bounded attempt");
    RecordAttempt(budget, yes, c);
    auto latest = yes;
    latest.Revision++;
    c.LatestAcceptedRevision++;
    Check(Decide(yes, c, budget) == Verdict::NoWrite, "older ON cannot override newer OFF");
    latest.Enable = false;
    c.EnabledNow = true;
    Check(Decide(latest, c, budget) == Verdict::ApplyOff, "latest manual OFF is preferred");
    RecordAttempt(budget, latest, c);
    c.EnabledNow = false;
    Check(Decide(latest, c, budget) == Verdict::AlreadyCorrect, "successful OFF is idempotent");

    // Never infer real-human proof from a typed boolean on the wire:
    // Owner and TrustedManualReceipt are out-of-band *unresolved* production inputs.
    std::cout << "A02 source-only intent fence: " << checked - failed
              << "/" << checked << " assertions passed (not gameplay)\n";
    return failed ? 1 : 0;
}
