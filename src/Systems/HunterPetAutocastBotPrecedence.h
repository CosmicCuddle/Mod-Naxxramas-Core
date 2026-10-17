/*
 * Hunter Playerbot autocast precedence - independent research model ONLY.
 * NOT wired to AzerothCore, Playerbots, IP, or Naxx runtime.
 * No native spell changes or persistence. Every verdict is advisory.
 */
#ifndef NAXXRAMAS_HUNTER_PET_AUTOCAST_BOT_PRECEDENCE_H
#define NAXXRAMAS_HUNTER_PET_AUTOCAST_BOT_PRECEDENCE_H
#include <cstdint>

namespace NaxxramasCore::HunterAutocastBotPrecedence
{
    enum class CommandSource : std::uint8_t
    {
        NoneOrUnknown,
        PreHandlerPacket,
        HypotheticalVerifiedMasterCommand
    };

    enum class Verdict : std::uint8_t
    {
        Skip,
        ObserveBotPolicyMatch,
        ObserveBotPolicyMismatch,
        MasterMatchesBotPolicy,
        MasterConflictNeedsCoordination
    };

    struct Evidence
    {
        bool hunterBotVerified = false;
        bool correctActivePet = false;
        bool legalKnownRankUnderIP = false;
        bool nativeAutocastable = false;
        bool postIPReconciliationVerified = false;
        bool botDefaultPolicyKnown = false;
        bool botDefaultOn = false;
        bool observedNativeOn = false;
        CommandSource command = CommandSource::NoneOrUnknown;
        bool masterActorAuthenticated = false;
        bool commandAppliedToExactPetAndSpell = false;
        bool requestedOn = false;
    };

    [[nodiscard]] constexpr Verdict Evaluate(Evidence const& e) noexcept
    {
        // A model cannot *create* these proofs. No production producer exists.
        if (!e.hunterBotVerified || !e.correctActivePet ||
            !e.legalKnownRankUnderIP || !e.nativeAutocastable ||
            !e.postIPReconciliationVerified || !e.botDefaultPolicyKnown)
            return Verdict::Skip;

        if (e.command == CommandSource::NoneOrUnknown)
            return e.observedNativeOn == e.botDefaultOn
                ? Verdict::ObserveBotPolicyMatch
                : Verdict::ObserveBotPolicyMismatch;

        // Packet-format command alone is not a master instruction.
        if (e.command != CommandSource::HypotheticalVerifiedMasterCommand ||
            !e.masterActorAuthenticated ||
            !e.commandAppliedToExactPetAndSpell ||
            e.observedNativeOn != e.requestedOn)
            return Verdict::Skip;

        // A compatible choice needs no extra bot-policy override.
        if (e.requestedOn == e.botDefaultOn)
            return Verdict::MasterMatchesBotPolicy;

        // A conflicting choice needs explicit coordination with Playerbots.
        // Even when policy is believed inactive, the model cannot authorize
        // modifying Pet, AI, IP or stored preferences.
        return Verdict::MasterConflictNeedsCoordination;
    }
}
#endif
