// B09 P3: deterministic tests of the REAL src/Events/ElementalInvasionCalendar.cpp.
//
// The production file is compiled unmodified in this translation unit against
// the small stubs in tests/b09_stubs (Config, GameEventMgr, Log, ScriptMgr).
// The clock is controlled by linking with -Wl,--wrap=time, and the timezone
// by TZ + tzset(), so every case is reproducible. Needs glibc and tzdata.
//
// Build: g++ -std=c++17 -Itests/b09_stubs -Isrc/Events
//          tests/elemental_invasion_calendar_tests.cpp -Wl,--wrap=time
#include "ElementalInvasionCalendar.cpp"

#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>

namespace
{
    std::time_t g_now = 0;
    int g_timeCalls = 0;
}

extern "C" std::time_t __wrap_time(std::time_t* out)
{
    ++g_timeCalls;
    if (out)
        *out = g_now;
    return g_now;
}

namespace
{
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

    void Configure(uint32 hour, uint32 minute, uint32 days)
    {
        ElementalInvasionHour = hour;
        ElementalInvasionMinute = minute;
        ElementalInvasionDurationDays = days;
    }

    // -1 = could not compute, 0 = inactive, 1 = active.
    int Window(std::time_t now)
    {
        bool active = false;
        if (!InMonthlyWindow(now, active))
            return -1;
        return active ? 1 : 0;
    }

    int DaysInMonth(int y, int m)
    {
        static int const days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
        bool const leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
        return m == 2 && leap ? 29 : days[m - 1];
    }

    // ---- window arithmetic in UTC -------------------------------------
    void TestDefaultWindowUtc()
    {
        Zone("UTC");
        Configure(0, 0, 5);
        CHECK(Window(Utc(2026, 9, 30, 23, 59, 59)) == 0);
        CHECK(Window(Utc(2026, 10, 1)) == 1);                 // start inclusive
        CHECK(Window(Utc(2026, 10, 3, 12)) == 1);
        CHECK(Window(Utc(2026, 10, 5, 23, 59, 59)) == 1);
        CHECK(Window(Utc(2026, 10, 6)) == 0);                 // end exclusive
        CHECK(Window(Utc(2026, 10, 28, 14, 0)) == 0);
        // Year boundary.
        CHECK(Window(Utc(2026, 12, 31, 23, 59, 59)) == 0);
        CHECK(Window(Utc(2027, 1, 1)) == 1);
        CHECK(Window(Utc(2027, 1, 5, 23, 59, 59)) == 1);
        CHECK(Window(Utc(2027, 1, 6)) == 0);
    }

    // Every month of 2023-2030 (leap and non-leap Februaries, 30/31-day
    // months), several start times and every allowed duration: the window is
    // exactly [1st H:M, (1+D)th H:M) and day-by-day membership matches.
    void TestAllMonthsAllDurationsUtc()
    {
        Zone("UTC");
        struct Start { uint32 h, m; } const starts[] = {{0, 0}, {13, 30}, {23, 59}};
        for (Start const st : starts)
            for (uint32 d = 1; d <= 27; ++d)
            {
                Configure(st.h, st.m, d);
                for (int y = 2023; y <= 2030; ++y)
                    for (int mo = 1; mo <= 12; ++mo)
                    {
                        int const h = static_cast<int>(st.h);
                        int const mi = static_cast<int>(st.m);
                        std::time_t const begin = Utc(y, mo, 1, h, mi);
                        std::time_t const end = Utc(y, mo, 1 + static_cast<int>(d), h, mi);
                        CHECK(Window(begin - 1) == 0);
                        CHECK(Window(begin) == 1);
                        CHECK(Window(end - 1) == 1);
                        CHECK(Window(end) == 0);
                        for (int day = 1; day <= DaysInMonth(y, mo); ++day)
                        {
                            std::time_t const probe = Utc(y, mo, day, h, mi);
                            bool const expect = day >= 1 && day < 1 + static_cast<int>(d);
                            CHECK(Window(probe) == (expect ? 1 : 0));
                        }
                    }
            }
    }

