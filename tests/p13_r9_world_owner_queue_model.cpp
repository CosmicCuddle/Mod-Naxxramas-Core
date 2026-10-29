// P13-R9 TEST-ONLY abstract candidate: a bounded immutable map-worker observation
// queue, with EXCLUSIVE world-thread processing after worker join.
//
// NOT production HonorOverflow logic. No Player*, money, chat, DB, hooks,
// real server, or any source modification. Tests only ownership invariants.
// Input sequence and generation are hypothetical; pinned core does NOT
// provide this contract automatically. C++17/20, ASan+UBSan, TSAN.
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

struct Observation final
{
    std::uint32_t guid = 0;
    std::uint64_t incarnation = 0;
    std::uint64_t sequence = 0;
    std::uint32_t contribution = 0;
    bool battleground = false;
};
static_assert(std::is_trivially_copyable<Observation>::value,
              "Map workers must pass immutable data, never Player pointers");

void Check(bool condition, char const* label)
{
    if (!condition)
        throw std::runtime_error(label);
}

struct SessionState final
{
    std::uint64_t incarnation = 0;
    std::uint64_t lastSequence = 0;
    std::uint32_t lastContribution = 0;
    std::uint32_t accepted = 0;
    std::uint32_t pendingBgSamples = 0;
    bool invalid = false;
};

class HypotheticalWorldOwner final
{
public:
    explicit HypotheticalWorldOwner(std::size_t queueLimit)
        : owner(std::this_thread::get_id()), capacity(queueLimit)
    {
        Check(capacity > 0, "zero queue capacity");
    }

    void Begin(std::uint32_t guid, std::uint64_t incarnation)
    {
        RequireWorldThread();
        Check(incarnation > 0, "unproven zero incarnation");
        sessions[guid] = SessionState{incarnation};
    }

    void Retire(std::uint32_t guid)
    {
        RequireWorldThread();
        sessions.erase(guid);
        // The queue deliberately retains stale observations for a later
        // epoch check. Never retain or dereference a Player* here.
    }

    bool Submit(Observation const& observation)
    {
        std::lock_guard<std::mutex> lock(queueMutex);
        if (poisoned.count(observation.guid))
            return false;
#ifdef P13_R9_MUTANT_OVERFLOW
        if (false)
#else
        if (pending.size() >= capacity)
#endif
        {
            // A dropped event invalidates that GUID's sequence, not just the
            // single missing item. No guessed monetary recovery is allowed.
            poisoned.insert(observation.guid);
            return false;
        }
        pending.push_back(observation);
        return true;
    }

    void DrainAfterJoin()
    {
        RequireWorldThread();
        std::vector<Observation> local;
        std::unordered_set<std::uint32_t> blocked;
        {
            std::lock_guard<std::mutex> lock(queueMutex);
            local.swap(pending);
            blocked = poisoned;
        }
        std::sort(local.begin(), local.end(), [](Observation const& a, Observation const& b) {
            if (a.guid != b.guid) return a.guid < b.guid;
            if (a.incarnation != b.incarnation) return a.incarnation < b.incarnation;
            return a.sequence < b.sequence;
        });
        for (Observation const& sample : local)
        {
            auto it = sessions.find(sample.guid);
            if (it == sessions.end())
                continue;
            SessionState& state = it->second;
            if (blocked.count(sample.guid) != 0)
            {
                state.invalid = true;
                continue;
            }
#ifdef P13_R9_MUTANT_EPOCH
            if (false)
#else
            if (state.incarnation != sample.incarnation)
#endif
                continue;
            if (state.invalid)
                continue;
#ifdef P13_R9_MUTANT_DUPLICATE
            if (false)
#else
            if (sample.sequence <= state.lastSequence)
#endif
                continue;
            if (sample.sequence != state.lastSequence + 1)
            {
                state.invalid = true;
                continue;
            }
            state.lastSequence = sample.sequence;
            state.lastContribution = sample.contribution;
            ++state.accepted;
            if (sample.battleground)
                ++state.pendingBgSamples;
            ++acceptedOverall;
        }
    }

    bool FinishBgAfterJoin(std::uint32_t guid, std::uint32_t& count)
    {
        RequireWorldThread();
        std::lock_guard<std::mutex> lock(queueMutex);
        bool stillPending = std::any_of(
            pending.begin(), pending.end(),
            [guid](Observation const& o) { return o.guid == guid; });
#ifdef P13_R9_MUTANT_BG_BARRIER
        if (false)
#else
        if (stillPending)
#endif
            return false;
        auto it = sessions.find(guid);
        if (it == sessions.end() || it->second.invalid ||
            poisoned.count(guid) || !it->second.pendingBgSamples)
            return false;
        count = it->second.pendingBgSamples;
        it->second.pendingBgSamples = 0;
        return true;
    }

    SessionState Read(std::uint32_t guid) const
    {
        RequireWorldThread();
        auto it = sessions.find(guid);
        Check(it != sessions.end(), "missing synthetic world-owned session");
        return it->second;
    }

    std::size_t SessionCount() const
    {
        RequireWorldThread();
        return sessions.size();
    }

    std::uint32_t AcceptedTotal() const
    {
        RequireWorldThread();
        return acceptedOverall;
    }

private:
    void RequireWorldThread() const
    {
        Check(std::this_thread::get_id() == owner,
              "world-owned state read/write from a producer thread");
    }

