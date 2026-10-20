"""Source contract and adversarial model for the F10 one-bucket design.

These tests do not start a worldserver, apply SQL, or throw a bucket.
A pass is not gameplay acceptance. Core pins run only when F10_CORE_OLD
and F10_CORE_NEW point at Grimfeather checkouts of the two reviewed SHAs.
"""
from __future__ import annotations

import hashlib
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHADE = (ROOT / "src/Events/HallowsEndShadeOfTheHorseman.cpp").read_text()
HEADER = (ROOT / "src/Events/HallowsEndSoloFire.h").read_text()
SQL = (ROOT / "data/sql/db-world/2026_09_21_00_event_script_overrides.sql").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
DOC = (ROOT / "docs/research/F10-hallows-end-one-bucket-S1.md").read_text()
WORKFLOW = (ROOT / ".github/workflows/f10-s1-one-bucket.yml").read_text()

PINNED = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
PROSPECTIVE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
HALLOWS_BLOB = "02282feb50f24debd6bbeb0fe9b928db6adabd21"
NAMES_BLOB = "e93f9e13d5ab2c98b134c5c632fa1f6f688afa15"
CREATURE_BLOB = "899a56b0f5d7bac6536a48e038acb23ba8a70812"
MODULE_BASE = "c193be076dedd5bbf1dafa01fb4ca15f16e07f9e"

BUCKET_LANDS = 42339
SPLASH = 42348
CREATE_BUCKET = 42349
FIRE_AURA = 42074
SPREAD = 42079
START_FIRE = 42132
NPC_FIRE = 23686
NPC_TRAIN = 23537
NPC_SHADE = 23543
NPC_OTHER = 99999

NORMAL = "normal"
TRAIN = "train"
OTHER = "other"


def line(text: str, number: int) -> str:
    return text.splitlines()[number - 1]


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def between(text: str, start: str, end: str) -> str:
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0]


def gates(
    one_bucket=1,
    solo_enabled=1,
    real_players=1,
    caster_is_player=True,
    caster_real=True,
    event_active=True,
    npc=NPC_FIRE,
    in_shade_list=True,
    spell=BUCKET_LANDS,
    hit_accepted=True,
    shade_matches=1,
):
    """S2 decision. Amount is intentionally not a parameter."""
    return bool(
        one_bucket == 1
        and solo_enabled == 1
        and real_players == 1
        and caster_is_player
        and caster_real
        and event_active
        and npc == NPC_FIRE
        and in_shade_list
        and spell == BUCKET_LANDS
        and hit_accepted
        and shade_matches == 1
    )


def stock_splash(kind, amount, alive):
    """Core SpellHit for 42348. Returns amount, alive, action."""
    if not alive:
        return amount, False, "already-out"
    if kind == NORMAL:
        if amount > 2:
            return amount - 2, True, "partial"
        return amount, False, "removed"
    if kind == TRAIN:
        if amount > 1:
            return amount - 1, True, "train-partial"
        return amount, False, "removed"
    return amount, alive, "untouched"


class Fire:
    """One 42074 aura plus any child fires already launched by a spread tick."""

    def __init__(self, amount):
        self.amount = amount
        self.alive = True
        self.tick = 0
        self.spreads = 0
        self.children = []

    def core_tick(self):
        if not self.alive:
            return
        self.tick += 1
        amount = self.amount
        if amount < 3:
            amount += 1
        elif self.tick % 3 != 2:
            return
        self.amount = amount
        if amount >= 3:
            self.spreads += 1
            self.children.append(Fire(0))