    void TestLeapFebruary()
    {
        Zone("UTC");
        Configure(0, 0, 27);
        CHECK(Window(Utc(2028, 2, 27, 23, 59, 59)) == 1);
        CHECK(Window(Utc(2028, 2, 28)) == 0);
        CHECK(Window(Utc(2028, 2, 29, 12)) == 0);   // leap day is after the window
        CHECK(Window(Utc(2028, 3, 1)) == 1);
        CHECK(Window(Utc(2027, 2, 28, 12)) == 0);
        CHECK(Window(Utc(2027, 3, 1)) == 1);
        // 2100 is not a leap year; 2000 was.
        CHECK(Window(Utc(2000, 2, 29, 12)) == 0);
        CHECK(Window(Utc(2100, 3, 1)) == 1);
        CHECK(Window(Utc(2100, 2, 28, 12)) == 0);
    }

    // On the 1st before the configured time, no previous-month window can
    // still be open: the longest window ends on the 28th.
    void TestBeforeStartOnTheFirst()
    {
        Zone("UTC");
        Configure(23, 59, 27);
        CHECK(Window(Utc(2026, 11, 1, 0, 0)) == 0);
        CHECK(Window(Utc(2026, 11, 1, 23, 58, 59)) == 0);
        CHECK(Window(Utc(2026, 11, 1, 23, 59)) == 1);
        CHECK(Window(Utc(2026, 10, 28, 23, 58, 59)) == 1);
        CHECK(Window(Utc(2026, 10, 28, 23, 59)) == 0);
        CHECK(Window(Utc(2026, 10, 31, 23, 59, 59)) == 0);
    }

    // ---- local time and daylight saving ---------------------------------
    void TestDstInsideWindow()
    {
        // New York, DST starts 2024-03-10: the window ends at LOCAL midnight
        // on the 28th (04:00Z, EDT), not 27*24h after the start (05:00Z).
        Zone("America/New_York");
        Configure(0, 0, 27);
        CHECK(Window(Utc(2024, 3, 1, 4, 59, 59)) == 0);
        CHECK(Window(Utc(2024, 3, 1, 5)) == 1);
        CHECK(Window(Utc(2024, 3, 28, 3, 59, 59)) == 1);
        CHECK(Window(Utc(2024, 3, 28, 4)) == 0);
        // DST ends 2024-11-03: ends at EST midnight (05:00Z).
        CHECK(Window(Utc(2024, 11, 1, 3, 59, 59)) == 0);
        CHECK(Window(Utc(2024, 11, 1, 4)) == 1);
        CHECK(Window(Utc(2024, 11, 28, 4, 59, 59)) == 1);
        CHECK(Window(Utc(2024, 11, 28, 5)) == 0);

        // London, BST ends 2026-10-25: 1 Oct 00:00 BST = 30 Sep 23:00Z,
        // 28 Oct 00:00 GMT = 28 Oct 00:00Z.
        Zone("Europe/London");
        CHECK(Window(Utc(2026, 9, 30, 22, 59, 59)) == 0);
        CHECK(Window(Utc(2026, 9, 30, 23)) == 1);
        CHECK(Window(Utc(2026, 10, 27, 23, 59, 59)) == 1);
        CHECK(Window(Utc(2026, 10, 28)) == 0);
        // Default 5 days in London summer and winter.
        Configure(0, 0, 5);
        CHECK(Window(Utc(2026, 7, 5, 22, 59, 59)) == 1);   // 5 Jul 23:59:59 BST
        CHECK(Window(Utc(2026, 7, 5, 23)) == 0);           // 6 Jul 00:00 BST
        CHECK(Window(Utc(2026, 12, 5, 23, 59, 59)) == 1);
        CHECK(Window(Utc(2026, 12, 6)) == 0);
    }

