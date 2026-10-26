#include "HunterPetAutocastLifetimeBudgetModel.h"
#include <iostream>

using namespace NaxxramasHunterPetAutocast::IntentFence;
using namespace NaxxramasHunterPetAutocast::LifetimeModel;

namespace
{
    int checks = 0;
    int fails = 0;
    void Check(bool ok, char const* why)
    {
        ++checks;
        if (!ok) { ++fails; std::cerr << "FAIL " << why << "\n"; }
    }

    Identity Pet(uint64_t generation = 1, uint8_t birth = 1)
    {
        Identity p;
        p.PlayerGuid = 1200;
        p.PetNumber = 42;
        p.ServerEpoch = 101;
        p.SummonGeneration = generation;
        p.BirthToken[0] = birth; // HYPOTHETICAL trusted token, NOT sourced
        p.ServerToken[0] = 4;
        p.ServerToken[1] = static_cast<uint8_t>(generation);
        return p;
    }

    AcceptedManualChoice Choice(bool enable = true, uint64_t revision = 21,
                                uint32_t chain = 100)
    {
        AcceptedManualChoice c;
        c.Pet = Pet();
        c.Revision = revision;
        c.RevisionDomain = 77;
        c.SpellChain = chain;
        c.Enable = enable;
        c.TrustedManualReceipt = true; // fabricated trusted fixture only
        c.TrustedBirthAtReceipt = true;
        return c;
    }

    CurrentObservation Current(AcceptedManualChoice const& choice, uint64_t generation = 1)
    {
        CurrentObservation s;
        s.Pet = Pet(generation);
        s.LatestAcceptedRevision = choice.Revision;
        s.LatestRevisionDomain = choice.RevisionDomain;
        s.TrustedCurrentBirth = true; // fabricated, NOT real authority
        s.AllowedSpellChain = choice.SpellChain;
        s.AllowedSpellId = choice.SpellChain + 1;
        s.BookRevision = generation + 100;
        s.Owner = OwnerMode::Human; // fabricated, no Playerbots query
        s.ReceiverAuthenticated = true;
        s.AddonOptIn = true;
        s.HasVerifiedClientTransport = true;
        s.NoUnresolvedNewerManualClick = true;
        s.SelectedCurrentPet = true;
        s.RankAllowedByIP = true; // fabricated allowed rank
        s.SpellPresent = true;
        s.SpellAutocastable = true;
        s.SpellbookConsistent = true;
        s.EnabledNow = !choice.Enable;
        return s;
    }
}

