"""Source-model and pinned-core checks for the F10 S1 Hallow's End design.

These tests do not start a worldserver, apply SQL, or accept a quest.
A pass is not gameplay acceptance. Core pins run only when F10_CORE_OLD and
F10_CORE_NEW point at Grimfeather checkouts of the two reviewed SHAs.
"""
from __future__ import annotations

import hashlib
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "src/Events/HallowsEndShadeOfTheHorseman.cpp").read_text()
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()
SQL = (ROOT / "data/sql/db-world/2026_09_21_00_event_script_overrides.sql").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
DOC = (ROOT / "docs/research/F10-hallows-end-solo-fire-S1.md").read_text()

PINNED = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
PROSPECTIVE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
HALLOWS_BLOB = "02282feb50f24debd6bbeb0fe9b928db6adabd21"
MODULE_BASE = "1f5f317c3991bbac66cc92a7112bbde3c929c232"

QUESTS = (11219, 11131, 12139, 12135)


def line(text: str, number: int) -> str:
    return text.splitlines()[number - 1]


def stripped_lines(text: str):
    return [row.strip() for row in text.splitlines()]


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def validated_multiplier(raw):
    """Reject anything outside 1..8. Do not clamp into a live timer."""
    if type(raw) is not int:
        return None
    if 1 <= raw <= 8:
        return raw
    return None


def stock_player_count(initial, nearby):
    """Mirror CastFires' playerCount / sizeCount. None means no cast."""
    if nearby <= 0:
        return None
    player_count = nearby - 1
    if not initial:
        player_rate = max(0.0, 0.5 - player_count * 0.25)
        return player_count, player_rate
    return player_count + 1, None


