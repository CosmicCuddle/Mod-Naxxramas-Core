// A01 P2: native tests for src/Systems/GolemaggActionAuditTrace.h and a
// model of the audit's sample/duplicate step in BotGolemaggActionAudit.cpp.
// Pure standard C++; no core, Playerbots or server.
#include "GolemaggActionAuditTrace.h"

#include <cstdio>
#include <string>

using NaxxramasGolemaggActionAudit::BoundActionTrace;

namespace
{
    constexpr std::size_t MAX_ACTION_TEXT = 320; // BotGolemaggActionAudit.cpp
    constexpr int MAX_SAMPLES_PER_BOT = 24;       // BotGolemaggActionAudit.cpp
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

    std::string Bound(std::string s, std::size_t max = MAX_ACTION_TEXT)
    {
        BoundActionTrace(s, max);
        return s;
    }

    // The per-bot state and steps the .cpp runs once thresholds and lookup
    // presence are unchanged: sentinel, bound, duplicate check, cache, log.
    struct Model
    {
        std::string lastTrace;
        int samples = 0;
        std::size_t largestCache = 0;
        std::string lastLogged;

        void Offer(std::string trace, bool thresholdChanged = false)
        {
            if (samples >= MAX_SAMPLES_PER_BOT)
                return;
            if (trace.empty())
                trace = "(no recent action)";
            BoundActionTrace(trace, MAX_ACTION_TEXT);
            if (trace == lastTrace && !thresholdChanged)
                return;
            lastTrace = trace;
            largestCache = std::max(largestCache, lastTrace.size());
            lastLogged = trace;
            ++samples;
        }
    };

    void TestBounds()
    {
        CHECK(Bound("").empty());
        CHECK(Bound("x") == "x");
        std::string const at319(319, 'a');
        std::string const at320(320, 'b');
        CHECK(Bound(at319) == at319);
        CHECK(Bound(at320) == at320);

        std::string over = "Z" + std::string(320, 'c');
        CHECK(Bound(over) == std::string(320, 'c'));            // oldest byte dropped

        std::string huge(100000, 'p');
        huge.replace(huge.size() - 5, 5, "melee");
        std::string const bounded = Bound(huge);
        CHECK(bounded.size() == MAX_ACTION_TEXT);
        CHECK(bounded.compare(bounded.size() - 5, 5, "melee") == 0); // newest kept

        CHECK(Bound(std::string(10, 'q'), 0).empty());
        CHECK(Bound(std::string(10, 'q'), 3) == "qqq");

        // Embedded NUL bytes count as bytes and are kept.
        std::string nul("a\0b", 3);
        CHECK(Bound(nul) == nul);
        CHECK(Bound(nul, 2) == std::string("\0b", 2));
    }

    void TestLineBreaks()
    {
        CHECK(Bound("reach melee\nmc golemagg back off") == "reach melee mc golemagg back off");
        CHECK(Bound("a\r\nb") == "a  b");
        CHECK(Bound("\n\r\n\r") == "    ");
        // Normalising after the cut: a break in the dropped prefix is gone,
        // one at the boundary becomes a space, and the length is unchanged.
        std::string s = "\n" + std::string(318, 'k') + "\n\r";
        CHECK(s.size() == 321);
        CHECK(Bound(s) == std::string(318, 'k') + "  ");
        // Any input: no line break survives, never longer than the cap.
        for (std::size_t len : {0u, 1u, 160u, 320u, 321u, 640u, 5000u})
        {
            std::string t;
            for (std::size_t i = 0; i < len; ++i)
                t.push_back("ab\n\rc"[i % 5]);
            std::string const b = Bound(t);
            CHECK(b.size() == std::min(len, MAX_ACTION_TEXT));
            CHECK(b.find('\n') == std::string::npos);
            CHECK(b.find('\r') == std::string::npos);
            CHECK(Bound(b) == b);                                 // idempotent
        }
    }

    void TestEquivalence()
    {
        std::string const tail(320, 't');
        CHECK(Bound("old-prefix-1" + tail) == Bound("other-much-longer-prefix-2" + tail));
        CHECK(Bound("x" + tail) != Bound(std::string(320, 'u')));
        CHECK(Bound("reach melee\nattack") == Bound("reach melee attack"));
        CHECK(Bound("reach melee\rattack") == Bound("reach melee\nattack"));
    }

    void TestModel()
    {
        // Negative: 100 tails that only differ before the last 320 bytes
        // would all log the same line. Exactly one sample is spent and the
        // cache never holds more than the cap.
        Model m;
        std::string const tail(320, 'r');
        for (int i = 0; i < 100; ++i)
            m.Offer(std::string(static_cast<std::size_t>(1000 + i), 'h') + tail);
        CHECK(m.samples == 1);
        CHECK(m.largestCache == MAX_ACTION_TEXT);
        CHECK(m.lastLogged == tail);

        // Line-break-only differences are the same logged line too.
        Model n;
        n.Offer("reach melee\nattack");
        n.Offer("reach melee\rattack");
        n.Offer("reach melee attack");
        CHECK(n.samples == 1);

        // A real change in the logged tail is still sampled.
        n.Offer("mc golemagg back off");
        CHECK(n.samples == 2);
        // A threshold change still samples an identical tail.
        n.Offer("mc golemagg back off", true);
        CHECK(n.samples == 3);

        // The sentinel is bounded and deduplicated like any other text.
        Model e;
        e.Offer("");
        e.Offer("");
        CHECK(e.samples == 1);
        CHECK(e.lastLogged == "(no recent action)");

        // The 24-sample cap is unchanged.
        Model c;
        for (int i = 0; i < 200; ++i)
            c.Offer("action " + std::to_string(i));
        CHECK(c.samples == MAX_SAMPLES_PER_BOT);
        CHECK(c.lastLogged == "action 23");

        // Huge inputs: the cache stays at the cap across many distinct tails.
        Model h;
        for (int i = 0; i < 24; ++i)
            h.Offer(std::string(200000, 'g') + std::to_string(i));
        CHECK(h.samples == 24);
        CHECK(h.largestCache == MAX_ACTION_TEXT);
    }
}

int main()
{
    TestBounds();
    TestLineBreaks();
    TestEquivalence();
    TestModel();
    if (failures != 0)
    {
        std::printf("FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    std::printf("PASS: Golemagg audit trace bound, %d checks\n", checks);
    return 0;
}
