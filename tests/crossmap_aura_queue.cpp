// Standalone tests for src/Systems/CrossMapAuraQueue.h (#114 follow-up).
// Build: g++ -std=c++17 -Wall -Wextra -Werror -pedantic -pthread
//        -Isrc/Systems tests/crossmap_aura_queue.cpp
// Optional: add -fsanitize=thread to check the locking.

#include "CrossMapAuraQueue.h"

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

using NaxxramasCrossMapAura::AuraKey;
using NaxxramasCrossMapAura::RemovalQueue;

namespace
{
    int Failures = 0;

    void Check(bool ok, char const* what)
    {
        if (!ok)
        {
            std::printf("FAIL: %s\n", what);
            ++Failures;
        }
        else
        {
            std::printf("ok:   %s\n", what);
        }
    }

    std::vector<AuraKey> DrainAll(RemovalQueue& queue)
    {
        std::vector<AuraKey> removed;
        queue.Drain([&](AuraKey const& key) { removed.push_back(key); });
        return removed;
    }

    constexpr uint32_t BOT = 101;
    constexpr uint32_t OTHER_BOT = 202;
    constexpr uint32_t FLASK = 17628;
    constexpr uint32_t JUJU_FLURRY = 16322;
    constexpr uint32_t PET_BUFF = 24382;
}