    // Configured start falls in a DST gap on the 1st (that local time does
    // not exist). The window must still start ON the 1st local date, at or
    // after the transition, and never in the previous month.
    void TestStartInDstGap()
    {
        // Asuncion 2017-10-01: 00:00 -04 -> 01:00 -03 at 04:00Z.
        Zone("America/Asuncion");
        Configure(0, 0, 5);
        CHECK(Window(Utc(2017, 10, 1, 3, 59, 59)) == 0);   // 30 Sep 23:59:59 -04
        CHECK(Window(Utc(2017, 10, 1, 4)) == 1);           // 1 Oct 01:00 -03
        CHECK(Window(Utc(2017, 10, 6, 2, 59, 59)) == 1);
        CHECK(Window(Utc(2017, 10, 6, 3)) == 0);           // 6 Oct 00:00 -03

        // Sydney 2017-10-01: 02:00 AEST -> 03:00 AEDT at 30 Sep 16:00Z.
        // Configured 02:30 does not exist; it starts within one hour of the
        // transition (glibc: 03:30 AEDT) and ends 6 Oct 02:30 AEDT.
        Zone("Australia/Sydney");
        Configure(2, 30, 5);
        std::time_t const transition = Utc(2017, 9, 30, 16);
        CHECK(Window(transition - 1) == 0);
        int starts = 0;
        std::time_t startAt = 0;
        for (std::time_t t = transition; t <= transition + 3600; t += 60)
            if (Window(t) == 1 && Window(t - 60) == 0)
            {
                ++starts;
                startAt = t;
            }
        CHECK(starts == 1);
        CHECK(startAt >= transition && startAt <= transition + 3600);
        CHECK(Window(Utc(2017, 10, 5, 15, 29, 59)) == 1);
        CHECK(Window(Utc(2017, 10, 5, 15, 30)) == 0);

        // Lord Howe 2017-10-01: 30-minute DST, 02:00 +10:30 -> 02:30 +11
        // at 30 Sep 15:30Z. Configured 02:15 does not exist.
        Zone("Australia/Lord_Howe");
        Configure(2, 15, 5);
        std::time_t const lhTransition = Utc(2017, 9, 30, 15, 30);
        CHECK(Window(lhTransition - 1) == 0);
        CHECK(Window(lhTransition + 1800) == 1);
        CHECK(Window(Utc(2017, 10, 5, 15, 14, 59)) == 1);   // 6 Oct 02:14:59 +11
        CHECK(Window(Utc(2017, 10, 5, 15, 15)) == 0);
    }

    // Configured start is ambiguous (clocks go back on the 1st). Either
    // occurrence is a valid start; the window opens once and the end is exact.
    void TestStartInDstOverlap()
    {
        // Sydney 2018-04-01: 03:00 AEDT -> 02:00 AEST at 31 Mar 16:00Z.
        // 02:30 occurs at 15:30Z (AEDT) and 16:30Z (AEST).
        Zone("Australia/Sydney");
        Configure(2, 30, 5);
        CHECK(Window(Utc(2018, 3, 31, 15, 29, 59)) == 0);
        bool const first = Window(Utc(2018, 3, 31, 15, 30)) == 1;
        bool const second = Window(Utc(2018, 3, 31, 16, 30)) == 1;
        CHECK(second);
        CHECK(first ? Window(Utc(2018, 3, 31, 16, 29, 59)) == 1
                    : Window(Utc(2018, 3, 31, 16, 29, 59)) == 0);
        CHECK(Window(Utc(2018, 4, 5, 16, 29, 59)) == 1);    // 6 Apr 02:29:59 AEST
        CHECK(Window(Utc(2018, 4, 5, 16, 30)) == 0);

        // Lord Howe 2018-04-01: 02:00 +11 -> 01:30 +10:30 at 31 Mar 15:00Z.
        // 01:45 occurs at 14:45Z (+11) and 15:15Z (+10:30).
        Zone("Australia/Lord_Howe");
        Configure(1, 45, 5);
        CHECK(Window(Utc(2018, 3, 31, 14, 44, 59)) == 0);
        CHECK(Window(Utc(2018, 3, 31, 15, 15)) == 1);
        CHECK(Window(Utc(2018, 4, 5, 15, 14, 59)) == 1);    // 6 Apr 01:44:59 +10:30
        CHECK(Window(Utc(2018, 4, 5, 15, 15)) == 0);
    }

    // ---- configuration --------------------------------------------------
    struct Config
    {
        bool enabled;
        uint32 hour;
        uint32 minute;
        uint32 days;
    };

    Config LoadWith(std::map<std::string, bool> bools, std::map<std::string, uint32> uints,
                    NaxxramasCoreElementalInvasionCalendar& script, bool reload = false)
    {
        StubConfigMgr::instance().bools = std::move(bools);
        StubConfigMgr::instance().uints = std::move(uints);
        script.OnBeforeConfigLoad(reload);
        return {ElementalInvasionEnabled, ElementalInvasionHour, ElementalInvasionMinute,
                ElementalInvasionDurationDays};
    }

