/*
 * Naxxramas Core
 *
 * Cross-map aura removal queue (#114 follow-up).
 *
 * Bot consumable cleanup can run on the master's map thread while a bot
 * is still on another map, which another worker is updating. Touching
 * that bot's auras there is a data race. Instead, the master's thread
 * records small identifiers here, and the world thread removes the auras
 * after all map workers have finished.
 *
 * Stale-work safety: each (bot, spell, pet) key carries a generation that
 * the module bumps whenever it applies or takes ownership of that aura.
 * A queued removal keeps the generation it saw when it was queued, and is
 * dropped if the module re-applied the aura in the meantime. A delayed
 * removal therefore never strips a newer module application.
 *
 * Dependency-free so it can be unit-tested without the server.
 */

#ifndef NAXXRAMAS_CORE_CROSS_MAP_AURA_QUEUE_H
#define NAXXRAMAS_CORE_CROSS_MAP_AURA_QUEUE_H

#include <cstddef>
#include <cstdint>
#include <map>
#include <mutex>
#include <tuple>
#include <vector>

namespace NaxxramasCrossMapAura
{
    struct AuraKey
    {
        uint32_t BotGuid = 0;
        uint32_t SpellId = 0;
        bool IsPet = false;

        bool operator<(AuraKey const& other) const
        {
            return std::tie(BotGuid, SpellId, IsPet) <
                std::tie(other.BotGuid, other.SpellId, other.IsPet);
        }

        bool operator==(AuraKey const& other) const
        {
            return BotGuid == other.BotGuid &&
                SpellId == other.SpellId &&
                IsPet == other.IsPet;
        }
    };

    struct PendingRemoval
    {
        AuraKey Key;
        uint64_t Generation = 0;
    };

    class RemovalQueue
    {
    public:
        // The module applied (or took ownership of) this aura.
        void NoteApplied(AuraKey const& key)
        {
            std::lock_guard<std::mutex> lock(_lock);
            ++_generation[key];
        }

        // Remember to remove this aura later, as of its current generation.
        void Enqueue(AuraKey const& key)
        {
            std::lock_guard<std::mutex> lock(_lock);
            _pending.push_back({ key, CurrentLocked(key) });
        }

        std::size_t PendingCount() const
        {
            std::lock_guard<std::mutex> lock(_lock);
            return _pending.size();
        }

        // Takes every queued removal and calls remove(key) for each one
        // that is still current. The lock is NOT held while remove runs,
        // so it may resolve players, touch auras or even enqueue again
        // (a new entry waits for the next drain). Returns how many
        // removals were attempted.
        template <class Remove>
        std::size_t Drain(Remove&& remove)
        {
            std::vector<PendingRemoval> work;

            {
                std::lock_guard<std::mutex> lock(_lock);
                work.swap(_pending);
            }

            std::size_t attempted = 0;

            for (PendingRemoval const& pending : work)
            {
                if (!IsCurrent(pending))
                    continue;

                remove(pending.Key);
                ++attempted;
            }

            return attempted;
        }

    private:
        bool IsCurrent(PendingRemoval const& pending) const
        {
            std::lock_guard<std::mutex> lock(_lock);
            return CurrentLocked(pending.Key) == pending.Generation;
        }

        uint64_t CurrentLocked(AuraKey const& key) const
        {
            auto itr = _generation.find(key);
            return itr == _generation.end() ? 0 : itr->second;
        }

        mutable std::mutex _lock;
        std::map<AuraKey, uint64_t> _generation;
        std::vector<PendingRemoval> _pending;
    };
}

#endif
