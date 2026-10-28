#ifndef NAXXRAMAS_CORE_CONFIG_FLAG_SNAPSHOT_H
#define NAXXRAMAS_CORE_CONFIG_FLAG_SNAPSHOT_H

// A boolean setting read on the world thread (WorldScript::OnAfterConfigLoad,
// at startup and on every .reload config) and read lock-free from any thread.
// Map-thread hooks must use this instead of calling sConfigMgr themselves.

#include <atomic>

namespace NaxxramasConfigSnapshot
{
    class Flag
    {
    public:
        constexpr explicit Flag(bool initial) : _value(initial) {}

        void Store(bool value) { _value.store(value, std::memory_order_relaxed); }
        bool Load() const { return _value.load(std::memory_order_relaxed); }

    private:
        std::atomic<bool> _value;
    };
}

#endif // NAXXRAMAS_CORE_CONFIG_FLAG_SNAPSHOT_H
