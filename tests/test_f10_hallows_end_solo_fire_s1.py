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
    return sum(1 for unit in units if unit["alive"] and not unit["bot"])


def solo_path(enabled, units):
    return bool(enabled) and real_player_count(units) == 1


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

    def test_this_milestone_does_not_arm_a_solo_mode(self):
        self.assertNotIn("SetPeriodicTimer", MODULE)
        self.assertNotIn("SetAmount", MODULE)
        self.assertNotIn("SetObjectScale", MODULE)
        self.assertNotIn("HallowsEnd.SoloFire", MODULE)
        self.assertNotIn("HallowsEnd.SoloFire", CONF)
        self.assertNotIn("23686", SQL)
        self.assertNotIn("42074", SQL)
        self.assertIn("npc_naxxramas_hallows_end_soh", SQL)
        self.assertIn("entry` = 23543", SQL)
        self.assertEqual(LOADER.count("AddHallowsEndShadeOfTheHorsemanScripts();"), 2)

    def test_module_keeps_the_30s_cycle_and_counter_threshold(self):
        self.assertEqual(line(MODULE, 312).strip(), "if (counter > 14)")
        self.assertEqual(line(MODULE, 359).strip(), "events.Repeat(30s);")
        self.assertEqual(line(MODULE, 217).strip(), "events.ScheduleEvent(2, 25s);")
        self.assertEqual(line(MODULE, 218).strip(), "events.ScheduleEvent(2, 43s);")
        self.assertEqual(line(MODULE, 219).strip(), "events.ScheduleEvent(3, 63s);")
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