    std::thread::id const owner;
    std::size_t const capacity;
    std::mutex queueMutex;
    std::vector<Observation> pending;
    std::unordered_set<std::uint32_t> poisoned;
    // ONLY the owning thread accesses sessions, including during Drain.
    std::unordered_map<std::uint32_t, SessionState> sessions;
    std::uint32_t acceptedOverall = 0;
};

int main()
{
    try
    {
        // Eight actual concurrent producers; no writes to shared state map.
        constexpr std::uint32_t Workers = 8;
        constexpr std::uint32_t PerWorker = 40;
        HypotheticalWorldOwner world(Workers * PerWorker + 1);
        for (std::uint32_t guid = 1000; guid < 1000 + Workers * PerWorker; ++guid)
            world.Begin(guid, 1);
        std::vector<std::thread> producers;
        for (std::uint32_t worker = 0; worker < Workers; ++worker)
        {
            producers.emplace_back([&, worker] {
                for (std::uint32_t i = 0; i < PerWorker; ++i)
                {
                    std::uint32_t guid = 1000 + worker * PerWorker + i;
                    Check(world.Submit({guid, 1, 1, i + 1, false}),
                          "worker queue unexpectedly full");
                }
            });
        }
        for (auto& producer : producers)
            producer.join();
        world.DrainAfterJoin();
        Check(world.SessionCount() == Workers * PerWorker, "worker state lost");
        Check(world.AcceptedTotal() == Workers * PerWorker, "worker samples not unique");
        Check(world.Read(1000).lastContribution == 1, "first immutable value lost");
        Check(world.Read(1319).lastContribution == 40, "last immutable value lost");

        // GUID reuse: stale previous incarnation cannot poison new session.
        HypotheticalWorldOwner reused(8);
        reused.Begin(71, 1);
        Check(reused.Submit({71, 1, 1, 99, false}), "old enqueue failed");
        reused.Retire(71);
        reused.Begin(71, 2);
        Check(reused.Submit({71, 2, 1, 5, false}), "new enqueue failed");
        reused.DrainAfterJoin();
        Check(reused.Read(71).accepted == 1, "old incarnation accepted");
        Check(reused.Read(71).lastContribution == 5, "stale incarnation leaked");

        // Exact same sequence must never process twice. BG must wait for all
        // queued observations to drain; close must not happen twice.
        HypotheticalWorldOwner bg(8);
        bg.Begin(72, 9);
        Check(bg.Submit({72, 9, 1, 7, true}), "BG first sample missing");
        bg.DrainAfterJoin();
        Check(bg.Submit({72, 9, 2, 8, true}), "BG second sample missing");
        std::uint32_t received = 0;
        Check(!bg.FinishBgAfterJoin(72, received), "BG summary closed before queue drained");
        bg.DrainAfterJoin();
        Check(bg.Submit({72, 9, 2, 8, true}), "duplicate submission missing");
        bg.DrainAfterJoin();
        Check(bg.Read(72).accepted == 2, "duplicate observation processed");
        Check(bg.FinishBgAfterJoin(72, received), "BG summary cannot flush after barrier");
        Check(received == 2, "BG summary sample count wrong");
        Check(!bg.FinishBgAfterJoin(72, received), "BG summary emitted twice");

        // Full queue invalidates the GUID instead of silently discarding only
        // one observation and awarding with a broken sequence.
        HypotheticalWorldOwner full(2);
        full.Begin(73, 1);
        Check(full.Submit({73, 1, 1, 1, false}), "first bounded enqueue failed");
        Check(full.Submit({73, 1, 2, 2, false}), "second bounded enqueue failed");
        Check(!full.Submit({73, 1, 3, 3, false}), "overflow must fail closed");
        full.DrainAfterJoin();
        Check(full.Read(73).invalid && full.Read(73).accepted == 0,
              "overflow leaked partially accepted observations");

        // Missing sequence invalidates future observations.
        HypotheticalWorldOwner gap(8);
        gap.Begin(74, 3);
        Check(gap.Submit({74, 3, 1, 1, false}), "first gap sample missing");
        Check(gap.Submit({74, 3, 3, 3, false}), "third gap sample missing");
        gap.DrainAfterJoin();
        Check(gap.Read(74).invalid && gap.Read(74).accepted == 1,
              "sequence gap silently crossed");

        // Retired GUID without a live incarnation must never be re-created
        // by late callbacks.
        HypotheticalWorldOwner gone(4);
        gone.Begin(75, 4);
        gone.Retire(75);
        Check(gone.Submit({75, 4, 1, 1, false}), "late sample enqueue failed");
        gone.DrainAfterJoin();
        Check(gone.SessionCount() == 0 && gone.AcceptedTotal() == 0,
              "late callback recreated retired identity");

        std::cout << "PASS: P13 R9 synthetic ownership, 8 workers, stale epochs, "
                     "duplicates, BG barrier, overflow, gaps, retired GUID\n";
        std::cout << "LIMITATION: no Player*, monetary semantics, actual hook wiring, "
                     "or proven core incarnation/sequence transport\n";
        return 0;
    }
    catch (std::exception const& e)
    {
        std::cerr << "EXPECTED/REAL MODEL FAILURE: " << e.what() << '\n';
        return 1;
    }
}
