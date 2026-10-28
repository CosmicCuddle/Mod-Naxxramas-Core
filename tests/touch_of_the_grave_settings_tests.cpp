// P6: native tests for src/Racials/Forsaken/TouchOfTheGraveSettings.h.
// Pure standard C++; build with -pthread.
//
// OldMultiplier below is the main 80e9de1 GetProgressionMultiplier logic
// (TouchOfTheGrave.cpp L60-L153) with its two sConfigMgr reads turned into
// parameters and nothing else changed. The new code must agree exactly.
#include "TouchOfTheGraveSettings.h"

#include <atomic>
#include <cstdio>
#include <thread>
#include <vector>

using namespace NaxxramasTouchOfTheGrave;

namespace
{
    constexpr int EXPECTED_CHECKS = 2503139; // 2*21*21*86*11*3 grid + 23 named
    int failures = 0;
    int checks = 0;

#define CHECK(cond)                                                          \
    do                                                                       \
    {                                                                        \
        ++checks;                                                            \
        if (!(cond))                                                         \
        {                                                                    \
            ++failures;                                                      \
            if (failures < 20)                                               \
                std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
        }                                                                    \
    } while (0)

    // ---- verbatim reference (main 80e9de1) ------------------------------
    bool OldHasPassedProgression(std::uint8_t progression, std::uint8_t requiredProgression,
                                 std::uint8_t progressionLimit)
    {
        if (!requiredProgression)
            return false;

        if (progressionLimit &&
            requiredProgression > progressionLimit)
        {
            return false;
        }

        return progression >= requiredProgression;
    }

    float OldMultiplier(bool enabled /* was sConfigMgr IndividualProgression.Enable */,
                        std::uint8_t progressionLimit /* was sConfigMgr ProgressionLimit */,
                        std::uint8_t progression, std::uint8_t level,
                        float vanillaAdjustment, float tbcAdjustment)
    {
        if (!enabled)
            return 1.0f;

        if (!OldHasPassedProgression(progression, 8, progressionLimit))
        {
            if (level <= 10)
                return 1.0f;

            float adjustmentApplyPercent =
                (float(level) - 10.0f) / 50.0f;

            return 1.0f -
                ((1.0f - vanillaAdjustment) *
                 adjustmentApplyPercent);
        }

        if (!OldHasPassedProgression(progression, 13, progressionLimit))
            return tbcAdjustment;

        return 1.0f;
    }
    // ----------------------------------------------------------------------

    bool SameBits(float a, float b) { return a == b || (a != a && b != b); }

    void TestEquivalenceGrid()
    {
        float const adjustments[] = {0.0f, 0.1f, 0.25f, 0.5f, 0.6f, 0.75f, 0.9f, 1.0f, 1.2f, 2.0f, -0.5f};
        for (bool enabled : {false, true})
            for (unsigned limit = 0; limit <= 20; ++limit)
                for (unsigned progression = 0; progression <= 20; ++progression)
                    for (unsigned level = 0; level <= 85; ++level)
                        for (float v : adjustments)
                            for (float t : {0.5f, 0.75f, 1.0f})
                            {
                                auto const l8 = static_cast<std::uint8_t>(limit);
                                auto const p8 = static_cast<std::uint8_t>(progression);
                                auto const lv = static_cast<std::uint8_t>(level);
                                CHECK(SameBits(ProgressionMultiplier(enabled, l8, p8, lv, v, t),
                                               OldMultiplier(enabled, l8, p8, lv, v, t)));
                            }
    }

