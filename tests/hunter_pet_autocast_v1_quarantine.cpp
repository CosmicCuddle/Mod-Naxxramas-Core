#include "HunterPetAutocastAddon.h"
#include <iostream>
#include <memory>
#include <string>

using namespace NaxxramasHunterPetAutocast;

namespace
{
    int checks = 0;
    int failures = 0;
    void Check(bool value, char const* message)
    {
        ++checks;
        if (!value)
        {
            ++failures;
            std::cerr << "FAIL: " << message << "\n";
        }
    }

    SpellLookup Lookup(uint32_t spell, void const*)
    {
        SpellLookup result;
        if (spell == 1742 || spell == 17259)
        {
            result.Autocastable = true;
            result.ChainId = spell == 17259 ? 17253 : spell;
        }
        return result;
    }

    bool Receive(OptInStore& store, uint64_t player, uint32_t seq,
                 bool enabled, uint64_t now)
    {
        std::string const message = "NXCPAK\tv1|" + std::to_string(seq) +
                                    "|1/1|17259=" + (enabled ? "1" : "0");
        return store.Accept(player, true, message, now, &Lookup, nullptr)
            == IngestResult::Published;
    }
}

int main()
{
    OptInStore store;
    std::shared_ptr<PreferenceSnapshot const> pref;
    uint64_t const guidA = 31, guidB = 32;

    Check(!EligibleForAutomaticRestore(nullptr), "no snapshot cannot apply");
    Check(Receive(store, guidA, 1, true, 100), "well-formed v1 ON still parses");
    Check(store.Read(guidA, pref) != 0, "published v1 sequence readable");
    Check(bool(pref), "snapshot present");
    if (pref)
    {
        Check(pref->OptedIn, "v1 opt-in still parses for diagnostic research");
        Check(!pref->VerifiedHumanManualOrigin, "v1 ON cannot prove manual human authority");
        Check(!EligibleForAutomaticRestore(pref.get()), "v1 ON cannot authorize restoration");
        Check(pref->Choices.size() == 1, "legacy choice remains available without enabling writes");
    }

    Check(Receive(store, guidA, 2, false, 200), "well-formed v1 OFF publishes");
    store.Read(guidA, pref);
    Check(bool(pref) && pref->Choices.size() == 1, "OFF stored as one choice");
    if (pref)
    {
        Check(!pref->Choices[0].Enabled, "most recent v1 OFF value decodes");
        Check(!pref->VerifiedHumanManualOrigin, "v1 OFF also lacks manual authority");
        Check(!EligibleForAutomaticRestore(pref.get()), "v1 OFF cannot authorize restoration");
    }

    Check(Receive(store, guidB, 1, true, 300), "second player ON");
    store.Read(guidB, pref);
    Check(bool(pref) && !EligibleForAutomaticRestore(pref.get()), "other player's v1 remains quarantined");

    store.OnLogin(guidA);
    store.Read(guidA, pref);
    Check(bool(pref) && !EligibleForAutomaticRestore(pref.get()), "login-retained v1 snapshot remains unsafe");

    Check(Receive(store, guidA, 1, true, 400), "new login v1 sequence");
    store.Read(guidA, pref);
    Check(bool(pref) && !EligibleForAutomaticRestore(pref.get()), "replayed v1 cannot promote authority");

    store.OnLogout(guidA);
    Check(store.Read(guidA, pref) == 0 && !pref, "logout clears v1 source");
    store.ClearAll();
    Check(store.Read(guidB, pref) == 0 && !pref, "config-off clears v1 source");

    PreferenceSnapshot fabricated;
    fabricated.OptedIn = true;
    Check(!EligibleForAutomaticRestore(&fabricated), "synthetic opt-in flag is insufficient");
    fabricated.VerifiedHumanManualOrigin = true;
    Check(EligibleForAutomaticRestore(&fabricated),
        "gate's hypothetical strong-verified input is a CONTRACT, not a trust attestation");

    std::cout << "A02 v1 fail-closed native contract: " << (checks - failures)
              << "/" << checks << " assertions passed (offline only)\n";
    return failures ? 1 : 0;
}