    void TestConfig()
    {
        NaxxramasCoreElementalInvasionCalendar script;
        std::string const p = "NaxxramasCore.ElementalInvasion.";

        Config c = LoadWith({}, {}, script);                   // all absent
        CHECK(!c.enabled && c.hour == 0 && c.minute == 0 && c.days == 5);

        c = LoadWith({{p + "Enabled", true}},
                     {{p + "Hour", 24}, {p + "Minute", 60}, {p + "DurationDays", 0}}, script);
        CHECK(c.enabled && c.hour == 23 && c.minute == 59 && c.days == 1);

        uint32 const huge = std::numeric_limits<uint32>::max();
        c = LoadWith({{p + "Enabled", true}},
                     {{p + "Hour", huge}, {p + "Minute", huge}, {p + "DurationDays", huge}}, script);
        CHECK(c.hour == 23 && c.minute == 59 && c.days == 27);

        c = LoadWith({{p + "Enabled", false}}, {{p + "DurationDays", 28}}, script);
        CHECK(!c.enabled && c.days == 27);

        c = LoadWith({}, {{p + "Hour", 23}, {p + "Minute", 59}, {p + "DurationDays", 27}}, script);
        CHECK(c.hour == 23 && c.minute == 59 && c.days == 27);

        // .reload config re-reads the same way.
        c = LoadWith({{p + "Enabled", true}}, {{p + "DurationDays", 3}}, script, true);
        CHECK(c.enabled && c.days == 3 && c.hour == 0);

        // Hooks registered: BeforeConfigLoad, Startup, Update.
        CHECK(script.Hooks.size() == 3);
    }

    // ---- event 13 synchronisation (fail closed) --------------------------
    GameEventMgr& Events() { return *sGameEventMgr; }

    void ResetEvents(std::size_t count, GameEventState state13)
    {
        GameEventMgr& e = Events();
        e.events.assign(count, GameEventData{});
        if (count > ELEMENTAL_INVASIONS_EVENT_ID)
            e.events[ELEMENTAL_INVASIONS_EVENT_ID].State = state13;
        e.active.clear();
        e.startSucceeds = true;
        e.mapReads = 0;
        e.activeQueries = 0;
        e.starts.clear();
        e.stops.clear();
        StubLogLines().clear();
    }

    int CountLog(char const* level, char const* fragment)
    {
        int n = 0;
        for (StubLogLine const& line : StubLogLines())
            if (line.level == level && line.text.find(fragment) != std::string::npos)
                ++n;
        return n;
    }

    // n ticks of one minute each; the first runs immediately after startup.
    void Minutes(NaxxramasCoreElementalInvasionCalendar& s, int n)
    {
        for (int i = 0; i < n; ++i)
            s.OnUpdate(CHECK_INTERVAL_MS);
    }

    NaxxramasCoreElementalInvasionCalendar& Fresh(bool enabled)
    {
        static NaxxramasCoreElementalInvasionCalendar* script = nullptr;
        delete script;
        script = new NaxxramasCoreElementalInvasionCalendar();
        Zone("UTC");
        Configure(0, 0, 5);
        ElementalInvasionEnabled = enabled;
        script->OnStartup();
        return *script;
    }

    std::time_t const IN_WINDOW = Utc(2026, 11, 2, 12);
    std::time_t const OUT_OF_WINDOW = Utc(2026, 11, 20, 12);

    void TestDisabledNeverTouchesEvent13()
    {
        ResetEvents(20, GAMEEVENT_INTERNAL);
        Events().active.insert(ELEMENTAL_INVASIONS_EVENT_ID);
        NaxxramasCoreElementalInvasionCalendar& s = Fresh(false);
        g_now = OUT_OF_WINDOW;
        int const timeCalls = g_timeCalls;
        Minutes(s, 30);
        g_now = IN_WINDOW;
        Events().active.clear();
        Minutes(s, 30);
        CHECK(Events().Touches() == 0);
        CHECK(g_timeCalls == timeCalls);
        CHECK(StubLogLines().empty());
    }

