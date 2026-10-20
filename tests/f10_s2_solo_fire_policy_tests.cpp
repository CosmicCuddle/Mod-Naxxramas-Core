/* Deterministic policy tests for HallowsEndSoloFire.h.
 * No worldserver, SQL, or DBC. A pass is not gameplay acceptance.
 * The TRACE lines are compared with the signed-off S1 Python model.
 */

#include "HallowsEndSoloFire.h"

#include <cstdio>
#include <cstring>
#include <string>

namespace
{
int g_failures = 0;

#define CHECK(cond)                                                                 \
    do                                                                              \
    {                                                                               \
        if (!(cond))                                                                \
        {                                                                           \
            std::fprintf(stderr, "CHECK failed %s:%d: %s\n", __FILE__, __LINE__, #cond); \
            ++g_failures;                                                           \
        }                                                                           \
    } while (0)

using namespace NaxxramasCore::HallowsEndSoloFire;

void CheckProvenance()
{
    CHECK(std::strcmp(PinnedCoreSha, "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7") == 0);
    CHECK(std::strcmp(ProspectiveCoreSha, "8daffdabe9202c228e45d833c9a1d399597a15cd") == 0);
    CHECK(std::strcmp(HallowsEndBlobSha, "02282feb50f24debd6bbeb0fe9b928db6adabd21") == 0);
    CHECK(std::strcmp(PlayerbotsSha, "037c01418b5d01506917a3db9b44fd56ac5f965c") == 0);
    CHECK(std::strcmp(IndividualProgressionSha, "4ff4b5fcc1480348f058c632573143e62d4e3a41") == 0);
    CHECK(FireAuraSpellId == 42074u);
    CHECK(FireAuraEffectIndex == 0u);
    CHECK(std::strcmp(DefaultEnabledRaw, "0") == 0);
    CHECK(std::strcmp(DefaultMultiplierRaw, "3") == 0);
    CHECK(std::strcmp(EnabledConfigKey, "NaxxramasCore.HallowsEnd.SoloFire.Enabled") == 0);
    CHECK(std::strcmp(MultiplierConfigKey, "NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier") == 0);
}

void CheckParsing()
{
    CHECK(EnabledFromRaw("0") == 0);
    CHECK(EnabledFromRaw("1") == 1);
    CHECK(EnabledFromRaw(" 1 ") == 1);
    CHECK(EnabledFromRaw("+1") == 1);
    CHECK(EnabledFromRaw("01") == 1);
    CHECK(EnabledFromRaw("2") == 0);
    CHECK(EnabledFromRaw("-1") == 0);
    CHECK(EnabledFromRaw("true") == 0);
    CHECK(EnabledFromRaw("1.0") == 0);
    CHECK(EnabledFromRaw("") == 0);
    CHECK(EnabledFromRaw("  ") == 0);
    CHECK(EnabledFromRaw(DefaultEnabledRaw) == 0);

    for (int32_t value = 1; value <= 8; ++value)
    {
        std::optional<int32_t> parsed = MultiplierFromRaw(std::to_string(value));
        CHECK(parsed.has_value());
        CHECK(*parsed == value);
    }

    for (char const* bad : {"0", "-1", "9", "100", "1.5", "true", "", "  ", "0x3", "3.0", "+9"})
    {
        CHECK(!MultiplierFromRaw(bad).has_value());
    }

    std::optional<int32_t> trimmed = MultiplierFromRaw(" 3 ");
    CHECK(trimmed.has_value() && *trimmed == 3);
    std::optional<int32_t> plus = MultiplierFromRaw("+3");
    CHECK(plus.has_value() && *plus == 3);
    std::optional<int32_t> padded = MultiplierFromRaw("08");
    CHECK(padded.has_value() && *padded == 8);
    CHECK(MultiplierFromRaw(DefaultMultiplierRaw) == 3);
}

void CheckNearbyCounts()
{
    PopulationCounts oneHumanBots[] = {
        {1, 1},
        {2, 1},
        {9, 1},
    };
    for (PopulationCounts counts : oneHumanBots)
    {
        CHECK(EffectiveNearbyCount(1, counts) == 1u);
        CHECK(EffectiveNearbyCount(0, counts) == counts.alivePlayers);
        CHECK(EffectiveNearbyCount(2, counts) == counts.alivePlayers);
    }

    PopulationCounts legacy[] = {
        {8, 0},
        {10, 2},
        {2, 2},
        {9, 2},
        {5, 0},
    };
    for (PopulationCounts counts : legacy)
    {
        CHECK(!SoloPathActive(1, counts.realPlayers));
        CHECK(EffectiveNearbyCount(1, counts) == counts.alivePlayers);
        CHECK(EffectiveNearbyCount(0, counts) == counts.alivePlayers);
    }

    CHECK(SoloPathActive(1, 1));
    CHECK(!SoloPathActive(0, 1));
    CHECK(!SoloPathActive(1, 0));
    CHECK(!SoloPathActive(1, 2));
    CHECK(EffectiveNearbyCount(EnabledFromRaw("2"), PopulationCounts{9, 1}) == 9u);
}

void CheckTimerAndScale()
{
    WatchState watch;
    PollResult first = PollActiveTrigger(watch, true, 1, 2, 1.5f, 0, 1500);
    CHECK(!first.scale.writeScale);
    CHECK(!first.timer.writeTimer);
    CHECK(first.timer.edge == TimerEdge::FirstSight);
    CHECK(first.watch.hasEdge);
    CHECK(first.watch.edgeArmed);
    CHECK(first.watch.lastTick == 0u);
    CHECK(first.watch.lastAmount == 2);

    PollResult again = PollActiveTrigger(first.watch, true, 1, 2, 1.5f, 0, 1500);
    CHECK(!again.timer.writeTimer);
    CHECK(!again.scale.writeScale);
    CHECK(again.timer.edge == TimerEdge::SameTick);

    PollResult grew = PollActiveTrigger(again.watch, true, 1, 3, 1.5f, 1, 1500);
    CHECK(!grew.scale.writeScale);
    CHECK(!grew.timer.writeTimer);
    CHECK(grew.timer.edge == TimerEdge::TickChange);
    CHECK(grew.watch.lastTick == 1u);

    PollResult dropped = PollActiveTrigger(grew.watch, true, 1, 1, 1.5f, 0, 1500);
    CHECK(dropped.scale.writeScale);
    CHECK(dropped.scale.scale == 0.5f);
    CHECK(!dropped.timer.writeTimer);
    CHECK(dropped.watch.lastAmount == 1);

    PollResult held = PollActiveTrigger(dropped.watch, true, 1, 1, 0.5f, 0, 1500);
    CHECK(!held.scale.writeScale);
    CHECK(!held.timer.writeTimer);

    WatchState fresh;
    int writes = 0;
    WatchState cursor;
    for (int i = 0; i < 50; ++i)
    {
        PollResult step = PollActiveTrigger(cursor, true, 3, 2, 1.5f, 0, 1500);
        if (step.timer.writeTimer)
            ++writes;
        cursor = step.watch;
    }
    CHECK(writes == 1);
    CHECK(cursor.lastTick == 0u);
    (void)fresh;

    PollResult stretch = PollActiveTrigger(WatchState{}, true, 2, 2, 1.5f, 0, 1500);
    CHECK(stretch.timer.writeTimer);
    CHECK(stretch.timer.timerValue == 3000);

    PollResult same = PollActiveTrigger(stretch.watch, true, 2, 2, 1.5f, 0, 1500);
    CHECK(!same.timer.writeTimer);

    PollResult changed = PollActiveTrigger(same.watch, true, 8, 3, 1.5f, 1, 1500);
    CHECK(changed.timer.writeTimer);
    CHECK(changed.timer.timerValue == 12000);
    CHECK(changed.watch.lastTick == 1u);

    PollResult wide = PollActiveTrigger(WatchState{}, true, 4, 2, 1.5f, 0, 60001);
    CHECK(!wide.timer.writeTimer);
    CHECK(wide.watch.hasEdge);
    CHECK(wide.watch.lastTick == 0u);

    PollResult top = PollActiveTrigger(WatchState{}, true, 8, 2, 1.5f, 0, 60000);
    CHECK(top.timer.writeTimer);
    CHECK(top.timer.timerValue == 480000);

    PollResult zeroAmp = PollActiveTrigger(WatchState{}, true, 4, 2, 1.5f, 0, 0);
    CHECK(!zeroAmp.timer.writeTimer);
    CHECK(zeroAmp.watch.hasEdge);

    WatchState rejected;
    PollResult bad = PollActiveTrigger(rejected, false, 0, 2, 1.5f, 0, 1500);
    CHECK(!bad.timer.writeTimer);
    CHECK(!bad.watch.hasEdge);
    CHECK(bad.timer.edge == TimerEdge::Rejected);
    CHECK(bad.watch.lastAmount == 2);

    PollResult badDrop = PollActiveTrigger(bad.watch, false, 9, 1, 1.5f, 4, 1500);
    CHECK(badDrop.scale.writeScale);
    CHECK(badDrop.scale.scale == 0.5f);
    CHECK(!badDrop.watch.hasEdge);
    CHECK(badDrop.watch.lastTick == 0u);

    PollResult later = PollActiveTrigger(badDrop.watch, true, 3, 1, 0.5f, 4, 1500);
    CHECK(later.timer.edge == TimerEdge::FirstSight);
    CHECK(later.timer.writeTimer);
    CHECK(later.timer.timerValue == 4500);

    WatchState armed = changed.watch;
    uint32_t storedTick = armed.lastTick;
    PollResult skipped = PollActiveTrigger(armed, false, 3, 3, 1.5f, storedTick + 5, 1500);
    CHECK(!skipped.timer.writeTimer);
    CHECK(skipped.watch.hasEdge);
    CHECK(skipped.watch.edgeArmed);
    CHECK(skipped.watch.lastTick == storedTick);

    PollResult resumed = PollActiveTrigger(skipped.watch, true, 3, 3, 1.5f, storedTick + 5, 1500);
    CHECK(resumed.timer.edge == TimerEdge::TickChange);
    CHECK(resumed.timer.writeTimer);
    CHECK(resumed.timer.timerValue == 4500);
}

char const* EdgeName(TimerEdge edge)
{
    switch (edge)
    {
        case TimerEdge::SameTick:
            return "SameTick";
        case TimerEdge::FirstSight:
            return "FirstSight";
        case TimerEdge::Rearm:
            return "Rearm";
        case TimerEdge::TickChange:
            return "TickChange";
        case TimerEdge::Rejected:
            return "Rejected";
    }
    return "Unknown";
}

struct HeldWatch
{
    bool present = false;
    WatchState watch;
};

/* Same gate the Shade uses. A drop forgets the watch before the next sight. */
HeldWatch StepObservation(
    HeldWatch held,
    bool triggerUsable,
    bool auraPresent,
    int32_t multiplier,
    int32_t amount,
    float scale,
    uint32_t tick,
    int32_t amplitude,
    PollResult* written)
{
    if (RetentionForObservation(triggerUsable, auraPresent) != WatchRetention::Keep)
    {
        if (written)
            *written = PollResult{};
        return HeldWatch{};
    }

    PollResult result = PollActiveTrigger(
        held.present ? held.watch : WatchState{},
        true,
        multiplier,
        amount,
        scale,
        tick,
        amplitude);
    if (written)
        *written = result;

    HeldWatch next;
    next.present = true;
    next.watch = result.watch;
    return next;
}

void CheckAbsentAuraReignite()
{
    CHECK(RetentionForObservation(true, true) == WatchRetention::Keep);
    CHECK(RetentionForObservation(true, false) == WatchRetention::Drop);
    CHECK(RetentionForObservation(false, true) == WatchRetention::Drop);
    CHECK(RetentionForObservation(false, false) == WatchRetention::Drop);

    PollResult armed = PollActiveTrigger(WatchState{}, true, 3, 3, 2.0f, 0, 1500);
    CHECK(armed.timer.edge == TimerEdge::FirstSight);
    CHECK(armed.timer.writeTimer);
    CHECK(armed.timer.timerValue == 4500);
    CHECK(armed.watch.lastAmount == 3);
    CHECK(armed.watch.lastTick == 0u);

    /* The defect: the old watch is still applied to the new aura. */
    PollResult staleSame = PollActiveTrigger(armed.watch, true, 3, 1, 1.0f, 0, 1500);
    CHECK(staleSame.scale.writeScale);
    CHECK(staleSame.scale.scale == 0.5f);
    CHECK(staleSame.timer.edge == TimerEdge::SameTick);
    CHECK(!staleSame.timer.writeTimer);

    PollResult staleMoved = PollActiveTrigger(armed.watch, true, 3, 1, 1.0f, 4, 1500);
    CHECK(staleMoved.scale.writeScale);
    CHECK(staleMoved.scale.scale == 0.5f);
    CHECK(staleMoved.timer.edge == TimerEdge::TickChange);
    CHECK(staleMoved.timer.writeTimer);

    HeldWatch held;
    PollResult first;
    held = StepObservation(held, true, true, 3, 3, 2.0f, 0, 1500, &first);
    CHECK(held.present);
    CHECK(first.timer.edge == TimerEdge::FirstSight);
    CHECK(first.timer.writeTimer);
    CHECK(first.timer.timerValue == 4500);
    CHECK(!first.scale.writeScale);

    PollResult absent;
    held = StepObservation(held, true, false, 3, 0, 0.0f, 0, 0, &absent);
    CHECK(!held.present);

    PollResult reignited;
    held = StepObservation(held, true, true, 3, 1, 1.0f, 0, 1500, &reignited);
    CHECK(held.present);
    CHECK(!reignited.scale.writeScale);
    CHECK(reignited.timer.edge == TimerEdge::FirstSight);
    CHECK(reignited.timer.writeTimer);
    CHECK(reignited.timer.timerValue == 4500);
    CHECK(reignited.watch.lastAmount == 1);
    CHECK(reignited.watch.lastTick == 0u);
    CHECK(reignited.watch.hasEdge);
    CHECK(reignited.watch.edgeArmed);

    HeldWatch moved;
    PollResult movedFirst;
    moved = StepObservation(moved, true, true, 3, 3, 2.0f, 0, 1500, &movedFirst);
    PollResult movedGone;
    moved = StepObservation(moved, true, false, 3, 0, 0.0f, 0, 0, &movedGone);
    CHECK(!moved.present);
    PollResult movedBack;
    moved = StepObservation(moved, true, true, 3, 1, 1.0f, 4, 1500, &movedBack);
    CHECK(!movedBack.scale.writeScale);
    CHECK(movedBack.timer.edge == TimerEdge::FirstSight);
    CHECK(movedBack.timer.writeTimer);
    CHECK(movedBack.timer.timerValue == 4500);
    CHECK(movedBack.watch.lastTick == 4u);
    CHECK(movedBack.watch.lastAmount == 1);

    HeldWatch missing;
    PollResult missingFirst;
    missing = StepObservation(missing, true, true, 3, 3, 2.0f, 2, 1500, &missingFirst);
    CHECK(missing.present);
    PollResult despawned;
    missing = StepObservation(missing, false, false, 3, 0, 0.0f, 0, 0, &despawned);
    CHECK(!missing.present);
    PollResult respawned;
    missing = StepObservation(missing, true, true, 8, 1, 1.0f, 0, 1500, &respawned);
    CHECK(!respawned.scale.writeScale);
    CHECK(respawned.timer.edge == TimerEdge::FirstSight);
    CHECK(respawned.timer.writeTimer);
    CHECK(respawned.timer.timerValue == 12000);

    HeldWatch wrongEntry;
    PollResult wrongFirst;
    wrongEntry = StepObservation(wrongEntry, true, true, 3, 2, 1.5f, 1, 1500, &wrongFirst);
    PollResult wrongGone;
    wrongEntry = StepObservation(wrongEntry, false, true, 3, 2, 1.5f, 1, 1500, &wrongGone);
    CHECK(!wrongEntry.present);

    HeldWatch quiet;
    PollResult quietFirst;
    quiet = StepObservation(quiet, true, true, 1, 3, 2.0f, 0, 1500, &quietFirst);
    PollResult quietGone;
    quiet = StepObservation(quiet, true, false, 1, 0, 0.0f, 0, 0, &quietGone);
    CHECK(!quiet.present);
    PollResult quietBack;
    quiet = StepObservation(quiet, true, true, 1, 1, 1.0f, 0, 1500, &quietBack);
    CHECK(quietBack.timer.edge == TimerEdge::FirstSight);
    CHECK(!quietBack.timer.writeTimer);
    CHECK(!quietBack.scale.writeScale);

    /* An aura that stays present is still the same fire. A bucket that
     * resets the tick and lowers the amount must keep scale correction.
     */
    HeldWatch bucket;
    PollResult bucketSeen;
    bucket = StepObservation(bucket, true, true, 3, 3, 1.5f, 0, 1500, &bucketSeen);
    PollResult bucketDrop;
    bucket = StepObservation(bucket, true, true, 3, 1, 1.5f, 0, 1500, &bucketDrop);
    CHECK(bucket.present);
    CHECK(bucketDrop.scale.writeScale);
    CHECK(bucketDrop.scale.scale == 0.5f);
    CHECK(bucketDrop.timer.edge == TimerEdge::SameTick);

    std::printf(
        "CASE same-tick writeScale=%d edge=%s writeTimer=%d timer=%d\n",
        reignited.scale.writeScale ? 1 : 0,
        EdgeName(reignited.timer.edge),
        reignited.timer.writeTimer ? 1 : 0,
        reignited.timer.timerValue);
    std::printf(
        "CASE different-tick writeScale=%d edge=%s writeTimer=%d timer=%d\n",
        movedBack.scale.writeScale ? 1 : 0,
        EdgeName(movedBack.timer.edge),
        movedBack.timer.writeTimer ? 1 : 0,
        movedBack.timer.timerValue);
    std::printf(
        "CASE missing-trigger writeScale=%d edge=%s writeTimer=%d timer=%d\n",
        respawned.scale.writeScale ? 1 : 0,
        EdgeName(respawned.timer.edge),
        respawned.timer.writeTimer ? 1 : 0,
        respawned.timer.timerValue);
    std::printf(
        "CASE mult1-reignite writeScale=%d edge=%s writeTimer=%d timer=%d\n",
        quietBack.scale.writeScale ? 1 : 0,
        EdgeName(quietBack.timer.edge),
        quietBack.timer.writeTimer ? 1 : 0,
        quietBack.timer.timerValue);
}

void CheckDisarmRearm()
{
    PollResult seen = PollActiveTrigger(WatchState{}, true, 3, 2, 1.5f, 0, 1500);
    CHECK(seen.timer.writeTimer);
    CHECK(seen.timer.timerValue == 4500);

    WatchState off = DisarmWatch(seen.watch);
    CHECK(off.hasEdge);
    CHECK(!off.edgeArmed);
    CHECK(off.lastTick == 0u);
    CHECK(off.hasAmount);
    CHECK(off.lastAmount == 2);

    PollResult rearm = PollActiveTrigger(off, true, 3, 1, 1.5f, 4, 1500);
    CHECK(rearm.timer.edge == TimerEdge::Rearm);
    CHECK(!rearm.timer.writeTimer);
    CHECK(rearm.scale.writeScale);
    CHECK(rearm.scale.scale == 0.5f);
    CHECK(rearm.watch.edgeArmed);
    CHECK(rearm.watch.lastTick == 4u);

    PollResult held = PollActiveTrigger(rearm.watch, true, 8, 1, 0.5f, 4, 1500);
    CHECK(!held.timer.writeTimer);
    CHECK(held.timer.edge == TimerEdge::SameTick);

    PollResult moved = PollActiveTrigger(held.watch, true, 3, 2, 1.0f, 5, 1500);
    CHECK(!moved.scale.writeScale);
    CHECK(moved.timer.writeTimer);
    CHECK(moved.timer.timerValue == 4500);
    CHECK(moved.watch.lastTick == 5u);

    WatchState never = DisarmWatch(WatchState{});
    CHECK(!never.hasEdge);
    PollResult firstAfter = PollActiveTrigger(never, true, 3, 2, 1.5f, 0, 1500);
    CHECK(firstAfter.timer.edge == TimerEdge::FirstSight);
    CHECK(firstAfter.timer.writeTimer);
}

struct ModelFire
{
    int32_t amount = 2;
    float scale = 1.5f;
    int32_t amplitude = 1500;
    int32_t timer = 1500;
    int32_t tick = 0;
    bool alive = true;

    void core_tick()
    {
        tick += 1;
        timer += amplitude;
        if (!alive)
            return;
        int32_t next = amount;
        if (next < 3)
            next += 1;
        else if (tick % 3 != 2)
            return;
        amount = next;
        if (next <= 3)
            scale = static_cast<float>(next) / 2.0f;
    }

    void advance(int32_t diff)
    {
        if (!alive)
            return;
        timer -= diff;
        while (alive && timer <= 0)
            core_tick();
    }

    void bucket()
    {
        if (!alive)
            return;
        if (amount > 2)
        {
            timer = amplitude;
            tick = 0;
            amount -= 2;
            return;
        }
        alive = false;
    }
};

void ApplyPoll(ModelFire& fire, WatchState& watch, bool solo, int mult)
{
    if (!solo)
    {
        watch = DisarmWatch(watch);
        return;
    }

    std::optional<int32_t> parsed = MultiplierFromRaw(std::to_string(mult));
    PollResult result = PollActiveTrigger(
        watch,
        parsed.has_value(),
        parsed.value_or(0),
        fire.amount,
        fire.scale,
        static_cast<uint32_t>(fire.tick),
        fire.amplitude);
    if (result.scale.writeScale)
        fire.scale = result.scale.scale;
    if (result.timer.writeTimer)
        fire.timer = result.timer.timerValue;
    watch = result.watch;
}

void PrintTrace(char const* step, ModelFire const& fire, WatchState const& watch)
{
    std::printf(
        "TRACE step=%s timer=%d tick=%d amount=%d scale=%.6f armed=%d has_edge=%d last_tick=%s alive=%d\n",
        step,
        fire.timer,
        fire.tick,
        fire.amount,
        fire.scale,
        watch.edgeArmed ? 1 : 0,
        watch.hasEdge ? 1 : 0,
        watch.edgeArmed ? std::to_string(watch.lastTick).c_str() : "na",
        fire.alive ? 1 : 0);
}

void RunSharedTrace()
{
    ModelFire fire;
    WatchState watch;

    auto trace = [&](char const* step)
    {
        PrintTrace(step, fire, watch);
    };

    fire.advance(400);
    trace("advance-400");
    ApplyPoll(fire, watch, true, 0);
    trace("poll-reject-0");
    fire.amount = 1;
    fire.scale = 1.5f;
    ApplyPoll(fire, watch, true, 9);
    trace("poll-reject-9-after-fall");
    ApplyPoll(fire, watch, true, 3);
    trace("poll-first-3");
    ApplyPoll(fire, watch, true, 3);
    trace("poll-same-3");
    fire.advance(100);
    trace("advance-100");
    ApplyPoll(fire, watch, true, 2);
    trace("poll-same-2");
    fire.advance(4400);
    trace("advance-4400");
    ApplyPoll(fire, watch, true, 8);
    trace("poll-tick-8");
    fire.advance(12000);
    trace("advance-to-amount-3");
    fire.bucket();
    fire.advance(200);
    trace("bucket-advance-200");
    ApplyPoll(fire, watch, true, 1);
    trace("poll-mult1-after-bucket");
    ApplyPoll(fire, watch, false, 3);
    trace("poll-off");
    fire.amount = 0;
    fire.scale = 1.5f;
    ApplyPoll(fire, watch, false, 3);
    trace("poll-off-during-fall");
    ApplyPoll(fire, watch, true, 3);
    trace("poll-rearm");
    ApplyPoll(fire, watch, true, 3);
    trace("poll-rearm-same");
    int32_t guard = 0;
    while (fire.alive && fire.tick == static_cast<int32_t>(watch.lastTick) && guard < 20)
    {
        fire.advance(fire.amplitude > 0 ? fire.amplitude : 1);
        ++guard;
    }
    trace("advance-to-next-tick");
    ApplyPoll(fire, watch, true, 3);
    trace("poll-after-rearm-tick");
}
}

int RunRetainQuery(int argc, char** argv)
{
    if (argc != 4)
        return 2;
    int triggerUsable = 0;
    int auraPresent = 0;
    if (std::sscanf(argv[2], "%d", &triggerUsable) != 1 ||
        std::sscanf(argv[3], "%d", &auraPresent) != 1)
        return 2;
    WatchRetention retention = RetentionForObservation(triggerUsable != 0, auraPresent != 0);
    std::printf("%s\n", retention == WatchRetention::Keep ? "Keep" : "Drop");
    return 0;
}

int RunPollQuery(int argc, char** argv)
{
    if (argc != 13)
        return 2;

    int hasEdge = 0;
    int edgeArmed = 0;
    unsigned int lastTick = 0;
    int hasAmount = 0;
    int lastAmount = 0;
    int accepted = 0;
    int multiplier = 0;
    int amount = 0;
    float scale = 0.0f;
    unsigned int tick = 0;
    int amplitude = 0;
    if (std::sscanf(argv[2], "%d", &hasEdge) != 1 ||
        std::sscanf(argv[3], "%d", &edgeArmed) != 1 ||
        std::sscanf(argv[4], "%u", &lastTick) != 1 ||
        std::sscanf(argv[5], "%d", &hasAmount) != 1 ||
        std::sscanf(argv[6], "%d", &lastAmount) != 1 ||
        std::sscanf(argv[7], "%d", &accepted) != 1 ||
        std::sscanf(argv[8], "%d", &multiplier) != 1 ||
        std::sscanf(argv[9], "%d", &amount) != 1 ||
        std::sscanf(argv[10], "%f", &scale) != 1 ||
        std::sscanf(argv[11], "%u", &tick) != 1 ||
        std::sscanf(argv[12], "%d", &amplitude) != 1)
        return 2;

    WatchState watch;
    watch.hasEdge = hasEdge != 0;
    watch.edgeArmed = edgeArmed != 0;
    watch.lastTick = lastTick;
    watch.hasAmount = hasAmount != 0;
    watch.lastAmount = lastAmount;

    PollResult result = PollActiveTrigger(
        watch,
        accepted != 0,
        multiplier,
        amount,
        scale,
        tick,
        amplitude);
    std::printf(
        "writeScale=%d scale=%.6f edge=%s writeTimer=%d timer=%d hasEdge=%d edgeArmed=%d lastTick=%u hasAmount=%d lastAmount=%d\n",
        result.scale.writeScale ? 1 : 0,
        result.scale.scale,
        EdgeName(result.timer.edge),
        result.timer.writeTimer ? 1 : 0,
        result.timer.timerValue,
        result.watch.hasEdge ? 1 : 0,
        result.watch.edgeArmed ? 1 : 0,
        result.watch.lastTick,
        result.watch.hasAmount ? 1 : 0,
        result.watch.lastAmount);
    return 0;
}

int main(int argc, char** argv)
{
    if (argc > 1 && std::strcmp(argv[1], "--retain") == 0)
        return RunRetainQuery(argc, argv);
    if (argc > 1 && std::strcmp(argv[1], "--poll") == 0)
        return RunPollQuery(argc, argv);

    CheckProvenance();
    CheckParsing();
    CheckNearbyCounts();
    CheckTimerAndScale();
    CheckAbsentAuraReignite();
    CheckDisarmRearm();
    if (g_failures != 0)
    {
        std::fprintf(stderr, "F10_S2_POLICY_FAIL %d\n", g_failures);
        return 1;
    }
    RunSharedTrace();
    std::printf("F10_S2_POLICY_OK\n");
    return 0;
}