int main()
{
    // Mount/dismount/teleport may recreate Pet* for the SAME true birth.
    // 10 incarnations x 2 attempts each = the maximum 20 total, not 200.
    {
        Ledger lifetime;
        AttemptLedger incarnation;
        auto on = Choice();
        for (uint64_t gen = 1; gen <= 10; ++gen)
        {
            auto now = Current(on, gen);
            for (unsigned attempt = 0; attempt < 2; ++attempt)
            {
                Check(DecideWithLifetime(on, now, incarnation, lifetime) == Verdict::ApplyOn,
                      "new incarnation allowed until lifetime ceiling");
                Check(ReserveWithLifetime(on, now, incarnation, lifetime),
                      "pre-toggle reservation counts even when toggle never sticks");
            }
            Check(DecideWithLifetime(on, now, incarnation, lifetime) == Verdict::NoWrite,
                  "per-book/choice limit within current incarnation");
        }
        auto eleventh = Current(on, 11);
        Check(DecideTracked(on, eleventh, incarnation) == Verdict::ApplyOn,
              "baseline per-incarnation policy permits attempt 21");
        Check(DecideWithLifetime(on, eleventh, incarnation, lifetime) == Verdict::NoWrite,
              "global per-choice cap blocks attempt 21 after 10 resummons");
        Check(!ReserveWithLifetime(on, eleventh, incarnation, lifetime),
              "global cap never increments or writes after exhaustion");
        Check(lifetime.Entries[0].Attempts == 20,
              "no count inflation or hidden reset at lifetime ceiling");

        // Other spell chain is independent.
        auto claw = Choice(true, 21, 200);
        auto clawNow = Current(claw, 11);
        Check(ReserveWithLifetime(claw, clawNow, incarnation, lifetime),
              "another chain receives its own lifetime budget");
        Check(lifetime.Entries[1].Attempts == 1, "other chain count stays separate");

        // The newest human OFF (hypothetically accepted) must not inherit
        // old ON retry exhaustion; old ON may never be replayed after it.
        auto off = Choice(false, 22, 100);
        auto offNow = Current(off, 11);
        Check(DecideWithLifetime(off, offNow, incarnation, lifetime) == Verdict::ApplyOff,
              "new OFF has an independent revision allowance");
        Check(ReserveWithLifetime(off, offNow, incarnation, lifetime),
              "new OFF reserves one attempt");
        Check(lifetime.Entries[0].Attempts == 1,
              "new OFF revision resets only its chain lifetime count");
        Check(lifetime.Entries[1].Attempts == 1,
              "new OFF does not reset an unrelated chain");
        auto oldOnNow = Current(on, 11);
        oldOnNow.LatestAcceptedRevision = 22;
        Check(DecideWithLifetime(on, oldOnNow, incarnation, lifetime) == Verdict::NoWrite,
              "stale ON revision denied after later OFF");

        // Replacing the pet with an identical PetNumber is NOT the same birth.
        auto replacement = Choice();
        replacement.Pet = Pet(1, 2);
        auto replacedNow = Current(replacement);
        replacedNow.Pet = Pet(2, 2);
        Check(DecideWithLifetime(on, replacedNow, incarnation, lifetime) == Verdict::NoWrite,
              "old-birth request cannot target recycled PetNumber");
        Check(ReserveWithLifetime(replacement, replacedNow, incarnation, lifetime),
              "new certified birth has separate retry budget");
        Check(lifetime.Entries[2].Attempts == 1,
              "new certified birth does not inherit older birth's counter");

        // No fabricated source of trust is accepted if mandatory gates fail.
        auto unknown = Current(on, 12);
        unknown.TrustedCurrentBirth = false;
        Check(DecideWithLifetime(on, unknown, incarnation, lifetime) == Verdict::NoWrite,
              "unknown current birth fails closed");
        auto untrusted = Choice();
        untrusted.TrustedManualReceipt = false;
        Check(DecideWithLifetime(untrusted, Current(untrusted,12), incarnation, lifetime)
              == Verdict::NoWrite, "untrusted module-only candidate fails closed");
        auto bot = Current(on, 12);
        bot.Owner = OwnerMode::BotOrSelfBot;
        Check(DecideWithLifetime(on, bot, incarnation, lifetime) == Verdict::NoWrite,
              "attached SelfBot mode fails closed");
    }

    // Finite keys must not be evicted to reset a previous choice's budget.
    {
        Ledger full;
        AttemptLedger incarnation;
        for (uint32_t chain = 1; chain <= kMaxLifetimeKeys; ++chain)
        {
            auto ch = Choice(true, 5, chain);
            auto cur = Current(ch);
            Check(ReserveWithLifetime(ch, cur, incarnation, full),
                  "fill a distinct bounded lifetime key");
        }
        auto newChain = Choice(true, 5, 999);
        auto newNow = Current(newChain, 2);
        Check(DecideWithLifetime(newChain, newNow, incarnation, full) == Verdict::NoWrite,
              "unknown 33rd lifetime choice denies after resummon despite freed per-summon slots");
        Check(!ReserveWithLifetime(newChain, newNow, incarnation, full),
              "full lifetime ledger cannot silently evict prior choice");
        auto newRevision = Choice(false, 6, 1);
        auto newerNow = Current(newRevision, 2);
        Check(ReserveWithLifetime(newRevision, newerNow, incarnation, full),
              "existing chain may accept newer OFF despite full ledger");
        Check(full.Entries[0].Attempts == 1,
              "new revision for existing chain does not retain old attempt usage");
    }

    // Important unsolved limitation: an IN-MEMORY budget can be restarted.
    // This positive test is NOT permission to re-enable writes after reboot.
    {
        Ledger freshAfterRestart;
        AttemptLedger freshSummon;
        auto on = Choice();
        Check(DecideWithLifetime(on, Current(on), freshSummon, freshAfterRestart)
              == Verdict::ApplyOn,
              "new empty process loses limit state: persistence remains a blocker");
    }

    std::cout << "A02 cross-incarnation retry model: "
              << checks - fails << "/" << checks
              << " assertions passed (UNWIRED, not gameplay)\n";
    return fails == 0 ? 0 : 1;
}
