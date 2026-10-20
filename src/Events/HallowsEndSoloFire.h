/*
 * Naxxramas Core - Hallow's End solo fire policy.
 *
 * Pure decisions for the module Shade AI. This header does not include
 * AzerothCore types and does not cast, extinguish, or resize anything.
 * HallowsEndShadeOfTheHorseman.cpp is the only caller that may write a
 * live aura timer or an object scale, and only when a decision here says so.
 *
 * Provenance, read from Grimfeather/azerothcore-wotlk (not upstream):
 *   pinned core       a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7
 *   prospective core  8daffdabe9202c228e45d833c9a1d399597a15cd
 *   hallows_end.cpp   blob 02282feb50f24debd6bbeb0fe9b928db6adabd21
 *                     (byte-identical at both commits; lines below apply to both)
 *   spell_hallows_end_base_fire          hallows_end.cpp:305
 *     CalcPeriodic                       hallows_end.cpp:309
 *     HandleEffectPeriodicUpdate         hallows_end.cpp:320
 *     registered                         hallows_end.cpp:1511
 *   npc_soh_fire_trigger                 hallows_end.cpp:523
 *     self-cast 42074                    hallows_end.cpp:536
 *     GetAuraEffect(..., EFFECT_0)       hallows_end.cpp:537
 *     SpellHit scale 0.5f + 0.5f*amount  hallows_end.cpp:566
 *     bucket splash 42348                hallows_end.cpp:570
 *     bucket ResetPeriodic(true)         hallows_end.cpp:577
 *     bucket SetAmount(amt - 2)          hallows_end.cpp:578
 *     bucket RemoveAllAuras              hallows_end.cpp:581
 *     registered                         hallows_end.cpp:1519
 *   AuraEffect::GetAmplitude             SpellAuraEffects.h:59
 *   AuraEffect::GetAmount                SpellAuraEffects.h:64
 *   AuraEffect::SetPeriodicTimer         SpellAuraEffects.h:69
 *   AuraEffect::GetTickNumber            SpellAuraEffects.h:87
 *   AuraEffect::ResetPeriodic            SpellAuraEffects.h:89
 *   m_amplitude is private               SpellAuraEffects.h:142
 *   Unit::GetAuraEffect                  Unit.h:1439 at the pinned commit,
 *                                        Unit.h:1440 at the prospective commit
 *   Object::GetObjectScale               Object.h:126
 *   Object::SetObjectScale               Object.h:127
 *   AnyPlayerInObjectRangeCheck          GridNotifiers.h:1379
 *     defaults reqAlive = true, disallowGM = false at GridNotifiers.h:1382
 *   EFFECT_0 = 0                         SharedDefines.h:31
 *   ConfigMgr::GetOption                 Config.h:68
 *   string GetOption does not parse ints Config.cpp:601
 *   numeric GetOption substitutes the default for a bad token
 *                                        Config.cpp:584
 *   quoted config characters are removed Config.cpp:327
 *   GET_PLAYERBOT_AI                     mod-playerbots 037c01418b5d01506917a3db9b44fd56ac5f965c
 *                                        src/Script/Playerbots.h:31
 *   Individual Progression pin           4ff4b5fcc1480348f058c632573143e62d4e3a41
 *                                        (no Hallow's End fire script)
 *
 * The Shade poll must not restart ticks. There is no amplitude setter.
 * A splash that removes the aura, and the 2-to-3 spread tick, stay inside
 * the core script. This policy cannot fake either one.
 *
 * While the solo path is active, a missing trigger or a missing 42074
 * effect drops that GUID's watch. The next effect is a first sight and
 * has no remembered amount. DisarmWatch is a different operation: the
 * path going inactive keeps the amount so a later re-arm can still see
 * a drop. A removal and a new cast that both finish between two polls
 * are not observed. No public field identifies one Aura application:
 *   Aura::GetApplyTime                 SpellAuras.h:129 at both SHAs
 *     returns m_applyTime, whole seconds (SpellAuras.h:262)
 *     set from GameTime::GetGameTime() SpellAuras.cpp:355 at the pinned SHA,
 *                                      SpellAuras.cpp:362 at the prospective SHA
 *   GameTime::GetGameTime              GameTime.h:30 at both SHAs, returns Seconds
 *   GameTime::GetGameTimeMS            GameTime.h:33 at both SHAs, not stored on Aura
 *   Aura::GetId                        SpellAuras.cpp:410 pinned, :417 prospective
 *                                      returns the spell id, not an instance
 *   AuraEffect::GetId                  SpellAuraEffects.cpp:432 at both SHAs
 *                                      returns the spell id
 *   AuraEffect::GetBase                SpellAuraEffects.h:49 at both SHAs
 *                                      returns Aura*. The pointer does not
 *                                      outlive the aura, so it is not stored.
 */

