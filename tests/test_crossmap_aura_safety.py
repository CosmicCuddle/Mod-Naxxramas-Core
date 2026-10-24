"""Source contract for the #114 cross-map aura safety follow-up.

Checks the wiring in BotRaidConsumables.cpp against CS01's S2 acceptance
contract (#114 comments 6382444645 and 6382474675):
- the flag defaults OFF in C++ and in the .conf.dist;
- OFF keeps every existing path unchanged;
- ON never touches an off-map bot's auras from the master's map thread,
  for BOTH tracker.Auras and tracker.TimedAuras;
- removals are drained on the world thread, outside the queue lock;
- a newer module application cancels a stale queued removal.

Source-level only. It does not prove runtime race freedom.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"
QUEUE = ROOT / "src/Systems/CrossMapAuraQueue.h"
CONF = ROOT / "conf/mod_naxxramas_core.conf.dist"
FLAG = "NaxxramasCore.BotConsumables.CrossMapAuraSafety"


def strip_comments(source):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)


def function_body(code, signature):
    start = code.index(signature)
    return code[start:code.index("\n    }\n", start)]


class FlagDefaults(unittest.TestCase):
    def test_conf_default_off(self):
        lines = CONF.read_text(encoding="utf-8").splitlines()
        self.assertIn(FLAG + " = 0", lines)
        self.assertEqual(sum(1 for line in lines if line.startswith(FLAG)), 1)

    def test_cpp_default_off(self):
        code = strip_comments(SOURCE.read_text(encoding="utf-8"))
        self.assertIn("std::atomic<bool> CrossMapAuraSafetyEnabled{ false };", code)
        self.assertRegex(code, r'"%s",\s*false\)' % re.escape(FLAG))
        self.assertEqual(code.count('"%s"' % FLAG), 1)

    def test_flag_loaded_on_config_load_not_per_tick(self):
        code = strip_comments(SOURCE.read_text(encoding="utf-8"))
        load = function_body(code, "void OnAfterConfigLoad(")
        self.assertIn(FLAG, load)
        self.assertIn("WORLDHOOK_ON_AFTER_CONFIG_LOAD", code)


class OffParity(unittest.TestCase):
    def setUp(self):
        self.code = strip_comments(SOURCE.read_text(encoding="utf-8"))

    def test_note_applied_is_noop_when_off(self):
        body = function_body(self.code, "void NoteModuleAuraApplied(")
        self.assertLess(body.index("if (!IsCrossMapAuraSafetyEnabled())"),
                        body.index("CrossMapAuraRemovals.NoteApplied("))

    def test_clear_defers_only_on_invalid_location_path(self):
        self.assertIn("bool deferOffMap = false)", self.code)
        calls = re.findall(r"ClearTrackedAuras\(([^;]*?)\);", self.code, re.S)
        deferred = [c for c in calls if "IsCrossMapAuraSafetyEnabled()" in c]
        self.assertEqual(len(deferred), 1)
        update = function_body(self.code, "void OnPlayerUpdate(")
        self.assertIn("IsCrossMapAuraSafetyEnabled());", update)
        # Command paths keep the two-argument (immediate) form.
        for call in calls:
            if call is deferred[0]:
                continue
            self.assertEqual(call.count(","), 1, call)

    def test_every_new_map_thread_gate_is_behind_the_flag(self):
        timed = function_body(self.code, "void ProcessTimedAuras(")
        self.assertIn("(IsCrossMapAuraSafetyEnabled() &&\n"
                      "                    !IsPlayerOnMap(master->GetMap(), bot))", timed)
        check = function_body(self.code, "void CheckTrackedAuras(")
        self.assertIn("IsCrossMapAuraSafetyEnabled();", check)
        self.assertIn("if (crossMapSafety &&", check)

    def test_status_command_count_is_unchanged(self):
        count = function_body(self.code, "uint32 CountMissingAuras(")
        self.assertNotIn("IsPlayerOnMap", count)
        self.assertNotIn("CrossMapAuraRemovals", count)


class MapThreadNeverTouchesOffMapBots(unittest.TestCase):
    def setUp(self):
        self.code = strip_comments(SOURCE.read_text(encoding="utf-8"))

    def test_on_map_check_is_pointer_comparison_only(self):
        body = function_body(self.code, "bool IsPlayerOnMap(")
        self.assertIn("map->GetPlayers()", body)
        self.assertIn("ref.GetSource() == candidate", body)
        self.assertNotIn("candidate->", body)

    def test_timed_refresh_checks_map_before_dereferencing(self):
        timed = function_body(self.code, "void ProcessTimedAuras(")
        self.assertLess(timed.index("IsPlayerOnMap(master->GetMap(), bot)"),
                        timed.index("!bot->IsInWorld()"))

    def test_check_skips_before_resolving_target(self):
        check = function_body(self.code, "void CheckTrackedAuras(")
        self.assertLess(check.index("IsPlayerOnMap("),
                        check.index("ResolveTrackedAuraTarget("))
        gate = check[check.index("if (crossMapSafety &&"):check.index("ResolveTrackedAuraTarget(")]
        self.assertNotIn("MissingNotified", gate)

    def test_clear_queues_both_vectors_before_any_dereference(self):
        clear = function_body(self.code, "void ClearTrackedAuras(")
        auras_loop = clear[clear.index("tracker.Auras"):clear.index("tracker.TimedAuras")]
        timed_loop = clear[clear.index("tracker.TimedAuras"):]

        self.assertIn("if (deferOffMap)", auras_loop)
        self.assertIn("tracked.IsPetAura", auras_loop)
        self.assertLess(auras_loop.index("CrossMapAuraRemovals.Enqueue("),
                        auras_loop.index("ResolveTrackedAuraTarget("))

        self.assertIn("if (deferOffMap &&", timed_loop)
        self.assertIn("timed.SpellId", timed_loop)
        self.assertLess(timed_loop.index("CrossMapAuraRemovals.Enqueue("),
                        timed_loop.index("!bot->IsInWorld()"))
        self.assertLess(timed_loop.index("CrossMapAuraRemovals.Enqueue("),
                        timed_loop.index("RemoveAurasDueToSpell("))


class WorldThreadDrain(unittest.TestCase):
    def setUp(self):
        self.code = strip_comments(SOURCE.read_text(encoding="utf-8"))

    def test_drain_only_in_world_update(self):
        self.assertEqual(self.code.count("CrossMapAuraRemovals.Drain("), 1)
        update = self.code[self.code.index("class NaxxramasCoreBotRaidConsumablesWorld"):]
        self.assertIn("WORLDHOOK_ON_UPDATE", update)
        on_update = function_body(update, "void OnUpdate(")
        self.assertIn("CrossMapAuraRemovals.Drain(", on_update)
        self.assertIn("new NaxxramasCoreBotRaidConsumablesWorld();", self.code)

    def test_drain_resolves_by_guid_not_master_manager(self):
        update = self.code[self.code.index("class NaxxramasCoreBotRaidConsumablesWorld"):]
        on_update = function_body(update, "void OnUpdate(")
        self.assertIn("ObjectAccessor::FindPlayerByLowGUID(", on_update)
        self.assertNotIn("ResolvePreparedBot", on_update)
        self.assertNotIn("GetPlayerbotMgr", on_update)
        self.assertIn("if (key.IsPet)", on_update)
        self.assertIn("RemoveAurasDueToSpell(", on_update)

    def test_pet_removal_requires_the_same_pet(self):
        # CS01 #116 review 5637833818: never strip a different pet.
        self.assertIn("uint64 TargetGuidRaw = 0;", self.code)
        add = function_body(self.code, "void AddTrackedAura(")
        self.assertEqual(add.count("TargetGuidRaw = targetGuid.GetRawValue();"), 2)
        apply = function_body(self.code, "bool ApplyTrackedAura(")
        self.assertEqual(apply.count("target->GetGUID(),"), 2)
        clear = function_body(self.code, "void ClearTrackedAuras(")
        self.assertIn("tracked.TargetGuidRaw);", clear)
        update = self.code[self.code.index("class NaxxramasCoreBotRaidConsumablesWorld"):]
        on_update = function_body(update, "void OnUpdate(")
        self.assertIn("Pet* pet = bot->GetPet();", on_update)
        self.assertIn("pet->GetGUID().GetRawValue() != targetGuidRaw", on_update)
        self.assertLess(on_update.index("!= targetGuidRaw"),
                        on_update.index("RemoveAurasDueToSpell("))

    def test_drain_is_not_gated_by_the_flag(self):
        update = self.code[self.code.index("class NaxxramasCoreBotRaidConsumablesWorld"):]
        on_update = function_body(update, "void OnUpdate(")
        self.assertNotIn("IsCrossMapAuraSafetyEnabled", on_update)


class StaleWorkGeneration(unittest.TestCase):
    def setUp(self):
        self.code = strip_comments(SOURCE.read_text(encoding="utf-8"))

    def test_generation_is_bumped_before_every_module_application(self):
        # Before the aura is touched, so a concurrent removal of the same
        # key either sees the new generation or finishes first (#116 review).
        apply = function_body(self.code, "bool ApplyTrackedAura(")
        self.assertLess(apply.index("NoteModuleAuraApplied("), apply.index("GetAura(spellId)"))
        self.assertLess(apply.index("NoteModuleAuraApplied("), apply.index("RemoveAurasDueToSpell("))
        self.assertLess(apply.index("NoteModuleAuraApplied("), apply.index("AddAura("))
        self.assertLess(apply.index("NoteModuleAuraApplied("), apply.index("AddTrackedAura("))
        juju = function_body(self.code, "void ApplyTimedJujuFlurry(")
        self.assertLess(juju.index("NoteModuleAuraApplied("), juju.index("RemoveAurasDueToSpell("))
        self.assertLess(juju.index("NoteModuleAuraApplied("), juju.index("AddAura("))
        timed = function_body(self.code, "void ProcessTimedAuras(")
        self.assertLess(timed.index("NoteModuleAuraApplied("), timed.index("bot->AddAura("))
        gfpp = function_body(self.code, "void ProcessOneShotFireProtections(")
        self.assertLess(gfpp.index("NoteModuleAuraApplied("), gfpp.index("bot->AddAura("))

    def test_queue_lock_discipline(self):
        header = QUEUE.read_text(encoding="utf-8")
        drain = header[header.index("std::size_t Drain("):header.index("private:")]
        swap_block = drain[drain.index("{\n                std::lock_guard"):drain.index("work.swap(_pending);")]
        self.assertIn("std::lock_guard<std::mutex> lock(_lock);", swap_block)
        loop = drain[drain.index("for (PendingRemoval const& pending : work)"):]
        self.assertNotIn("lock_guard", loop)
        self.assertLess(loop.index("BeginRemovalIfCurrent(pending)"),
                        loop.index("remove(pending.Key, pending.TargetToken)"))
        self.assertLess(loop.index("EndRemovalGuard"), loop.index("remove(pending.Key, pending.TargetToken)"))
        for method in ("void Enqueue(", "bool BeginRemovalIfCurrent(", "void EndRemoval("):
            body = header[header.index(method):]
            body = body[:body.index("\n        }\n")]
            self.assertIn("std::lock_guard<std::mutex> lock(_lock);", body, method)

    def test_check_and_mark_are_atomic_and_notes_wait(self):
        header = QUEUE.read_text(encoding="utf-8")
        begin = header[header.index("bool BeginRemovalIfCurrent("):]
        begin = begin[:begin.index("\n        }\n")]
        self.assertLess(begin.index("CurrentLocked(pending.Key) != pending.Generation"),
                        begin.index("_removing = pending.Key;"))
        note = header[header.index("void NoteApplied("):]
        note = note[:note.index("\n        }\n")]
        self.assertIn("std::unique_lock<std::mutex> lock(_lock);", note)
        self.assertIn("_removalDone.wait(lock", note)
        self.assertIn("!(*_removing == key)", note)
        self.assertLess(note.index("_removalDone.wait("), note.index("_generation[key] = ++_lastStamp;"))
        end = header[header.index("void EndRemoval("):]
        self.assertIn("_removing.reset();", end)
        self.assertIn("_removalDone.notify_all();", end)

    def test_generation_map_is_bounded_without_aba(self):
        # CS01 #118 6383075641: retire stamps after each drain, but only
        # those no queued removal refers to; stamps are never reused.
        header = QUEUE.read_text(encoding="utf-8")
        self.assertIn("_generation[key] = ++_lastStamp;", header)
        self.assertNotIn("++_generation[key]", header)
        drain = header[header.index("std::size_t Drain("):header.index("private:")]
        self.assertLess(drain.index("for (PendingRemoval const& pending : work)"),
                        drain.index("RetireUnreferenced();"))
        retire = header[header.index("void RetireUnreferenced("):]
        retire = retire[:retire.index("\n        }\n")]
        self.assertIn("std::lock_guard<std::mutex> lock(_lock);", retire)
        self.assertIn("for (PendingRemoval const& pending : _pending)", retire)

    def test_no_raw_pointers_in_queue(self):
        header = strip_comments(QUEUE.read_text(encoding="utf-8"))
        self.assertNotIn("Player", header)
        self.assertNotIn("Unit", header)
        # No pointer-typed declarations (members, locals or parameters).
        self.assertIsNone(re.search(r"\b\w+\s*\*\s*(const\s+)?\w+\s*[;=,)]", header))


if __name__ == "__main__":
    unittest.main()