    void TestMissingOrNonInternalEvent13FailsClosed()
    {
        char const* setup = "requires game_event.eventEntry=13";
        for (std::size_t count : {std::size_t(0), std::size_t(13)})
        {
            ResetEvents(count, GAMEEVENT_INTERNAL);
            NaxxramasCoreElementalInvasionCalendar& s = Fresh(true);
            g_now = IN_WINDOW;
            Minutes(s, 10);
            CHECK(Events().starts.empty() && Events().stops.empty());
            CHECK(CountLog("ERROR", setup) == 1);                  // once, not per minute
        }
        for (GameEventState st : {GAMEEVENT_NORMAL, GAMEEVENT_WORLD_INACTIVE,
                                  GAMEEVENT_WORLD_CONDITIONS, GAMEEVENT_WORLD_NEXTPHASE,
                                  GAMEEVENT_WORLD_FINISHED})
        {
            ResetEvents(20, st);
            Events().active.insert(ELEMENTAL_INVASIONS_EVENT_ID);  // stock event running
            NaxxramasCoreElementalInvasionCalendar& s = Fresh(true);
            g_now = OUT_OF_WINDOW;                                  // would otherwise stop it
            Minutes(s, 5);
            g_now = IN_WINDOW;
            Events().active.clear();                                // would otherwise start it
            Minutes(s, 5);
            CHECK(Events().starts.empty() && Events().stops.empty());
            CHECK(CountLog("ERROR", setup) == 1);
        }
    }

    void TestStartAndStopAtBoundaries()
    {
        ResetEvents(20, GAMEEVENT_INTERNAL);
        NaxxramasCoreElementalInvasionCalendar& s = Fresh(true);

        g_now = Utc(2026, 10, 31, 23, 59);
        Minutes(s, 1);
        CHECK(Events().starts.empty());

        g_now = Utc(2026, 11, 1);
        Minutes(s, 1);
        CHECK(Events().starts.size() == 1 && Events().starts[0] == ELEMENTAL_INVASIONS_EVENT_ID);
        CHECK(CountLog("INFO", "started") == 1);

        for (int i = 0; i < 60; ++i)                                // stays started, no repeats
        {
            g_now += 60;
            Minutes(s, 1);
        }
        CHECK(Events().starts.size() == 1 && Events().stops.empty());

        g_now = Utc(2026, 11, 5, 23, 59, 59);
        Minutes(s, 1);
        CHECK(Events().stops.empty());
        g_now = Utc(2026, 11, 6);
        Minutes(s, 1);
        CHECK(Events().stops.size() == 1 && Events().stops[0] == ELEMENTAL_INVASIONS_EVENT_ID);
        CHECK(CountLog("INFO", "ended") == 1);
        g_now += 3600;
        Minutes(s, 5);
        CHECK(Events().stops.size() == 1 && Events().starts.size() == 1);

        // Restart inside the window resumes; restart outside stops a stale run.
        ResetEvents(20, GAMEEVENT_INTERNAL);
        NaxxramasCoreElementalInvasionCalendar& r = Fresh(true);
        g_now = IN_WINDOW;
        Minutes(r, 1);
        CHECK(Events().starts.size() == 1);
        ResetEvents(20, GAMEEVENT_INTERNAL);
        Events().active.insert(ELEMENTAL_INVASIONS_EVENT_ID);
        NaxxramasCoreElementalInvasionCalendar& q = Fresh(true);
        g_now = OUT_OF_WINDOW;
        Minutes(q, 1);
        CHECK(Events().stops.size() == 1 && Events().starts.empty());
    }

    void TestStartFailureRetriesAndLogsOnce()
    {
        ResetEvents(20, GAMEEVENT_INTERNAL);
        Events().startSucceeds = false;
        NaxxramasCoreElementalInvasionCalendar& s = Fresh(true);
        g_now = IN_WINDOW;
        Minutes(s, 10);
        CHECK(Events().starts.size() == 10);                       // retried each minute
        CHECK(CountLog("ERROR", "Could not start") == 1);         // reported once
        Events().startSucceeds = true;
        Minutes(s, 1);
        CHECK(Events().starts.size() == 11);
        CHECK(CountLog("INFO", "started") == 1);
        // A later failure after a success is reported again (latch reset).
        Events().active.clear();
        Events().startSucceeds = false;
        Minutes(s, 3);
        CHECK(CountLog("ERROR", "Could not start") == 2);
    }

