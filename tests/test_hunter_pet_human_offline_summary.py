"""Disposable Hunter autocast audit LOG fixtures. No owner data or live realm."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/summarize_hunter_pet_human_autocast_audit.py"
spec = importlib.util.spec_from_file_location("hunter_human_offline", PATH)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def snapshot(owner="837190", before="bar[3:25011/25011/129,] known[25011/25011/129/1,]",
             after="bar[3:25011/25011/129,] known[25011/25011/129/1,]"):
    return ("[module] HunterPetAutocast GENERIC audit: later owner=" + owner +
            " before=" + before + " after=" + after + " (not IP completion)")


def toggle(owner="837190", requested="ON", opcode="CMSG_PET_SPELL_AUTOCAST"):
    return ("[module] HunterPetAutocast AUDIT ONLY: owner=" + owner +
            " petnumber=924 spell=25011 requested=" + requested + " source=" +
            opcode + " native=matching-state-only; actor not attributable; no mutation")


class HumanOfflineAuditTests(unittest.TestCase):
    def test_no_change_is_not_restoration_proof(self):
        counts, owners = audit.summarize([snapshot()])
        self.assertEqual(owners, 1)
        self.assertEqual(counts["comparable_generic_snapshots"], 1)
        self.assertNotIn("autocast_list_membership_changes_in_snapshot", counts)
        self.assertNotIn("native_match_requested_on", counts)

    def test_rank_and_membership_changes_independent(self):
        before = "bar[3:25011/25011/129,] known[25011/25011/129/1,]"
        after = "bar[3:25012/25011/130,] known[25012/25011/130/0,]"
        counts, _ = audit.summarize([snapshot(before=before, after=after)])
        self.assertEqual(counts["rank_id_changes_in_snapshot"], 1)
        self.assertEqual(counts["native_active_flag_changes_in_snapshot"], 1)
        self.assertEqual(counts["autocast_list_membership_changes_in_snapshot"], 1)
        self.assertNotIn("native_match_requested_off", counts)

    def test_independent_ability_families(self):
        before = ("bar[] known[25011/25011/129/1,17253/17253/130/0,]")
        after = ("bar[] known[25011/25011/129/1,17253/17253/129/1,]")
        counts, owners = audit.summarize([snapshot(before=before, after=after)])
        self.assertEqual(owners, 1)
        self.assertEqual(counts["autocast_list_membership_changes_in_snapshot"], 1)
        self.assertEqual(counts["native_active_flag_changes_in_snapshot"], 1)
        self.assertNotIn("rank_id_changes_in_snapshot", counts)

    def test_removed_or_new_family_counted_not_assigned_actor(self):
        counts, _ = audit.summarize([
            snapshot(before="bar[] known[]", after="bar[] known[999/999/130/0,]")
        ])
        self.assertEqual(counts["family_added_or_removed_in_snapshot"], 1)
        self.assertNotIn("native_match_requested_off", counts)

    def test_duplicate_rank_family_and_truncation_not_comparable(self):
        first = snapshot(after="bar[] known[25011/25011/129/1,25012/25011/130/0,]")
        second = snapshot(after="bar[] known[25011/25011/129/1,truncated,]")
        counts, owners = audit.summarize([first, second])
        self.assertEqual(owners, 1)
        self.assertEqual(counts["paired_generic_snapshot_lines"], 2)
        self.assertEqual(counts["ambiguous_or_truncated_snapshots"], 2)
        self.assertNotIn("comparable_generic_snapshots", counts)

    def test_next_update_native_match_on_off_not_actor_authentication(self):
        counts, owners = audit.summarize([
            toggle(requested="ON"),
            toggle(requested="OFF", opcode="CMSG_PET_SET_ACTION"),
        ])
        self.assertEqual(owners, 1)
        self.assertEqual(counts["next_update_native_matches"], 2)
        self.assertEqual(counts["native_match_requested_on"], 1)
        self.assertEqual(counts["native_match_requested_off"], 1)
        self.assertEqual(counts["native_match_from_spell_opcode"], 1)
        self.assertEqual(counts["native_match_from_actionbar_opcode"], 1)

    def test_learning_packet_remains_unattributed(self):
        learn = ("[module] HunterPetAutocast LEARN-PACKET audit: "
                 "owner=837190 petnumber=924 learnedSpell=25011 observed; "
                 "origin may be IP or another legal learn path")
        counts, owners = audit.summarize([learn])
        self.assertEqual(owners, 1)
        self.assertEqual(counts["learn_packets_observed_unattributed"], 1)
        self.assertNotIn("native_match_requested_on", counts)

    def test_irrelevant_and_unrecognized_audit_lines_are_not_false_evidence(self):
        counts, owners = audit.summarize([
            "worldserver random output", "HunterPetAutocast unknown audit: owner=837190",
            "[module] HunterPetAutocast AUDIT ONLY: owner=837190 requested=ON",
        ])
        self.assertEqual(owners, 0)
        self.assertEqual(counts["audit_lines"], 2)
        self.assertEqual(counts["other_audit_lines"], 2)

    def test_cli_never_emits_owner_pet_or_spell_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.log"
            path.write_text(snapshot() + "\n" + toggle())
            out = io.StringIO()
            argv = sys.argv
            try:
                sys.argv = ["offline", str(path)]
                with redirect_stdout(out):
                    self.assertEqual(audit.main(), 0)
            finally:
                sys.argv = argv
            text = out.getvalue()
            self.assertNotIn("837190", text)
            self.assertNotIn("924", text)
            self.assertNotIn("25011", text)
            self.assertNotIn("CMSG_PET_", text)
            self.assertIn("NOT proof Individual Progression completed", text)
            self.assertEqual(path.read_text().count("837190"), 2)

    def test_missing_or_irrelevant_file_returns_non_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.log"
            capture = io.StringIO()
            argv = sys.argv
            try:
                sys.argv = ["offline", str(path)]
                with redirect_stdout(capture):
                    self.assertEqual(audit.main(), 2)
                path.write_text("not the target log\n")
                with redirect_stdout(capture):
                    self.assertEqual(audit.main(), 1)
            finally:
                sys.argv = argv


if __name__ == "__main__":
    unittest.main()