    void TestKnownValues()
    {
        // Vanilla, no progression: level 60 applies the full adjustment.
        CHECK(ProgressionMultiplier(true, 0, 0, 60, 0.5f, 0.75f) == 0.5f);
        // Level 35 is halfway: 1 - 0.5 * 0.5.
        CHECK(ProgressionMultiplier(true, 0, 0, 35, 0.5f, 0.75f) == 0.75f);
        // Level 10 and below: no adjustment.
        CHECK(ProgressionMultiplier(true, 0, 0, 10, 0.5f, 0.75f) == 1.0f);
        // TBC band 8..12 uses the TBC adjustment; 13+ is WotLK.
        CHECK(ProgressionMultiplier(true, 0, 8, 70, 0.5f, 0.75f) == 0.75f);
        CHECK(ProgressionMultiplier(true, 0, 12, 70, 0.5f, 0.75f) == 0.75f);
        CHECK(ProgressionMultiplier(true, 0, 13, 80, 0.5f, 0.75f) == 1.0f);
        // A progression limit below the stage keeps the earlier band.
        CHECK(ProgressionMultiplier(true, 7, 18, 60, 0.5f, 0.75f) == 0.5f);
        CHECK(ProgressionMultiplier(true, 12, 18, 70, 0.5f, 0.75f) == 0.75f);
        // Disabled: always 1.
        CHECK(ProgressionMultiplier(false, 0, 0, 60, 0.5f, 0.75f) == 1.0f);
        // A zero requirement never counts as passed, even at stage 18.
        CHECK(!HasPassedProgression(18, 0, 0));
        CHECK(!HasPassedProgression(0, 0, 18));
    }

    void TestSnapshotDefaultsAndReload()
    {
        SettingsSnapshot snap;
        IpSettings const before = snap.Load();
        // Before the first config load the snapshot equals the old
        // sConfigMgr defaults: Enable=true, limit 0, all adjustments 1.0.
        CHECK(before.enabled && before.progressionLimit == 0);
        CHECK(before.vanillaPower == 1.0f && before.tbcPower == 1.0f);
        CHECK(before.vanillaHealing == 1.0f && before.tbcHealing == 1.0f);

        IpSettings loaded;
        loaded.enabled = false;
        loaded.progressionLimit = 12;
        loaded.vanillaPower = 0.6f;
        loaded.tbcPower = 0.8f;
        loaded.vanillaHealing = 0.55f;
        loaded.tbcHealing = 0.85f;
        snap.Store(loaded);
        IpSettings const after = snap.Load();
        CHECK(!after.enabled && after.progressionLimit == 12);
        CHECK(after.vanillaPower == 0.6f && after.tbcPower == 0.8f);
        CHECK(after.vanillaHealing == 0.55f && after.tbcHealing == 0.85f);

        // .reload config: a second Store fully replaces the first.
        IpSettings reloaded;
        reloaded.vanillaHealing = 0.4f;
        snap.Store(reloaded);
        IpSettings const again = snap.Load();
        CHECK(again.enabled && again.progressionLimit == 0 && again.vanillaPower == 1.0f);
        CHECK(again.vanillaHealing == 0.4f);
    }

    void TestLockFree()
    {
        CHECK(std::atomic<float>{}.is_lock_free());
        CHECK(std::atomic<std::uint8_t>{}.is_lock_free());
        CHECK(std::atomic<bool>{}.is_lock_free());
    }

    // One world-thread writer, eight map-thread readers (MapUpdate.Threads=8).
    // Under -fsanitize=thread this proves there is no data race; every read
    // value must be one that was written.
    void TestConcurrentReloadAndReads()
    {
        SettingsSnapshot snap;
        std::atomic<bool> stop{false};
        std::atomic<int> bad{0};
        std::vector<std::thread> readers;
        for (int r = 0; r < 8; ++r)
            readers.emplace_back([&] {
                while (!stop.load(std::memory_order_acquire))
                {
                    IpSettings const s = snap.Load();
                    if (s.vanillaPower != 1.0f && s.vanillaPower != 0.5f)
                        bad.fetch_add(1);
                    if (s.progressionLimit != 0 && s.progressionLimit != 12)
                        bad.fetch_add(1);
                }
            });
        IpSettings a;
        IpSettings b;
        b.vanillaPower = 0.5f;
        b.progressionLimit = 12;
        for (int i = 0; i < 20000; ++i)
            snap.Store(i % 2 ? a : b);
        stop.store(true, std::memory_order_release);
        for (auto& t : readers)
            t.join();
        CHECK(bad.load() == 0);
    }
}

int main()
{
    TestEquivalenceGrid();
    TestKnownValues();
    TestSnapshotDefaultsAndReload();
    TestLockFree();
    TestConcurrentReloadAndReads();
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
    std::printf("PASS: Touch of the Grave settings, %d checks\n", checks);
    return 0;
}
