#ifndef NAXXRAMAS_CORE_CONSUMABLE_COOLDOWN_STORE_H
#define NAXXRAMAS_CORE_CONSUMABLE_COOLDOWN_STORE_H

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <vector>

// Bot Consumables command cooldowns (#155).
//
// The `.bot consumables` command starts and checks a cooldown on the world
// thread, while a death resets the group's cooldowns from that player's map
// thread, and with MapUpdate.Threads > 1 several maps run at once. The
// cooldown must also outlive logout, so it cannot live on the Player.
//
// One mutex guards only this map. Callers pass plain numbers: the lock is
// never held while calling game code, sending chat or touching a Player or
// Group. Pure standard C++ so it can be tested natively with threads.
namespace NaxxramasConsumables
{
    class CooldownStore
    {
    public:
        // Seconds left for guid at `now`; 0 when there is none. An expired
        // entry is removed, exactly as the previous unlocked code did.
        uint32_t Remaining(uint32_t guid, uint64_t now)
        {
            std::lock_guard<std::mutex> guard(_lock);
            auto itr = _until.find(guid);
            if (itr == _until.end())
                return 0;
            if (itr->second <= now)
            {
                _until.erase(itr);
                return 0;
            }
            return static_cast<uint32_t>(itr->second - now);
        }

        // Starts (or restarts) guid's cooldown until `until`.
        void Start(uint32_t guid, uint64_t until)
        {
            std::lock_guard<std::mutex> guard(_lock);
            _until[guid] = until;
        }

        // A death resets these players' cooldowns. The caller collects the
        // guids first, without this lock.
        void Reset(std::vector<uint32_t> const& guids)
        {
            std::lock_guard<std::mutex> guard(_lock);
            for (uint32_t guid : guids)
                _until.erase(guid);
        }

        std::size_t Size()
        {
            std::lock_guard<std::mutex> guard(_lock);
            return _until.size();
        }

    private:
        std::mutex _lock;
        std::unordered_map<uint32_t, uint64_t> _until;
    };
}

#endif // NAXXRAMAS_CORE_CONSUMABLE_COOLDOWN_STORE_H
