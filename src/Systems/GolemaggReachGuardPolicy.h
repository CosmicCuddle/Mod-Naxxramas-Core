#ifndef NAXXRAMAS_CORE_GOLEMAGG_REACH_GUARD_POLICY_H
#define NAXXRAMAS_CORE_GOLEMAGG_REACH_GUARD_POLICY_H

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cstdint>
#include <memory>
#include <string>
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
               c.targetHealthPct > BURN_PHASE_HEALTH_PCT &&
               c.magmaSplashStacks >= MAGMA_SPLASH_BACK_OFF_STACKS;
    }

    // Optional comma-separated character-name list. An empty setting covers
    // every eligible Altbot. A non-empty setting that contains no usable
    // name covers nobody, so a typo never widens the scope.
    class NameFilter
    {
    public:
        static NameFilter Parse(std::string const& raw)
        {
            NameFilter filter;
            if (Trim(raw).empty())
            {
                filter._allowAll = true;
                return filter;
            }

            std::string::size_type start = 0;
            while (start <= raw.size())
            {
                std::string::size_type const comma = raw.find(',', start);
                std::string::size_type const end = comma == std::string::npos ? raw.size() : comma;
                std::string name = Lower(Trim(raw.substr(start, end - start)));
                if (!name.empty())
                    filter._names.push_back(std::move(name));
                if (comma == std::string::npos)
                    break;
                start = comma + 1;
            }
            return filter;
        }

        bool Allows(std::string const& characterName) const
        {
            if (_allowAll)
                return true;
            std::string const lowered = Lower(characterName);
            return std::find(_names.begin(), _names.end(), lowered) != _names.end();
        }

        bool AllowsAll() const { return _allowAll; }
        std::size_t Size() const { return _names.size(); }

    private:
        static std::string Trim(std::string const& value)
        {
            std::string::size_type const first = value.find_first_not_of(" \t\r\n");
            if (first == std::string::npos)
                return std::string();
            std::string::size_type const last = value.find_last_not_of(" \t\r\n");
            return value.substr(first, last - first + 1);
        }

        static std::string Lower(std::string value)
        {
            std::transform(value.begin(), value.end(), value.begin(),
                [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
            return value;
        }

        bool _allowAll = false;
        std::vector<std::string> _names;
    };

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
