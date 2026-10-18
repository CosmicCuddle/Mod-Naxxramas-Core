/*
 * Proposed Playerbots -> Naxx pet-autocast bridge: STANDALONE TEST MODEL.
 * Not included or registered by Worldserver. No runtime provenance producer,
 * SQL, preference cache, toggling, or other mutable Pet operations.
 */
#ifndef NAXXRAMAS_HUNTER_PET_AUTOCAST_PLAYERBOT_BRIDGE_CONTRACT_H
#define NAXXRAMAS_HUNTER_PET_AUTOCAST_PLAYERBOT_BRIDGE_CONTRACT_H
#include <cstdint>

namespace NaxxramasCore::HunterAutocastPlayerbotBridge
{
    constexpr std::uint16_t ContractVersion = 1;

    enum class Origin : std::uint8_t
    {
        Unknown,
        BotDefault,
        FactoryOrTame,
        OtherAI,
        HypotheticalAuthenticatedMaster
    };
    enum class Verdict : std::uint8_t
    {
        Skip,
        AutomatedObservationOnly,
        MasterCandidateOnly,
        MasterConflictNeedsBotCoordination
    };

    struct Identity
    {
        std::uint64_t processEpoch = 0;
        std::uint64_t botGuid = 0;
        std::uint64_t ownerSessionEpoch = 0;
        std::uint64_t petIncarnation = 0; // NOT PetNumber or an address
        std::uint64_t petEventGeneration = 0;
    };

    [[nodiscard]] constexpr bool SameIdentity(Identity const& a,
        Identity const& b) noexcept
    {
        return a.processEpoch != 0 && a.processEpoch == b.processEpoch &&
            a.botGuid != 0 && a.botGuid == b.botGuid &&
            a.ownerSessionEpoch != 0 &&
                a.ownerSessionEpoch == b.ownerSessionEpoch &&
            a.petIncarnation != 0 &&
                a.petIncarnation == b.petIncarnation &&
            a.petEventGeneration != 0 &&
                a.petEventGeneration == b.petEventGeneration;
    }

    // These bools model proofs a hypothetical *trusted upstream producer*
    // must provide. Setting a bool in Naxx cannot authenticate an actor.
    struct Notification
    {
        std::uint16_t version = 0;
        Identity identity;
        std::uint64_t operationSequence = 0;
        std::uint32_t spellId = 0;
        std::uint32_t rankFamily = 0;
        Origin origin = Origin::Unknown;
        bool trustedProducer = false;
        bool nativeOperationAttempted = false;
        bool nativeChangeApplied = false;
        bool petKnowsLegalRank = false;
        bool nativeAutocastable = false;
        bool ipReconciliationCompleted = false;
        bool beforeNativeOn = false;
        bool afterNativeOn = false;
        bool requestedOn = false;
        bool masterIdentityAndCommandVerified = false;
        bool botDefaultKnown = false;
        bool botDefaultOn = false;
        bool botPolicyOverrideCoordinated = false;
    };

    struct Current
    {
        Identity identity;
        std::uint32_t spellId = 0;
        std::uint32_t rankFamily = 0;
        bool stillSameActivePet = false;
        bool ownerSessionActive = false;
        bool nativeOn = false;
    };

    class Consumer
    {
    public:
        constexpr explicit Consumer(Identity expected) noexcept
            : _expected(expected) { }
        constexpr void Invalidate() noexcept { _invalid = true; }

        [[nodiscard]] constexpr Verdict Review(
            Notification const& event, Current const& now) noexcept
        {
            if (_invalid || event.version != ContractVersion ||
                !SameIdentity(_expected, event.identity) ||
                !SameIdentity(_expected, now.identity) ||
                !now.stillSameActivePet || !now.ownerSessionActive ||
                event.operationSequence == 0 ||
                event.operationSequence <= _lastAcceptedSequence ||
                event.spellId == 0 || event.rankFamily == 0 ||
                event.spellId != now.spellId ||
                event.rankFamily != now.rankFamily ||
                !event.trustedProducer || !event.nativeOperationAttempted ||
                !event.petKnowsLegalRank || !event.nativeAutocastable ||
                !event.ipReconciliationCompleted ||
                event.afterNativeOn != now.nativeOn ||
                // A producer may claim a native change only if BEFORE and
                // AFTER native states actually differ on the same Pet.
                // An idempotent command is not an applied state transition.
                event.nativeChangeApplied !=
                    (event.beforeNativeOn != event.afterNativeOn))
                return Verdict::Skip;

            if (event.origin == Origin::BotDefault ||
                event.origin == Origin::FactoryOrTame ||
                event.origin == Origin::OtherAI)
            {
                _lastAcceptedSequence = event.operationSequence;
                return Verdict::AutomatedObservationOnly;
            }

            if (event.origin != Origin::HypotheticalAuthenticatedMaster ||
                !event.masterIdentityAndCommandVerified ||
                !event.nativeChangeApplied ||
                event.requestedOn != now.nativeOn ||
                !event.botDefaultKnown)
                return Verdict::Skip;

            _lastAcceptedSequence = event.operationSequence;
            if (event.requestedOn != event.botDefaultOn &&
                !event.botPolicyOverrideCoordinated)
                return Verdict::MasterConflictNeedsBotCoordination;

            // Advisory ONLY: not a permission to store state or toggle Pet.
            return Verdict::MasterCandidateOnly;
        }

    private:
        Identity _expected;
        std::uint64_t _lastAcceptedSequence = 0;
        bool _invalid = false;
    };
}
#endif
