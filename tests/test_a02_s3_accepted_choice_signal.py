"""Negative tests for the A02 S3 two-phase autocast candidate.

The model is scripts/a02_s3_accepted_choice_signal.py. Citation checks
refetch the pinned cores and Individual Progression. A pass is not an
in-game summon, relog, rank change, or worldserver link.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from a02_s3_accepted_choice_signal import (  # noqa: E402
    CORE_CITATIONS,
    CORE_NEW,
    CORE_OLD,
    HOOKS,
    IP_SHA,
    SERVER_SCRIPT_HOOKS,
    Attempt,
    Book,
    Packet,
    SpellView,
    apply_accepted_toggle,
    autocast_handler_body,
    delta_records,
    equality_records,
    explicit_off_collision,
    extract_virtual_hooks,
    handler_calls_script,
    header_matches_manifest,
    learn_default,
    explicit_on,
    replace_rank,
    run_world_tick,
    two_phase_is_sound,
    two_phase_verdict,
    unguarded_equality_records,
    verify_citations,
)
from a02_s3_hook_manifest import HOOKS as MANIFEST_HOOKS  # noqa: E402

HEADER = (ROOT / "src/Systems/HunterPetAutocastRestore.h").read_text(encoding="utf-8")
SOURCE = (ROOT / "src/Systems/HunterPetAutocastRestore.cpp").read_text(encoding="utf-8")
RESEARCH = (ROOT / "docs/research/a02-s3-accepted-choice-signal.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/a02-s3-accepted-choice-signal.yml").read_text(encoding="utf-8")


def book_off(spell_id: int = 17255, guid: int = 100) -> Book:
    return Book(guid, 7, {spell_id: learn_default()})


class CandidateCollisionTests(unittest.TestCase):
    def test_verdict_is_unsound_because_off_inputs_match(self):
        self.assertEqual(two_phase_verdict(), "unsound")
        self.assertFalse(two_phase_is_sound())
        accepted, rejected = explicit_off_collision()
        self.assertEqual(accepted.attempts[0].handler, "accepted_noop")
        self.assertEqual(rejected.attempts[0].handler, "rejected_not_autocastable")
        self.assertEqual(accepted.session_book.spells[17255], learn_default())
        self.assertEqual(rejected.session_book.spells[17255], learn_default())
        self.assertEqual(len(accepted.session_confirmed), 1)
        self.assertEqual(len(rejected.session_confirmed), 1)
        self.assertEqual(accepted.player_confirmed, accepted.session_confirmed)
        self.assertEqual(rejected.player_confirmed, rejected.session_confirmed)

    def test_delta_records_neither_side_of_the_off_collision(self):
        before = learn_default()
        after, how = apply_accepted_toggle(before, False)
        self.assertEqual(how, "accepted_noop")
        self.assertEqual(after, before)
        attempt = Attempt(100, 17255, False, how)
        book = Book(100, 7, {17255: after})
        self.assertFalse(delta_records(attempt, before, book))
        rejected = Attempt(100, 17255, False, "rejected_not_autocastable")
        self.assertFalse(delta_records(rejected, before, book))
        self.assertTrue(equality_records(attempt, book))
        self.assertTrue(equality_records(rejected, book))

    def test_later_hook_reject_matches_accepted_noop_off(self):
        base = book_off()
        accepted = run_world_tick(base, [Packet(100, 17255, False, "before_sessions")])
        blocked = run_world_tick(base, [Packet(100, 17255, False, "before_sessions", reject="later_hook")])
        self.assertEqual(blocked.attempts[0].handler, "rejected_later_hook")
        self.assertEqual(accepted.session_book.spells[17255], blocked.session_book.spells[17255])
        self.assertEqual(len(blocked.session_confirmed), 1)

    def test_on_from_off_is_visible_and_does_not_make_off_sound(self):
        base = book_off()
        turned_on = run_world_tick(base, [Packet(100, 17255, True, "before_sessions")])
        rejected_on = run_world_tick(base, [Packet(100, 17255, True, "before_sessions", reject="not_owner")])
        self.assertEqual(turned_on.attempts[0].handler, "accepted_changed")
        self.assertEqual(turned_on.session_book.spells[17255], explicit_on())
        self.assertEqual(len(turned_on.session_confirmed), 1)
        self.assertEqual(rejected_on.session_confirmed, ())
        self.assertEqual(rejected_on.session_book.spells[17255], learn_default())
        self.assertFalse(two_phase_is_sound())

    def test_already_on_noop_collides_with_a_rejected_on(self):
        base = Book(100, 7, {17255: explicit_on()})
        accepted = run_world_tick(base, [Packet(100, 17255, True, "before_sessions")])
        rejected = run_world_tick(base, [Packet(100, 17255, True, "before_sessions", reject="not_owner")])
        self.assertEqual(accepted.attempts[0].handler, "accepted_noop")
        self.assertEqual(len(accepted.session_confirmed), 1)
        self.assertEqual(len(rejected.session_confirmed), 1)
        self.assertEqual(accepted.session_book.spells[17255], rejected.session_book.spells[17255])

    def test_no_packet_does_not_confirm(self):
        result = run_world_tick(book_off(), [])
        self.assertEqual(result.attempts, ())
        self.assertEqual(result.session_confirmed, ())
        self.assertEqual(result.player_confirmed, ())

    def test_set_action_makes_a_rejected_on_look_accepted(self):
        result = run_world_tick(
            book_off(),
            [Packet(100, 17255, True, "before_sessions", reject="not_owner")],
            extra_set_action=("after_world_packets", 17255, True),
        )
        self.assertEqual(result.attempts[0].handler, "rejected_not_owner")
        self.assertEqual(result.session_book.spells[17255], explicit_on())
        self.assertEqual(len(result.session_confirmed), 1)
        self.assertEqual(result.session_confirmed[0].handler, "rejected_not_owner")

    def test_multiple_packets_collapse_to_the_final_state(self):
        result = run_world_tick(
            book_off(),
            [
                Packet(100, 17255, True, "before_sessions"),
                Packet(100, 17255, False, "before_sessions"),
            ],
        )
        self.assertEqual(result.attempts[0].handler, "accepted_changed")
        self.assertEqual(result.attempts[1].handler, "accepted_changed")
        self.assertEqual(result.session_book.spells[17255], learn_default())
        self.assertEqual([attempt.requested_on for attempt in result.session_confirmed], [False])

    def test_ip_learn_after_observation_confirms_a_rejected_new_rank(self):
        base = Book(100, 7, {17253: explicit_on()})
        packet = Packet(100, 17255, False, "before_sessions", reject="missing")
        result = run_world_tick(base, [packet], ip_swap=(17253, 17255))
        self.assertEqual(result.attempts[0].handler, "rejected_missing")
        self.assertEqual(result.session_confirmed, ())
        self.assertEqual(result.player_confirmed, ())
        self.assertEqual(len(result.next_session_confirmed), 1)
        self.assertEqual(result.next_session_confirmed[0].handler, "rejected_missing")
        self.assertEqual(result.after_pet.spells[17255], learn_default())
        self.assertNotIn(17253, result.after_pet.spells)

    def test_real_off_confirmation_does_not_follow_the_replacement_rank(self):
        base = Book(100, 7, {17253: explicit_on()})
        result = run_world_tick(base, [Packet(100, 17253, False, "before_sessions")], ip_swap=(17253, 17255))
        self.assertEqual(result.session_confirmed[0].handler, "accepted_changed")
        self.assertEqual(result.next_session_confirmed, ())
        self.assertEqual(result.after_pet.spells[17255], learn_default())

    def test_non_full_map_step_delays_ip_until_a_later_observation(self):
        base = Book(100, 7, {17253: explicit_on()})
        packet = Packet(100, 17255, False, "before_sessions", reject="missing")
        early = run_world_tick(base, [packet], full_map_step=False, ip_swap=(17253, 17255))
        self.assertIn(17253, early.after_pet.spells)
        self.assertNotIn(17255, early.after_pet.spells)
        self.assertEqual(early.next_session_confirmed, ())
        later = replace_rank(early.after_pet, 17253, 17255)
        confirmed = [attempt for attempt in early.attempts if equality_records(attempt, later)]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0].handler, "rejected_missing")

    def test_map_thread_packet_misses_the_same_tick_session_hook(self):
        base = Book(100, 7, {17253: explicit_on()})
        result = run_world_tick(base, [Packet(100, 17253, False, "during_map")])
        self.assertEqual(result.session_confirmed, ())
        self.assertEqual(result.player_confirmed[0].handler, "accepted_changed")
        self.assertEqual(result.player_book.spells[17253].active, 0x81)

    def test_guid_check_blocks_a_swap_and_an_unguarded_store_does_not(self):
        base = book_off()
        result = run_world_tick(
            base,
            [Packet(100, 17255, False, "before_sessions")],
            swap_at=("before_map", 200),
        )
        self.assertEqual(len(result.session_confirmed), 1)
        self.assertEqual(result.player_book.guid, 200)
        self.assertEqual(result.player_confirmed, ())
        self.assertEqual(len(tuple(unguarded_equality_records(attempt, result.player_book) for attempt in result.attempts if unguarded_equality_records(attempt, result.player_book))), 1)

    def test_dismiss_and_relog_drop_a_guid_scoped_attempt(self):
        dismissed = run_world_tick(book_off(), [Packet(100, 17255, False, "before_sessions")], dismiss_at="before_map")
        self.assertIsNone(dismissed.player_book)
        self.assertEqual(dismissed.player_confirmed, ())
        relog = run_world_tick(book_off(), [Packet(100, 17255, False, "before_sessions")], swap_at=("before_world_session", 300))
        self.assertEqual(relog.attempts[0].handler, "rejected_missing")
        self.assertEqual(relog.session_confirmed, ())

    def test_guid_check_does_not_repair_the_off_collision(self):
        accepted, rejected = explicit_off_collision()
        self.assertEqual(accepted.session_confirmed[0].pet_guid, rejected.session_confirmed[0].pet_guid)
        self.assertFalse(two_phase_is_sound())


class ContractNegativeTests(unittest.TestCase):
    def test_manifest_is_the_imported_hook_list(self):
        self.assertEqual(HOOKS, MANIFEST_HOOKS)
        self.assertGreater(len(HOOKS), 400)
        self.assertEqual(hooks_named("ServerScript.h"), list(SERVER_SCRIPT_HOOKS))

    def test_added_virtual_fails_closed(self):
        sample = "class ServerScript {\n virtual bool CanPacketReceive(WorldSession*, WorldPacket const&) { return true; }\n};\n"
        self.assertEqual(extract_virtual_hooks(sample), [(2, "CanPacketReceive")])
        mutated = sample.replace(
            "};",
            " virtual void OnPacketReceived(WorldSession*, WorldPacket const&) {}\n};\n",
        )
        mutated_hooks = extract_virtual_hooks(mutated)
        self.assertIn("OnPacketReceived", [name for _line, name in mutated_hooks])
        failures = header_matches_manifest("ServerScript.h", sample)
        self.assertTrue(failures)
        self.assertTrue(header_matches_manifest("ServerScript.h", mutated))

    def test_script_call_inside_the_handler_fails_closed(self):
        clean = "void WorldSession::HandlePetSpellAutocastOpcode() {\n}\nvoid WorldSession::HandlePetCastSpellOpcode"
        self.assertFalse(handler_calls_script(autocast_handler_body(clean)))
        dirty = clean.replace("{", "{ sScriptMgr->OnPetSpellAutocastAccepted(); ", 1)
        self.assertTrue(handler_calls_script(autocast_handler_body(dirty)))

    def test_choice_source_stays_false_and_no_prototype_is_subscribed(self):
        start = HEADER.index("inline constexpr bool AtomicModuleOnlyChoiceSourceExists()")
        end = HEADER.index("inline constexpr bool RuntimeObservesIpReconciledFlag()")
        body = HEADER[start:end]
        self.assertIn("return false;", body)
        self.assertNotIn("return true;", body)
        self.assertIn("BLOCKED: NO ATOMIC MODULE-ONLY CHOICE SOURCE", HEADER)
        self.assertNotIn("CanPacketReceive", SOURCE)
        self.assertNotIn("OnSessionUpdate", SOURCE)
        self.assertNotIn("OnPlayerUpdate", SOURCE)
        self.assertNotIn("OnPetSpellAutocastAccepted", SOURCE)
        self.assertNotIn("CMSG_PET_SPELL_AUTOCAST", SOURCE)

    def test_workflow_is_read_only_and_does_not_upload(self):
        self.assertIn("contents: read", WORKFLOW)
        self.assertNotIn("contents: write", WORKFLOW)
        self.assertNotIn("upload-artifact", WORKFLOW)
        self.assertNotIn("actions/upload", WORKFLOW)
        self.assertNotIn("worldserver", WORKFLOW.lower())
        self.assertIn(CORE_OLD, RESEARCH)
        self.assertIn(CORE_NEW, RESEARCH)
        self.assertIn(IP_SHA, RESEARCH)

    def test_research_records_the_unsound_verdict_and_the_optional_hook(self):
        for needle in (
            "unsound",
            "VERIFIED",
            "POTENTIAL ISSUE",
            "UNKNOWN",
            "NOT TESTED",
            "not an owner decision",
            "OnPetSpellAutocastAccepted",
            "AtomicModuleOnlyChoiceSourceExists",
            "CanPacketReceive",
            "OnSessionUpdate",
            "OnPlayerUpdate",
            "CMSG_PET_SET_ACTION",
            "PendingPetSpellCheck",
            "No post-handler",
            "learn-default",
        ):
            self.assertIn(needle, RESEARCH, needle)
        for filename, line, name in HOOKS:
            self.assertIn(f"{filename}:{line} {name}", RESEARCH)

    def test_pinned_source_contract(self):
        failures = verify_citations()
        self.assertEqual(failures, [], "\n".join(failures[:20]))


def hooks_named(header_name: str) -> list[tuple[int, str]]:
    return [(line, name) for filename, line, name in HOOKS if filename == header_name]


if __name__ == "__main__":
    unittest.main()