int main()
{
    // 1. A queued removal is performed exactly once.
    {
        RemovalQueue queue;
        queue.NoteApplied({ BOT, FLASK, false });
        queue.Enqueue({ BOT, FLASK, false });
        auto first = DrainAll(queue);
        auto second = DrainAll(queue);
        Check(first.size() == 1 && first[0] == AuraKey{ BOT, FLASK, false },
            "queued removal is drained once");
        Check(second.empty(), "second drain is empty");
    }

    // 2. Stale-work gate: the module re-applies before the drain.
    {
        RemovalQueue queue;
        queue.NoteApplied({ BOT, FLASK, false });
        queue.Enqueue({ BOT, FLASK, false });
        queue.NoteApplied({ BOT, FLASK, false }); // new preparation
        Check(DrainAll(queue).empty(),
            "removal queued before a re-application is skipped");
    }

    // 3. Re-application of a DIFFERENT spell does not cancel the removal.
    {
        RemovalQueue queue;
        queue.Enqueue({ BOT, FLASK, false });
        queue.NoteApplied({ BOT, JUJU_FLURRY, false });
        auto removed = DrainAll(queue);
        Check(removed.size() == 1 && removed[0].SpellId == FLASK,
            "other spell's re-application does not cancel removal");
    }

    // 4. Pet and bot keys are distinct, and the pet flag is preserved.
    {
        RemovalQueue queue;
        queue.Enqueue({ BOT, PET_BUFF, true });
        queue.NoteApplied({ BOT, PET_BUFF, false }); // bot, not pet
        auto removed = DrainAll(queue);
        Check(removed.size() == 1 && removed[0].IsPet,
            "pet removal keeps IsPet and ignores bot-key re-application");

        RemovalQueue petQueue;
        petQueue.Enqueue({ BOT, PET_BUFF, true });
        petQueue.NoteApplied({ BOT, PET_BUFF, true }); // pet re-buffed
        Check(DrainAll(petQueue).empty(),
            "pet removal skipped after pet re-application");
    }

    // 5. CS01 mandatory case: master teleports out while the bot stays in
    //    MC with BOTH an ordinary tracked buff (tracker.Auras, here also a
    //    pet buff) and a timed Juju Flurry (tracker.TimedAuras). Both
    //    vectors are queued; a newer Juju application must survive.
    {
        RemovalQueue queue;
        queue.NoteApplied({ BOT, FLASK, false });
        queue.NoteApplied({ BOT, PET_BUFF, true });
        queue.NoteApplied({ BOT, JUJU_FLURRY, false });

        // Invalid-location cleanup on the master's map thread:
        queue.Enqueue({ BOT, FLASK, false });       // tracker.Auras
        queue.Enqueue({ BOT, PET_BUFF, true });     // tracker.Auras (pet)
        queue.Enqueue({ BOT, JUJU_FLURRY, false }); // tracker.TimedAuras

        Check(queue.PendingCount() == 3, "both aura vectors are queued");

        // Before the drain, another leader's tracker re-applies Juju.
        queue.NoteApplied({ BOT, JUJU_FLURRY, false });

        auto removed = DrainAll(queue);
        bool flask = false;
        bool pet = false;
        bool juju = false;
        for (AuraKey const& key : removed)
        {
            flask = flask || (key == AuraKey{ BOT, FLASK, false });
            pet = pet || (key == AuraKey{ BOT, PET_BUFF, true });
            juju = juju || key.SpellId == JUJU_FLURRY;
        }
        Check(flask && pet && !juju && removed.size() == 2,
            "teleport case: tracked + pet removed, newer Juju kept");
    }

    // 6. A remover that cannot find the bot (logged out) is harmless,
    //    and the entry is not retried.
    {
        RemovalQueue queue;
        queue.Enqueue({ OTHER_BOT, FLASK, false });
        std::size_t calls = 0;
        queue.Drain([&](AuraKey const&) { ++calls; /* bot not found */ });
        Check(calls == 1 && queue.PendingCount() == 0,
            "missing bot: one attempt, nothing left queued");
    }

    // 7. The lock is not held during the remover: re-entrant use works
    //    and a new entry waits for the next drain.
    {
        RemovalQueue queue;
        queue.Enqueue({ BOT, FLASK, false });
        std::size_t calls = 0;
        queue.Drain([&](AuraKey const&)
        {
            ++calls;
            queue.NoteApplied({ OTHER_BOT, FLASK, false });
            queue.Enqueue({ OTHER_BOT, FLASK, false });
        });
        Check(calls == 1 && queue.PendingCount() == 1,
            "remover may enqueue without deadlock; entry waits");
        Check(DrainAll(queue).size() == 1, "re-entrant entry drains next time");
    }

    // 8. CS01 #116 interleaving: the drain has passed the generation check
    //    and is inside the removal when a map worker re-applies the SAME
    //    aura. NoteApplied must wait for the removal to finish, so the
    //    re-application lands after it and survives.
    {
        RemovalQueue queue;
        AuraKey const key{ BOT, JUJU_FLURRY, false };
        queue.NoteApplied(key);
        queue.Enqueue(key);

        std::atomic<bool> auraPresent{ true };
        std::atomic<bool> noteReturned{ false };
        bool blockedDuringRemoval = false;
        std::thread worker;

        queue.Drain([&](AuraKey const&)
        {
            // Check already passed. A worker now re-applies the aura.
            worker = std::thread([&]()
            {
                queue.NoteApplied(key);   // must wait for the removal
                noteReturned = true;
                auraPresent = true;       // the module's new application
            });

            std::this_thread::sleep_for(std::chrono::milliseconds(150));
            blockedDuringRemoval = !noteReturned.load();
            auraPresent = false;          // the (stale) removal itself
        });
        worker.join();

        Check(blockedDuringRemoval,
            "interleave: NoteApplied for the key being removed waits");
        Check(auraPresent.load(),
            "interleave: re-application after the removal survives");

        // The new generation is current: a later queued removal still works.
        queue.Enqueue(key);
        Check(DrainAll(queue).size() == 1,
            "interleave: later removal of the new generation proceeds");
    }

    // 9. A different key is never blocked by an in-progress removal.
    {
        RemovalQueue queue;
        queue.Enqueue({ BOT, FLASK, false });
        std::atomic<bool> otherReturned{ false };
        queue.Drain([&](AuraKey const&)
        {
            std::thread other([&]()
            {
                queue.NoteApplied({ BOT, JUJU_FLURRY, false });
                otherReturned = true;
            });
            other.join(); // would hang here if other keys were blocked
        });
        Check(otherReturned.load(),
            "interleave: other keys are not blocked during a removal");
    }

    // 10. If the remover throws, the mark is cleared and NoteApplied
    //     for that key does not block afterwards.
    {
        RemovalQueue queue;
        AuraKey const key{ BOT, FLASK, false };
        queue.Enqueue(key);
        bool threw = false;
        try
        {
            queue.Drain([](AuraKey const&) { throw 1; });
        }
        catch (int)
        {
            threw = true;
        }
        std::atomic<bool> returned{ false };
        std::thread after([&]()
        {
            queue.NoteApplied(key);
            returned = true;
        });
        after.join();
        Check(threw && returned.load(),
            "remover exception clears the in-progress mark");
    }

    // 11. Concurrent producers (map workers) and NoteApplied calls.
    {
        RemovalQueue queue;
        constexpr int THREADS = 8;
        constexpr int PER_THREAD = 500;
        std::vector<std::thread> workers;
        for (int t = 0; t < THREADS; ++t)
        {
            workers.emplace_back([&queue, t]()
            {
                for (int i = 0; i < PER_THREAD; ++i)
                {
                    uint32_t bot = uint32_t(1000 + t);
                    queue.NoteApplied({ bot, uint32_t(i), false });
                    queue.Enqueue({ bot, uint32_t(i), false });
                }
            });
        }
        for (std::thread& worker : workers)
            worker.join();

        Check(queue.PendingCount() == std::size_t(THREADS * PER_THREAD),
            "concurrent enqueue keeps every entry");
        Check(DrainAll(queue).size() == std::size_t(THREADS * PER_THREAD),
            "concurrent entries all drain (none stale)");
    }

    std::printf("%s (%d failure%s)\n",
        Failures ? "FAILED" : "OK", Failures, Failures == 1 ? "" : "s");
    return Failures ? EXIT_FAILURE : EXIT_SUCCESS;
}
