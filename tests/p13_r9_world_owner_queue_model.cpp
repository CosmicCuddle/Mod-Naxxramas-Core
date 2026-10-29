// P13-R9 TEST-ONLY abstract candidate: a bounded immutable map-worker observation
// queue, with EXCLUSIVE world-thread processing after worker join.
//
// NOT production HonorOverflow logic. No Player*, money, chat, DB, hooks,
// real server, or any source modification. Tests only ownership invariants.
// Input sequence and generation are hypothetical; pinned core does NOT
// provide this contract automatically. C++17/20, ASan+UBSan, TSAN.
#include <algorithm>
#include <atomic>
#include <limits>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iostream>
#include <mutex>
#include <set>
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
        SessionState state;
        state.incarnation = incarnation;
        sessions[guid] = state;
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
        if (poisoned.count(QuarantineKey(observation.guid, observation.incarnation)))
            return false;
#ifdef P13_R9_MUTANT_OVERFLOW
        if (false)
#else
        if (pending.size() >= capacity)
#endif
        {
            // A dropped event invalidates that GUID's sequence, not just the
            // single missing item. No guessed monetary recovery is allowed.
            poisoned.insert(QuarantineKey(observation.guid, observation.incarnation));
            return false;
        }
        pending.push_back(observation);
        return true;
    }

    void DrainAfterJoin()
    {
        RequireWorldThread();
        std::vector<Observation> local;
        std::set<std::pair<std::uint32_t, std::uint64_t>> blocked;
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
            // Identity matching must PRECEDE applying a quarantine, or
            // a queued poisoned old epoch can invalidate a fresh session.
#ifdef P13_R9_MUTANT_EPOCH
            if (false)
#else
            if (state.incarnation != sample.incarnation)
#endif
                continue;
            if (blocked.count(QuarantineKey(sample.guid, sample.incarnation)) != 0)
            {
                state.invalid = true;
                continue;
            }
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
        (void)stillPending;
        if (false)
#else
        if (stillPending)
#endif
            return false;
        auto it = sessions.find(guid);
        if (it == sessions.end() || it->second.invalid ||
            poisoned.count(QuarantineKey(guid, it->second.incarnation)) ||
            !it->second.pendingBgSamples)
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
    using IncarnationKey = std::pair<std::uint32_t, std::uint64_t>;

    static IncarnationKey QuarantineKey(std::uint32_t guid, std::uint64_t incarnation)
    {
#ifdef P13_R9_MUTANT_POISON_SCOPE
        (void)incarnation;
        return {guid, 0}; // DELIBERATE wrong variant: poisons future sessions
#else
        return {guid, incarnation};
#endif
    }

    void RequireWorldThread() const
    {
        Check(std::this_thread::get_id() == owner,
              "world-owned state read/write from a producer thread");
    }

    std::thread::id const owner;
    std::size_t const capacity;
    std::mutex queueMutex;
    std::vector<Observation> pending;
    // Model-only quarantine is scoped to the hypothetical incarnation. This
    // set is NOT bounded/pruned: memory/lifetime policy is still unresolved.
    std::set<IncarnationKey> poisoned;
    // ONLY the owning thread accesses sessions, including during Drain.
    std::unordered_map<std::uint32_t, SessionState> sessions;
    std::uint32_t acceptedOverall = 0;
};

// An INDEPENDENT test-only admission sketch, distinct from the R9 world-state
// queue above. Its hypothetical world-issued lease DOES NOT exist in pinned
// core. It proves only that stale producer traffic cannot consume this model's
// bounded queue/retired registry. This is not a Player identity or payout fix.
class HypotheticalBoundedAdmission final
{
public:
    struct Lease final
    {
        std::uint32_t guid = 0;
        std::uint64_t incarnation = 0;
    };

    HypotheticalBoundedAdmission(std::size_t maxSessions, std::size_t maxPending)
        : owner(std::this_thread::get_id()),
          liveCapacity(maxSessions), queueCapacity(maxPending)
    {
        Check(maxSessions > 0 && maxPending > 0, "zero synthetic admission limit");
    }

