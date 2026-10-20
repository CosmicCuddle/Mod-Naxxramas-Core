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
CONFIG_CPP = (ROOT / "src/Events/HallowsEndSoloFireConfig.cpp").read_text()
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


_POLICY_CACHE: dict[str, object] = {}


def policy_program() -> dict[str, object]:
    """Compile the policy binary once and run its default checks."""
    if _POLICY_CACHE:
        return _POLICY_CACHE
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
    _POLICY_CACHE.update(
        {
            "path": binary,
            "compile_cmd": compile_cmd,
            "stdout": ran.stdout,
            "stderr": ran.stderr,
            "code": ran.returncode,
        }
    )
    return _POLICY_CACHE


def policy_query(args: list[str]) -> str:
    program = policy_program()
    ran = subprocess.run(
        [str(program["path"]), *args],
        capture_output=True,
        text=True,
    )
    if ran.returncode != 0:
        raise AssertionError(ran.stderr or ran.stdout)
    return ran.stdout.strip()


def policy_retain(trigger_usable: bool, aura_present: bool) -> str:
    return policy_query(
        [
            "--retain",
            "1" if trigger_usable else "0",
            "1" if aura_present else "0",
        ]
    )


def policy_poll(
    watch: dict[str, object] | None,
    accepted: bool,
    multiplier: int,
    amount: int,
    scale: float,
    tick: int,
    amplitude: int,
) -> dict[str, object]:
    if watch is None:
        remembered = ["0", "0", "0", "0", "0"]
    else:
        remembered = [
            "1" if watch["hasEdge"] else "0",
            "1" if watch["edgeArmed"] else "0",
            str(watch["lastTick"]),
            "1" if watch["hasAmount"] else "0",
            str(watch["lastAmount"]),
        ]
    text = policy_query(
        [
            "--poll",
            *remembered,
            "1" if accepted else "0",
            str(multiplier),
            str(amount),
            f"{scale:.6f}",
            str(tick),
            str(amplitude),
        ]
    )
    parts = dict(item.split("=", 1) for item in text.split())
    return {
        "writeScale": parts["writeScale"] == "1",
        "scale": float(parts["scale"]),
        "edge": parts["edge"],
        "writeTimer": parts["writeTimer"] == "1",
        "timer": int(parts["timer"]),
        "watch": {
            "hasEdge": parts["hasEdge"] == "1",
            "edgeArmed": parts["edgeArmed"] == "1",
            "lastTick": int(parts["lastTick"]),
            "hasAmount": parts["hasAmount"] == "1",
            "lastAmount": int(parts["lastAmount"]),
        },
        "line": text,
    }