def resolve_bucket(fire, kind, ctx, timing="immediate"):
    """Apply one accepted-or-not bucket using the design order.

    immediate: stock splash SpellHit finishes, then the feature may clear.
    delayed: the feature clears at the 42339 hit, and the splash arrives after.
    A tick during a delayed splash is a separate call and is not done here.
    """
    feature = gates(npc=_kind_npc(kind, ctx), **{k: ctx[k] for k in ctx if k != "npc"})
    # npc in ctx wins when the caller set it; _kind_npc only fills the default.
    if "npc" in ctx:
        feature = gates(**ctx)
    stock_action = "not-run"
    feature_cleared = False
    if timing == "immediate":
        if ctx.get("hit_accepted", True) and ctx.get("spell", BUCKET_LANDS) == BUCKET_LANDS:
            fire.amount, fire.alive, stock_action = stock_splash(kind, fire.amount, fire.alive)
        if feature and fire.alive:
            fire.alive = False
            feature_cleared = True
        elif feature:
            feature_cleared = True
    elif timing == "delayed":
        if feature:
            fire.alive = False
            feature_cleared = True
            stock_action = "skipped-no-aura"
        elif ctx.get("hit_accepted", True) and ctx.get("spell", BUCKET_LANDS) == BUCKET_LANDS:
            fire.amount, fire.alive, stock_action = stock_splash(kind, fire.amount, fire.alive)
    else:
        raise AssertionError(timing)
    return {
        "feature": feature,
        "feature_cleared": feature_cleared,
        "stock_action": stock_action,
        "amount": fire.amount,
        "alive": fire.alive,
        "spreads": fire.spreads,
    }


def _kind_npc(kind, ctx):
    if "npc" in ctx:
        return ctx["npc"]
    if kind == TRAIN:
        return NPC_TRAIN
    if kind == OTHER:
        return NPC_OTHER
    return NPC_FIRE


def solo_ctx(**overrides):
    ctx = {
        "one_bucket": 1,
        "solo_enabled": 1,
        "real_players": 1,
        "caster_is_player": True,
        "caster_real": True,
        "event_active": True,
        "npc": NPC_FIRE,
        "in_shade_list": True,
        "spell": BUCKET_LANDS,
        "hit_accepted": True,
        "shade_matches": 1,
    }
    ctx.update(overrides)
    return ctx


def rejected_amount_observer(before, after):
    """The forbidden rule: any amount drop is a reason to extinguish."""
    return after < before


class DesignDocContract(unittest.TestCase):
    def test_document_names_the_pins_and_the_verdict(self):
        self.assertIn(PINNED, DOC)
        self.assertIn(PROSPECTIVE, DOC)
        self.assertIn(HALLOWS_BLOB, DOC)
        self.assertIn(NAMES_BLOB, DOC)
        self.assertIn(CREATURE_BLOB, DOC)
        self.assertIn(MODULE_BASE, DOC)
        self.assertIn("6292945249", DOC)
        for label in ("VERIFIED", "POTENTIAL ISSUE", "UNKNOWN", "NOT TESTED"):
            self.assertIn(label, DOC)
        self.assertIn("No gameplay C++ was added", DOC)
        self.assertIn("AllSpellScript::OnDummyEffect", DOC)
        self.assertIn("aura amount decreased", DOC)
        self.assertIn("NaxxramasCore.HallowsEnd.SoloFire.OneBucket", DOC)
        self.assertIn("does not implement that action", DOC)

    def test_workflow_does_not_upload_artifacts(self):
        self.assertIn("contents: read", WORKFLOW)
        self.assertNotIn("actions/upload-artifact", WORKFLOW)
        self.assertIn("test_f10_hallows_end_one_bucket_s1.py", WORKFLOW)
        self.assertIn(PINNED, WORKFLOW)
        self.assertIn(PROSPECTIVE, WORKFLOW)