    Lease Begin(std::uint32_t guid)
    {
        RequireWorldThread();
        std::lock_guard<std::mutex> lock(mutex);
        Check(guid > 0 && active.find(guid) == active.end(), "duplicate live lease");
        Check(active.size() < liveCapacity, "active synthetic sessions at bound");
        Check(nextIncarnation < std::numeric_limits<std::uint64_t>::max(),
              "synthetic incarnation counter exhausted");
        Lease result{guid, ++nextIncarnation};
        active.emplace(guid, Active{result.incarnation, false});
        return result;
    }

    void Retire(Lease lease)
    {
        RequireWorldThread();
        std::lock_guard<std::mutex> lock(mutex);
        auto it = active.find(lease.guid);
        Check(it != active.end() && it->second.incarnation == lease.incarnation,
              "retire requires active matching lease");
        active.erase(it);
#ifndef P13_R9_MUTANT_ADMISSION_PURGE
        pending.erase(std::remove_if(pending.begin(), pending.end(),
            [lease](Observation const& sample) {
                return sample.guid == lease.guid &&
                       sample.incarnation == lease.incarnation;
            }), pending.end());
#endif
    }

    bool Submit(Observation observation)
    {
        std::lock_guard<std::mutex> lock(mutex);
        auto it = active.find(observation.guid);
        if (it == active.end())
            return false;
#ifndef P13_R9_MUTANT_ADMISSION_STALE
        if (it->second.incarnation != observation.incarnation)
            return false;
#endif
        if (it->second.invalid)
            return false;
        if (pending.size() >= queueCapacity)
        {
            it->second.invalid = true; // No partial processing for this lease.
            return false;
        }
        pending.push_back(observation);
        return true;
    }

    std::size_t DrainAfterJoin()
    {
        RequireWorldThread();
        std::lock_guard<std::mutex> lock(mutex);
        std::size_t accepted = 0;
        for (Observation const& sample : pending)
        {
            auto it = active.find(sample.guid);
            if (it != active.end() &&
                it->second.incarnation == sample.incarnation && !it->second.invalid)
                ++accepted;
        }
        pending.clear();
        return accepted;
    }

    std::size_t Pending() const
    {
        RequireWorldThread();
        std::lock_guard<std::mutex> lock(mutex);
        return pending.size();
    }

    std::size_t ActiveCount() const
    {
        RequireWorldThread();
        std::lock_guard<std::mutex> lock(mutex);
        return active.size();
    }

private:
    struct Active final
    {
        std::uint64_t incarnation = 0;
        bool invalid = false;
    };

    void RequireWorldThread() const
    {
        Check(std::this_thread::get_id() == owner,
              "admission lifecycle is world-owner only");
    }

    std::thread::id const owner;
    std::size_t const liveCapacity;
    std::size_t const queueCapacity;
    std::uint64_t nextIncarnation = 0; // Hypothetical, not a core API.
    mutable std::mutex mutex;
    std::unordered_map<std::uint32_t, Active> active;
    std::vector<Observation> pending;
};

