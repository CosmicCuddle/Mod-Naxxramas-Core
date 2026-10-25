// #155 native tests for ConsumableCooldownStore.h (no core headers).
//
// Build: g++ -std=c++17 -Wall -Wextra -Werror -pthread -Isrc/Systems
//        tests/consumable_cooldown_store.cpp
// Under ThreadSanitizer (-fsanitize=thread) the contention test must report
// nothing. Built with -DNAXX_TSAN_NEGATIVE_CONTROL it instead runs the same
// workload on an UNLOCKED map, the shape main 80e9de1 had, which
// ThreadSanitizer must flag; that proves the contention test has teeth.
#include "ConsumableCooldownStore.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <unordered_map>
#include <vector>

namespace
{
    int failures = 0;

    void Check(bool ok, char const* what)
    {
        if (!ok)
        {
            std::printf("FAIL: %s\n", what);
            ++failures;
        }
    }

    // Same semantics as the old unlocked code (main 80e9de1, L433-L508).
    struct UnlockedReference
    {
        std::unordered_map<uint32_t, uint64_t> until;

        uint32_t Remaining(uint32_t guid, uint64_t now)
        {
            auto itr = until.find(guid);
            if (itr == until.end())
                return 0;
            if (itr->second <= now)
            {
                until.erase(itr);
                return 0;
            }
            return static_cast<uint32_t>(itr->second - now);
        }
        void Start(uint32_t guid, uint64_t value) { until[guid] = value; }
        void Reset(std::vector<uint32_t> const& guids)
        {
            for (uint32_t guid : guids)
                until.erase(guid);
        }
    };

    void Semantics()
    {
        NaxxramasConsumables::CooldownStore store;
        Check(store.Remaining(7, 100) == 0, "no cooldown -> 0");
        store.Start(7, 700);
        Check(store.Remaining(7, 100) == 600, "remaining = until - now");
        Check(store.Remaining(7, 699) == 1, "one second left");
        Check(store.Remaining(7, 700) == 0, "expires at until");
        Check(store.Size() == 0, "expired entry removed on read");
        store.Start(7, 700);
        store.Start(7, 1300);
        Check(store.Remaining(7, 100) == 1200, "restart overwrites");
        store.Start(8, 900);
        store.Start(9, 900);
        store.Reset({7, 8, 42});
        Check(store.Remaining(7, 100) == 0 && store.Remaining(8, 100) == 0,
              "group reset clears members");
        Check(store.Remaining(9, 100) == 800, "non-members keep cooldown");
        store.Reset({});
        Check(store.Size() == 1, "empty reset is a no-op");
    }

    // Randomised parity with the unlocked reference, single-threaded.
    void Parity()
    {
        NaxxramasConsumables::CooldownStore store;
        UnlockedReference ref;
        uint32_t seed = 12345;
        auto next = [&seed]() { seed = seed * 1103515245u + 12345u; return seed >> 8; };
        for (int i = 0; i < 20000; ++i)
        {
            uint32_t guid = next() % 32;
            uint64_t now = 1000 + next() % 2000;
            switch (next() % 3)
            {
                case 0:
                    Check(store.Remaining(guid, now) == ref.Remaining(guid, now), "parity remaining");
                    break;
                case 1:
                    store.Start(guid, now + 600);
                    ref.Start(guid, now + 600);
                    break;
                default:
                {
                    std::vector<uint32_t> group = {guid, (guid + 1) % 32, (guid + 5) % 32};
                    store.Reset(group);
                    ref.Reset(group);
                }
            }
            if (failures)
                return;
        }
        Check(store.Size() == ref.until.size(), "parity size");
    }

    template <typename Store>
    void Hammer(Store& store, std::atomic<uint64_t>& sink)
    {
        // 8 workers, as MapUpdate.Threads = 8, plus the world thread pattern.
        std::vector<std::thread> workers;
        for (uint32_t t = 0; t < 8; ++t)
        {
            workers.emplace_back([&store, &sink, t]() {
                uint64_t local = 0;
                for (uint32_t i = 0; i < 20000; ++i)
                {
                    uint32_t guid = (i * 7 + t * 131) % 4096;
                    store.Start(guid, 100 + (i % 50));
                    local += store.Remaining(guid ^ 1, 120);
                    if (i % 16 == 0)
                        store.Reset({guid, guid + 1, guid + 2, guid + 3});
                }
                sink += local;
            });
        }
        for (std::thread& worker : workers)
            worker.join();
    }
}

int main()
{
#ifdef NAXX_TSAN_NEGATIVE_CONTROL
    UnlockedReference unlocked;
    std::atomic<uint64_t> sink{0};
    Hammer(unlocked, sink);
    std::printf("NEGATIVE CONTROL ran (ThreadSanitizer must report a data race)\n");
    return 0;
#else
    Semantics();
    Parity();
    NaxxramasConsumables::CooldownStore store;
    std::atomic<uint64_t> sink{0};
    Hammer(store, sink);
    Check(store.Size() <= 4096, "contention left a bounded, consistent map");
    if (failures)
        return 1;
    std::printf("PASS: cooldown store semantics, parity and 8-thread contention\n");
    return 0;
#endif
}