    void TestCheckIntervalAndStartupReset()
    {
        ResetEvents(20, GAMEEVENT_INTERNAL);
        NaxxramasCoreElementalInvasionCalendar& s = Fresh(true);
        g_now = OUT_OF_WINDOW;
        s.OnUpdate(1);                                             // first tick syncs at once
        int const reads = Events().mapReads;
        CHECK(reads == 1);
        for (int i = 0; i < 59; ++i)
            s.OnUpdate(1000);                                       // 59.0 s
        s.OnUpdate(999);                                            // 59.999 s
        CHECK(Events().mapReads == reads);
        s.OnUpdate(1);                                              // 60.000 s
        CHECK(Events().mapReads == reads + 1);
        s.OnUpdate(10 * 60 * 1000);                                 // a long hitch syncs once
        CHECK(Events().mapReads == reads + 2);
        s.OnUpdate(1);
        CHECK(Events().mapReads == reads + 2);
        s.OnStartup();
        s.OnUpdate(1);
        CHECK(Events().mapReads == reads + 3);
    }

    // Setup recovers, then breaks again: the setup error is reported again.
    void TestSetupErrorLatchResetsOnRecovery()
    {
        ResetEvents(20, GAMEEVENT_NORMAL);
        NaxxramasCoreElementalInvasionCalendar& s = Fresh(true);
        g_now = OUT_OF_WINDOW;
        Minutes(s, 3);
        Events().events[ELEMENTAL_INVASIONS_EVENT_ID].State = GAMEEVENT_INTERNAL;
        Minutes(s, 3);
        Events().events[ELEMENTAL_INVASIONS_EVENT_ID].State = GAMEEVENT_NORMAL;
        Minutes(s, 3);
        CHECK(CountLog("ERROR", "requires game_event.eventEntry=13") == 2);
    }

    // A time the calendar cannot compute must not start or stop event 13,
    // and must be reported once, not every minute.
    void TestUncomputableWindowFailsClosed()
    {
        ResetEvents(20, GAMEEVENT_INTERNAL);
        Events().active.insert(ELEMENTAL_INVASIONS_EVENT_ID);
        NaxxramasCoreElementalInvasionCalendar& s = Fresh(true);
        g_now = std::numeric_limits<std::time_t>::max();            // localtime_r overflows
        CHECK(Window(g_now) == -1);
        Minutes(s, 10);
        CHECK(Events().starts.empty() && Events().stops.empty());
        CHECK(Events().active.count(ELEMENTAL_INVASIONS_EVENT_ID) == 1);
        CHECK(CountLog("ERROR", "Could not calculate") == 1);
        // Clock recovers: normal control resumes.
        g_now = OUT_OF_WINDOW;
        Minutes(s, 1);
        CHECK(Events().stops.size() == 1);
        // Fails again after recovering: reported again, once.
        g_now = std::numeric_limits<std::time_t>::max();
        Minutes(s, 5);
        CHECK(CountLog("ERROR", "Could not calculate") == 2);
        // Window errors never consume the setup-error report.
        Events().events[ELEMENTAL_INVASIONS_EVENT_ID].State = GAMEEVENT_NORMAL;
        Minutes(s, 2);
        CHECK(CountLog("ERROR", "requires game_event.eventEntry=13") == 1);
    }

    void TestTzdataPresent()
    {
        // Guards against a runner without tzdata silently treating every
        // zone as UTC (which would make the DST cases vacuous).
        Zone("America/New_York");
        std::tm local = {};
        std::time_t const t = Utc(2024, 7, 1, 12);
        localtime_r(&t, &local);
        CHECK(local.tm_hour == 8 && local.tm_isdst == 1);
        Zone("Australia/Lord_Howe");
        std::time_t const u = Utc(2024, 7, 1, 0);
        localtime_r(&u, &local);
        CHECK(local.tm_hour == 10 && local.tm_min == 30);
    }
}

int main()
{
    TestTzdataPresent();
    TestDefaultWindowUtc();
    TestAllMonthsAllDurationsUtc();
    TestLeapFebruary();
    TestBeforeStartOnTheFirst();
    TestDstInsideWindow();
    TestStartInDstGap();
    TestStartInDstOverlap();
    TestConfig();
    TestDisabledNeverTouchesEvent13();
    TestMissingOrNonInternalEvent13FailsClosed();
    TestStartAndStopAtBoundaries();
    TestStartFailureRetriesAndLogsOnce();
    TestCheckIntervalAndStartupReset();
    TestSetupErrorLatchResetsOnRecovery();
    TestUncomputableWindowFailsClosed();

    if (failures != 0)
    {
        std::printf("FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    std::printf("PASS: Elemental Invasions calendar, %d checks\n", checks);
    return 0;
}