#ifndef NAXXRAMAS_CORE_HALLOWS_END_SOLO_FIRE_H
#define NAXXRAMAS_CORE_HALLOWS_END_SOLO_FIRE_H

#include <charconv>
#include <cstdint>
#include <limits>
#include <optional>
#include <string_view>
#include <system_error>

namespace NaxxramasCore::HallowsEndSoloFire
{
inline constexpr char EnabledConfigKey[] =
    "NaxxramasCore.HallowsEnd.SoloFire.Enabled";
inline constexpr char MultiplierConfigKey[] =
    "NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier";
inline constexpr char DefaultEnabledRaw[] = "0";
inline constexpr char DefaultMultiplierRaw[] = "3";

/* Non-inline. HallowsEndSoloFireConfig.cpp reads the raw strings and
 * applies EnabledFromRaw / MultiplierFromRaw. The Shade script calls
 * these. They are the binary markers for the config read.
 */
int32_t ReadHallowsEndSoloFireEnabledSetting();
std::optional<int32_t> ReadHallowsEndSoloFireMultiplierSetting();

inline constexpr uint32_t FireAuraSpellId = 42074;
inline constexpr uint8_t FireAuraEffectIndex = 0;
inline constexpr int32_t MinAcceptedMultiplier = 1;
inline constexpr int32_t MaxAcceptedMultiplier = 8;
inline constexpr int32_t MinWritableMultiplier = 2;
inline constexpr int32_t MinWritableAmplitude = 1;
inline constexpr int32_t MaxWritableAmplitude = 60000;

inline constexpr char PinnedCoreSha[] =
    "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7";
inline constexpr char ProspectiveCoreSha[] =
    "8daffdabe9202c228e45d833c9a1d399597a15cd";
inline constexpr char HallowsEndBlobSha[] =
    "02282feb50f24debd6bbeb0fe9b928db6adabd21";
inline constexpr char PlayerbotsSha[] =
    "037c01418b5d01506917a3db9b44fd56ac5f965c";
inline constexpr char IndividualProgressionSha[] =
    "4ff4b5fcc1480348f058c632573143e62d4e3a41";

/* Whole token, base 10. Leading or trailing ASCII space is ignored.
 * A sign is allowed. Any other leftover character rejects the token.
 * The numeric config parser is not used: a bad token there becomes the
 * default instead of a rejection.
 */
inline std::optional<int32_t> ParseStrictInt(std::string_view raw)
{
    std::size_t begin = 0;
    while (begin < raw.size() &&
           (raw[begin] == ' ' || raw[begin] == '\t' ||
            raw[begin] == '\r' || raw[begin] == '\n'))
        ++begin;

    std::size_t end = raw.size();
    while (end > begin &&
           (raw[end - 1] == ' ' || raw[end - 1] == '\t' ||
            raw[end - 1] == '\r' || raw[end - 1] == '\n'))
        --end;

    if (begin >= end)
        return std::nullopt;

    std::string_view text = raw.substr(begin, end - begin);
    /* libstdc++ from_chars rejects a leading '+'. A single plus is still
     * a sign, so strip one. A second sign fails the full-token check.
     */
    if (text.front() == '+')
    {
        text.remove_prefix(1);
        if (text.empty())
            return std::nullopt;
    }

    int32_t value = 0;
    char const* first = text.data();
    char const* last = first + text.size();
    std::from_chars_result parsed = std::from_chars(first, last, value, 10);
    if (parsed.ec != std::errc() || parsed.ptr != last)
        return std::nullopt;
    return value;
}

/* Exactly 1 enables the solo path. Every other token, including a
 * missing-key default of "0", is off. Values are not clamped.
 */
inline int32_t EnabledFromRaw(std::string_view raw)
{
    std::optional<int32_t> parsed = ParseStrictInt(raw);
    if (!parsed || *parsed != 1)
        return 0;
    return 1;
}

/* Integers 1 through 8. 1 is a timer-write no-op. Anything else,
 * including 0, negatives, and values above 8, is rejected. Not clamped.
 */
inline std::optional<int32_t> MultiplierFromRaw(std::string_view raw)
{
    std::optional<int32_t> parsed = ParseStrictInt(raw);
    if (!parsed ||
        *parsed < MinAcceptedMultiplier ||
        *parsed > MaxAcceptedMultiplier)
        return std::nullopt;
    return parsed;
}

struct PopulationCounts
{
    uint32_t alivePlayers = 0;
    uint32_t realPlayers = 0;
};

inline bool SoloPathActive(int32_t enabled, uint32_t realPlayers)
{
    return enabled == 1 && realPlayers == 1;
}

/* Nearby count observed by the unchanged CastFires formulas.
 * Solo on and exactly one real player: 1.
 * Off, zero real players, or two or more real players: the legacy alive count.
 */
inline uint32_t EffectiveNearbyCount(int32_t enabled, PopulationCounts counts)
{
    if (SoloPathActive(enabled, counts.realPlayers))
        return 1;
    return counts.alivePlayers;
}

inline bool AmplitudeWritable(int32_t amplitude)
{
    return amplitude >= MinWritableAmplitude && amplitude <= MaxWritableAmplitude;
}

inline float AmountMatchedScale(int32_t amount)
{
    return static_cast<float>(amount) / 2.0f;
}

/* Product of a 2..8 multiplier and an in-range amplitude.
 * The product has to fit in the timer field. 1 is not writable.
 */
inline bool TimerProduct(int32_t amplitude, int32_t multiplier, int32_t& out)
{
    if (multiplier < MinWritableMultiplier || multiplier > MaxAcceptedMultiplier)
        return false;
    if (!AmplitudeWritable(amplitude))
        return false;

    int64_t product =
        static_cast<int64_t>(amplitude) * static_cast<int64_t>(multiplier);
    if (product > static_cast<int64_t>(std::numeric_limits<int32_t>::max()) ||
        product < static_cast<int64_t>(std::numeric_limits<int32_t>::min()))
        return false;

    out = static_cast<int32_t>(product);
    return true;
}

enum class TimerEdge : uint8_t
{
    SameTick = 0,
    FirstSight,
    Rearm,
    TickChange,
    Rejected
};

/* Keep: this GUID resolved to entry 23686 and 42074 effect 0 is present.
 * Drop: the trigger is missing, the entry is wrong, or the effect is absent.
 * Drop removes the watch. It is not DisarmWatch.
 */
enum class WatchRetention : uint8_t
{
    Drop = 0,
    Keep
};

struct WatchState
{
    bool hasEdge = false;
    bool edgeArmed = false;
    uint32_t lastTick = 0;
    bool hasAmount = false;
    int32_t lastAmount = 0;
};

struct ScaleDecision
{
    bool writeScale = false;
    float scale = 0.0f;
};

struct TimerDecision
{
    TimerEdge edge = TimerEdge::SameTick;
    bool writeTimer = false;
    int32_t timerValue = 0;
};

struct PollResult
{
    ScaleDecision scale;
    TimerDecision timer;
    WatchState watch;
};

/* Solo-active observation gate. Both inputs have to be true to keep
 * the watch. The next kept observation then starts from an empty watch
 * when the previous one was dropped, which is first sight and no
 * remembered amount. This does not see a 42074 that was removed and
 * cast again entirely between two calls.
 */
inline WatchRetention RetentionForObservation(bool triggerUsable, bool auraPresent)
{
    if (triggerUsable && auraPresent)
        return WatchRetention::Keep;
    return WatchRetention::Drop;
}

/* One active-span observation of a single trigger.
 * Scale uses the last active amount and does not read the multiplier.
 * A rejected multiplier leaves edge memory untouched.
 * Re-arm stores the tick it sees now and does not write the timer.
 * The same tick writes nothing. First sight and a later tick change may.
 */
inline PollResult PollActiveTrigger(
    WatchState watch,
    bool multiplierAccepted,
    int32_t multiplier,
    int32_t amount,
    float scale,
    uint32_t tick,
    int32_t amplitude)
{
    PollResult result;
    result.watch = watch;

    if (watch.hasAmount &&
        amount < watch.lastAmount &&
        scale > AmountMatchedScale(amount))
    {
        result.scale.writeScale = true;
        result.scale.scale = AmountMatchedScale(amount);
    }

    result.watch.hasAmount = true;
    result.watch.lastAmount = amount;

    if (!multiplierAccepted)
    {
        result.timer.edge = TimerEdge::Rejected;
        return result;
    }

    auto finish = [&](TimerEdge edge, bool allowWrite)
    {
        result.timer.edge = edge;
        result.watch.hasEdge = true;
        result.watch.edgeArmed = true;
        result.watch.lastTick = tick;
        if (!allowWrite)
            return;

        int32_t product = 0;
        if (TimerProduct(amplitude, multiplier, product))
        {
            result.timer.writeTimer = true;
            result.timer.timerValue = product;
        }
    };

    if (!watch.hasEdge)
    {
        finish(TimerEdge::FirstSight, true);
        return result;
    }

    if (!watch.edgeArmed)
    {
        finish(TimerEdge::Rearm, false);
        return result;
    }

    if (watch.lastTick != tick)
    {
        finish(TimerEdge::TickChange, true);
        return result;
    }

    result.timer.edge = TimerEdge::SameTick;
    return result;
}

/* Same-event cleanup when the solo path is inactive. The trigger stays
 * known so the next active poll re-arms instead of treating the elapsed
 * ticks as a first sight. The last amount is kept so a drop during the
 * inactive gap can still match scale on the next active poll. The timer
 * itself is not written. A missing 42074 while the path is active is
 * not this function: that observation drops the watch.
 */
inline WatchState DisarmWatch(WatchState watch)
{
    watch.edgeArmed = false;
    watch.lastTick = 0;
    return watch;
}
}

#endif
