// P10: deterministic tests of the REAL src/Systems/HonorReset.cpp schedule.
//
// The production file is compiled unmodified in this translation unit
// against tests/honor_reset_stubs, with the clock wrapped (-Wl,--wrap=time)
// and TZ controlled. Needs glibc and tzdata.
//
// Build: g++ -std=c++17 -Itests/honor_reset_stubs -Isrc/Systems
//          tests/honor_reset_schedule_tests.cpp -Wl,--wrap=time
#include "HonorReset.cpp"

#ifdef P10_OLD_SOURCE
// Red check against main 80e9de1, which has no bound: same value here so
// the tests compile; the old AddWeeks / loop are what get exercised.
namespace { constexpr uint32 MAX_INTERVAL_WEEKS = 306783373u; }
#endif

#include <climits>
#include <cstdio>
#include <cstdlib>

namespace
{
    std::time_t g_now = 0;
}

extern "C" std::time_t __wrap_time(std::time_t* out)
{
    if (out)
        *out = g_now;
    return g_now;
}

namespace
{
    constexpr int EXPECTED_CHECKS = 48; // 9 + 9 + 11 + 5 + 4 + 2 x 5
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

    constexpr std::time_t DAY = 86400;
    constexpr std::time_t WEEK = 7 * DAY;

    void Zone(char const* tz)
    {
        setenv("TZ", tz, 1);
        tzset();
    }

    std::time_t Utc(int y, int mo, int d, int h = 0, int mi = 0, int s = 0)
    {
        std::tm t = {};
        t.tm_year = y - 1900;
        t.tm_mon = mo - 1;
        t.tm_mday = d;
        t.tm_hour = h;
        t.tm_min = mi;
        t.tm_sec = s;
        return timegm(&t);
    }

    // The defaults: Wednesday 2026-10-07 06:00 local, every two weeks.
    void Defaults(uint32 weeks = 2)
    {
        HonorResetIntervalWeeks = weeks;
        HonorResetDayOfWeek = 3;
        HonorResetHour = 6;
        HonorResetMinute = 0;
        HonorResetAnchorDate = "2026-10-07";
        HonorResetNotify = true;
    }

    void TestAddWeeksBounds()
    {
        Zone("UTC");
        CHECK(MAX_INTERVAL_WEEKS == 306783373u);           // (INT_MAX - 31) / 7
        std::time_t const base = Utc(2026, 10, 7, 6);
        CHECK(AddWeeks(base, 1) == base + WEEK);
        CHECK(AddWeeks(base, 2) == base + 2 * WEEK);
        CHECK(AddWeeks(base, 52) == base + 52 * WEEK);
        // The largest accepted interval still moves forward.
        std::time_t const far = AddWeeks(base, MAX_INTERVAL_WEEKS);
        CHECK(far != static_cast<std::time_t>(-1) && far > base);
        // Past the bound, and the old wrapping values: unrepresentable.
        CHECK(AddWeeks(base, MAX_INTERVAL_WEEKS + 1) == static_cast<std::time_t>(-1));
        CHECK(AddWeeks(base, 306783379u) == static_cast<std::time_t>(-1));   // weeks*7 > INT_MAX
        CHECK(AddWeeks(base, 613566757u) == static_cast<std::time_t>(-1));   // weeks*7 wraps to 3 days
        CHECK(AddWeeks(base, UINT32_MAX) == static_cast<std::time_t>(-1)); // weeks*7 wraps to -7 days
    }

    void TestScheduleUtc()
    {
        Zone("UTC");
        Defaults(2);
        std::time_t const anchor = Utc(2026, 10, 7, 6);
        CHECK(GetLatestScheduledReset(anchor - 1) == 0);
        CHECK(GetLatestScheduledReset(anchor) == anchor);
        CHECK(GetLatestScheduledReset(anchor + 2 * WEEK - 1) == anchor);
        CHECK(GetLatestScheduledReset(anchor + 2 * WEEK) == anchor + 2 * WEEK);
        CHECK(GetLatestScheduledReset(anchor + 53 * WEEK) == anchor + 52 * WEEK);

        Defaults(1);
        CHECK(GetLatestScheduledReset(anchor + WEEK + 5) == anchor + WEEK);
        CHECK(GetLatestScheduledReset(anchor + 100 * WEEK + 1) == anchor + 100 * WEEK);

        // Invalid anchor or weekday: no schedule (unchanged behaviour).
        Defaults(2);
        HonorResetAnchorDate = "not-a-date";
        CHECK(GetLatestScheduledReset(anchor + WEEK) == 0);
        Defaults(2);
        HonorResetDayOfWeek = 2;                            // 2026-10-07 is a Wednesday
        CHECK(GetLatestScheduledReset(anchor + WEEK) == 0);
    }