class ModuleDoesNotImplementOneBucket(unittest.TestCase):
    def test_shade_has_no_bucket_handler_and_the_poll_does_not_clear(self):
        self.assertNotIn("void SpellHit", SHADE)
        self.assertNotIn("42339", SHADE)
        self.assertNotIn("42348", SHADE)
        self.assertNotIn("OnDummyEffect", SHADE)
        self.assertNotIn("OneBucket", SHADE)
        poll = between(SHADE, "void PollSoloFires()", "void CastFires(")
        self.assertNotIn("RemoveAllAuras", poll)
        self.assertNotIn("SetAmount", poll)
        self.assertIn("SetPeriodicTimer", poll)

    def test_sql_and_config_do_not_grow_a_one_bucket_switch(self):
        self.assertNotIn("23686", SQL)
        self.assertNotIn("42339", SQL)
        self.assertNotIn("42348", SQL)
        self.assertNotIn("42074", SQL)
        self.assertIn("npc_naxxramas_hallows_end_soh", SQL)
        self.assertNotIn("OneBucket", CONF)
        self.assertIn("NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0", CONF)
        self.assertNotIn("OnDummyEffect", HEADER)
        self.assertNotIn("42339", HEADER)


class AdversarialModel(unittest.TestCase):
    def test_b1_b2_b3_bucket_on_amount_1_2_and_3(self):
        expected = {
            1: ("removed", False),
            2: ("removed", False),
            3: ("partial", False),
        }
        for amount, (stock, alive) in expected.items():
            fire = Fire(amount)
            result = resolve_bucket(fire, NORMAL, solo_ctx())
            self.assertTrue(result["feature"], amount)
            self.assertTrue(result["feature_cleared"], amount)
            self.assertEqual(result["stock_action"], stock, amount)
            self.assertFalse(alive, amount)
            self.assertFalse(result["alive"], amount)

    def test_b4_training_fire_keeps_stock_math(self):
        big = Fire(3)
        result = resolve_bucket(big, TRAIN, solo_ctx(npc=NPC_TRAIN))
        self.assertFalse(result["feature"])
        self.assertFalse(result["feature_cleared"])
        self.assertEqual(result["stock_action"], "train-partial")
        self.assertEqual((result["amount"], result["alive"]), (2, True))
        small = Fire(1)
        result = resolve_bucket(small, TRAIN, solo_ctx(npc=NPC_TRAIN))
        self.assertFalse(result["feature"])
        self.assertEqual(result["stock_action"], "removed")
        self.assertFalse(result["alive"])

    def test_b5_bot_throw_does_not_apply(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(caster_real=False))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"], result["stock_action"]), (1, True, "partial"))

    def test_b6_two_real_players_do_not_apply(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(real_players=2))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"]), (1, True))

    def test_b7_inactive_event_does_not_apply(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(event_active=False))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"]), (1, True))

    def test_b8_wrong_npc_is_untouched(self):
        fire = Fire(3)
        result = resolve_bucket(fire, OTHER, solo_ctx(npc=NPC_OTHER))
        self.assertFalse(result["feature"])
        self.assertEqual(result["stock_action"], "untouched")
        self.assertEqual((result["amount"], result["alive"]), (3, True))

    def test_b9_fire_outside_the_shade_list_stays_on_stock(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(in_shade_list=False))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"]), (1, True))

    def test_b10_feature_off_is_stock(self):
        for amount, stock, alive, end_amount in (
            (1, "removed", False, 1),
            (2, "removed", False, 2),
            (3, "partial", True, 1),
        ):
            fire = Fire(amount)
            result = resolve_bucket(fire, NORMAL, solo_ctx(one_bucket=0))
            self.assertFalse(result["feature"], amount)
            self.assertFalse(result["feature_cleared"], amount)
            self.assertEqual(result["stock_action"], stock, amount)
            self.assertEqual(result["alive"], alive, amount)
            self.assertEqual(result["amount"], end_amount, amount)

    def test_b11_one_bucket_key_does_not_bypass_solo_enabled(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(solo_enabled=0))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"]), (1, True))

    def test_b12_spread_that_already_happened_is_not_undone(self):
        parent = Fire(2)
        parent.core_tick()
        self.assertEqual((parent.amount, parent.spreads, len(parent.children)), (3, 1, 1))
        child = parent.children[0]
        result = resolve_bucket(parent, NORMAL, solo_ctx())
        self.assertTrue(result["feature"])
        self.assertFalse(result["alive"])
        self.assertEqual(result["spreads"], 1)
        self.assertTrue(child.alive)
        self.assertEqual(child.amount, 0)

    def test_b13_bucket_before_the_tick_prevents_the_spread(self):
        fire = Fire(2)
        result = resolve_bucket(fire, NORMAL, solo_ctx())
        self.assertFalse(result["alive"])
        fire.core_tick()
        self.assertEqual(fire.spreads, 0)
        self.assertEqual(fire.children, [])

    def test_b14_feature_off_leaves_the_parent_and_the_child(self):
        parent = Fire(2)
        parent.core_tick()
        child = parent.children[0]
        result = resolve_bucket(parent, NORMAL, solo_ctx(one_bucket=0))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"], result["spreads"]), (1, True, 1))
        self.assertTrue(child.alive)

    def test_b15_a_missed_bucket_lands_hit_changes_nothing(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(hit_accepted=False))
        self.assertFalse(result["feature"])
        self.assertEqual(result["stock_action"], "not-run")
        self.assertEqual((result["amount"], result["alive"]), (3, True))

    def test_b16_splash_id_alone_is_not_the_hook(self):
        self.assertFalse(gates(**solo_ctx(spell=SPLASH)))
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(spell=SPLASH))
        self.assertFalse(result["feature"])
        self.assertEqual(result["stock_action"], "not-run")
        self.assertEqual((result["amount"], result["alive"]), (3, True))

    def test_b17_amount_drop_without_a_bucket_does_not_extinguish(self):
        self.assertTrue(rejected_amount_observer(3, 1))
        self.assertFalse(gates(**solo_ctx(hit_accepted=False, spell=0)))
        fire = Fire(3)
        fire.amount = 1
        result = resolve_bucket(fire, NORMAL, solo_ctx(hit_accepted=False, spell=0))
        self.assertFalse(result["feature_cleared"])
        self.assertTrue(result["alive"])
        self.assertEqual(result["amount"], 1)

    def test_b18_bots_only_stay_on_stock(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(real_players=0, caster_real=False))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"]), (1, True))

    def test_b19_bots_nearby_do_not_block_a_real_throw(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(real_players=1))
        self.assertTrue(result["feature"])
        self.assertFalse(result["alive"])

    def test_b20_delayed_splash_clears_before_a_flight_tick(self):
        fire = Fire(2)
        result = resolve_bucket(fire, NORMAL, solo_ctx(), timing="delayed")
        self.assertTrue(result["feature_cleared"])
        self.assertEqual(result["stock_action"], "skipped-no-aura")
        self.assertFalse(result["alive"])
        fire.core_tick()
        self.assertEqual(fire.spreads, 0)

    def test_b21_delayed_stock_splash_can_lose_to_a_tick(self):
        fire = Fire(2)
        fire.core_tick()
        self.assertEqual((fire.amount, fire.spreads), (3, 1))
        result = resolve_bucket(fire, NORMAL, solo_ctx(one_bucket=0), timing="delayed")
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"], result["spreads"]), (1, True, 1))

    def test_b22_two_shades_block_the_feature(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(shade_matches=2))
        self.assertFalse(result["feature"])
        self.assertEqual((result["amount"], result["alive"]), (1, True))
        none = resolve_bucket(Fire(3), NORMAL, solo_ctx(shade_matches=0))
        self.assertFalse(none["feature"])

    def test_b23_a_gm_thrower_is_the_real_player(self):
        fire = Fire(3)
        result = resolve_bucket(fire, NORMAL, solo_ctx(caster_real=True, real_players=1))
        self.assertTrue(result["feature"])
        self.assertFalse(result["alive"])

    def test_b24_the_same_gates_accept_every_amount(self):
        decision = gates(**solo_ctx())
        self.assertTrue(decision)
        for amount in (0, 1, 2, 3, 9):
            self.assertTrue(gates(**solo_ctx()), amount)
            self.assertFalse(gates(**solo_ctx(one_bucket=0)), amount)

    def test_non_player_caster_and_bad_keys_do_not_apply(self):
        self.assertFalse(gates(**solo_ctx(caster_is_player=False)))
        self.assertFalse(gates(**solo_ctx(one_bucket=2)))
        self.assertFalse(gates(**solo_ctx(solo_enabled=2)))
        self.assertFalse(gates(**solo_ctx(event_active=False, in_shade_list=True)))


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

    def test_hallows_end_blob_and_bucket_lines(self):
        relative = "src/server/scripts/Events/hallows_end.cpp"
        old = (self.old / relative).read_bytes()
        new = (self.new / relative).read_bytes()
        self.assertEqual(old, new)
        self.assertEqual(git_blob_sha1(old), HALLOWS_BLOB)
        text = old.decode()
        expectations = {
            255: "SPELL_SPREAD_FIRE                       = 42079,",
            256: "SPELL_CREATE_BUCKET                     = 42349,",
            257: "SPELL_WATER_SPLASH                      = 42348,",
            294: "GetCaster()->CastSpell(target, SPELL_CREATE_BUCKET, true);",
            296: "GetCaster()->CastSpell(tgt, SPELL_WATER_SPLASH, true);",
            301: "OnEffectHitTarget += SpellEffectFn(spell_hallows_end_bucket_lands::HandleDummy, EFFECT_0, SPELL_EFFECT_DUMMY);",
            325: "if (amount < 3)",
            326: "amount++;",
            336: "owner->CastSpell(owner, SPELL_SPREAD_FIRE, true);",
            523: "struct npc_soh_fire_trigger : public NullCreatureAI",
            570: "else if (spellInfo->Id == SPELL_WATER_SPLASH)",
            575: "if (amt > 2)",
            578: "aurEff->SetAmount(amt - 2);",
            581: "me->RemoveAllAuras();",
            902: "struct npc_hallows_end_train_fire : public NullCreatureAI",
            922: "if (spellInfo->Id == SPELL_WATER_SPLASH && caster->ToPlayer())",
            927: "if (amt > 1)",
            928: "aurEff->SetAmount(amt - 1);",
            930: "me->RemoveAllAuras();",
            1511: "RegisterSpellScript(spell_hallows_end_base_fire);",
            1512: "RegisterSpellScript(spell_hallows_end_bucket_lands);",
            1515: "RegisterCreatureAI(npc_hallows_end_train_fire);",
            1519: "RegisterCreatureAI(npc_soh_fire_trigger);",
        }
        for number, expected in expectations.items():
            self.assertEqual(line(text, number).strip(), expected)
        handler = between(text, "class spell_hallows_end_bucket_lands", "class spell_hallows_end_base_fire")
        self.assertNotIn("PreventHitDefaultEffect", handler)

    def test_sql_bindings_are_one_row_and_42348_has_none(self):
        relative = "data/sql/base/db_world/spell_script_names.sql"
        old = (self.old / relative).read_bytes()
        new = (self.new / relative).read_bytes()
        self.assertEqual(old, new)
        self.assertEqual(git_blob_sha1(old), NAMES_BLOB)
        text = old.decode()
        self.assertEqual(text.count("(42074,"), 1)
        self.assertEqual(text.count("(42339,"), 1)
        self.assertEqual(text.count("(42348,"), 0)
        self.assertEqual(text.count("(42349,"), 0)
        self.assertEqual(text.count("(42079,"), 0)
        self.assertEqual(text.count("(42132,"), 0)
        self.assertIn("(42074,'spell_hallows_end_base_fire'),", line(text, 1087))
        self.assertIn("(42339,'spell_hallows_end_bucket_lands'),", line(text, 1092))
        creatures = (self.old / "data/sql/base/db_world/creature_template.sql").read_bytes()
        self.assertEqual(creatures, (self.new / "data/sql/base/db_world/creature_template.sql").read_bytes())
        self.assertEqual(git_blob_sha1(creatures), CREATURE_BLOB)
        body = creatures.decode()
        train = next(row for row in body.splitlines() if row.startswith("(23537,"))
        shade = next(row for row in body.splitlines() if row.startswith("(23543,"))
        trigger = next(row for row in body.splitlines() if row.startswith("(23686,"))
        self.assertIn("'npc_hallows_end_train_fire'", train)
        self.assertIn("'npc_hallows_end_soh'", shade)
        self.assertIn("'npc_soh_fire_trigger'", trigger)
        for name in ("spell_dbc.sql", "spell_linked_spell.sql", "spell_scripts.sql"):
            sql = self.read(self.old, "data/sql/base/db_world/" + name)
            self.assertEqual(sql, self.read(self.new, "data/sql/base/db_world/" + name), name)
            for spell_id in (BUCKET_LANDS, SPLASH, CREATE_BUCKET, FIRE_AURA, SPREAD, START_FIRE):
                self.assertNotIn("(%d," % spell_id, sql, name)

    def test_dummy_hook_runs_after_the_stock_handler_and_does_not_replace_it(self):
        old_effects = self.read(self.old, "src/server/game/Spells/SpellEffects.cpp")
        new_effects = self.read(self.new, "src/server/game/Spells/SpellEffects.cpp")
        old_dummy = between(old_effects, "void Spell::EffectDummy", "void Spell::EffectTriggerSpell")
        new_dummy = between(new_effects, "void Spell::EffectDummy", "void Spell::EffectTriggerSpell")
        self.assertEqual(old_dummy, new_dummy)
        self.assertIn(
            "sScriptMgr->OnDummyEffect(m_caster, m_spellInfo->Id, effIndex, unitTarget->ToCreature());",
            line(old_effects, 800),
        )
        self.assertIn(
            "sScriptMgr->OnDummyEffect(m_caster, m_spellInfo->Id, effIndex, unitTarget->ToCreature());",
            line(new_effects, 800),
        )
        for root in (self.old, self.new):
            header = self.read(root, "src/server/game/Scripting/ScriptDefines/AllSpellScript.h")
            source = self.read(root, "src/server/game/Scripting/ScriptDefines/AllSpellScript.cpp")
            self.assertIn(
                "virtual void OnDummyEffect(WorldObject* /*caster*/, uint32 /*spellID*/, SpellEffIndex /*effIndex*/, Creature* /*creatureTarget*/)",
                line(header, 92),
            )
            self.assertIn("ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE", line(source, 74))
            self.assertIn("if (enabledHooks.empty())", line(source, 101))
            macros = self.read(root, "src/server/game/Scripting/ScriptMgrMacros.h")
            self.assertIn("#define CALL_ENABLED_HOOKS(scriptType, hookType, action)", macros)
            self.assertNotIn("SpellHit", header)

    def test_spell_script_load_rules(self):
        for root, insert_line, handle_line in (
            (self.old, 6392, 5861),
            (self.new, 6405, 5862),
        ):
            mgr = self.read(root, "src/server/game/Globals/ObjectMgr.h")
            self.assertIn("typedef std::multimap<uint32, uint32> SpellScriptsContainer;", line(mgr, 390))
            cpp = self.read(root, "src/server/game/Globals/ObjectMgr.cpp")
            self.assertIn(
                "_spellScriptsStore.insert(SpellScriptsContainer::value_type(spellInfo->Id, GetScriptId(scriptName)));",
                line(cpp, insert_line),
            )
            spell = self.read(root, "src/server/game/Spells/Spell.cpp")
            self.assertIn("bool preventDefault = CallScriptEffectHandlers((SpellEffIndex)i, mode);", line(spell, handle_line))
            self.assertIn("if (!preventDefault && eff < TOTAL_SPELL_EFFECTS)", line(spell, handle_line + 2))
        loader = self.read(self.old, "src/server/game/Scripting/ScriptDefines/SpellScriptLoader.cpp")
        self.assertEqual(loader, self.read(self.new, "src/server/game/Scripting/ScriptDefines/SpellScriptLoader.cpp"))
        create = between(loader, "void ScriptMgr::CreateSpellScripts", "void ScriptMgr::CreateAuraScripts")
        self.assertIn("GetSpellScriptsBounds", create)
        self.assertIn("scriptVector.push_back(script);", create)
        header = self.read(self.old, "src/server/game/Scripting/ScriptDefines/SpellScriptLoader.h")
        self.assertIn("[[nodiscard]] bool IsDatabaseBound() const override { return true; }", header)
        self.assertIn("#define RegisterSpellScript(spell_script) RegisterSpellScriptWithArgs(spell_script, #spell_script)", header)
        obj = self.read(self.old, "src/server/game/Scripting/ScriptObject.h")
        self.assertIn("[[nodiscard]] virtual bool isAfterLoadScript() const { return IsDatabaseBound(); }", obj)
        registry = self.read(self.old, "src/server/game/Scripting/ScriptMgr.h")
        self.assertEqual(registry, self.read(self.new, "src/server/game/Scripting/ScriptMgr.h"))
        self.assertIn("delete oldScript;", line(registry, 866))
        self.assertIn('LOG_ERROR("sql.sql", "Script named \'{}\' is not assigned in the database.",', line(registry, 882))

    def test_no_public_spellhit_hook_and_ai_replacement_is_first(self):
        for root in (self.old, self.new):
            for relative in (
                "src/server/game/Scripting/ScriptDefines/AllSpellScript.h",
                "src/server/game/Scripting/ScriptDefines/AllCreatureScript.h",
                "src/server/game/Scripting/ScriptDefines/UnitScript.h",
            ):
                self.assertNotIn("SpellHit", self.read(root, relative), relative)
            creature = self.read(root, "src/server/game/Scripting/ScriptDefines/CreatureScript.cpp")
            body = between(creature, "CreatureAI* ScriptMgr::GetCreatureAI", "void ScriptMgr::OnFfaPvpStateUpdate")
            self.assertIn("if (retAI)", body)
            self.assertLess(body.index("if (retAI)"), body.index("GetScriptById"))
            selector = self.read(root, "src/server/game/AI/CreatureAISelector.cpp")
            self.assertIn("if (CreatureAI* scriptedAI = sScriptMgr->GetCreatureAI(creature))", line(selector, 85))
            player = self.read(root, "src/server/game/Scripting/ScriptDefines/PlayerScript.h")
            self.assertIn("// Called in Spell::Cast.", line(player, 348))
            self.assertIn("virtual void OnPlayerSpellCast", line(player, 349))

    def test_cast_hooks_are_not_the_impact_path(self):
        old = self.read(self.old, "src/server/game/Spells/Spell.cpp")
        new = self.read(self.new, "src/server/game/Spells/Spell.cpp")
        self.assertIn("should be done before the spell is actually executed", line(old, 3947))
        self.assertIn("sScriptMgr->OnPlayerSpellCast(playerCaster, this, skipCheck);", line(old, 3948))
        self.assertIn("should be done before the spell is actually executed", line(new, 3948))
        self.assertIn("sScriptMgr->OnPlayerSpellCast(playerCaster, this, skipCheck);", line(new, 3949))
        self.assertIn("if ((m_spellInfo->Speed > 0.0f && !m_spellInfo->IsChanneled())", line(old, 4131))
        self.assertIn("handle_immediate();", line(old, 4159))
        self.assertIn("sScriptMgr->OnSpellCast(this, unitCaster, m_spellInfo, skipCheck);", line(old, 4212))
        self.assertIn("if ((m_spellInfo->Speed > 0.0f && !m_spellInfo->IsChanneled())", line(new, 4132))
        self.assertIn("handle_immediate();", line(new, 4160))
        self.assertIn("sScriptMgr->OnSpellCast(this, unitCaster, m_spellInfo, skipCheck);", line(new, 4213))
        self.assertIn("if (missInfo == SPELL_MISS_NONE)", line(old, 2709))
        self.assertIn("SpellMissInfo missInfo2 = DoSpellHitOnUnit(spellHitTarget, mask, target->scaleAura);", line(old, 2744))
        self.assertIn("spellHitTarget->ToCreature()->AI()->SpellHit(unitCaster, m_spellInfo);", line(old, 3067))
        self.assertIn("CallScriptAfterHitHandlers();", line(old, 3084))
        self.assertIn("return SPELL_MISS_IMMUNE;", line(old, 3097))
        self.assertLess(old.splitlines().index(line(old, 3097)), old.splitlines().index(line(old, 3341)))
        self.assertIn("HandleEffects(unit, nullptr, nullptr, effectNumber, SPELL_EFFECT_HANDLE_HIT_TARGET);", line(old, 3341))
        self.assertIn("if (missInfo == SPELL_MISS_NONE)", line(new, 2705))
        self.assertIn("SpellMissInfo missInfo2 = DoSpellHitOnUnit(spellHitTarget, mask, target->scaleAura);", line(new, 2740))
        self.assertIn(
            "spellHitTarget->ToCreature()->AI()->SpellHit(unitCaster ? unitCaster : m_originalCaster, m_spellInfo);",
            line(new, 3063),
        )
        self.assertIn("CallScriptAfterHitHandlers();", line(new, 3080))
        self.assertIn("return SPELL_MISS_IMMUNE;", line(new, 3093))
        self.assertIn("HandleEffects(unit, nullptr, nullptr, effectNumber, SPELL_EFFECT_HANDLE_HIT_TARGET);", line(new, 3342))
        self.assertLess(3093, 3342)


