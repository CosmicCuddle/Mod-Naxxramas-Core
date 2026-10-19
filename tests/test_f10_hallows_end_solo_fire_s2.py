"""Source-model tests for the F10 S2 Shade solo-fire implementation.

These tests do not start a worldserver, apply SQL, or accept a quest.
A pass is not gameplay acceptance. The policy binary is the header in
src/Events/HallowsEndSoloFire.h. Its TRACE output is compared with the
signed-off S1 model.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import test_f10_hallows_end_solo_fire_s1 as s1

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "src/Events/HallowsEndShadeOfTheHorseman.cpp").read_text()
HEADER = (ROOT / "src/Events/HallowsEndSoloFire.h").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
SQL = (ROOT / "data/sql/db-world/2026_09_21_00_event_script_overrides.sql").read_text()
DOC = (ROOT / "docs/research/F10-hallows-end-solo-fire-S2.md").read_text()
WORKFLOW = (ROOT / ".github/workflows/f10-s2-source-pin.yml").read_text()
POLICY_SOURCE = ROOT / "tests/f10_s2_solo_fire_policy_tests.cpp"
FORCED = (ROOT / "src/Systems/ForcedPvP.cpp").read_text()

PINNED = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
PROSPECTIVE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
HALLOWS_BLOB = "02282feb50f24debd6bbeb0fe9b928db6adabd21"
PLAYERBOTS = "037c01418b5d01506917a3db9b44fd56ac5f965c"
INDIVIDUAL = "4ff4b5fcc1480348f058c632573143e62d4e3a41"


def extract_function(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(signature)


def trace_line(step: str, fire: s1.Fire, watch: s1.EdgeWatch) -> str:
    state = watch.triggers.get("t")
    has_edge = 1 if state else 0
    armed = 1 if state and state["armed"] else 0
    last = str(state["last_tick"]) if armed else "na"
    alive = 1 if fire.alive else 0
    return (
        f"TRACE step={step} timer={fire.timer} tick={fire.tick} "
        f"amount={fire.amount} scale={fire.scale:.6f} armed={armed} "
        f"has_edge={has_edge} last_tick={last} alive={alive}"
    )


def s1_oracle_trace() -> list[str]:
    """Same steps as RunSharedTrace in the policy binary."""
    fire = s1.Fire(2, 1500)
    watch = s1.EdgeWatch()
    previous = None
    lines = []

    def remember(step: str) -> None:
        lines.append(trace_line(step, fire, watch))

    def apply_poll(solo: bool, multiplier: int) -> None:
        nonlocal previous
        s1.poll_solo_fire(
            fire,
            solo,
            multiplier,
            watch,
            guid="t",
            previous_amount=previous,
        )
        if solo:
            previous = fire.amount

    fire.advance(400)
    remember("advance-400")
    apply_poll(True, 0)
    remember("poll-reject-0")
    fire.amount = 1
    fire.scale = 1.5
    apply_poll(True, 9)
    remember("poll-reject-9-after-fall")
    apply_poll(True, 3)
    remember("poll-first-3")
    apply_poll(True, 3)
    remember("poll-same-3")
    fire.advance(100)
    remember("advance-100")
    apply_poll(True, 2)
    remember("poll-same-2")
    fire.advance(4400)
    remember("advance-4400")
    apply_poll(True, 8)
    remember("poll-tick-8")
    fire.advance(12000)
    remember("advance-to-amount-3")
    fire.bucket()
    fire.advance(200)
    remember("bucket-advance-200")
    apply_poll(True, 1)
    remember("poll-mult1-after-bucket")
    apply_poll(False, 3)
    remember("poll-off")
    fire.amount = 0
    fire.scale = 1.5
    apply_poll(False, 3)
    remember("poll-off-during-fall")
    apply_poll(True, 3)
    remember("poll-rearm")
    apply_poll(True, 3)
    remember("poll-rearm-same")
    guard = 0
    armed_tick = watch.triggers["t"]["last_tick"]
    while fire.alive and fire.tick == armed_tick and guard < 20:
        fire.advance(fire.amplitude if fire.amplitude > 0 else 1)
        guard += 1
    remember("advance-to-next-tick")
    apply_poll(True, 3)
    remember("poll-after-rearm-tick")
    return lines


class PolicyBinary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = Path("/tmp/f10_s2_solo_fire_policy_tests")
        compile_cmd = [
            "g++",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "src/Events"),
            str(POLICY_SOURCE),
            "-o",
            str(binary),
        ]
        compiled = subprocess.run(compile_cmd, capture_output=True, text=True)
        if compiled.returncode != 0:
            raise AssertionError(compiled.stderr)
        ran = subprocess.run([str(binary)], capture_output=True, text=True)
        cls.compile_cmd = compile_cmd
        cls.binary_stdout = ran.stdout
        cls.binary_stderr = ran.stderr
        cls.binary_code = ran.returncode

    def test_policy_binary_passes_and_matches_the_s1_model(self):
        self.assertEqual(
            self.binary_code,
            0,
            self.binary_stdout + self.binary_stderr,
        )
        self.assertIn("F10_S2_POLICY_OK", self.binary_stdout)
        produced = [
            line for line in self.binary_stdout.splitlines() if line.startswith("TRACE ")
        ]
        expected = s1_oracle_trace()
        self.assertEqual(produced, expected)


class SoloCountAndLegacyFormulas(unittest.TestCase):
    def test_one_real_player_with_zero_one_or_eight_bots_is_effective_count_one(self):
        casting = {"unburned": 6, "triggers": 10}
        for bots in (0, 1, 8):
            units = s1.population(humans=1, bots=bots)
            self.assertEqual(s1.real_player_count(units), 1)
            self.assertEqual(s1.legacy_nearby_count(units), 1 + bots)
            self.assertTrue(s1.solo_path(1, units))
            self.assertFalse(s1.solo_path(0, units))
            self.assertEqual(s1.effective_nearby_count(1, units), 1)
            self.assertEqual(s1.effective_nearby_count(0, units), 1 + bots)
            on_initial = s1.cast_fires_result(1, True)
            off_initial = s1.cast_fires_result(1 + bots, True)
            self.assertEqual(on_initial["player_count"], 1)
            self.assertEqual(on_initial["size_count"], 2)
            self.assertEqual(on_initial["starting_amount"], 2)
            on_later = s1.cast_fires_result(1, False, **casting)
            self.assertEqual(on_later["player_count"], 0)
            self.assertEqual(on_later["size_count"], 1)
            self.assertEqual(on_later["player_rate"], 0.5)
            self.assertEqual(on_later["starting_amount"], 1)
            self.assertFalse(on_later["skipped"])
            if bots:
                self.assertNotEqual(off_initial["nearby"], on_initial["nearby"])
                self.assertEqual(off_initial["nearby"], 1 + bots)

    def test_off_zero_real_and_two_real_keep_the_legacy_list(self):
        groups = [
            s1.population(humans=1, bots=8),
            s1.population(bots=8),
            s1.population(humans=2, bots=8),
            s1.population(humans=2),
            s1.population(gms=1, bots=8),
        ]
        for units in groups:
            legacy = s1.legacy_nearby_count(units)
            for enabled in (0, 2):
                self.assertEqual(s1.effective_nearby_count(enabled, units), legacy)
            if s1.real_player_count(units) != 1:
                self.assertEqual(s1.effective_nearby_count(1, units), legacy)
                self.assertFalse(s1.solo_path(1, units))
        one_gm = s1.population(gms=1, bots=8)
        self.assertEqual(s1.effective_nearby_count(1, one_gm), 1)
        self.assertEqual(s1.cast_fires_result(1, True)["size_count"], 2)
        self.assertEqual(s1.cast_fires_result(9, True)["size_count"], 5)

    def test_rejected_multiplier_does_not_change_the_count_rule(self):
        units = s1.population(humans=1, bots=8)
        self.assertIsNone(s1.validated_multiplier(0))
        self.assertIsNone(s1.validated_multiplier(9))
        self.assertIsNone(s1.validated_multiplier("3"))
        self.assertEqual(s1.validated_multiplier(1), 1)
        self.assertEqual(s1.effective_nearby_count(1, units), 1)

    def test_multiplier_one_and_rejected_values_follow_the_s1_poll(self):
        fire = s1.Fire(2, 1500)
        fire.advance(400)
        watch = s1.EdgeWatch()
        s1.poll_solo_fire(fire, True, 1, watch)
        self.assertEqual((fire.timer, fire.tick), (1100, 0))
        s1.poll_solo_fire(fire, True, 1, watch)
        self.assertEqual(fire.timer, 1100)
        self.assertNotEqual(fire.timer, fire.amplitude * 1)

        rejected = s1.Fire(2, 1500)
        rejected.advance(100)
        empty = s1.EdgeWatch()
        s1.poll_solo_fire(rejected, True, 0, empty)
        self.assertEqual(rejected.timer, 1400)
        self.assertNotIn("t", empty.triggers)
        rejected.amount = 1
        rejected.scale = 1.5
        s1.poll_solo_fire(rejected, True, 9, empty, previous_amount=3)
        self.assertEqual(rejected.scale, 0.5)
        self.assertEqual(rejected.timer, 1400)
        self.assertNotIn("t", empty.triggers)

    def test_scale_correction_requires_a_real_amount_drop(self):
        fire = s1.Fire(2, 1500)
        watch = s1.EdgeWatch()
        s1.poll_solo_fire(fire, True, 1, watch, previous_amount=None)
        self.assertEqual(fire.scale, 1.5)
        s1.poll_solo_fire(fire, True, 1, watch, previous_amount=2)
        self.assertEqual(fire.scale, 1.5)
        fire.amount = 3
        fire.scale = 1.5
        s1.poll_solo_fire(fire, True, 1, watch, previous_amount=2)
        self.assertEqual(fire.scale, 1.5)
        fire.amount = 1
        s1.poll_solo_fire(fire, True, 1, watch, previous_amount=3)
        self.assertEqual(fire.scale, 0.5)
        self.assertEqual(fire.amount, 1)
        self.assertEqual(fire.timer, 1500)


class ShadeSourceContract(unittest.TestCase):
    def test_formulas_timing_and_threshold_are_unchanged(self):
        rows = [row.strip() for row in MODULE.splitlines()]
        self.assertEqual(rows.count("if (counter > 14)"), 1)
        self.assertEqual(rows.count("events.Repeat(30s);"), 1)
        self.assertIn("events.ScheduleEvent(2, 25s);", rows)
        self.assertIn("events.ScheduleEvent(2, 43s);", rows)
        self.assertIn("events.ScheduleEvent(3, 63s);", rows)
        self.assertIn("players.size()) - 1;", MODULE)
        self.assertIn("playerCount += 1;", MODULE)
        self.assertIn("(playerCount / 3) + 1;", MODULE)
        self.assertIn("playerCount % 2;", MODULE)
        self.assertIn("playerCount * 0.25f", MODULE)
        cast = extract_function(MODULE, "void CastFires(bool initial)")
        self.assertLess(cast.index("SoloFirePathActive"), cast.index("players.size()) - 1;"))
        narrow = cast.split("players.size()) - 1;", 1)[0]
        self.assertIn("if (SoloFirePathActive(players))", narrow)
        self.assertIn("IsHallowsEndShadePlayerBot", narrow)
        self.assertNotIn("Multiplier", cast)
        self.assertNotIn("SetPeriodicTimer", cast)
        self.assertNotIn("SetObjectScale", cast)

    def test_poll_is_edge_only_and_does_not_fake_a_splash(self):
        update = extract_function(MODULE, "void UpdateAI(uint32 diff) override")
        self.assertLess(update.index("UNIT_STATE_CASTING"), update.index("PollSoloFires();"))
        self.assertLess(update.index("PollSoloFires();"), update.index("ExecuteEvent()"))
        poll = extract_function(MODULE, "void PollSoloFires()")
        self.assertLess(poll.index("!= 1"), poll.index("CollectNearbyHallowsPlayers"))
        self.assertLess(poll.index("DisarmSoloFireWatches"), poll.index("PollActiveTrigger"))
        self.assertLess(poll.index("writeScale"), poll.index("SetObjectScale"))
        self.assertLess(poll.index("writeTimer"), poll.index("SetPeriodicTimer"))
        for forbidden in (
            "CalculatePeriodic",
            "ResetPeriodic",
            "RemoveAllAuras",
            "SetAmount",
            "CastSpell",
            "42348",
            "SetStackAmount",
            "ChangeAmount",
            "SPELL_WATER_SPLASH",
        ):
            self.assertNotIn(forbidden, poll)
        self.assertIn("GetAuraEffect", poll)
        self.assertIn("GetTickNumber", poll)
        self.assertIn("GetAmplitude", poll)
        self.assertIn("GetAmount", poll)
        self.assertIn("GetObjectScale", poll)
        self.assertIn("NPC_FIRE_TRIGGER", poll)
        reset = extract_function(MODULE, "void Reset() override")
        self.assertIn("soloFireWatches.clear();", reset)
        disarm = extract_function(MODULE, "void DisarmSoloFireWatches()")
        self.assertIn("DisarmWatch", disarm)
        self.assertNotIn("clear()", disarm)
        self.assertNotIn("CalculatePeriodic", MODULE)
        self.assertNotIn("ResetPeriodic", MODULE)
        self.assertNotIn("SetAmount", MODULE)

    def test_bots_are_classified_like_forced_pvp_and_gms_are_kept(self):
        self.assertIn('__has_include("Playerbots.h")', MODULE)
        self.assertIn("GET_PLAYERBOT_AI(player) != nullptr", MODULE)
        self.assertIn("GET_PLAYERBOT_AI(player) != nullptr", FORCED)
        self.assertNotIn("IsGameMaster", MODULE)
        self.assertNotIn("disallowGM", MODULE)
        self.assertIn("AnyPlayerInObjectRangeCheck checker(\n            me,\n            60.0f);", MODULE)
        for path_id in (235431, 235432, 235433, 235434, 235435, 235436):
            self.assertIn(str(path_id), MODULE)
        for quest in (11219, 11131, 12139, 12135):
            self.assertIn(str(quest), MODULE)

    def test_config_defaults_are_off_and_numeric_fallback_is_not_used(self):
        self.assertIn("NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0\n", CONF)
        self.assertIn("NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier = 3\n", CONF)
        self.assertEqual(CONF.count("HallowsEnd.SoloFire.Enabled"), 1)
        self.assertEqual(CONF.count("HallowsEnd.SoloFire.PeriodMultiplier"), 1)
        reader = extract_function(MODULE, "std::string ReadSoloFireConfigRaw(")
        self.assertEqual(MODULE.count("GetOption<std::string>"), 1)
        self.assertIn("false);", reader)
        self.assertNotIn("GetOption<bool>", MODULE)
        self.assertNotIn("GetOption<int", MODULE)
        self.assertNotIn("GetOption<uint", MODULE)
        self.assertIn('inline constexpr char DefaultEnabledRaw[] = "0";', HEADER)
        self.assertIn('inline constexpr char DefaultMultiplierRaw[] = "3";', HEADER)
        self.assertNotIn("23686", SQL)
        self.assertNotIn("42074", SQL)
        self.assertNotIn("spell_hallows_end_base_fire", SQL)
        self.assertNotIn("npc_soh_fire_trigger", SQL)

    def test_failure_clear_stays_on_the_failure_path_only(self):
        poll = extract_function(MODULE, "void PollSoloFires()")
        finish = extract_function(MODULE, "void FinishEvent(bool failed)")
        evade = extract_function(MODULE, "void EnterEvadeMode(")
        self.assertNotIn("RemoveAllAuras", poll)
        self.assertIn("RemoveAllAuras", finish)
        self.assertNotIn("RemoveAllAuras", evade)
        self.assertIn("DespawnOrUnsummon", evade)

    def test_provenance_is_recorded_on_the_header_and_in_the_s2_doc(self):
        for sha in (PINNED, PROSPECTIVE, HALLOWS_BLOB, PLAYERBOTS, INDIVIDUAL):
            self.assertIn(sha, HEADER)
            self.assertIn(sha, DOC)
        for symbol in (
            "spell_hallows_end_base_fire",
            "npc_soh_fire_trigger",
            "SetPeriodicTimer",
            "GetAuraEffect",
            "AnyPlayerInObjectRangeCheck",
            "GET_PLAYERBOT_AI",
        ):
            self.assertIn(symbol, HEADER)
            self.assertIn(symbol, DOC)
        self.assertIn("hallows_end.cpp:305", HEADER)
        self.assertIn("hallows_end.cpp:523", HEADER)
        self.assertIn("hallows_end.cpp:570", HEADER)
        self.assertIn("SpellAuraEffects.h:69", HEADER)
        self.assertIn("Unit.h:1439", HEADER)
        self.assertIn("Unit.h:1440", HEADER)
        self.assertIn("Object.h:127", HEADER)
        self.assertIn("GridNotifiers.h:1379", HEADER)
        self.assertIn("SharedDefines.h:31", HEADER)
        self.assertIn("instant", DOC.lower())
        self.assertIn("NOT TESTED", DOC)
        self.assertIn("VERIFIED", DOC)
        self.assertIn("default off", DOC.lower())

    def test_source_workflow_cannot_upload_artifacts(self):
        self.assertIn("contents: read", WORKFLOW)
        self.assertNotIn("upload-artifact", WORKFLOW)
        self.assertNotIn("actions/upload-artifact", WORKFLOW)
        self.assertIn("cs02/f10-s2-shade-module-2026-10-20", WORKFLOW)
        self.assertIn("test_f10_hallows_end_solo_fire_s*.py", WORKFLOW)
        touched = list(Path(ROOT / ".github/workflows").glob("f10-s2*.yml"))
        self.assertEqual(len(touched), 1)
        for path in touched:
            text = path.read_text()
            self.assertNotIn("upload-artifact", text)
            self.assertIn("contents: read", text)


class PinnedProvenanceLines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = __import__("os").environ.get("F10_CORE_OLD")
        new = __import__("os").environ.get("F10_CORE_NEW")
        if not old or not new:
            raise unittest.SkipTest("F10_CORE_OLD and F10_CORE_NEW are not set")
        cls.old = Path(old)
        cls.new = Path(new)

    def line(self, root: Path, relative: str, number: int) -> str:
        return (root / relative).read_text().splitlines()[number - 1]

    def test_cited_core_lines_match_both_shas(self):
        expectations = {
            "src/server/scripts/Events/hallows_end.cpp": {
                305: "class spell_hallows_end_base_fire",
                320: "void HandleEffectPeriodicUpdate",
                523: "struct npc_soh_fire_trigger",
                536: "SPELL_FIRE_AURA_BASE",
                570: "SPELL_WATER_SPLASH",
                577: "ResetPeriodic(true)",
                578: "SetAmount(amt - 2)",
                1511: "spell_hallows_end_base_fire",
                1519: "npc_soh_fire_trigger",
            },
            "src/server/game/Spells/Auras/SpellAuraEffects.h": {
                59: "GetAmplitude()",
                64: "GetAmount()",
                69: "SetPeriodicTimer",
                87: "GetTickNumber()",
                89: "ResetPeriodic",
                142: "m_amplitude",
            },
            "src/server/game/Entities/Object/Object.h": {
                126: "GetObjectScale()",
                127: "SetObjectScale",
            },
            "src/server/shared/SharedDefines.h": {
                31: "EFFECT_0 = 0",
            },
        }
        for relative, rows in expectations.items():
            for number, snippet in rows.items():
                self.assertIn(snippet, self.line(self.old, relative, number), f"{relative}:{number}")
                self.assertIn(snippet, self.line(self.new, relative, number), f"{relative}:{number}")
        self.assertIn(
            "GetAuraEffect(uint32 spellId, uint8 effIndex",
            self.line(self.old, "src/server/game/Entities/Unit/Unit.h", 1439),
        )
        self.assertIn(
            "GetAuraEffect(uint32 spellId, uint8 effIndex",
            self.line(self.new, "src/server/game/Entities/Unit/Unit.h", 1440),
        )
        old_config = (self.old / "src/common/Configuration/Config.cpp").read_text()
        new_config = (self.new / "src/common/Configuration/Config.cpp").read_text()
        for text in (old_config, new_config):
            self.assertIn("return def;", text)
            self.assertIn('value.erase(std::remove(value.begin(), value.end(), \'"\'), value.end());', text)
        grid = (self.old / "src/server/game/Grids/Notifiers/GridNotifiers.h").read_text()
        self.assertIn(
            "AnyPlayerInObjectRangeCheck(WorldObject const* obj, float range, bool reqAlive = true, bool disallowGM = false)",
            grid,
        )


if __name__ == "__main__":
    unittest.main()
