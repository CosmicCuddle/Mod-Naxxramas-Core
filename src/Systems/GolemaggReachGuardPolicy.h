#ifndef NAXXRAMAS_CORE_GOLEMAGG_REACH_GUARD_POLICY_H
#define NAXXRAMAS_CORE_GOLEMAGG_REACH_GUARD_POLICY_H

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <memory>
#include <vector>

// Pure standard-C++ policy for the Golemagg reach-melee guard. It has no
// AzerothCore or Playerbots dependencies so it can be tested on its own.
namespace NaxxramasGolemaggReachGuard
{
    constexpr std::uint32_t MOLTEN_CORE_MAP = 409;
    constexpr std::uint32_t GOLEMAGG_ENTRY = 11988;
    constexpr std::uint32_t MAGMA_SPLASH_SPELL = 13880;
    // Mirrors Playerbots MCHelpers.h MAGMA_SPLASH_BACK_OFF_STACKS.
    constexpr std::uint32_t MAGMA_SPLASH_BACK_OFF_STACKS = 20;
    // Playerbots stops Magma Splash management at or below 10% boss health.
    constexpr float BURN_PHASE_HEALTH_PCT = 10.0f;
    constexpr char const* REACH_MELEE_ACTION = "reach melee";

    // Everything the guard needs to decide one "reach melee" attempt.
    struct ReachMeleeContext
    {
        bool enabled = false;
        bool botAlive = false;
        std::uint32_t mapId = 0;
        bool isAltBot = false;
        bool isTank = false;
        bool isDps = false;
        bool isMelee = false;
        bool nameAllowed = false;
        bool targetPresent = false;
        std::uint32_t targetEntry = 0;
        bool targetAlive = false;
        bool targetInCombat = false;
        float targetHealthPct = 0.0f;
        std::uint32_t magmaSplashStacks = 0;
    };

    // True only when Playerbots' own Golemagg back-off conditions hold, so
    // walking back into melee would conflict with the back-off. Any missing
    // or unexpected input allows the action.
    inline bool ShouldDenyReachMelee(ReachMeleeContext const& c)
    {
        return c.enabled &&
               c.botAlive &&
               c.mapId == MOLTEN_CORE_MAP &&
               c.isAltBot &&
               !c.isTank && c.isDps && c.isMelee &&
               c.nameAllowed &&
               c.targetPresent &&
               c.targetEntry == GOLEMAGG_ENTRY &&
               c.targetAlive &&
               c.targetInCombat &&
               c.targetHealthPct > BURN_PHASE_HEALTH_PCT &&
               c.magmaSplashStacks >= MAGMA_SPLASH_BACK_OFF_STACKS;
    }

    // Shared liveness flag between a registered listener and the per-Player
    // record. Playerbots deletes listeners together with their engine, and
    // the listener destructor clears the flag.
    using LivenessToken = std::shared_ptr<std::atomic<bool>>;

    // Per-Player bookkeeping so each bot AI's combat engine receives exactly
    // one listener. Templated so it can be tested with stand-in types.
    template <typename AI, typename EngineT>
    struct RegistrationRecord
    {
        AI const* ai = nullptr;
        std::vector<EngineT const*> engines;
        LivenessToken alive;
    };

    // Returns true when the caller must attach a new listener to `engine`,
    // and records it. A different AI object, or a token cleared by a deleted
    // listener, starts a fresh record (Playerbots can replace a live
    // Player's AI, and a new AI may reuse a freed address).
    template <typename AI, typename EngineT>
    bool NeedsRegistration(RegistrationRecord<AI, EngineT>& record, AI const* ai, EngineT const* engine)
    {
        if (!ai || !engine)
            return false;

        if (record.ai != ai || !record.alive || !record.alive->load())
        {
            record.ai = ai;
            record.engines.clear();
            record.alive = std::make_shared<std::atomic<bool>>(true);
        }

        if (std::find(record.engines.begin(), record.engines.end(), engine) != record.engines.end())
            return false;

        record.engines.push_back(engine);
        return true;
    }
}

#endif // NAXXRAMAS_CORE_GOLEMAGG_REACH_GUARD_POLICY_H