    // The P10 defect: these used to never leave the loop.
    void TestExtremeIntervalsTerminate()
    {
        Zone("UTC");
        std::time_t const anchor = Utc(2026, 10, 7, 6);
        std::time_t const later = Utc(2027, 10, 7, 6);
        for (uint32 weeks : {UINT32_MAX, 613566757u, 306783379u, MAX_INTERVAL_WEEKS + 1, MAX_INTERVAL_WEEKS})
        {
            Defaults(weeks);
            CHECK(GetLatestScheduledReset(later) == anchor);   // only the anchor falls in range
            CHECK(GetLatestScheduledReset(anchor - 1) == 0);
        }
        // An interval of 0 (only reachable by bypassing the config clamp)
        // would not move forward either; the progress guard stops it.
        Defaults(0);
        CHECK(GetLatestScheduledReset(later) == anchor);
    }

    // Local wall-clock time is kept across the BST -> GMT change.
    void TestDstLondon()
    {
        Zone("Europe/London");
        Defaults(2);
        std::time_t const anchor = Utc(2026, 10, 7, 5);     // 06:00 BST
        std::time_t const second = Utc(2026, 10, 21, 5);    // 06:00 BST
        std::time_t const third = Utc(2026, 11, 4, 6);      // 06:00 GMT
        CHECK(GetLatestScheduledReset(anchor) == anchor);
        CHECK(GetLatestScheduledReset(second) == second);
        CHECK(GetLatestScheduledReset(third - 1) == second);
        CHECK(GetLatestScheduledReset(third) == third);
        std::tm local = {};
        CHECK(GetLocalTime(third, local) && local.tm_hour == 6 && local.tm_wday == 3);
    }

    void TestConfigClampUnchanged()
    {
        NaxxramasCoreHonorReset script;
        std::string const p = "NaxxramasCore.HonorReset.";
        StubConfigMgr& cfg = StubConfigMgr::instance();
        cfg.uints = {{p + "IntervalWeeks", 0}};
        script.OnBeforeConfigLoad(false);
        CHECK(HonorResetIntervalWeeks == 1);
        cfg.uints = {{p + "IntervalWeeks", UINT32_MAX}};
        script.OnBeforeConfigLoad(false);
        CHECK(HonorResetIntervalWeeks == UINT32_MAX);        // no new cap is chosen
        cfg.uints = {};
        script.OnBeforeConfigLoad(false);
        CHECK(HonorResetIntervalWeeks == 2 && !HonorResetEnabled);
        CHECK(HonorResetAnchorDate == "2026-10-07" && HonorResetDayOfWeek == 3);
    }

    void TestEndToEnd(uint32 weeks, int expectedAfterYear)
    {
        Zone("UTC");
        CharacterDatabase = StubCharacterDatabase{};
        WorldSession session;
        Player online;
        online.session = &session;                           // notified only with a session
        sWorldSessionMgr->online = {&online};
        StubChatMessages = 0;

        std::string const p = "NaxxramasCore.HonorReset.";
        StubConfigMgr& cfg = StubConfigMgr::instance();
        cfg.bools = {{p + "Enabled", true}};
        cfg.uints = {{p + "IntervalWeeks", weeks}};
        NaxxramasCoreHonorReset script;
        script.OnBeforeConfigLoad(false);

        std::time_t const anchor = Utc(2026, 10, 7, 6);
        g_now = anchor + 3 * DAY;
        script.OnStartup();                                  // catches up the anchor reset
        CHECK(CharacterDatabase.honorResets == 1);
        CHECK(online.honor == 0 && StubChatMessages == 1);
        CHECK(CharacterDatabase.lastReset == static_cast<uint64>(anchor));

        online.honor = 50;
        script.OnUpdate(HONOR_RESET_CHECK_INTERVAL);         // same cycle: no repeat
        CHECK(CharacterDatabase.honorResets == 1 && online.honor == 50);

        g_now = anchor + 365 * DAY;
        script.OnUpdate(HONOR_RESET_CHECK_INTERVAL);
        CHECK(CharacterDatabase.honorResets == expectedAfterYear);
    }
}

int main()
{
    TestAddWeeksBounds();
    TestScheduleUtc();
    TestExtremeIntervalsTerminate();
    TestDstLondon();
    TestConfigClampUnchanged();
    TestEndToEnd(2, 2);             // one more reset (the latest), not one per fortnight missed
    TestEndToEnd(UINT32_MAX, 1);    // extreme interval: anchor only, and it terminates

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
    std::printf("PASS: Honor reset schedule, %d checks\n", checks);
    return 0;
}
