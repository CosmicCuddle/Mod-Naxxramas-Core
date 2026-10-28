#ifndef NAXXRAMAS_CORE_PLAYER_IDENTITY_POLICY_H
#define NAXXRAMAS_CORE_PLAYER_IDENTITY_POLICY_H

// F14 P1: who is a human, a Random Playerbot or an AltBot, and should a
// Blood Elf / Draenei row be hidden from a Vanilla-stage observer?
//
// Pure standard C++. Not wired into any hook: nothing in the module includes
// this header yet, so runtime behaviour is unchanged (F14 stays default OFF).
// See docs/research/F14-PLAYER-IDENTITY-CLASSIFIER.md for the source facts
// and the world-thread adapter contract a later, separately reviewed step
// would need.
//
// Fail-closed rule: anything not positively known to be a human is treated
// as "not human". Under the bots-only policy that means the row is hidden,
// exactly as under the hide-all policy.

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <utility>
#include <vector>

namespace NaxxramasPlayerIdentity
{
    constexpr std::uint8_t RACE_BLOODELF = 10;
    constexpr std::uint8_t RACE_DRAENEI = 11;

    enum class Identity : std::uint8_t
    {
        Unknown = 0,  // not positively identified; never shown under policy B
        Human,        // live client socket and no Playerbots AI
        SelfBot,      // live client socket, AI attached, master is itself
        RandomBot,    // no socket, AI attached, in Random Playerbot set
        AltBot,       // no socket, AI attached, not random, not self
    };

    // Facts for one Player, sampled on the world thread while the map
    // workers are idle (World::Update runs ScriptMgr::OnWorldUpdate after
    // MapMgr::Update has waited for them). Map threads never sample these.
    struct Facts
    {
        bool inWorld = false;
        bool hasSession = false;
        bool socketOpen = false;        // !WorldSession::IsSocketClosed()
        bool playerbotsEnabled = false; // sPlayerbotAIConfig.Enabled at sample time
        bool botAiAttached = false;     // GET_PLAYERBOT_AI(player) != nullptr
        bool botMasterIsSelf = false;   // botAI->GetMaster() == player
        bool randomBotListed = false;   // sRandomPlayerbotMgr.IsRandomBot(player)
    };

    // Positive evidence only. Playerbots creates every bot WorldSession with
    // a null socket, so an open socket is the human signal; "no AI attached"
    // alone is negative evidence (it is also what a disabled Playerbots
    // config reports for every bot) and never proves a human.
    constexpr Identity Classify(Facts const& f)
    {
        if (!f.inWorld || !f.hasSession)
            return Identity::Unknown;

        if (f.socketOpen)
        {
            if (f.randomBotListed)
                return Identity::Unknown;          // contradiction
            if (!f.botAiAttached)
                return Identity::Human;
            if (f.botMasterIsSelf)
                return Identity::SelfBot;
            return Identity::Unknown;              // socket owned, AI mastered elsewhere
        }

        // No socket: a bot, or a human in the logout grace period.
        if (!f.playerbotsEnabled || !f.botAiAttached || f.botMasterIsSelf)
            return Identity::Unknown;
        return f.randomBotListed ? Identity::RandomBot : Identity::AltBot;
    }

    enum class Policy : std::uint8_t
    {
        HideAllTbcRaces = 0, // (A) every Blood Elf / Draenei row is hidden
        HideBotsOnly = 1,    // (B) provisional: positively-human rows stay visible
    };

    // Unknown config values fall back to (A), the stricter policy.
    constexpr Policy ParsePolicy(long long raw)
    {
        return raw == 1 ? Policy::HideBotsOnly : Policy::HideAllTbcRaces;
    }

    struct PolicyConfig
    {
        Policy policy = Policy::HideAllTbcRaces;
        bool selfBotCountsAsHuman = false;     // provisional owner choice; default hide
    };

    constexpr bool IsTbcRace(std::uint8_t race)
    {
        return race == RACE_BLOODELF || race == RACE_DRAENEI;
    }

    // rowIsObserver keeps the observer's own row (F14 R4, owner choice O1).
    constexpr bool HideTbcRow(PolicyConfig const& config, std::uint8_t race,
                              bool rowIsObserver, Identity identity)
    {
        if (!IsTbcRace(race) || rowIsObserver)
            return false;
        if (config.policy != Policy::HideBotsOnly)
            return true;
        if (identity == Identity::Human)
            return false;
        if (identity == Identity::SelfBot && config.selfBotCountsAsHuman)
            return false;
        return true;
    }

    // World-thread writer, any-thread reader. Each publish replaces the whole
    // immutable snapshot; readers copy the shared_ptr under the mutex and
    // then read without it, so a reader never sees a half-built snapshot.
    class IdentityBoard
    {
    public:
        using Clock = std::chrono::steady_clock;
        static constexpr std::size_t MAX_ENTRIES = 32768;

        // Duplicate GUIDs become Unknown; GUID 0 never resolves. More than
        // MAX_ENTRIES rows publishes an invalid snapshot (everything Unknown)
        // rather than a partial one.
        void Publish(Clock::time_point sampledAt,
                     std::vector<std::pair<std::uint32_t, Facts>> const& rows)
        {
            auto next = std::make_shared<Snapshot>();
            next->sampledAt = sampledAt;
            if (rows.size() <= MAX_ENTRIES)
            {
                next->valid = true;
                next->entries.reserve(rows.size());
                for (auto const& [guidLow, facts] : rows)
                {
                    auto const [it, inserted] = next->entries.emplace(guidLow, Classify(facts));
                    if (!inserted)
                        it->second = Identity::Unknown;
                }
            }

            std::lock_guard<std::mutex> lock(_mutex);
            _current = std::move(next);
        }

        void Invalidate()
        {
            std::lock_guard<std::mutex> lock(_mutex);
            _current.reset();
        }

        // A snapshot older than maxAge, or apparently from the future, is not
        // trusted: the row may belong to a player who logged out or in since.
        Identity Lookup(std::uint32_t guidLow, Clock::time_point now,
                        Clock::duration maxAge) const
        {
            std::shared_ptr<Snapshot const> snapshot;
            {
                std::lock_guard<std::mutex> lock(_mutex);
                snapshot = _current;
            }
            if (!snapshot || !snapshot->valid || guidLow == 0)
                return Identity::Unknown;
            if (now < snapshot->sampledAt || now - snapshot->sampledAt > maxAge)
                return Identity::Unknown;
            auto const it = snapshot->entries.find(guidLow);
            return it == snapshot->entries.end() ? Identity::Unknown : it->second;
        }

    private:
        struct Snapshot
        {
            Clock::time_point sampledAt{};
            bool valid = false;
            std::unordered_map<std::uint32_t, Identity> entries;
        };

        mutable std::mutex _mutex;
        std::shared_ptr<Snapshot const> _current;
    };
}

#endif // NAXXRAMAS_CORE_PLAYER_IDENTITY_POLICY_H