void TestHypotheticalBoundedAdmission()
{
    HypotheticalBoundedAdmission gate(1, 2);
    auto old = gate.Begin(88);
    Check(gate.Submit({old.guid, old.incarnation, 1, 1, false}),
          "old lease admission failed");
    gate.Retire(old);
    Check(gate.Pending() == 0, "retired pending observations were not purged");
    Check(gate.ActiveCount() == 0, "retired lease held active memory");

    auto fresh = gate.Begin(88);
    Check(fresh.incarnation > old.incarnation,
          "world-issued synthetic incarnation did not advance");
    std::atomic<bool> staleAdmitted{false};
    std::vector<std::thread> staleWorkers;
    for (int worker = 0; worker < 8; ++worker)
    {
        staleWorkers.emplace_back([&, worker] {
            for (int i = 0; i < 100; ++i)
            {
                if (gate.Submit({old.guid, old.incarnation,
                                 static_cast<std::uint64_t>(worker * 100 + i + 1),
                                 9, false}))
                    staleAdmitted.store(true, std::memory_order_relaxed);
            }
        });
    }
    for (auto& worker : staleWorkers)
        worker.join();
    Check(!staleAdmitted.load(std::memory_order_relaxed),
          "stale workers consumed active queue capacity");
    Check(gate.Pending() == 0, "stale workers occupied the new queue");
    Check(gate.Submit({fresh.guid, fresh.incarnation, 1, 42, false}),
          "fresh incarnation cannot submit after stale worker flood");
    Check(gate.DrainAfterJoin() == 1, "fresh admission lost after stale flood");
    gate.Retire(fresh);

    // Hypothetical ownership does not accumulate tombstones. The only retained
    // counter is a 64-bit monotonic sequence; exhaustion fails closed.
    for (int i = 0; i < 1500; ++i)
    {
        auto lease = gate.Begin(88);
        Check(gate.Submit({lease.guid, lease.incarnation, 1, 2, false}),
              "bounded relog admission failed");
        gate.Retire(lease);
        Check(gate.ActiveCount() == 0 && gate.Pending() == 0,
              "retired synthetic sessions accumulated unbounded entries");
    }

    auto current = gate.Begin(88);
    Check(gate.Submit({current.guid, current.incarnation, 1, 3, false}),
          "first current event failed");
    Check(gate.Submit({current.guid, current.incarnation, 2, 4, false}),
          "second current event failed");
    Check(!gate.Submit({current.guid, current.incarnation, 3, 5, false}),
          "admission queue overflow must fail closed");
    Check(gate.DrainAfterJoin() == 0,
          "invalid lease partially admitted after queue overflow");
    gate.Retire(current);
    auto replacement = gate.Begin(88);
    Check(gate.Submit({replacement.guid, replacement.incarnation, 1, 6, false}),
          "new lease stayed poisoned after prior admission overflow");
    Check(gate.DrainAfterJoin() == 1, "new lease not admitted after old overflow");
    gate.Retire(replacement);
    Check(gate.ActiveCount() == 0 && gate.Pending() == 0,
          "bounded admission did not reclaim synthetic state");
    std::cout << "PASS: bounded admission alternative, 8 stale workers, "
                 "1500 relogs, active/queue bounds, overflow recovery\n";
    std::cout << "LIMITATION: invented world-issued leases; no real core ownership, "
                 "ordering, currency or BG semantics\n";
}

// SOURCE-BOUNDARY COUNTEREXAMPLE: a new WorldSession/socket does NOT imply
// a new Player object. Pinned core's same-Player offline reconnect rebinds
// Player::SetSession to a different WorldSession WITHOUT OnPlayerLogin; true
// fresh DB login creates a new Player and invokes the login script hook.
// The tokens here are hypothetical, never a core API or production hook.
struct HypotheticalPlayerLifecycle final
{
    std::uint64_t playerLifetime = 0;
    std::uint64_t socketSession = 0;
    std::uint32_t honorSnapshot = 0;
    std::uint32_t pendingBgObservations = 0;

    void NewPlayerFromDB(std::uint64_t lifetime, std::uint64_t socket)
    {
        playerLifetime = lifetime;
        socketSession = socket;
        honorSnapshot = 0;
        pendingBgObservations = 0;
    }

    void RecordHonorAndBg(std::uint32_t honor, std::uint32_t bgCount)
    {
        honorSnapshot = honor;
        pendingBgObservations = bgCount;
    }

    void RebindSamePlayerAfterDisconnect(std::uint64_t newSocket)
    {
        Check(playerLifetime != 0 && newSocket != socketSession,
              "invalid synthetic same-Player session rebind");
        socketSession = newSocket;
#ifdef P13_R9_MUTANT_RECONNECT_ROTATE
        ++playerLifetime; // WRONG: conflates WorldSession with Player lifetime
#endif
#ifdef P13_R9_MUTANT_RECONNECT_CLEAR
        pendingBgObservations = 0; // WRONG: fakes absent OnPlayerLogin reset
#endif
    }