def _matching_paren(text: str, open_at: int) -> int:
    depth = 0
    for index in range(open_at, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError("unbalanced parenthesis")


def _brace_body(text: str, open_at: int) -> str:
    depth = 0
    for index in range(open_at, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1:index]
    raise AssertionError("unbalanced brace")


def retention_drop_body(poll: str) -> str | None:
    """Body of the if that drops a watch when retention is not Keep.

    Returns None when that branch does not erase the id and continue
    before any timer or scale write. A bare 'erase' substring is not enough.
    """
    start = 0
    marker = "RetentionForObservation("
    found = None
    while True:
        at = poll.find("if (", start)
        if at < 0:
            break
        open_paren = poll.find("(", at)
        close_paren = _matching_paren(poll, open_paren)
        condition = poll[open_paren + 1:close_paren]
        rest = poll[close_paren + 1:].lstrip()
        if rest.startswith("{") and marker in condition:
            body_open = close_paren + 1 + (len(poll[close_paren + 1:]) - len(rest))
            found = (condition, _brace_body(poll, body_open))
            break
        start = at + 3
    if found is None:
        return None
    condition, body = found
    if "triggerUsable" not in condition or "aura != nullptr" not in condition:
        return None
    collapsed = "".join(condition.split())
    drop_comparison = "!=NaxxramasCore::HallowsEndSoloFire::WatchRetention::Keep"
    if drop_comparison not in collapsed:
        return None
    erase_at = body.find("soloFireWatches.erase(id);")
    continue_at = body.find("continue;")
    if erase_at < 0 or continue_at < 0 or erase_at > continue_at:
        return None
    if "PollActiveTrigger" in body or "SetObjectScale" in body or "SetPeriodicTimer" in body:
        return None
    retain_at = poll.find(marker)
    active_at = poll.find("PollActiveTrigger")
    if retain_at < 0 or active_at < 0 or retain_at > active_at:
        return None
    return body


def observe_source_poll(poll: str, watch: dict[str, object] | None, step: dict[str, object]):
    """Apply one PollSoloFires iteration using the real missing-aura branch.

    The retain/poll decisions are the compiled policy. Whether a dropped
    observation erases the watch is taken from that branch's body.
    """
    retention = policy_retain(step["trigger_usable"], step["aura_present"])
    if retention == "Drop":
        if retention_drop_body(poll) is None:
            return watch, {"erased": False, "skipped": True}
        return None, {"erased": True, "skipped": False}
    if retention != "Keep":
        raise AssertionError(retention)
    result = policy_poll(
        watch,
        True,
        step["multiplier"],
        step["amount"],
        step["scale"],
        step["tick"],
        step["amplitude"],
    )
    result["erased"] = False
    result["skipped"] = False
    return result["watch"], result


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
        program = policy_program()
        cls.compile_cmd = program["compile_cmd"]
        cls.binary_stdout = program["stdout"]
        cls.binary_stderr = program["stderr"]
        cls.binary_code = program["code"]

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
        self.assertIsNotNone(retention_drop_body(poll))
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
        self.assertNotIn("GetOption<", MODULE)
        self.assertEqual(CONFIG_CPP.count("GetOption<std::string>"), 2)
        self.assertEqual(CONFIG_CPP.count("false);"), 2)
        self.assertNotIn("GetOption<bool>", CONFIG_CPP)
        self.assertNotIn("GetOption<int", CONFIG_CPP)
        self.assertNotIn("GetOption<uint", CONFIG_CPP)
        self.assertIn(
            "NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireEnabledSetting()",
            MODULE,
        )
        self.assertIn(
            "NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireMultiplierSetting()",
            MODULE,
        )
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


class MissingAuraLifecycle(unittest.TestCase):
    """The Shade missing-aura branch, executed, not searched for as text."""

    @classmethod
    def setUpClass(cls):
        program = policy_program()
        if program["code"] != 0:
            raise AssertionError(program["stdout"] + program["stderr"])
        cls.poll = extract_function(MODULE, "void PollSoloFires()")
        cls.cases = {
            line.split()[1]: line
            for line in str(program["stdout"]).splitlines()
            if line.startswith("CASE ")
        }

    def _final(self, steps: list[dict[str, object]]):
        watch = None
        result = None
        for step in steps:
            watch, result = observe_source_poll(self.poll, watch, step)
        return watch, result

    def test_same_tick_reignite_stretches_and_does_not_shrink(self):
        self.assertIsNotNone(retention_drop_body(self.poll))
        first = {
            "trigger_usable": True,
            "aura_present": True,
            "multiplier": 3,
            "amount": 3,
            "scale": 2.0,
            "tick": 0,
            "amplitude": 1500,
        }
        watch, seen = observe_source_poll(self.poll, None, first)
        self.assertEqual(seen["edge"], "FirstSight")
        self.assertTrue(seen["writeTimer"])
        self.assertEqual(seen["timer"], 4500)
        self.assertFalse(seen["writeScale"])

        stale = policy_poll(watch, True, 3, 1, 1.0, 0, 1500)
        self.assertTrue(stale["writeScale"])
        self.assertEqual(stale["scale"], 0.5)
        self.assertEqual(stale["edge"], "SameTick")
        self.assertFalse(stale["writeTimer"])

        absent = {
            "trigger_usable": True,
            "aura_present": False,
            "multiplier": 3,
            "amount": 0,
            "scale": 0.0,
            "tick": 0,
            "amplitude": 0,
        }
        watch, gone = observe_source_poll(self.poll, watch, absent)
        self.assertTrue(gone["erased"])
        self.assertIsNone(watch)

        renewed = {
            "trigger_usable": True,
            "aura_present": True,
            "multiplier": 3,
            "amount": 1,
            "scale": 1.0,
            "tick": 0,
            "amplitude": 1500,
        }
        watch, again = observe_source_poll(self.poll, watch, renewed)
        self.assertFalse(again["writeScale"])
        self.assertEqual(again["edge"], "FirstSight")
        self.assertTrue(again["writeTimer"])
        self.assertEqual(again["timer"], 4500)
        self.assertEqual(watch["lastAmount"], 1)
        self.assertEqual(watch["lastTick"], 0)
        self.assertEqual(
            self.cases["same-tick"],
            "CASE same-tick writeScale=0 edge=FirstSight writeTimer=1 timer=4500",
        )

    def test_different_tick_reignite_is_first_sight_without_a_scale_drop(self):
        steps = [
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 3,
                "amount": 3,
                "scale": 2.0,
                "tick": 0,
                "amplitude": 1500,
            },
            {
                "trigger_usable": True,
                "aura_present": False,
                "multiplier": 3,
                "amount": 0,
                "scale": 0.0,
                "tick": 0,
                "amplitude": 0,
            },
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 3,
                "amount": 1,
                "scale": 1.0,
                "tick": 4,
                "amplitude": 1500,
            },
        ]
        watch, again = self._final(steps)
        self.assertFalse(again["erased"])
        self.assertFalse(again["writeScale"])
        self.assertEqual(again["edge"], "FirstSight")
        self.assertNotEqual(again["edge"], "TickChange")
        self.assertTrue(again["writeTimer"])
        self.assertEqual(again["timer"], 4500)
        self.assertEqual(watch["lastTick"], 4)
        self.assertEqual(watch["lastAmount"], 1)
        stale = policy_poll(
            {
                "hasEdge": True,
                "edgeArmed": True,
                "lastTick": 0,
                "hasAmount": True,
                "lastAmount": 3,
            },
            True,
            3,
            1,
            1.0,
            4,
            1500,
        )
        self.assertTrue(stale["writeScale"])
        self.assertEqual(stale["scale"], 0.5)
        self.assertEqual(stale["edge"], "TickChange")
        self.assertEqual(
            self.cases["different-tick"],
            "CASE different-tick writeScale=0 edge=FirstSight writeTimer=1 timer=4500",
        )

    def test_missing_trigger_drops_the_watch_and_the_next_fire_is_first_sight(self):
        steps = [
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 3,
                "amount": 3,
                "scale": 2.0,
                "tick": 2,
                "amplitude": 1500,
            },
            {
                "trigger_usable": False,
                "aura_present": False,
                "multiplier": 3,
                "amount": 0,
                "scale": 0.0,
                "tick": 0,
                "amplitude": 0,
            },
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 8,
                "amount": 1,
                "scale": 1.0,
                "tick": 0,
                "amplitude": 1500,
            },
        ]
        watch = None
        gone = None
        again = None
        for step in steps:
            watch, result = observe_source_poll(self.poll, watch, step)
            if step["trigger_usable"]:
                again = result
            else:
                gone = result
                self.assertIsNone(watch)
        self.assertIsNotNone(gone)
        self.assertTrue(gone["erased"])
        self.assertFalse(again["writeScale"])
        self.assertEqual(again["edge"], "FirstSight")
        self.assertTrue(again["writeTimer"])
        self.assertEqual(again["timer"], 12000)
        self.assertEqual(watch["lastAmount"], 1)
        self.assertEqual(
            self.cases["missing-trigger"],
            "CASE missing-trigger writeScale=0 edge=FirstSight writeTimer=1 timer=12000",
        )

    def test_multiplier_one_reignite_stores_first_sight_without_a_timer_write(self):
        steps = [
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 1,
                "amount": 3,
                "scale": 2.0,
                "tick": 0,
                "amplitude": 1500,
            },
            {
                "trigger_usable": True,
                "aura_present": False,
                "multiplier": 1,
                "amount": 0,
                "scale": 0.0,
                "tick": 0,
                "amplitude": 0,
            },
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 1,
                "amount": 1,
                "scale": 1.0,
                "tick": 0,
                "amplitude": 1500,
            },
        ]
        watch, again = self._final(steps)
        self.assertEqual(again["edge"], "FirstSight")
        self.assertFalse(again["writeTimer"])
        self.assertFalse(again["writeScale"])
        self.assertEqual(watch["lastAmount"], 1)
        self.assertEqual(
            self.cases["mult1-reignite"],
            "CASE mult1-reignite writeScale=0 edge=FirstSight writeTimer=0 timer=0",
        )

    def test_a_fire_that_stays_present_still_corrects_a_real_amount_drop(self):
        steps = [
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 3,
                "amount": 3,
                "scale": 1.5,
                "tick": 0,
                "amplitude": 1500,
            },
            {
                "trigger_usable": True,
                "aura_present": True,
                "multiplier": 3,
                "amount": 1,
                "scale": 1.5,
                "tick": 0,
                "amplitude": 1500,
            },
        ]
        watch, dropped = self._final(steps)
        self.assertFalse(dropped["erased"])
        self.assertTrue(dropped["writeScale"])
        self.assertEqual(dropped["scale"], 0.5)
        self.assertEqual(dropped["edge"], "SameTick")
        self.assertIsNotNone(watch)

    def test_between_poll_replacement_stays_a_documented_limit(self):
        self.assertIn("between two polls", DOC)
        self.assertIn("POTENTIAL ISSUE", DOC)
        self.assertIn("GetApplyTime", DOC)
        self.assertIn("SpellAuras.h:129", DOC)
        self.assertIn("SpellAuras.cpp:355", DOC)
        self.assertIn("SpellAuras.cpp:362", DOC)
        self.assertIn("GameTime.h:30", DOC)
        self.assertIn("SpellAuraEffects.h:49", HEADER)
        self.assertNotIn("GetApplyTime()", MODULE)


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

    def test_public_aura_fields_do_not_identify_one_application(self):
        for root in (self.old, self.new):
            auras = self.line(root, "src/server/game/Spells/Auras/SpellAuras.h", 129)
            self.assertIn("GetApplyTime() const { return m_applyTime; }", auras)
            stored = self.line(root, "src/server/game/Spells/Auras/SpellAuras.h", 262)
            self.assertIn("time_t const m_applyTime;", stored)
            base = self.line(root, "src/server/game/Spells/Auras/SpellAuraEffects.h", 49)
            self.assertIn("Aura* GetBase() const { return m_base; }", base)
            clock = self.line(root, "src/server/game/Time/GameTime.h", 30)
            self.assertIn("Seconds GetGameTime();", clock)
            millis = self.line(root, "src/server/game/Time/GameTime.h", 33)
            self.assertIn("Milliseconds GetGameTimeMS();", millis)
            effect_id = self.line(root, "src/server/game/Spells/Auras/SpellAuraEffects.cpp", 432)
            self.assertIn("uint32 AuraEffect::GetId() const", effect_id)
            effect_body = self.line(root, "src/server/game/Spells/Auras/SpellAuraEffects.cpp", 434)
            self.assertIn("return m_spellInfo->Id;", effect_body)
        self.assertIn(
            "Aura* GetAura(",
            self.line(self.old, "src/server/game/Entities/Unit/Unit.h", 1447),
        )
        self.assertIn(
            "Aura* GetAura(",
            self.line(self.new, "src/server/game/Entities/Unit/Unit.h", 1448),
        )
        self.assertIn(
            "m_applyTime(GameTime::GetGameTime().count())",
            self.line(self.old, "src/server/game/Spells/Auras/SpellAuras.cpp", 355),
        )
        self.assertIn(
            "m_applyTime(GameTime::GetGameTime().count())",
            self.line(self.new, "src/server/game/Spells/Auras/SpellAuras.cpp", 362),
        )
        self.assertIn(
            "return GetSpellInfo()->Id;",
            self.line(self.old, "src/server/game/Spells/Auras/SpellAuras.cpp", 412),
        )
        self.assertIn(
            "return GetSpellInfo()->Id;",
            self.line(self.new, "src/server/game/Spells/Auras/SpellAuras.cpp", 419),
        )


if __name__ == "__main__":
    unittest.main()
