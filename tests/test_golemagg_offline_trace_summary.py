"""Disposable-fixture tests for offline read-only Golemagg trace summaries."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/summarize_golemagg_action_audit.py"
spec = importlib.util.spec_from_file_location("golemagg_summary", SOURCE)
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


def line(bot="Grau", sequence=1, stacks=19, distance=9.0, lookup="true",
         hp="75.0", action="mc golemagg back off", current=True):
    extra = (
        f"retreat_stacks_20={'true' if stacks >= 20 else 'false'} "
        f"inside_retreat_12yd={'true' if lookup == 'true' and distance >= 0 and distance < 12 else 'false'} "
    ) if current else ""
    return (
        f"[2026-10-19] module: GolemaggActionAudit READ ONLY: bot={bot} "
        f"samples={sequence}/24 splash_stacks={stacks} splash_remaining_ms=14000 "
        f"{extra}boss_lookup_present={lookup} boss_hp_pct={hp} "
        f"boss_distance_yards={distance} current_target=Golemagg "
        f"recent_actions={action}"
    )


class GolemaggOfflineSummaryTests(unittest.TestCase):
    def test_repeated_action_tail_still_records_threshold_transitions(self):
        counts, bots = tool.summarize([
            line(sequence=1, stacks=19, distance=9),
            line(sequence=2, stacks=20, distance=13),
            line(sequence=3, stacks=21, distance=13),
            line(sequence=4, stacks=19, distance=11),
        ])
        self.assertEqual(bots, 1)
        self.assertEqual(counts["parsed_samples"], 4)
        self.assertEqual(counts["sampled_stack_bucket_changes"], 2)
        self.assertEqual(counts["sampled_distance_bucket_changes"], 2)
        self.assertEqual(counts["recent_back_off_mentions"], 4)

    def test_lookup_loss_does_not_imply_distance_boundary(self):
        counts, _ = tool.summarize([
            line(sequence=1, stacks=20, distance=11),
            line(sequence=2, stacks=20, distance=-1, lookup="false", hp="-1"),
            line(sequence=3, stacks=20, distance=13),
        ])
        self.assertEqual(counts["lookup_missing"], 1)
        self.assertNotIn("sampled_distance_bucket_changes", counts)

    def test_retreat_window_does_not_conflate_recent_backoff_tail(self):
        counts, bots = tool.summarize([
            line(sequence=1, stacks=19, distance=11, hp="75.0"),
            line(sequence=2, stacks=20, distance=11, hp="75.0"),
            line(sequence=3, stacks=20, distance=11, hp="9.0"),
            line(sequence=4, stacks=20, distance=13, hp="75.0"),
            line(sequence=5, stacks=20, distance=-1, lookup="false", hp="-1"),
        ])
        self.assertEqual(bots, 1)
        self.assertEqual(counts["recent_back_off_mentions"], 5)
        self.assertEqual(counts["sampled_retreat_condition_met"], 1)
        self.assertEqual(counts["back_off_mentions_with_condition"], 1)
        self.assertEqual(counts["back_off_mentions_without_confirmed_condition"], 4)

    def test_empty_action_history_sentinel_is_unknown_not_an_action(self):
        # Draft observer PR #40 can emit a meaningful threshold sample
        # while Playerbots' recent action history is temporarily empty.
        counts, bots = tool.summarize([
            line(sequence=1, action="(no recent action)", stacks=19, distance=11),
            line(sequence=2, action="(no recent action)", stacks=20, distance=11),
            line(sequence=3, action="(no recent action)", stacks=20, distance=13),
            line(sequence=4, action="mc golemagg back off", stacks=20, distance=11),
        ])
        self.assertEqual(bots, 1)
        self.assertEqual(counts["parsed_samples"], 4)
        self.assertEqual(counts["unavailable_recent_action_history_samples"], 3)
        self.assertEqual(counts["sampled_stack_bucket_changes"], 1)
        self.assertEqual(counts["sampled_distance_bucket_changes"], 2)
        self.assertEqual(counts["sampled_retreat_condition_met"], 2)
        self.assertEqual(counts["recent_back_off_mentions"], 1)
        self.assertEqual(counts["back_off_mentions_with_condition"], 1)

    def test_old_action_tail_not_relabelled_as_unknown(self):
        counts, bots = tool.summarize([line(sequence=1)])
        self.assertEqual(bots, 1)
        self.assertNotIn("unavailable_recent_action_history_samples", counts)

    def test_nonfinite_and_contradictory_samples_are_rejected(self):
        bad_stacks = line(sequence=2, stacks=19).replace(
            "retreat_stacks_20=false", "retreat_stacks_20=true")
        bad_distance = line(sequence=3, stacks=21, distance=13).replace(
            "inside_retreat_12yd=false", "inside_retreat_12yd=true")
        counts, bots = tool.summarize([
            line(sequence=1, hp="nan"),
            line(sequence=1, distance=float("inf")),
            bad_stacks, bad_distance, line(sequence=1),
        ])
        self.assertEqual(bots, 1)
        self.assertEqual(counts["candidate_lines"], 5)
        self.assertEqual(counts["unparsed_lines"], 4)
        self.assertEqual(counts["parsed_samples"], 1)

    def test_partial_or_duplicate_snapshot_fields_are_not_trusted(self):
        # A new-format audit should carry both threshold flags together.
        valid = line(sequence=1, stacks=20, distance=11)
        missing_distance_flag = valid.replace("inside_retreat_12yd=true ", "")
        missing_stack_flag = valid.replace("retreat_stacks_20=true ", "")
        doubled_stack = valid.replace(
            "splash_stacks=20 ", "splash_stacks=19 splash_stacks=20 "
        )
        doubled_threshold = valid.replace(
            "retreat_stacks_20=true ",
            "retreat_stacks_20=false retreat_stacks_20=true "
        )
        counts, bots = tool.summarize([
            missing_distance_flag, missing_stack_flag,
            doubled_stack, doubled_threshold, valid,
        ])
        self.assertEqual(bots, 1)
        self.assertEqual(counts["candidate_lines"], 5)
        self.assertEqual(counts["unparsed_lines"], 4)
        self.assertEqual(counts["parsed_samples"], 1)
        self.assertNotIn("legacy_without_explicit_thresholds", counts)

    def test_old_format_is_explicitly_marked_as_inferred(self):
        counts, _ = tool.summarize([
            line(sequence=1, current=False, stacks=19, distance=10),
            line(sequence=2, current=False, stacks=20, distance=13),
        ])
        self.assertEqual(counts["legacy_without_explicit_thresholds"], 2)
        self.assertEqual(counts["sampled_stack_bucket_changes"], 1)
        self.assertEqual(counts["sampled_distance_bucket_changes"], 1)

    def test_bot_separation_and_new_combat_sequence_reset(self):
        counts, bots = tool.summarize([
            line(bot="Grau", sequence=1, stacks=19),
            line(bot="OtherBot", sequence=1, stacks=21),
            line(bot="Grau", sequence=2, stacks=20),
            line(bot="Grau", sequence=1, stacks=19),
        ])
        self.assertEqual(bots, 2)
        self.assertEqual(counts["sampled_stack_bucket_changes"], 1)
        self.assertEqual(counts["sample_counter_reset_or_replay"], 1)

    def test_invalid_incomplete_observer_lines_fail_closed(self):
        counts, bots = tool.summarize([
            "Module: unrelated text",
            "GolemaggActionAudit READ ONLY: bot=Grau samples=1/24",
            line(sequence=1),
        ])
        self.assertEqual(bots, 1)
        self.assertEqual(counts["candidate_lines"], 2)
        self.assertEqual(counts["unparsed_lines"], 1)
        self.assertEqual(counts["parsed_samples"], 1)

    def test_cli_does_not_print_bot_name_or_raw_action_text(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "test.log"
            fixture.write_text(line(bot="SecretBotName", action="private action text") + "\n")
            capture = io.StringIO()
            old_argv = sys.argv
            try:
                sys.argv = ["read-only", str(fixture)]
                with redirect_stdout(capture):
                    code = tool.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(code, 0)
            self.assertNotIn("SecretBotName", capture.getvalue())
            self.assertNotIn("private action text", capture.getvalue())
            self.assertEqual(fixture.read_text().count("SecretBotName"), 1)

    def test_missing_file_is_not_fabricated_as_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = io.StringIO()
            old_argv = sys.argv
            try:
                sys.argv = ["read-only", str(Path(directory) / "absent.log")]
                with redirect_stdout(capture):
                    code = tool.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(code, 2)
            self.assertIn("No server action taken", capture.getvalue())


if __name__ == "__main__":
    unittest.main()