# Script names and spell_script_names-style rows. Bare ids are not bindings.
# Inspected non-bindings at the pinned neighbour SHAs, left out of the pattern:
# IP 4ff4b5fcc1480348f058c632573143e62d4e3a41 data/sql/world/base/pvp_vendors.sql:927
# and :1228 are vendor item 42348, tuples (33931, 42348, 2695) and (33924, 42348, 2695).
# Playerbots 037c01418b5d01506917a3db9b44fd56ac5f965c
# data/sql/playerbots/base/playerbots_travelnode_path.sql:402917 and :1153799 are
# path coordinates 3.42339 and 1.42339.
# data/sql/characters/base/0000_playerbots_names.sql:42349 and :42358 are name rows
# (42339,'Karaei',6) and (42348,'Karis',6).
_NEIGHBOUR_BINDING = re.compile(
    r"spell_hallows_end_|npc_soh_fire_trigger|npc_hallows_end_|hallows_end"
    r"|\(\s*(?:42339|42348|42349|42074|42079|42132)\s*,\s*'(?:spell_|npc_)"
)


class PinnedNeighbours(unittest.TestCase):
    def test_individual_progression_does_not_bind_this_fire(self):
        root = os.environ.get("F10_IP")
        if not root:
            self.skipTest("F10_IP is not set")
        self.assertEqual(_search(Path(root), _NEIGHBOUR_BINDING), [])

    def test_playerbots_does_not_bind_this_fire(self):
        root = os.environ.get("F10_PLAYERBOTS")
        if not root:
            self.skipTest("F10_PLAYERBOTS is not set")
        self.assertEqual(_search(Path(root), _NEIGHBOUR_BINDING), [])


def _search(root: Path, pattern: re.Pattern):
    hits = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        if pattern.search(text):
            hits.append(str(path.relative_to(root)))
    return hits


if __name__ == "__main__":
    unittest.main()