def size_count(player_count, initial):
    count = (player_count // 3) + 1
    if initial and player_count > 0:
        count += player_count % 2
    return count


def should_skip_later_wave(unburned, triggers, player_count):
    player_rate = max(0.0, 0.5 - player_count * 0.25)
    return unburned < triggers * player_rate


def starting_amount(spell, caster_get_data):
    if spell == "start":
        amount = 1
        if (caster_get_data % 3) > 0:
            amount = 2
        return amount
    if spell == "spread":
        amount = 0
        if (caster_get_data % 3) > 1:
            amount = 1
        return amount
    raise AssertionError(spell)


def period_multiplier_applies(caster_get_data):
    return (caster_get_data % 3) == 0


def scaled_amplitude(base, caster_get_data):
    amplitude = base
    if period_multiplier_applies(caster_get_data):
        amplitude = int(amplitude * 1.5)
    if amplitude <= 0:
        amplitude = 1000
    return amplitude


class Fire:
    """Core periodic-dummy and bucket rules for one 42074 aura.

    The first countdown equals the amplitude. That matches CalculatePeriodic
    when SPELL_ATTR5_EXTRA_INITIAL_PERIOD is absent. That attribute is not
    in the git tree; callers that need it must not treat this as DBC truth.
    """

    def __init__(self, amount, amplitude):
        self.amount = amount
        self.scale = 0.5 + 0.5 * amount
        self.amplitude = amplitude
        self.timer = amplitude
        self.tick = 0
        self.alive = True
        self.spreads = 0

    def core_tick(self):
        self.tick += 1
        self.timer += self.amplitude
        if not self.alive:
            return
        amount = self.amount
        if amount < 3:
            amount += 1
        elif self.tick % 3 != 2:
            return
        self.amount = amount
        if amount <= 3:
            self.scale = amount / 2.0
        if amount >= 3:
            self.spreads += 1

    def advance(self, diff):
        if not self.alive:
            return
        self.timer -= diff
        while self.alive and self.timer <= 0:
            self.core_tick()

    def bucket(self):
        if not self.alive:
            return "none"
        if self.amount > 2:
            self.timer = self.amplitude
            self.tick = 0
            self.amount -= 2
            return "partial"
        self.alive = False
        return "removed"

    def set_scale_only(self, scale):
        self.scale = scale


def real_player_count(units):
    """Alive non-bots. A GM is a real player; the gm flag is not an exclusion."""
    return sum(1 for unit in units if unit["alive"] and not unit["bot"])


def legacy_nearby_count(units):
    """Today's CastFires list: every alive Player, bots included."""
    return sum(1 for unit in units if unit["alive"])


def solo_path(enabled, units):
    return enabled == 1 and real_player_count(units) == 1


def effective_nearby_count(enabled, units):
    """Input to the unchanged CastFires formulas.

    Solo on and exactly one real player: 1. Every other case: the legacy
    alive count, so off / zero real / two-or-more real stay byte-equivalent.
    """
    if solo_path(enabled, units):
        return 1
    return legacy_nearby_count(units)


def population(humans=0, bots=0, gms=0, dead_humans=0):
    units = [{"alive": True, "bot": False, "gm": False} for _ in range(humans)]
    units += [{"alive": True, "bot": False, "gm": True} for _ in range(gms)]
    units += [{"alive": True, "bot": True, "gm": False} for _ in range(bots)]
    units += [{"alive": False, "bot": False, "gm": False} for _ in range(dead_humans)]
    return units


def cast_fires_result(nearby, initial, unburned=None, triggers=None):
    """Run the existing formulas. None means CastFires returned before them."""
    counted = stock_player_count(initial, nearby)
    if counted is None:
        return None
    player_count, player_rate = counted
    if not initial:
        skipped = False
        if unburned is not None:
            skipped = should_skip_later_wave(unburned, triggers, player_count)
        return {
            "nearby": nearby,
            "player_count": player_count,
            "size_count": None if skipped else size_count(player_count, False),
            "player_rate": player_rate,
            "skipped": skipped,
            "starting_amount": None if skipped else starting_amount("start", player_count),
        }
    return {
        "nearby": nearby,
        "player_count": player_count,
        "size_count": size_count(player_count, True),
        "player_rate": None,
        "skipped": False,
        "starting_amount": starting_amount("start", player_count),
    }


class EdgeWatch:
    """Per-trigger timer edge. Inactive watches keep no tick snapshot."""

    def __init__(self):
        self.triggers = {}

    def disarm_all(self):
        for state in self.triggers.values():
            state["armed"] = False
            state["last_tick"] = None


def _amplitude_in_range(amplitude):
    return type(amplitude) is int and 1 <= amplitude <= 60000


def poll_solo_fire(fire, solo_on, multiplier, watch, guid="t", previous_amount=None):
    """One designed Shade poll.

    Timer writes happen only for multipliers 2..8, and only on first sight
    or a tick change inside the current armed span. Multiplier 1 updates
    that memory and does not write. Turning solo off disarms every watch
    and writes nothing. Re-arming an existing trigger stores the tick it
    has now and does not write. Scale correction runs only while solo is
    on and does not read the multiplier.

    This function never assigns fire.tick. A tick change comes only from
    Fire.advance / Fire.bucket, which model core.
    """
    if not solo_on:
        watch.disarm_all()
        return watch

    if (
        previous_amount is not None
        and fire.alive
        and fire.amount < previous_amount
        and fire.scale > (fire.amount / 2.0)
    ):
        fire.scale = fire.amount / 2.0

    accepted = validated_multiplier(multiplier)
    if accepted is None:
        return watch

    def maybe_write():
        if accepted >= 2 and _amplitude_in_range(fire.amplitude):
            fire.timer = fire.amplitude * accepted

    state = watch.triggers.get(guid)
    if state is None:
        maybe_write()
        watch.triggers[guid] = {"armed": True, "last_tick": fire.tick}
        return watch

    if not state["armed"]:
        state["armed"] = True
        state["last_tick"] = fire.tick
        return watch

    if state["last_tick"] != fire.tick:
        maybe_write()
        state["last_tick"] = fire.tick
    return watch


def run_poll(mode, amplitude, diffs, multiplier=3):
    fire = Fire(2, amplitude)
    last_tick = None
    seen = False
    for diff in diffs:
        if mode == "reset_every_poll":
            fire.timer = fire.amplitude
            fire.tick = 0
        elif mode == "rewrite_timer_every_poll":
            fire.timer = fire.amplitude * multiplier
        elif mode == "calculate_periodic_every_poll":
            fire.tick = 0
            fire.timer = fire.amplitude
        fire.advance(diff)
        if mode == "edge":
            if not seen:
                fire.timer = fire.amplitude * multiplier
                seen = True
                last_tick = fire.tick
            elif fire.tick != last_tick:
                fire.timer = fire.amplitude * multiplier
                last_tick = fire.tick
    return fire


class DesignContract(unittest.TestCase):
    def test_document_names_both_shas_and_the_milestone_limit(self):
        self.assertIn(PINNED, DOC)
        self.assertIn(PROSPECTIVE, DOC)
        self.assertIn(MODULE_BASE, DOC)
        self.assertIn(HALLOWS_BLOB, DOC)
        self.assertIn("VERIFIED", DOC)
        self.assertIn("POTENTIAL ISSUE", DOC)
        self.assertIn("UNKNOWN", DOC)
        self.assertIn("NOT TESTED", DOC)
        self.assertIn("No gameplay-affecting C++", DOC)
        for hunch in ("(a)", "(b)", "(c)", "(d)"):
            self.assertIn(hunch, DOC)
        self.assertIn("timer-write no-op", DOC)
        self.assertIn("gameplay acceptance risk", DOC)
        self.assertIn("5578105960", DOC)
        self.assertIn("Source boundary: **none**.", DOC)
        self.assertIn("The poll does not call `CalculatePeriodic`.", DOC)
        self.assertIn("The poll does not call `ResetPeriodic`.", DOC)
        self.assertNotIn("Do not change `sizeCount`", DOC)
        self.assertIn("63 + 14 * 30 = 483", DOC)
        self.assertIn("400 * IN_MILLISECONDS", DOC)

    def test_cast_fires_formula_text_is_still_the_legacy_expression(self):
        self.assertIn("players.size()) - 1;", MODULE)
        self.assertIn("playerCount += 1;", MODULE)
        self.assertIn("(playerCount / 3) + 1;", MODULE)
        self.assertIn("playerCount % 2;", MODULE)
        self.assertIn("playerCount * 0.25f", MODULE)
        self.assertIn("if (counter > 14)", stripped_lines(MODULE))
        self.assertIn("events.Repeat(30s);", stripped_lines(MODULE))

    def test_core_spell_and_trigger_bindings_stay_out_of_module_sql(self):
        # S2 adds the default-off reader. These absences are still required:
        # the module must not rewrite aura amount or bind the core scripts.
        self.assertNotIn("SetAmount", MODULE)
        self.assertNotIn("CalculatePeriodic", MODULE)
        self.assertNotIn("ResetPeriodic", MODULE)
        self.assertNotIn("23686", SQL)
        self.assertNotIn("42074", SQL)
        self.assertIn("npc_naxxramas_hallows_end_soh", SQL)
        self.assertIn("entry` = 23543", SQL)
        self.assertEqual(LOADER.count("AddHallowsEndShadeOfTheHorsemanScripts();"), 2)

    def test_module_keeps_the_30s_cycle_and_counter_threshold(self):
        rows = stripped_lines(MODULE)
        self.assertIn("if (counter > 14)", rows)
        self.assertIn("events.Repeat(30s);", rows)
        self.assertIn("events.ScheduleEvent(2, 25s);", rows)
        self.assertIn("events.ScheduleEvent(2, 43s);", rows)
        self.assertIn("events.ScheduleEvent(3, 63s);", rows)
        self.assertIn("SPELL_START_FIRE", MODULE)
        self.assertNotIn("SPELL_SPREAD_FIRE", MODULE)
        self.assertNotIn("42079", MODULE)

    def test_unreachable_more_fires_talk_is_still_behind_the_finish(self):
        finish = MODULE.index("if (counter > 14)")
        talk = MODULE.index("counter == 15")
        self.assertLess(finish, talk)
        self.assertLess(talk, MODULE.index("CastFires(false);"))

    def test_quest_credit_fail_success_and_evade_remain(self):
        for quest in QUESTS:
            self.assertIn(str(quest), MODULE)
        self.assertIn("creature->RemoveAllAuras();", MODULE)
        self.assertIn("me->DespawnOrUnsummon(1ms);", MODULE)
        self.assertIn("events.ScheduleEvent(\n                4,", MODULE)
        evade = MODULE.split("void EnterEvadeMode(", 1)[1].split(
            "uint32 GetData(", 1)[0]
        self.assertIn("DespawnOrUnsummon", evade)
        self.assertNotIn("RemoveAllAuras", evade)


class StockAndSoloSelection(unittest.TestCase):
    def test_one_player_initial_and_later_counts(self):
        self.assertEqual(stock_player_count(True, 1), (1, None))
        self.assertEqual(size_count(1, True), 2)
        self.assertEqual(stock_player_count(False, 1)[0], 0)
        self.assertEqual(size_count(0, False), 1)
        self.assertTrue(should_skip_later_wave(unburned=1, triggers=10, player_count=0))
        self.assertFalse(should_skip_later_wave(unburned=6, triggers=10, player_count=0))

    def test_empty_range_does_not_invent_a_count(self):
        self.assertIsNone(stock_player_count(True, 0))
        self.assertIsNone(stock_player_count(False, 0))

    def test_two_initial_waves_share_the_plus_one(self):
        for _wave in (25, 43):
            player_count, _rate = stock_player_count(True, 1)
            self.assertEqual(player_count, 1)
            self.assertEqual(starting_amount("start", player_count), 2)

    def test_shade_lit_and_spread_lit_amounts_differ(self):
        self.assertEqual(starting_amount("start", 1), 2)
        self.assertEqual(starting_amount("start", 0), 1)
        self.assertEqual(starting_amount("spread", 0), 0)
        self.assertEqual(starting_amount("spread", 2), 1)

    def test_trigger_getdata_zero_always_requests_the_slowdown(self):
        self.assertTrue(period_multiplier_applies(0))
        self.assertFalse(period_multiplier_applies(1))
        self.assertFalse(period_multiplier_applies(2))
        self.assertEqual(scaled_amplitude(1000, 0), 1500)
        self.assertEqual(scaled_amplitude(2000, 0), 3000)
        self.assertEqual(scaled_amplitude(1000, 1), 1000)
        self.assertEqual(scaled_amplitude(0, 0), 1000)

    def test_forced_outcome_times(self):
        self.assertEqual(63 + 14 * 30, 483)
        self.assertEqual(63 + 21 * 15, 378)

    def test_feature_off_counts_bots_and_feature_on_does_not(self):
        units = [
            {"alive": True, "bot": False},
            {"alive": True, "bot": True},
            {"alive": True, "bot": True},
            {"alive": False, "bot": False},
        ]
        self.assertEqual(len([u for u in units if u["alive"]]), 3)
        self.assertFalse(solo_path(False, units))
        self.assertTrue(solo_path(True, units))
        two_real = units + [{"alive": True, "bot": False}]
        self.assertFalse(solo_path(True, two_real))
        bots_only = [{"alive": True, "bot": True}]
        self.assertFalse(solo_path(True, bots_only))
        self.assertFalse(solo_path(True, []))

    def test_multiplier_bounds_reject_freeze_and_overflow_values(self):
        for good in range(1, 9):
            self.assertEqual(validated_multiplier(good), good)
        for bad in (0, -1, 9, 100, True, 1.5, "3", None):
            self.assertIsNone(validated_multiplier(bad))

    def test_one_human_with_zero_one_or_eight_bots_matches_only_while_solo_is_on(self):
        casting = {"unburned": 6, "triggers": 10}
        throttled = {"unburned": 4, "triggers": 10}
        on_initial = []
        on_later = []
        on_throttled = []
        off_initial = []
        off_later = []
        for bots in (0, 1, 8):
            units = population(humans=1, bots=bots)
            self.assertEqual(effective_nearby_count(1, units), 1)
            self.assertEqual(effective_nearby_count(0, units), 1 + bots)
            self.assertEqual(legacy_nearby_count(units), 1 + bots)
            on_initial.append(cast_fires_result(1, True))
            on_later.append(cast_fires_result(1, False, **casting))
            on_throttled.append(cast_fires_result(1, False, **throttled))
            off_nearby = effective_nearby_count(0, units)
            off_initial.append(cast_fires_result(off_nearby, True))
            off_later.append(cast_fires_result(off_nearby, False, **casting))
            self.assertEqual(
                cast_fires_result(off_nearby, True),
                cast_fires_result(legacy_nearby_count(units), True),
            )
            self.assertEqual(
                cast_fires_result(off_nearby, False, **casting),
                cast_fires_result(legacy_nearby_count(units), False, **casting),
            )
            self.assertEqual(
                cast_fires_result(off_nearby, False, **throttled),
                cast_fires_result(legacy_nearby_count(units), False, **throttled),
            )
        self.assertEqual(len({tuple(sorted(item.items())) for item in on_initial}), 1)
        self.assertEqual(len({tuple(sorted(item.items())) for item in on_later}), 1)
        self.assertEqual(len({tuple(sorted(item.items())) for item in on_throttled}), 1)
        self.assertEqual(on_initial[0]["player_count"], 1)
        self.assertEqual(on_initial[0]["size_count"], 2)
        self.assertEqual(on_initial[0]["starting_amount"], 2)
        self.assertEqual(on_later[0]["player_count"], 0)
        self.assertEqual(on_later[0]["size_count"], 1)
        self.assertEqual(on_later[0]["player_rate"], 0.5)
        self.assertEqual(on_later[0]["starting_amount"], 1)
        self.assertFalse(on_later[0]["skipped"])
        self.assertTrue(on_throttled[0]["skipped"])
        self.assertEqual(on_throttled[0]["player_count"], 0)
        self.assertIsNone(on_throttled[0]["size_count"])
        self.assertEqual(off_initial[0], on_initial[0])
        self.assertEqual(off_later[0], on_later[0])
        self.assertEqual(off_initial[1]["nearby"], 2)
        self.assertEqual(off_initial[1]["size_count"], 1)
        self.assertEqual(off_initial[1]["player_count"], 2)
        self.assertEqual(off_initial[1]["starting_amount"], 2)
        self.assertEqual(off_later[1]["player_count"], 1)
        self.assertEqual(off_later[1]["size_count"], 1)
        self.assertEqual(off_later[1]["player_rate"], 0.25)
        self.assertEqual(off_later[1]["starting_amount"], 2)
        self.assertEqual(off_initial[2]["nearby"], 9)
        self.assertEqual(off_initial[2]["size_count"], 5)
        self.assertEqual(off_initial[2]["player_count"], 9)
        self.assertEqual(off_later[2]["player_count"], 8)
        self.assertEqual(off_later[2]["size_count"], 3)
        self.assertEqual(off_later[2]["player_rate"], 0.0)
        self.assertEqual(off_later[2]["starting_amount"], 2)
        self.assertNotEqual(off_initial[1], on_initial[0])
        self.assertNotEqual(off_initial[2], on_initial[0])
        self.assertNotEqual(off_later[2], on_later[0])

    def test_zero_real_and_two_real_stay_on_the_legacy_list(self):
        groups = [
            population(bots=8),
            population(humans=2, bots=8),
            population(humans=2),
            population(gms=2, bots=3),
            population(humans=1, gms=1, bots=4),
            population(dead_humans=1, bots=5),
        ]
        for units in groups:
            self.assertNotEqual(real_player_count(units), 1)
            for enabled in (0, 1, 2):
                nearby = effective_nearby_count(enabled, units)
                self.assertEqual(nearby, legacy_nearby_count(units))
                for initial in (True, False):
                    self.assertEqual(
                        cast_fires_result(nearby, initial, unburned=6, triggers=10),
                        cast_fires_result(
                            legacy_nearby_count(units), initial, unburned=6, triggers=10),
                    )

    def test_one_human_plus_dead_players_does_not_count_the_dead(self):
        units = population(humans=1, bots=8, dead_humans=3)
        self.assertEqual(real_player_count(units), 1)
        self.assertEqual(effective_nearby_count(1, units), 1)
        self.assertEqual(legacy_nearby_count(units), 9)

    def test_one_gm_is_the_single_real_player(self):
        units = population(gms=1, bots=8)
        human = population(humans=1, bots=8)
        self.assertEqual(real_player_count(units), 1)
        self.assertTrue(solo_path(1, units))
        self.assertEqual(effective_nearby_count(1, units), 1)
        self.assertEqual(
            cast_fires_result(effective_nearby_count(1, units), True),
            cast_fires_result(effective_nearby_count(1, human), True),
        )
        self.assertEqual(
            cast_fires_result(
                effective_nearby_count(1, units), False, unburned=6, triggers=10),
            cast_fires_result(
                effective_nearby_count(1, human), False, unburned=6, triggers=10),
        )
        self.assertEqual(effective_nearby_count(0, units), 9)
        self.assertEqual(
            cast_fires_result(effective_nearby_count(0, units), True)["size_count"],
            5,
        )

    def test_enabled_value_other_than_one_does_not_narrow_the_list(self):
        units = population(humans=1, bots=8)
        self.assertFalse(solo_path(2, units))
        self.assertEqual(effective_nearby_count(2, units), 9)
        self.assertEqual(cast_fires_result(9, True)["size_count"], 5)


class CoreFireModel(unittest.TestCase):
    def test_amount_two_spreads_on_the_first_tick(self):
        fire = Fire(2, 1500)
        fire.advance(1499)
        self.assertEqual(fire.spreads, 0)
        fire.advance(1)
        self.assertEqual(fire.tick, 1)
        self.assertEqual(fire.amount, 3)
        self.assertEqual(fire.scale, 1.5)
        self.assertEqual(fire.spreads, 1)

    def test_amount_one_and_zero_need_more_ticks(self):
        one = Fire(1, 1000)
        one.advance(1000)
        self.assertEqual((one.amount, one.spreads, one.scale), (2, 0, 1.0))
        one.advance(1000)
        self.assertEqual((one.amount, one.spreads), (3, 1))
        zero = Fire(0, 1000)
        zero.advance(3000)
        self.assertEqual(zero.spreads, 1)
        self.assertEqual(zero.amount, 3)

    def test_partial_bucket_lags_scale_and_does_not_extinguish(self):
        fire = Fire(2, 1500)
        fire.advance(1500)
        self.assertEqual(fire.amount, 3)
        held_scale = fire.scale
        self.assertEqual(fire.bucket(), "partial")
        self.assertEqual(fire.amount, 1)
        self.assertEqual(fire.tick, 0)
        self.assertEqual(fire.scale, held_scale)
        fire.advance(1500)
        self.assertEqual(fire.amount, 2)
        self.assertEqual(fire.scale, 1.0)
        self.assertEqual(fire.spreads, 1)
        fire.advance(1500)
        self.assertEqual(fire.spreads, 2)

    def test_small_fire_bucket_removes_the_aura(self):
        for amount in (0, 1, 2):
            fire = Fire(amount, 1500)
            self.assertEqual(fire.bucket(), "removed")
            self.assertFalse(fire.alive)

    def test_scale_write_is_not_a_bucket(self):
        fire = Fire(2, 1500)
        fire.advance(1500)
        fire.set_scale_only(0.5)
        self.assertEqual(fire.amount, 3)
        self.assertEqual(fire.spreads, 1)
        before = fire.spreads
        fire.advance(4500)
        self.assertGreater(fire.spreads, before)

    def test_capping_amount_until_the_tick_still_spreads_inside_it(self):
        fire = Fire(2, 1500)
        fire.amount = 2
        fire.advance(1500)
        self.assertEqual(fire.amount, 3)
        self.assertEqual(fire.spreads, 1)

    def test_edge_stretch_slows_later_intervals_without_zeroing_ticks(self):
        fire = run_poll("edge", 1500, [1500] + [1500] * 3, multiplier=3)
        self.assertEqual(fire.tick, 2)
        self.assertGreaterEqual(fire.spreads, 1)

    def test_polling_reset_or_unconditional_timer_writes_freeze_the_fire(self):
        diffs = [100] * 50
        for mode in (
            "reset_every_poll",
            "rewrite_timer_every_poll",
            "calculate_periodic_every_poll",
        ):
            fire = run_poll(mode, 1500, diffs)
            self.assertEqual(fire.tick, 0, mode)
            self.assertEqual(fire.spreads, 0, mode)

    def test_edge_stretch_does_let_ticks_complete(self):
        fire = run_poll("edge", 1500, [100] * 80, multiplier=3)
        self.assertGreater(fire.tick, 0)
        self.assertGreater(fire.spreads, 0)

    def test_multiplier_one_preserves_a_partially_elapsed_timer(self):
        fire = Fire(2, 1500)
        fire.advance(400)
        self.assertEqual((fire.timer, fire.tick), (1100, 0))
        watch = EdgeWatch()
        poll_solo_fire(fire, True, 1, watch)
        self.assertEqual((fire.timer, fire.tick), (1100, 0))
        poll_solo_fire(fire, True, 1, watch)
        self.assertEqual((fire.timer, fire.tick), (1100, 0))
        self.assertNotEqual(fire.timer, fire.amplitude)
        naive = Fire(2, 1500)
        naive.advance(400)
        naive.timer = naive.amplitude * 1
        self.assertEqual(naive.timer, 1500)
        self.assertNotEqual(fire.timer, naive.timer)
        fire.advance(1200)
        self.assertEqual((fire.tick, fire.timer), (1, 1400))
        poll_solo_fire(fire, True, 1, watch)
        self.assertEqual((fire.tick, fire.timer), (1, 1400))
        self.assertEqual(watch.triggers["t"]["last_tick"], 1)

    def test_multiplier_one_still_corrects_scale_after_a_bucket(self):
        fire = Fire(2, 1500)
        fire.advance(1500)
        self.assertEqual(fire.bucket(), "partial")
        self.assertEqual((fire.amount, fire.scale, fire.tick), (1, 1.5, 0))
        fire.advance(200)
        self.assertEqual(fire.timer, 1300)
        poll_solo_fire(fire, True, 1, EdgeWatch(), previous_amount=3)
        self.assertEqual(fire.scale, 0.5)
        self.assertEqual(fire.amount, 1)
        self.assertEqual(fire.tick, 0)
        self.assertEqual(fire.timer, 1300)

    def test_rejected_multiplier_skips_the_timer_and_still_corrects_scale(self):
        fire = Fire(2, 1500)
        fire.advance(100)
        watch = EdgeWatch()
        poll_solo_fire(fire, True, 0, watch)
        self.assertEqual((fire.timer, fire.tick), (1400, 0))
        self.assertNotIn("t", watch.triggers)
        fire.amount = 1
        fire.scale = 1.5
        poll_solo_fire(fire, True, 9, watch, previous_amount=3)
        self.assertEqual(fire.scale, 0.5)
        self.assertEqual((fire.timer, fire.tick), (1400, 0))
        self.assertNotIn("t", watch.triggers)
        poll_solo_fire(fire, True, "3", watch)
        self.assertNotIn("t", watch.triggers)
        self.assertEqual(fire.timer, 1400)

    def test_timer_writes_are_edge_triggered_for_two_through_eight_only(self):
        fire = Fire(2, 1500)
        watch = EdgeWatch()
        poll_solo_fire(fire, True, 2, watch)
        self.assertEqual((fire.timer, fire.tick), (3000, 0))
        poll_solo_fire(fire, True, 2, watch)
        self.assertEqual(fire.timer, 3000)
        fire.advance(100)
        poll_solo_fire(fire, True, 2, watch)
        self.assertEqual((fire.timer, fire.tick), (2900, 0))
        fire.advance(2900)
        self.assertEqual((fire.tick, fire.timer), (1, 1500))
        poll_solo_fire(fire, True, 8, watch)
        self.assertEqual(fire.timer, 12000)
        self.assertEqual(fire.tick, 1)
        out_of_range = Fire(2, 1500)
        out_of_range.amplitude = 60001
        out_of_range.timer = 400
        poll_solo_fire(out_of_range, True, 4, EdgeWatch())
        self.assertEqual((out_of_range.timer, out_of_range.tick), (400, 0))

    def test_turning_solo_off_preserves_the_timer_and_drops_tick_memory(self):
        fire = Fire(2, 1500)
        watch = EdgeWatch()
        poll_solo_fire(fire, True, 3, watch)
        self.assertEqual(fire.timer, 4500)
        fire.advance(1000)
        self.assertEqual((fire.timer, fire.tick), (3500, 0))

        poll_solo_fire(fire, False, 3, watch)
        self.assertEqual((fire.timer, fire.tick), (3500, 0))
        self.assertFalse(watch.triggers["t"]["armed"])
        self.assertIsNone(watch.triggers["t"]["last_tick"])

        fire.advance(500)
        poll_solo_fire(fire, False, 3, watch, previous_amount=fire.amount + 1)
        self.assertEqual((fire.timer, fire.tick), (3000, 0))
        self.assertEqual(fire.scale, 1.5)

        fire.advance(3000)
        self.assertEqual((fire.tick, fire.timer), (1, 1500))
        fire.advance(100)
        self.assertEqual((fire.tick, fire.timer), (1, 1400))
        poll_solo_fire(fire, False, 3, watch)
        self.assertEqual(fire.timer, 1400)

        poll_solo_fire(fire, True, 3, watch)
        self.assertEqual((fire.timer, fire.tick), (1400, 1))
        self.assertTrue(watch.triggers["t"]["armed"])
        self.assertEqual(watch.triggers["t"]["last_tick"], 1)
        poll_solo_fire(fire, True, 3, watch)
        self.assertEqual(fire.timer, 1400)

        fire.advance(1400)
        self.assertEqual((fire.tick, fire.timer), (2, 1500))
        poll_solo_fire(fire, True, 3, watch)
        self.assertEqual((fire.timer, fire.tick), (4500, 2))

        fresh = Fire(2, 1500)
        poll_solo_fire(fresh, True, 3, watch, guid="new")
        self.assertEqual((fresh.timer, fresh.tick), (4500, 0))
        self.assertEqual(fire.timer, 4500)


class PinnedCoreSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = os.environ.get("F10_CORE_OLD")
        new = os.environ.get("F10_CORE_NEW")
        if not old or not new:
            raise unittest.SkipTest(
                "F10_CORE_OLD and F10_CORE_NEW are not set; core SHA pin skipped"
            )
        cls.old = Path(old)
        cls.new = Path(new)

    def read(self, root: Path, relative: str) -> str:
        path = root / relative
        self.assertTrue(path.is_file(), relative)
        return path.read_text(errors="strict")

    def test_hallows_end_blob_is_identical_at_both_shas(self):
        relative = "src/server/scripts/Events/hallows_end.cpp"
        old = (self.old / relative).read_bytes()
        new = (self.new / relative).read_bytes()
        self.assertEqual(old, new)
        self.assertEqual(git_blob_sha1(old), HALLOWS_BLOB)
        text = old.decode()
        expectations = {
            313: "if (!(creature->AI()->GetData(0) % 3))",
            315: "amplitude = static_cast<int32>(amplitude * 1.5f);",
            327: "else if (aurEff->GetTickNumber() % 3 != 2)",
            334: "owner->SetObjectScale(amount / 2.0f);",
            336: "owner->CastSpell(owner, SPELL_SPREAD_FIRE, true);",
            523: "struct npc_soh_fire_trigger : public NullCreatureAI",
            536: "me->CastSpell(me, SPELL_FIRE_AURA_BASE, true);",
            570: "else if (spellInfo->Id == SPELL_WATER_SPLASH)",
            577: "aurEff->ResetPeriodic(true);",
            578: "aurEff->SetAmount(amt - 2);",
            581: "me->RemoveAllAuras();",
            705: "return playerCount;",
            742: "if (counter > 21)",
            766: "events.Repeat(15s);",
            1511: "RegisterSpellScript(spell_hallows_end_base_fire);",
            1512: "RegisterSpellScript(spell_hallows_end_bucket_lands);",
            1519: "RegisterCreatureAI(npc_soh_fire_trigger);",
        }
        for number, expected in expectations.items():
            self.assertIn(expected, line(text, number))
        self.assertIn("if (eventStarted >= 400 * IN_MILLISECONDS)", text)

    def test_aura_headers_have_no_amplitude_setter_and_reset_restarts_ticks(self):
        relative = "src/server/game/Spells/Auras/SpellAuraEffects.h"
        old = self.read(self.old, relative)
        new = self.read(self.new, relative)
        self.assertEqual(old, new)
        self.assertIn("int32 GetAmplitude() const { return m_amplitude; }", old)
        self.assertNotIn("SetAmplitude", old)
        self.assertIn(
            "void SetPeriodicTimer(int32 periodicTimer) { m_periodicTimer = periodicTimer; }",
            old,
        )
        self.assertIn(
            "void ResetPeriodic(bool resetPeriodicTimer = false) "
            "{ if (resetPeriodicTimer) m_periodicTimer = m_amplitude; m_tickNumber = 0;}",
            old,
        )
        self.assertIn("int32 m_amplitude;", old)
        self.assertLess(old.index("private:"), old.index("int32 m_amplitude;"))
        auras = self.read(self.old, "src/server/game/Spells/Auras/SpellAuras.h")
        self.assertEqual(
            auras,
            self.read(self.new, "src/server/game/Spells/Auras/SpellAuras.h"),
        )
        self.assertIn("uint8 GetStackAmount() const { return m_stackAmount; }", auras)
        self.assertIn("void SetStackAmount(uint8 num);", auras)

    def test_calculate_periodic_zeroes_ticks_and_update_calls_the_script(self):
        relative = "src/server/game/Spells/Auras/SpellAuraEffects.cpp"
        old = self.read(self.old, relative)
        new = self.read(self.new, relative)
        for text in (old, new):
            body = text.split("void AuraEffect::CalculatePeriodic", 1)[1].split(
                "void AuraEffect::CalculateSpellMod", 1)[0]
            self.assertIn("m_tickNumber = 0;", body)
            self.assertIn("m_amplitude = 1000;", body)
            self.assertIn("CallScriptEffectCalcPeriodicHandlers", body)
            update = text.split("void AuraEffect::Update(uint32 diff, Unit* caster)", 1)[1].split(
                "void AuraEffect::UpdatePeriodic", 1)[0]
            self.assertIn("++m_tickNumber;", update)
            self.assertIn("m_periodicTimer += m_amplitude;", update)
        self.assertEqual(
            line(old, 1070).strip(),
            "GetBase()->CallScriptEffectUpdatePeriodicHandlers(this);",
        )
        self.assertEqual(
            line(new, 1057).strip(),
            "GetBase()->CallScriptEffectUpdatePeriodicHandlers(this);",
        )
        self.assertIn("case 66823:", old)
        self.assertNotIn("case 66823:", new)

    def test_unit_lookups_and_scale_and_player_search(self):
        old_unit = self.read(self.old, "src/server/game/Entities/Unit/Unit.h")
        new_unit = self.read(self.new, "src/server/game/Entities/Unit/Unit.h")
        self.assertIn(
            "AuraEffect* GetAuraEffect(uint32 spellId, uint8 effIndex, ObjectGuid casterGUID = ObjectGuid::Empty) const;",
            line(old_unit, 1439),
        )
        self.assertIn(
            "AuraEffect* GetAuraEffect(uint32 spellId, uint8 effIndex, ObjectGuid casterGUID = ObjectGuid::Empty) const;",
            line(new_unit, 1440),
        )
        self.assertIn("bool HasPeriodicDummyAura()", line(old_unit, 1824))
        self.assertIn("bool HasPeriodicDummyAura()", line(new_unit, 1825))
        self.assertIn("HasAuraType(SPELL_AURA_PERIODIC_DUMMY)", old_unit)
        obj = self.read(self.old, "src/server/game/Entities/Object/Object.h")
        self.assertEqual(obj, self.read(self.new, "src/server/game/Entities/Object/Object.h"))
        self.assertIn(
            "void SetObjectScale(float scale) { SetFloatValue(OBJECT_FIELD_SCALE_X, scale); }",
            obj,
        )
        grid = self.read(self.old, "src/server/game/Grids/Notifiers/GridNotifiers.h")
        self.assertIn("class AnyPlayerInObjectRangeCheck", line(grid, 1379))
        self.assertIn("if (_reqAlive && !u->IsAlive())", grid)
        self.assertIn("if (_disallowGM && (u->IsGameMaster() || u->IsSpectator()))", grid)
        self.assertNotIn("Playerbot", grid)

    def test_null_ai_getdata_is_zero_and_spell_self_cast_uses_the_caster(self):
        unit_ai = self.read(self.old, "src/server/game/AI/CoreAI/UnitAI.h")
        self.assertEqual(unit_ai, self.read(self.new, "src/server/game/AI/CoreAI/UnitAI.h"))
        self.assertIn(
            "virtual uint32 GetData(uint32 /*id = 0*/) const { return 0; }",
            unit_ai,
        )
        passive = self.read(self.old, "src/server/game/AI/CoreAI/PassiveAI.h")
        self.assertEqual(passive, self.read(self.new, "src/server/game/AI/CoreAI/PassiveAI.h"))
        body = passive.split("class NullCreatureAI", 1)[1].split("class CritterAI", 1)[0]
        self.assertNotIn("GetData", body)
        for root in (self.old, self.new):
            spell = self.read(root, "src/server/game/Spells/Spell.cpp")
            ctor = spell.split("Spell::Spell(", 1)[1].split("m_spellState = SPELL_STATE_NULL;", 1)[0]
            self.assertIn("m_originalCasterGUID = m_caster->GetGUID();", ctor)
            self.assertIn("m_originalCaster = m_caster->ToUnit();", ctor)

    def test_sql_bindings_and_quest_time_allowed(self):
        names = self.read(self.old, "data/sql/base/db_world/spell_script_names.sql")
        self.assertEqual(
            names,
            self.read(self.new, "data/sql/base/db_world/spell_script_names.sql"),
        )
        self.assertIn("(42074,'spell_hallows_end_base_fire'),", names)
        self.assertIn("(42339,'spell_hallows_end_bucket_lands'),", names)
        self.assertNotIn("(42348,", names)
        creatures = self.read(self.old, "data/sql/base/db_world/creature_template.sql")
        self.assertEqual(
            creatures,
            self.read(self.new, "data/sql/base/db_world/creature_template.sql"),
        )
        shade = next(row for row in creatures.splitlines() if row.startswith("(23543,"))
        trigger = next(row for row in creatures.splitlines() if row.startswith("(23686,"))
        self.assertIn("'npc_hallows_end_soh'", shade)
        self.assertIn("'npc_soh_fire_trigger'", trigger)
        quests = self.read(self.old, "data/sql/base/db_world/quest_template.sql")
        self.assertEqual(
            quests,
            self.read(self.new, "data/sql/base/db_world/quest_template.sql"),
        )
        for quest_id, flags in (
            (11131, "4106"),
            (11219, "4106"),
            (12135, "4170"),
            (12139, "4170"),
        ):
            row = next(item for item in quests.splitlines() if item.startswith(f"({quest_id},"))
            values = _split_sql_tuple(row)
            self.assertEqual(values[72], "0", quest_id)
            self.assertEqual(values[20], flags, quest_id)
        quest_def = self.read(self.old, "src/server/game/Quests/QuestDef.h")
        self.assertEqual(quest_def, self.read(self.new, "src/server/game/Quests/QuestDef.h"))
        self.assertIn("QUEST_FLAGS_DAILY                   = 0x00001000,", quest_def)
        self.assertIn("QUEST_FLAGS_PARTY_ACCEPT            = 0x00000002,", quest_def)


class PinnedNeighbours(unittest.TestCase):
    def test_individual_progression_has_no_hallows_fire_source(self):
        root = os.environ.get("F10_IP")
        if not root:
            self.skipTest("F10_IP is not set")
        pattern = re.compile(
            r"(?<!\d)(?:42074|23686|23543)(?!\d)|hallows_end|npc_soh_fire_trigger|npc_hallows_end"
        )
        hits = []
        for path in Path(root).rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            if pattern.search(text):
                hits.append(str(path))
        self.assertEqual(hits, [])

    def test_playerbots_macro_used_by_the_existing_module_pattern(self):
        path = os.environ.get("F10_PLAYERBOTS_H")
        if not path:
            self.skipTest("F10_PLAYERBOTS_H is not set")
        text = Path(path).read_text()
        self.assertIn("#define GET_PLAYERBOT_AI(object) sPlayerbotsMgr.GetPlayerbotAI(object)", text)
        forced = (ROOT / "src/Systems/ForcedPvP.cpp").read_text()
        self.assertIn("GET_PLAYERBOT_AI(player) != nullptr", forced)


def _split_sql_tuple(row: str):
    body = row.strip()
    if body.endswith(","):
        body = body[:-1]
    if body.endswith(";"):
        body = body[:-1]
    assert body[0] == "(" and body[-1] == ")"
    body = body[1:-1]
    values = []
    current = []
    in_string = False
    escaped = False
    for char in body:
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                in_string = False
        elif char == "'":
            in_string = True
            current.append(char)
        elif char == ",":
            values.append("".join(current))
            current = []
        else:
            current.append(char)
    values.append("".join(current))
    return values


if __name__ == "__main__":
    unittest.main()
