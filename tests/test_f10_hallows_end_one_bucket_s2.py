"""F10 S2 one-bucket policy, source wiring, and pinned-core contract.

The policy binary is HallowsEndSoloFire.h. The Shade translation unit is
the only caller that may remove aura 42074. These tests do not start a
worldserver, apply SQL, or throw a bucket. A pass is not gameplay
acceptance. Whether splash 42348 is immediate or delayed is not decided
here.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHADE = (ROOT / "src/Events/HallowsEndShadeOfTheHorseman.cpp").read_text()
HEADER = (ROOT / "src/Events/HallowsEndSoloFire.h").read_text()
CONFIG_CPP = (ROOT / "src/Events/HallowsEndSoloFireConfig.cpp").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
SQL = (ROOT / "data/sql/db-world/2026_09_21_00_event_script_overrides.sql").read_text()
DOC = (ROOT / "docs/research/F10-hallows-end-one-bucket-S2.md").read_text()
WORKFLOW = (ROOT / ".github/workflows/f10-s2-one-bucket.yml").read_text()
POLICY = ROOT / "tests/f10_s2_one_bucket_policy_tests.cpp"

PINNED = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
PROSPECTIVE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
HALLOWS_BLOB = "02282feb50f24debd6bbeb0fe9b928db6adabd21"
NAMES_BLOB = "e93f9e13d5ab2c98b134c5c632fa1f6f688afa15"
CREATURE_BLOB = "899a56b0f5d7bac6536a48e038acb23ba8a70812"
PLAYERBOTS = "037c01418b5d01506917a3db9b44fd56ac5f965c"
INDIVIDUAL = "4ff4b5fcc1480348f058c632573143e62d4e3a41"

BUCKET = 42339
SPLASH = 42348
AURA = 42074
FIRE = 23686
TRAIN = 23537
SHADE_ENTRY = 23543


def line(text: str, number: int) -> str:
    return text.splitlines()[number - 1]


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def brace_body(text: str, signature: str) -> str:
    at = text.find(signature)
    if at < 0:
        raise AssertionError(f"missing {signature}")
    open_at = text.find("{", at)
    depth = 0
    for index in range(open_at, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1:index]
    raise AssertionError(f"unbalanced {signature}")


_POLICY: dict[str, object] = {}


def policy_program() -> dict[str, object]:
    if _POLICY:
        return _POLICY
    binary = Path("/tmp/f10_s2_one_bucket_policy_tests")
    compile_cmd = [
        "g++",
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(ROOT / "src/Events"),
        str(POLICY),
        "-o",
        str(binary),
    ]
    compiled = subprocess.run(compile_cmd, capture_output=True, text=True)
    if compiled.returncode != 0:
        raise AssertionError(compiled.stderr)
    ran = subprocess.run([str(binary)], capture_output=True, text=True)
    if ran.returncode != 0:
        raise AssertionError(ran.stderr or ran.stdout)
    _POLICY.update({"path": binary, "stdout": ran.stdout, "code": ran.returncode})
    return _POLICY


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


def armed() -> dict[str, int]:
    return {
        "hit": 1,
        "spell": BUCKET,
        "effect": 0,
        "entry": FIRE,
        "aura": 1,
        "one_bucket": 1,
        "solo": 1,
        "player": 1,
        "bot": 0,
        "census": 1,
        "reals": 1,
        "shades": 1,
    }


def decide(**overrides: int) -> dict[str, object]:
    facts = armed()
    facts.update(overrides)
    text = policy_query(
        [
            "--decide",
            str(facts["hit"]),
            str(facts["spell"]),
            str(facts["effect"]),
            str(facts["entry"]),
            str(facts["aura"]),
            str(facts["one_bucket"]),
            str(facts["solo"]),
            str(facts["player"]),
            str(facts["bot"]),
            str(facts["census"]),
            str(facts["reals"]),
            str(facts["shades"]),
        ]
    )
    parts = dict(item.split("=", 1) for item in text.split())
    return {
        "remove": parts["remove"] == "1",
        "reason": parts["reason"],
        "line": text,
    }


def simulate(timing: str, amount: int = 3, unrelated: int = 1, child: int = 1, **overrides: int) -> dict[str, int]:
    facts = armed()
    facts.update(overrides)
    text = policy_query(
        [
            "--simulate",
            timing,
            str(facts["hit"]),
            str(facts["spell"]),
            str(facts["effect"]),
            str(facts["entry"]),
            str(facts["aura"]),
            str(facts["one_bucket"]),
            str(facts["solo"]),
            str(facts["player"]),
            str(facts["bot"]),
            str(facts["census"]),
            str(facts["reals"]),
            str(facts["shades"]),
            str(amount),
            str(unrelated),
            str(child),
        ]
    )
    return {key: int(value) for key, value in (item.split("=", 1) for item in text.split())}


class PolicyBinary(unittest.TestCase):
    def test_self_check_passes(self):
        program = policy_program()
        self.assertEqual(program["code"], 0)
        self.assertIn("F10_ONE_BUCKET_POLICY_OK", program["stdout"])

    def test_sole_real_player_in_the_census_removes_the_fire_aura(self):
        decision = decide()
        self.assertTrue(decision["remove"])
        self.assertEqual(decision["reason"], "RemoveFireAura")

    def test_zero_humans_do_not_act(self):
        decision = decide(reals=0, census=0)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "Census")

    def test_two_humans_do_not_act(self):
        decision = decide(reals=2, census=1)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "Census")

    def test_outside_thrower_with_a_different_human_inside_does_not_act(self):
        decision = decide(reals=1, census=0)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "Census")

    def test_bots_only_do_not_act(self):
        decision = decide(bot=1, reals=0, census=1)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "BotCaster")

    def test_bot_throw_while_one_real_player_is_inside_does_not_act(self):
        decision = decide(bot=1, reals=1, census=1)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "BotCaster")

    def test_real_thrower_with_bots_nearby_still_acts(self):
        decision = decide(bot=0, reals=1, census=1)
        self.assertTrue(decision["remove"])

    def test_training_fire_does_not_act(self):
        decision = decide(entry=TRAIN)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "WrongTarget")

    def test_inactive_shade_count_does_not_act(self):
        decision = decide(shades=0)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "ShadeCount")

    def test_two_owning_shades_do_not_act(self):
        decision = decide(shades=2)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "ShadeCount")

    def test_wrong_spell_does_not_act(self):
        decision = decide(spell=SPLASH)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "WrongSpell")

    def test_wrong_effect_does_not_act(self):
        decision = decide(effect=1)
        self.assertEqual(decision["reason"], "WrongEffect")
        self.assertFalse(decision["remove"])

    def test_miss_or_cancel_does_not_act(self):
        decision = decide(hit=0)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "MissOrCancel")

    def test_missing_fire_aura_does_not_act(self):
        decision = decide(aura=0)
        self.assertFalse(decision["remove"])
        self.assertEqual(decision["reason"], "FireAuraAbsent")

    def test_each_flag_must_be_on(self):
        self.assertEqual(decide(one_bucket=0)["reason"], "OneBucketOff")
        self.assertEqual(decide(solo=0)["reason"], "SoloEnabledOff")
        self.assertEqual(decide(one_bucket=0, solo=0)["reason"], "OneBucketOff")
        self.assertEqual(decide(one_bucket=2, solo=1)["reason"], "OneBucketOff")
        self.assertFalse(decide(player=0)["remove"])
        self.assertEqual(decide(player=0)["reason"], "NotPlayer")

    def test_decision_does_not_read_amount(self):
        body = brace_body(HEADER, "struct OneBucketFacts")
        self.assertNotIn("amount", body)
        for _amount in (1, 2, 3):
            self.assertTrue(decide()["remove"])

    def test_child_fire_survives_a_parent_hit_for_both_splash_timings(self):
        for timing in ("immediate", "delayed"):
            result = simulate(timing, amount=3, child=1)
            self.assertEqual(result["child"], 1, timing)
            self.assertEqual(result["fire"], 0, timing)
            self.assertEqual(result["featureCasts"], 0, timing)
            self.assertEqual(result["credit"], 0, timing)
            self.assertEqual(result["featureStrippedUnrelated"], 0, timing)
            self.assertEqual(result["splashes"], 1, timing)

    def test_feature_does_not_strip_unrelated_aura_when_it_removes_42074(self):
        immediate = simulate("immediate", amount=3)
        delayed = simulate("delayed", amount=3)
        self.assertEqual(immediate["unrelated"], 1)
        self.assertEqual(delayed["unrelated"], 1)
        self.assertEqual(immediate["featureRemoves"], 1)
        self.assertEqual(delayed["featureRemoves"], 1)
        small = simulate("delayed", amount=1)
        self.assertEqual(small["fire"], 0)
        self.assertEqual(small["unrelated"], 1)
        self.assertEqual(small["featureRemoves"], 1)

    def test_immediate_small_fire_is_cleared_by_stock_before_the_feature(self):
        result = simulate("immediate", amount=1)
        self.assertEqual(result["fire"], 0)
        self.assertEqual(result["unrelated"], 0)
        self.assertEqual(result["featureRemoves"], 0)
        self.assertEqual(result["splashes"], 1)
        self.assertEqual(result["featureCasts"], 0)

    def test_flags_off_leave_stock_splash_for_both_timings(self):
        for timing in ("immediate", "delayed"):
            result = simulate(timing, amount=3, one_bucket=0)
            self.assertEqual(result["featureRemoves"], 0, timing)
            self.assertEqual(result["fire"], 1, timing)
            self.assertEqual(result["splashes"], 1, timing)
            self.assertEqual(result["child"], 1, timing)
            self.assertEqual(result["credit"], 0, timing)

    def test_training_fire_keeps_stock_credit_and_the_feature_stays_out(self):
        for timing in ("immediate", "delayed"):
            big = simulate(timing, amount=3, entry=TRAIN)
            small = simulate(timing, amount=1, entry=TRAIN)
            self.assertEqual(big["featureRemoves"], 0, timing)
            self.assertEqual(big["fire"], 1, timing)
            self.assertEqual(big["credit"], 1, timing)
            self.assertEqual(small["fire"], 0, timing)
            self.assertEqual(small["credit"], 1, timing)
            self.assertEqual(small["featureRemoves"], 0, timing)

    def test_miss_and_wrong_spell_do_not_splash_or_remove(self):
        missed = simulate("immediate", hit=0)
        wrong = simulate("immediate", spell=SPLASH)
        for result in (missed, wrong):
            self.assertEqual(result["featureRemoves"], 0)
            self.assertEqual(result["splashes"], 0)
            self.assertEqual(result["fire"], 1)
            self.assertEqual(result["child"], 1)
            self.assertEqual(result["credit"], 0)

    def test_outside_caster_and_disjoint_shades_leave_the_fire(self):
        outside = simulate("delayed", amount=3, census=0)
        disjoint = simulate("delayed", amount=3, shades=2)
        inactive = simulate("delayed", amount=3, shades=0)
        for result in (outside, disjoint, inactive):
            self.assertEqual(result["featureRemoves"], 0)
            self.assertEqual(result["fire"], 1)
            self.assertEqual(result["child"], 1)
            self.assertEqual(result["unrelated"], 1)
            self.assertEqual(result["credit"], 0)


class SourceWiring(unittest.TestCase):
    def test_hook_is_the_public_dummy_creature_callback_only(self):
        apply = brace_body(SHADE, "void ApplyHallowsEndOneBucket(")
        self.assertLess(apply.index("HasAura(FireAuraSpellId)"), apply.index("RemoveAurasDueToSpell"))
        self.assertIn("RemoveAurasDueToSpell(FireAuraSpellId)", apply)
        self.assertIn("DecideOneBucket", apply)
        self.assertIn("ReadHallowsEndSoloFireOneBucketSetting()", apply)
        self.assertIn("ReadHallowsEndSoloFireEnabledSetting()", apply)
        self.assertIn("CollectOneBucketOwnerCensus", apply)
        for forbidden in (
            "RemoveAllAuras",
            "CastSpell",
            "KilledMonsterCredit",
            "AreaExploredOrEventHappens",
            "SetAmount",
            "42348",
            "WaterSplashSpellId",
        ):
            self.assertNotIn(forbidden, apply)
        self.assertIn("ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE", SHADE)
        self.assertIn("new spell_naxxramas_hallows_end_one_bucket();", SHADE)
        self.assertNotIn("RegisterSpellScript", SHADE)
        self.assertNotIn("void SpellHit", SHADE)
        self.assertEqual(SHADE.count("ALLSPELLHOOK_"), 1)

    def test_phase_requires_the_fire_cycle_not_the_flag_alone(self):
        phase = brace_body(SHADE, "bool OneBucketFirePhaseActive() const")
        self.assertIn("fireCycleStarted", phase)
        self.assertIn("UNIT_FLAG_NON_ATTACKABLE", phase)
        reset = brace_body(SHADE, "void Reset() override")
        self.assertIn("fireCycleStarted = false;", reset)
        self.assertIn("UNIT_FLAG_NON_ATTACKABLE", reset)
        update = brace_body(SHADE, "void UpdateAI(uint32 diff) override")
        case_two = update.split("case 2:", 1)[1].split("case 3:", 1)[0]
        case_three = update.split("case 3:", 1)[1].split("case 4:", 1)[0]
        self.assertIn("fireCycleStarted = true;", case_two)
        self.assertIn("fireCycleStarted = true;", case_three)
        self.assertLess(case_two.index("fireCycleStarted = true;"), case_two.index("CastFires"))
        finish = brace_body(SHADE, "void FinishEvent(bool failed)")
        self.assertLess(finish.index("fireCycleStarted = false;"), finish.index("RemoveAllAuras"))
        census = brace_body(SHADE, "OneBucketOwnerCensus CollectOneBucketOwnerCensus(")
        self.assertIn("OneBucketFirePhaseActive()", census)
        self.assertIn("OwnsFireTrigger", census)
        self.assertIn("IsAlive()", census)
        self.assertIn("CountRealHallowsPlayers", census)
        self.assertIn("CollectNearbyHallowsPlayers", census)
        self.assertIn("100.0f", census)
        self.assertIn("NPC_SHADE_OF_HORSEMAN", census)

    def test_poll_still_does_not_extinguish_and_sql_is_unchanged(self):
        poll = brace_body(SHADE, "void PollSoloFires()")
        self.assertNotIn("RemoveAllAuras", poll)
        self.assertNotIn("RemoveAurasDueToSpell", poll)
        self.assertNotIn("42339", poll)
        self.assertNotIn("CastSpell", poll)
        self.assertNotIn("23686", SQL)
        self.assertNotIn("42339", SQL)
        self.assertNotIn("42348", SQL)
        self.assertNotIn("42074", SQL)
        self.assertIn("npc_naxxramas_hallows_end_soh", SQL)
        self.assertIn("WHERE `entry` = 23543;", SQL)

    def test_config_defaults_off_and_both_keys_are_required(self):
        self.assertIn("NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 0\n", CONF)
        self.assertIn("NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0\n", CONF)
        self.assertEqual(CONF.count("HallowsEnd.SoloFire.OneBucket = "), 1)
        decision = brace_body(HEADER, "inline OneBucketDecision DecideOneBucket(")
        self.assertLess(decision.index("oneBucket != 1"), decision.index("soloEnabled != 1"))
        self.assertLess(decision.index("soloEnabled != 1"), decision.index("casterInCensus"))
        self.assertIn('inline constexpr char DefaultOneBucketRaw[] = "0";', HEADER)
        self.assertIn("OneBucketFromRaw", CONFIG_CPP)
        self.assertIn("OneBucketConfigKey", CONFIG_CPP)
        self.assertEqual(CONFIG_CPP.count("GetOption<std::string>"), 3)
        self.assertNotIn("upload-artifact", WORKFLOW)

    def test_documents_and_workflow_keep_the_limits(self):
        for label in ("VERIFIED", "POTENTIAL ISSUE", "UNKNOWN", "NOT TESTED"):
            self.assertIn(label, DOC)
        self.assertIn(PINNED, DOC)
        self.assertIn(PROSPECTIVE, DOC)
        self.assertIn("42348", DOC)
        self.assertIn(PLAYERBOTS, DOC)
        self.assertIn(INDIVIDUAL, DOC)
        self.assertIn(str(AURA), HEADER)
        self.assertIn(str(SHADE_ENTRY), HEADER)
        self.assertIn("not a worldserver", DOC.lower())
        self.assertIn("contents: read", WORKFLOW)
        self.assertNotIn("upload-artifact", WORKFLOW)
        self.assertNotIn("actions/upload-artifact", WORKFLOW)
        self.assertIn("check_f10_one_bucket_tu_compile.py", WORKFLOW)
        self.assertIn(PINNED, WORKFLOW)
        self.assertIn(PROSPECTIVE, WORKFLOW)
        self.assertIn("cs02/f10-s2-one-bucket-2026-10-20", WORKFLOW)
        self.assertIn("HallowsEndShadeOfTheHorseman.cpp", WORKFLOW)
        self.assertIn("HallowsEndSoloFireConfig.cpp", WORKFLOW)


class PinnedCoreContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = os.environ.get("F10_CORE_OLD")
        new = os.environ.get("F10_CORE_NEW")
        if not old or not new:
            raise unittest.SkipTest("F10_CORE_OLD and F10_CORE_NEW are not set; core pin skipped")
        cls.old = Path(old)
        cls.new = Path(new)

    def read(self, root: Path, relative: str) -> str:
        path = root / relative
        self.assertTrue(path.is_file(), relative)
        return path.read_text(errors="strict")

    def test_bucket_binding_and_effect_dummy_are_the_same_text(self):
        relative = "src/server/scripts/Events/hallows_end.cpp"
        old = (self.old / relative).read_bytes()
        new = (self.new / relative).read_bytes()
        self.assertEqual(old, new)
        self.assertEqual(git_blob_sha1(old), HALLOWS_BLOB)
        text = old.decode()
        self.assertEqual(line(text, 253).strip(), "SPELL_FIRE_AURA_BASE                    = 42074,")
        self.assertEqual(line(text, 257).strip(), "SPELL_WATER_SPLASH                      = 42348,")
        self.assertEqual(line(text, 265).strip(), "NPC_FIRE_TRIGGER                        = 23686,")
        self.assertEqual(line(text, 264).strip(), "NPC_SHADE_OF_HORSEMAN                   = 23543,")
        self.assertIn("GetCaster()->CastSpell(tgt, SPELL_WATER_SPLASH, true);", line(text, 296))
        self.assertNotIn("PreventHitDefaultEffect", text.split("class spell_hallows_end_base_fire", 1)[0])
        self.assertEqual(
            line(text, 350).strip(),
            "DoEffectCalcPeriodic += AuraEffectCalcPeriodicFn(spell_hallows_end_base_fire::CalcPeriodic, EFFECT_0, SPELL_AURA_PERIODIC_DUMMY);",
        )
        self.assertEqual(line(text, 536).strip(), "me->CastSpell(me, SPELL_FIRE_AURA_BASE, true);")
        self.assertEqual(line(text, 572).strip(), "if (AuraEffect* aurEff = me->GetAuraEffect(SPELL_FIRE_AURA_BASE, EFFECT_0))")
        self.assertEqual(line(text, 581).strip(), "me->RemoveAllAuras();")
        self.assertEqual(line(text, 692).strip(), "me->SetUnitFlag(UNIT_FLAG_NON_ATTACKABLE);")
        self.assertEqual(line(text, 680).strip(), "me->GetCreaturesWithEntryInRange(temp, 100.0f, NPC_FIRE_TRIGGER);")
        self.assertIn("CastFires(true);", line(text, 721))
        self.assertIn("HasPeriodicDummyAura()", line(text, 729))
        self.assertEqual(line(text, 771).strip(), "me->ReplaceAllUnitFlags(UNIT_FLAG_NONE);")
        self.assertIn("me->DespawnOrUnsummon(1ms);", line(text, 700))
        self.assertNotIn("RemoveAllAuras", text.split("void EnterEvadeMode", 1)[1].split("uint32 GetData", 1)[0])
        self.assertIn("caster->ToPlayer()->KilledMonsterCredit", line(text, 932))
        names = (self.old / "data/sql/base/db_world/spell_script_names.sql").read_bytes()
        self.assertEqual(names, (self.new / "data/sql/base/db_world/spell_script_names.sql").read_bytes())
        self.assertEqual(git_blob_sha1(names), NAMES_BLOB)
        name_text = names.decode()
        self.assertEqual(name_text.count("(42339,"), 1)
        self.assertEqual(name_text.count("(42348,"), 0)
        self.assertIn("(42339,'spell_hallows_end_bucket_lands'),", line(name_text, 1092))
        creatures = (self.old / "data/sql/base/db_world/creature_template.sql").read_bytes()
        self.assertEqual(creatures, (self.new / "data/sql/base/db_world/creature_template.sql").read_bytes())
        self.assertEqual(git_blob_sha1(creatures), CREATURE_BLOB)
        body = creatures.decode()
        train = next(row for row in body.splitlines() if row.startswith("(23537,"))
        trigger = next(row for row in body.splitlines() if row.startswith("(23686,"))
        shade = next(row for row in body.splitlines() if row.startswith("(23543,"))
        self.assertIn("'npc_hallows_end_train_fire'", train)
        self.assertIn("'npc_soh_fire_trigger'", trigger)
        self.assertIn("'npc_hallows_end_soh'", shade)
        self.assertIn(str(TRAIN), line(body, 17567))
        self.assertIn(str(FIRE), line(body, 17715))

    def test_dummy_hook_follows_the_stock_handler_and_does_not_special_case_42339(self):
        relative = "src/server/game/Spells/SpellEffects.cpp"
        old = self.read(self.old, relative)
        new = self.read(self.new, relative)
        old_dummy = old.split("void Spell::EffectDummy", 1)[1].split("void Spell::EffectTriggerSpell", 1)[0]
        new_dummy = new.split("void Spell::EffectDummy", 1)[1].split("void Spell::EffectTriggerSpell", 1)[0]
        self.assertEqual(old_dummy, new_dummy)
        self.assertIn("effectHandleMode != SPELL_EFFECT_HANDLE_HIT_TARGET", old_dummy)
        self.assertIn("sScriptMgr->OnDummyEffect(m_caster, m_spellInfo->Id, effIndex, unitTarget->ToCreature());", old_dummy)
        self.assertNotIn("42339", old_dummy)
        self.assertNotIn("42348", old_dummy)
        for root in (self.old, self.new):
            hook = self.read(root, "src/server/game/Scripting/ScriptDefines/AllSpellScript.h")
            self.assertEqual(line(hook, 35).strip(), "ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE,")
            body = self.read(root, "src/server/game/Scripting/ScriptDefines/AllSpellScript.cpp")
            self.assertIn("if (enabledHooks.empty())", body)
            self.assertIn("ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE", body)

    def test_removal_and_census_apis_exist_at_both_pins(self):
        old_unit = self.read(self.old, "src/server/game/Entities/Unit/Unit.h")
        new_unit = self.read(self.new, "src/server/game/Entities/Unit/Unit.h")
        self.assertIn("void RemoveAurasDueToSpell(uint32 spellId", line(old_unit, 1408))
        self.assertIn("void RemoveAurasDueToSpell(uint32 spellId", line(new_unit, 1409))
        self.assertIn("bool HasAura(uint32 spellId", line(old_unit, 1500))
        self.assertIn("bool HasAura(uint32 spellId", line(new_unit, 1501))
        self.assertIn("HasPeriodicDummyAura()", line(old_unit, 1824))
        self.assertIn("HasPeriodicDummyAura()", line(new_unit, 1825))
        self.assertIn("bool IsAlive()", line(old_unit, 1798))
        self.assertIn("bool IsAlive()", line(new_unit, 1799))
        self.assertIn("HasUnitFlag(UnitFlags flags)", line(old_unit, 750))
        self.assertIn("HasUnitFlag(UnitFlags flags)", line(new_unit, 750))
        for root in (self.old, self.new):
            grid = self.read(root, "src/server/game/Grids/Notifiers/GridNotifiers.h")
            self.assertIn("class AnyPlayerInObjectRangeCheck", line(grid, 1379))
            self.assertIn("reqAlive = true, bool disallowGM = false", line(grid, 1382))
            creature = self.read(root, "src/server/game/Entities/Creature/Creature.h")
            self.assertIn("CreatureAI* AI()", line(creature, 144))
            obj = self.read(root, "src/server/game/Entities/Object/Object.h")
            self.assertIn("GetCreaturesWithEntryInRange", line(obj, 666))
            self.assertIn("Player* ToPlayer()", line(obj, 208))

    def test_base_sql_has_no_bucket_speed_or_pet_aura_row(self):
        for name in ("spell_dbc.sql", "spell_linked_spell.sql", "spell_scripts.sql", "spell_pet_auras.sql"):
            text = self.read(self.old, "data/sql/base/db_world/" + name)
            self.assertEqual(text, self.read(self.new, "data/sql/base/db_world/" + name))
            for spell in ("(42339,", "(42348,", "(42074,"):
                self.assertNotIn(spell, text, name)


if __name__ == "__main__":
    unittest.main()
