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
        p.BirthToken[0] = 0xB1;
        p.BirthToken[15] = 0xA4;  // synthetic ONLY: not evidence of a real birth authority
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
        x.RevisionDomain = 99; // synthetic authoritative counter domain
        x.SpellChain = 17253; // synthetic Bite chain, NOT a DBC assertion
        x.Enable = enabled;
        x.TrustedManualReceipt = true; // fixture input, not real attestation
        x.TrustedBirthAtReceipt = true; // fabricated verified-birth INPUT
        return x;
    }

    CurrentObservation Current(bool enabled = false)
    {
        CurrentObservation c;
        c.Pet = Pet();
        c.LatestAcceptedRevision = 21;
        c.LatestRevisionDomain = 99;
        c.TrustedCurrentBirth = true; // fixture-only, no production source
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
    // The SAME authenticated birth is permitted across new summon/session
    // incarnations. Treat these as synthetic acceptance examples ONLY.
    {
        auto summoned = c;
        summoned.Pet.SummonGeneration++;
        summoned.Pet.ServerToken[1] = 0x7A;
        Check(Decide(yes, summoned, budget) == Verdict::ApplyOn,
            "same certified pet birth resummon may preserve ON");
        auto relog = c;
        relog.Pet.ServerEpoch++;
        relog.Pet.ServerToken[2] = 0x7B;
        Check(Decide(yes, relog, budget) == Verdict::ApplyOn,
            "same certified persistent birth permits relog when proven");
    }
    trial("same PetNumber but replaced pet birth", [](auto&, auto& x) { x.Pet.BirthToken[15]++; });
    trial("missing current birth token", [](auto&, auto& x) { x.Pet.BirthToken = {}; });
    trial("missing accepted birth token", [](auto& choice, auto&) { choice.Pet.BirthToken = {}; });
    trial("different player", [](auto&, auto& x) { x.Pet.PlayerGuid++; });
    {
        auto nextSummonToken = c;
        nextSummonToken.Pet.ServerToken[15]++;
        Check(Decide(yes, nextSummonToken, budget) == Verdict::ApplyOn,
            "changed ephemeral token alone does not make same birth another pet");
    }
    trial("missing server token", [](auto&, auto& x) { x.Pet.ServerToken = {}; });
    trial("zero current pet number", [](auto&, auto& x) { x.Pet.PetNumber = 0; });
    trial("old accepted revision", [](auto&, auto& x) { x.LatestAcceptedRevision++; });
    trial("missing accepted revision", [](auto& x, auto&) { x.Revision = 0; });
    trial("missing revision domain", [](auto& x, auto&) { x.RevisionDomain = 0; });
    trial("reused revision in other domain", [](auto&, auto& x) { x.LatestRevisionDomain++; });
    trial("missing current birth attestation", [](auto&, auto& x) { x.TrustedCurrentBirth = false; });
    trial("missing accepted birth attestation", [](auto& x, auto&) { x.TrustedBirthAtReceipt = false; });
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
    // Previous summon attempts never exhaust a *new* summon, even when its
    // observed spellbook starts with the same revision number.
    {
        auto newSummon = c;
        newSummon.Pet.SummonGeneration++;
        newSummon.Pet.ServerToken[4] = 0xF2;
        Check(Decide(yes, newSummon, budget) == Verdict::ApplyOn,
            "old summon budget cannot block same birth new summon");
        RecordAttempt(budget, yes, newSummon);
        RecordAttempt(budget, yes, newSummon);
        Check(Decide(yes, newSummon, budget) == Verdict::NoWrite,
            "new summon also bounded to two attempts");
    }
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

    // If IP toggles/relearns repeatedly, every book revision must not
    // create unlimited retries. Cap at 2 per revision AND 20 per summon/choice.
    {
        auto oscillating = Current();
        auto accepted = Manual();
        AttemptBudget cap;
        for (uint64_t rev = 1; rev <= 10; ++rev)
        {
            oscillating.BookRevision = rev;
            for (unsigned j = 0; j < 2; ++j)
            {
                Check(Decide(accepted, oscillating, cap) == Verdict::ApplyOn,
                    "attempt within bounded IP loop");
                RecordAttempt(cap, accepted, oscillating);
            }
            Check(Decide(accepted, oscillating, cap) == Verdict::NoWrite,
                "same book revision never gets third attempt");
        }
        oscillating.BookRevision = 11;
        Check(cap.TotalAttempts == 20 && Decide(accepted, oscillating, cap) == Verdict::NoWrite,
            "global per-summon choice ceiling survives new IP rank revision");
        accepted.Revision++;
        accepted.Enable = false;
        oscillating.LatestAcceptedRevision++;
        oscillating.EnabledNow = true;
        Check(Decide(accepted, oscillating, cap) == Verdict::ApplyOff,
            "newer human OFF has independent budget after prior ON saturation");
        RecordAttempt(cap, accepted, oscillating);
        Check(cap.TotalAttempts == 1, "newer accepted manual revision resets total");
        auto resummoned = oscillating;
        resummoned.Pet.SummonGeneration++;
        resummoned.Pet.ServerToken[5] = 0xAA;
        Check(Decide(accepted, resummoned, cap) == Verdict::ApplyOff,
            "new certified incarnation has a separate bounded budget");
    }

    // Part27 adversarial multi-chain case: the old single shared mutable
    // AttemptBudget resets whenever the chain changes (60+ writes possible).
    // The new caller-owned ledger must independently cap each chain.
    {
        AttemptLedger ledger;
        auto bite = Manual();
        auto claw = Manual();
        claw.SpellChain = 16827;       // synthetic second chain
        auto biteNow = Current();
        auto clawNow = Current();
        clawNow.AllowedSpellChain = 16827;
        clawNow.AllowedSpellId = 16828;
        for (uint64_t rev = 1; rev <= 10; ++rev)
        {
            biteNow.BookRevision = rev;
            clawNow.BookRevision = rev;
            for (unsigned attempt = 0; attempt < 2; ++attempt)
            {
                Check(DecideTracked(bite, biteNow, ledger) == Verdict::ApplyOn,
                    "first chain retains separate attempts");
                Check(RecordTrackedAttempt(ledger, bite, biteNow),
                    "record first chain in bounded ledger");
                Check(DecideTracked(claw, clawNow, ledger) == Verdict::ApplyOn,
                    "second chain retains separate attempts");
                Check(RecordTrackedAttempt(ledger, claw, clawNow),
                    "record second chain in bounded ledger");
            }
            Check(DecideTracked(bite, biteNow, ledger) == Verdict::NoWrite,
                "first chain has no third try in same book");
            Check(DecideTracked(claw, clawNow, ledger) == Verdict::NoWrite,
                "second chain has no third try in same book");
        }
        biteNow.BookRevision = 11;
        clawNow.BookRevision = 11;
        Check(DecideTracked(bite, biteNow, ledger) == Verdict::NoWrite,
            "interleaved first chain still capped at twenty");
        Check(DecideTracked(claw, clawNow, ledger) == Verdict::NoWrite,
            "interleaved second chain still capped at twenty");
        // Fresh manual OFF on Bite is not consumed by the previous ON.
        auto off = bite;
        off.Revision++;
        off.Enable = false;
        biteNow.LatestAcceptedRevision++;
        biteNow.EnabledNow = true;
        Check(DecideTracked(off, biteNow, ledger) == Verdict::ApplyOff,
            "new manual OFF available after old ON hit cap");
        Check(RecordTrackedAttempt(ledger, off, biteNow),
            "new OFF records its own fresh revision budget");
        Check(DecideTracked(claw, clawNow, ledger) == Verdict::NoWrite,
            "new Bite OFF does not erase exhausted Claw budget");
        auto reSummoned = clawNow;
        reSummoned.Pet.SummonGeneration++;
        reSummoned.Pet.ServerToken[3]++;
        Check(DecideTracked(claw, reSummoned, ledger) == Verdict::ApplyOn,
            "verified new incarnation receives a fresh budget");
        Check(RecordTrackedAttempt(ledger, claw, reSummoned),
            "new incarnation safely resets previous chain records");
    }

    // Bounded-memory failure is a NO-WRITE, not LRU eviction of a distinct
    // chain's still active attempt history.
    {
        AttemptLedger bounded;
        for (uint32_t chain = 1; chain <= kMaxTrackedChainsPerIncarnation; ++chain)
        {
            auto intent = Manual();
            auto observation = Current();
            intent.SpellChain = chain;
            observation.AllowedSpellChain = chain;
            observation.AllowedSpellId = chain;
            Check(RecordTrackedAttempt(bounded, intent, observation),
                "fill finite source-only chain ledger");
        }
        auto extraIntent = Manual();
        auto extraObs = Current();
        extraIntent.SpellChain = 100000;
        extraObs.AllowedSpellChain = 100000;
        extraObs.AllowedSpellId = 100000;
        Check(DecideTracked(extraIntent, extraObs, bounded) == Verdict::NoWrite,
            "unknown 33rd chain fails closed with full ledger");
        Check(!RecordTrackedAttempt(bounded, extraIntent, extraObs),
            "full ledger cannot record overflow attempt");
    }
    // Never infer real-human proof from a typed boolean on the wire:
    // Owner and TrustedManualReceipt are out-of-band *unresolved* production inputs.
    std::cout << "A02 source-only intent fence: " << checked - failed
              << "/" << checked << " assertions passed (not gameplay)\n";
    return failed ? 1 : 0;
}