    void RetirePlayer()
    {
        playerLifetime = 0;
        socketSession = 0;
        honorSnapshot = 0;
        pendingBgObservations = 0;
    }
};

void TestReconnectIdentityIsNotSocketIdentity()
{
    HypotheticalPlayerLifecycle p;
    p.NewPlayerFromDB(101, 501);
    p.RecordHonorAndBg(75000, 3);
    p.RebindSamePlayerAfterDisconnect(502);
    Check(p.playerLifetime == 101,
          "socket reconnect rotated live Player lifetime");
    Check(p.socketSession == 502 && p.honorSnapshot == 75000,
          "socket reconnect lost live honor snapshot");
    Check(p.pendingBgObservations == 3,
          "socket reconnect erased pending BG summary without logout hook");
    // True end-of-Player lifetime, not merely disconnect; a later DB-created
    // Player with the same GUID must NOT inherit old in-memory state.
    p.RetirePlayer();
    p.NewPlayerFromDB(102, 503);
    Check(p.playerLifetime == 102 && p.honorSnapshot == 0 &&
          p.pendingBgObservations == 0,
          "fresh DB Player inherited old Player lifetime state");
    std::cout << "PASS: pinned reconnect counterexample, new socket != new Player lifetime\n";
    std::cout << "LIMITATION: source-bound synthetic lifecycle only; no owner disconnect "
                 "or Worldserver replay\n";
}

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
        Check(!bg.Read(72).invalid, "duplicate sequence invalidated state");
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

        // A dropped item in the old hypothetical incarnation must not
        // automatically poison a fresh incarnation of the same GUID.
        // This is NOT proof that original core exposes a reliable epoch.
        HypotheticalWorldOwner recovered(2);
        recovered.Begin(76, 1);
        Check(recovered.Submit({76, 1, 1, 2, false}), "old first enqueue missing");
        Check(recovered.Submit({76, 1, 2, 3, false}), "old second enqueue missing");
        Check(!recovered.Submit({76, 1, 3, 4, false}), "old overflow not quarantined");
        recovered.DrainAfterJoin();
        Check(recovered.Read(76).invalid, "old overflow state was not blocked");
        recovered.Retire(76);
        recovered.Begin(76, 2);
        Check(recovered.Submit({76, 2, 1, 12, false}),
              "new incarnation rejected by stale overflow quarantine");
        // A late, formerly poisoned old-epoch observation remains rejected.
        Check(!recovered.Submit({76, 1, 4, 13, false}),
              "stale poisoned incarnation was unexpectedly admitted");
        recovered.DrainAfterJoin();
        Check(!recovered.Read(76).invalid && recovered.Read(76).accepted == 1 &&
                  recovered.Read(76).lastContribution == 12,
              "old epoch poison leaked into current incarnation");

        // Overflowed old epoch's already queued observations must NOT
        // invalidate a NEW session when relog happens before draining.
        HypotheticalWorldOwner pendingOld(2);
        pendingOld.Begin(77, 1);
        Check(pendingOld.Submit({77, 1, 1, 1, false}), "old pending first missing");
        Check(pendingOld.Submit({77, 1, 2, 2, false}), "old pending second missing");
        Check(!pendingOld.Submit({77, 1, 3, 3, false}), "old pending overflow missing");
        pendingOld.Retire(77);
        pendingOld.Begin(77, 2);
        pendingOld.DrainAfterJoin();
        Check(!pendingOld.Read(77).invalid, "poisoned old pending batch invalidated new epoch");
        Check(pendingOld.Submit({77, 2, 1, 15, false}), "new after old pending batch rejected");
        pendingOld.DrainAfterJoin();
        Check(pendingOld.Read(77).accepted == 1 &&
                  pendingOld.Read(77).lastContribution == 15,
              "new epoch swallowed after old poisoned batch");

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

        TestReconnectIdentityIsNotSocketIdentity();
        TestHypotheticalBoundedAdmission();

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
