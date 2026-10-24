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
 * the module bumps BEFORE it applies or takes ownership of that aura.
 * A queued removal keeps the generation it saw when it was queued, and is
 * dropped if the generation moved on. The check and the removal are not
 * done under the lock (the remover touches game objects), so the key is
 * marked "being removed" in between: NoteApplied for that key waits until
 * the removal has finished. Every module application is therefore either
 * seen by the check (removal skipped) or happens after the removal (the
 * new aura survives).
 *
 * The remover must not call NoteApplied for the key it is removing.
 *
 * Dependency-free so it can be unit-tested without the server.
 */

#ifndef NAXXRAMAS_CORE_CROSS_MAP_AURA_QUEUE_H
#define NAXXRAMAS_CORE_CROSS_MAP_AURA_QUEUE_H

#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <map>
#include <mutex>
#include <optional>
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
        // Opaque identity of the unit that received the aura (for a pet,
        // its GUID at application time). Passed to the remover unchanged.
        uint64_t TargetToken = 0;
    };

    class RemovalQueue
    {
    public:
        // Call BEFORE the module applies (or takes ownership of) this aura.
        // Waits while the drain is removing this exact key.
        void NoteApplied(AuraKey const& key)
        {
            std::unique_lock<std::mutex> lock(_lock);
            auto notBeingRemoved = [&]()
            {
                return !_removing || !(*_removing == key);
            };

            if (!notBeingRemoved())
            {
                // Counted under the lock before waiting, so an observer
                // that sees the count knows this call is committed to wait.
                ++_blockedNotes;
                _removalDone.wait(lock, notBeingRemoved);
                --_blockedNotes;
            }

            ++_generation[key];
        }

        // How many NoteApplied calls are currently waiting for a removal.
        // Used by tests to build a deterministic interleaving.
        std::size_t BlockedNoteCount() const
        {
            std::lock_guard<std::mutex> lock(_lock);
            return _blockedNotes;
        }

        // Remember to remove this aura later, as of its current generation.
        void Enqueue(AuraKey const& key, uint64_t targetToken = 0)
        {
            std::lock_guard<std::mutex> lock(_lock);
            _pending.push_back({ key, CurrentLocked(key), targetToken });
        }

        std::size_t PendingCount() const
        {
            std::lock_guard<std::mutex> lock(_lock);
            return _pending.size();
        }

        // Takes every queued removal and calls remove(key, targetToken)
        // for each one
        // that is still current. The lock is NOT held while remove runs,
        // so it may resolve players, touch auras or even enqueue again
        // (a new entry waits for the next drain). While remove runs, the
        // key is marked as being removed so a concurrent NoteApplied for
        // it waits. Returns how many removals were attempted.
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
                if (!BeginRemovalIfCurrent(pending))
                    continue;

                // Clears the mark even if remove throws, so a waiting
                // NoteApplied can never block forever.
                struct EndRemovalGuard
                {
                    RemovalQueue& Queue;
                    ~EndRemovalGuard() { Queue.EndRemoval(); }
                } guard{ *this };

                remove(pending.Key, pending.TargetToken);
                ++attempted;
            }

            return attempted;
        }

    private:
        // Check and mark in one critical section, so no NoteApplied can
        // slip in between the check and the removal.
        bool BeginRemovalIfCurrent(PendingRemoval const& pending)
        {
            std::lock_guard<std::mutex> lock(_lock);

            if (CurrentLocked(pending.Key) != pending.Generation)
                return false;

            _removing = pending.Key;
            return true;
        }

        void EndRemoval()
        {
            {
                std::lock_guard<std::mutex> lock(_lock);
                _removing.reset();
            }

            _removalDone.notify_all();
        }

        uint64_t CurrentLocked(AuraKey const& key) const
        {
            auto itr = _generation.find(key);
            return itr == _generation.end() ? 0 : itr->second;
        }

        mutable std::mutex _lock;
        std::condition_variable _removalDone;
        std::optional<AuraKey> _removing;
        std::size_t _blockedNotes = 0;
        std::map<AuraKey, uint64_t> _generation;
        std::vector<PendingRemoval> _pending;
    };
}

#endif
