// P7: native tests for src/Systems/ConfigFlagSnapshot.h. Build with -pthread.
#include "ConfigFlagSnapshot.h"

#include <atomic>
#include <cstdio>
#include <thread>
#include <vector>

namespace
{
    constexpr int EXPECTED_CHECKS = 9;
    int failures = 0;
    int checks = 0;

#define CHECK(cond)                                                          \
    do                                                                       \
    {                                                                        \
        ++checks;                                                            \
        if (!(cond))                                                         \
        {                                                                    \
            ++failures;                                                      \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);      \
        }                                                                    \
    } while (0)

    // Same shape as BotTalentCompletion: default false until the first
    // config load, then whatever each load stores.
    NaxxramasConfigSnapshot::Flag Setting{false};
}

int main()
{
    CHECK(!Setting.Load());                     // before startup config load: the old default
    Setting.Store(true);                        // startup load with Enabled = 1
    CHECK(Setting.Load());
    Setting.Store(false);                       // .reload config with Enabled = 0
    CHECK(!Setting.Load());
    Setting.Store(true);
    CHECK(Setting.Load());

    NaxxramasConfigSnapshot::Flag defaultOn{true};
    CHECK(defaultOn.Load());
    CHECK(std::atomic<bool>{}.is_lock_free());

    // One world-thread writer, eight map-thread readers (MapUpdate.Threads=8).
    // Run under -fsanitize=thread to prove there is no data race.
    std::atomic<bool> stop{false};
    std::atomic<long> trues{0};
    std::atomic<long> falses{0};
    std::vector<std::thread> readers;
    for (int r = 0; r < 8; ++r)
        readers.emplace_back([&] {
            while (!stop.load(std::memory_order_acquire))
                (Setting.Load() ? trues : falses).fetch_add(1, std::memory_order_relaxed);
        });
    for (int i = 0; i < 20000; ++i)
        Setting.Store(i % 2 == 0);
    stop.store(true, std::memory_order_release);
    for (auto& t : readers)
        t.join();
    CHECK(trues.load() + falses.load() > 0);
    Setting.Store(false);
    CHECK(!Setting.Load());
    Setting.Store(true);
    CHECK(Setting.Load());

    if (checks != EXPECTED_CHECKS)
    {
        std::printf("COUNT DRIFT: ran %d checks, expected %d\n", checks, EXPECTED_CHECKS);
        return 1;
    }
    if (failures != 0)
    {
        std::printf("FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    std::printf("PASS: config flag snapshot, %d checks\n", checks);
    return 0;
}
