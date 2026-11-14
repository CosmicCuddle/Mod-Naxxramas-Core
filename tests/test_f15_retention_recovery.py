import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ret = load("retention_for_recovery", "scripts/f15_owned_retention_30d.py")
raw = load("raw_for_recovery", "scripts/f15_raw_evidence_bundle.py")
recovery = load("recovery", "scripts/f15_retention_recovery.py")

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def private_file(path: Path, data=b"x"):
    path.write_bytes(data)
    path.chmod(0o600)
    return path


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.archive = self.base / "Archived Logs"
        self.crash = self.base / "Crash Logs"
        self.rawroot = self.crash / "Raw Evidence"
        self.archive.mkdir(mode=0o700)
        self.crash.mkdir(mode=0o700)
        self.rawroot.mkdir(mode=0o700)

    def write_intent(self, root: Path, obj):
        p = root / "retention-intent.json"
        p.write_text(json.dumps(obj, sort_keys=True) + "\n")
        p.chmod(0o600)
        return p

    def snapshot_intent(self):
        data = private_file(self.archive / "old.log", b"old")
        manifest = private_file(self.archive / "old.json", b'{"kind":"fixture"}\n')
        obj = {
            "version": 2,
            "kind": "f15_retention_30d_snapshot",
            "snapshot": data.name,
            "manifest": manifest.name,
            "created_utc": NOW.isoformat(),
            "snapshot_identity": ret._identity(data),
            "manifest_identity": ret._identity(manifest),
        }
        self.write_intent(self.archive, obj)
        return data, manifest, obj

    def crash_intent(self):
        report = private_file(
            self.crash / "20261001T120000Z-Worldserver-worldserver-00000001.txt",
            b"report",
        )
        obj = {
            "version": 2,
            "kind": "f15_retention_30d_crash_report",
            "report": report.name,
            "observed_stamp": "20261001T120000Z",
            "report_identity": ret._identity(report),
        }
        self.write_intent(self.crash, obj)
        return report, obj

    def raw_intent(self):
        bundle = raw.write_bundle(
            self.rawroot,
            "worldserver-00000001",
            {"a.txt": "a", "b.txt": "b"},
            NOW,
            {"source": "fixture"},
        )
        manifest, files = raw._verify_bundle(bundle)
        targets = [
            {"name": p.name, "identity": raw._file_identity(p)}
            for p in files + [bundle / "manifest.json"]
        ]
        obj = {
            "version": 2,
            "kind": "f15_retention_30d_raw_evidence",
            "bundle": bundle.name,
            "bundle_identity": raw._bundle_identity(bundle),
            "incident_id": manifest["incident_id"],
            "created_utc": manifest["created_utc"],
            "targets": sorted(targets, key=lambda x: x["name"]),
        }
        self.write_intent(self.rawroot, obj)
        return bundle, obj

    def test_absent_roots_are_reported_without_creation(self):
        archive = self.base / "missing-archive"
        crash = self.base / "missing-crash"
        result = recovery.classify_all(archive, crash)
        self.assertEqual(result["snapshot_archive"]["classification"], "ROOT_ABSENT")
        self.assertEqual(result["crash_reports"]["classification"], "ROOT_ABSENT")
        self.assertEqual(result["raw_evidence"]["classification"], "ROOT_ABSENT")
        self.assertFalse(archive.exists())
        self.assertFalse(crash.exists())
        self.assertFalse(result["mutations_performed"])

    def test_snapshot_v2_intact_then_partial_then_absent(self):
        data, manifest, _obj = self.snapshot_intent()
        result = recovery.classify_snapshot_root(self.archive)
        self.assertEqual(result["classification"], "PRE_DELETE_TARGETS_INTACT")

        data.unlink()
        result = recovery.classify_snapshot_root(self.archive)
        self.assertEqual(result["classification"], "PARTIAL_DELETE")
        self.assertEqual(result["targets"]["snapshot"]["state"], "MISSING")
        self.assertEqual(result["targets"]["manifest"]["state"], "MATCH")

        manifest.unlink()
        result = recovery.classify_snapshot_root(self.archive)
        self.assertEqual(result["classification"], "TARGETS_ALREADY_ABSENT")

    def test_snapshot_replacement_is_not_treated_as_progress(self):
        data, _manifest, _obj = self.snapshot_intent()
        data.unlink()
        private_file(data, b"replacement")
        result = recovery.classify_snapshot_root(self.archive)
        self.assertEqual(result["classification"], "IDENTITY_MISMATCH_OR_FOREIGN")
        self.assertEqual(result["targets"]["snapshot"]["state"], "UNSAFE_OR_REPLACED")

    def test_legacy_snapshot_intent_is_identity_unproven(self):
        self.write_intent(self.archive, {
            "kind": "f15_retention_30d_snapshot",
            "snapshot": "old.log",
            "manifest": "old.json",
            "created_utc": NOW.isoformat(),
        })
        result = recovery.classify_snapshot_root(self.archive)
        self.assertEqual(result["classification"], "LEGACY_IDENTITY_UNPROVEN")

    def test_foreign_and_malformed_intents_are_not_repaired(self):
        self.write_intent(self.archive, {"version": 2, "kind": "someone_else"})
        self.assertEqual(
            recovery.classify_snapshot_root(self.archive)["classification"],
            "FOREIGN_OR_UNKNOWN_INTENT",
        )
        (self.archive / "retention-intent.json").write_text("{bad json")
        (self.archive / "retention-intent.json").chmod(0o600)
        self.assertEqual(
            recovery.classify_snapshot_root(self.archive)["classification"],
            "MALFORMED_INTENT",
        )

    def test_intent_symlink_is_reported_unsafe_and_target_untouched(self):
        target = self.base / "foreign-intent"
        target.write_text("{}")
        (self.archive / "retention-intent.json").symlink_to(target)
        result = recovery.classify_snapshot_root(self.archive)
        self.assertEqual(result["classification"], "UNSAFE_INTENT")
        self.assertEqual(target.read_text(), "{}")

    def test_crash_report_intact_then_absent(self):
        report, _obj = self.crash_intent()
        result = recovery.classify_crash_root(self.crash)
        self.assertEqual(result["classification"], "PRE_DELETE_TARGET_INTACT")
        report.unlink()
        result = recovery.classify_crash_root(self.crash)
        self.assertEqual(result["classification"], "REPORT_ALREADY_ABSENT_AFTER_INTENT")

    def test_crash_report_replacement_detected(self):
        report, _obj = self.crash_intent()
        report.unlink()
        private_file(report, b"replacement")
        result = recovery.classify_crash_root(self.crash)
        self.assertEqual(result["classification"], "IDENTITY_MISMATCH_OR_FOREIGN")

    def test_raw_v2_intact_partial_and_bundle_absent(self):
        bundle, _obj = self.raw_intent()
        result = recovery.classify_raw_root(self.rawroot)
        self.assertEqual(result["classification"], "PRE_DELETE_TARGETS_INTACT")

        (bundle / "a.txt").unlink()
        result = recovery.classify_raw_root(self.rawroot)
        self.assertEqual(result["classification"], "PARTIAL_DELETE")
        self.assertEqual(result["targets"]["a.txt"]["state"], "MISSING")

        for p in list(bundle.iterdir()):
            p.unlink()
        bundle.rmdir()
        result = recovery.classify_raw_root(self.rawroot)
        self.assertEqual(result["classification"], "BUNDLE_ALREADY_ABSENT_AFTER_INTENT")

    def test_raw_bundle_directory_replacement_detected(self):
        bundle, _obj = self.raw_intent()
        for p in list(bundle.iterdir()):
            p.unlink()
        bundle.rmdir()
        bundle.mkdir(mode=0o700)
        result = recovery.classify_raw_root(self.rawroot)
        self.assertEqual(result["classification"], "IDENTITY_MISMATCH_OR_FOREIGN")
        self.assertEqual(result["bundle_state"], "REPLACED")

    def test_partial_raw_bundle_without_retention_intent_is_distinguished(self):
        bundle = self.rawroot / "20261001T120000Z-worldserver-00000099"
        bundle.mkdir(mode=0o700)
        private_file(bundle / "stderr.txt", b"partial")
        result = recovery.classify_raw_root(self.rawroot)
        self.assertEqual(result["classification"], "PARTIAL_BUNDLE_WITHOUT_RETENTION_INTENT")
        self.assertEqual(result["partial_bundles"][0]["bundle"], bundle.name)

    def test_complete_raw_bundle_without_intent_is_normal(self):
        raw.write_bundle(
            self.rawroot, "worldserver-00000002",
            {"a.txt": "x"}, NOW, {"source": "fixture"},
        )
        result = recovery.classify_raw_root(self.rawroot)
        self.assertEqual(result["classification"], "NO_UNFINISHED_INTENT")
        self.assertEqual(result["partial_bundles"], [])

    def test_classifier_does_not_remove_intent_or_targets(self):
        data, manifest, _obj = self.snapshot_intent()
        before = {
            "intent": (self.archive / "retention-intent.json").read_bytes(),
            "data": data.read_bytes(),
            "manifest": manifest.read_bytes(),
        }
        recovery.classify_snapshot_root(self.archive)
        self.assertEqual((self.archive / "retention-intent.json").read_bytes(), before["intent"])
        self.assertEqual(data.read_bytes(), before["data"])
        self.assertEqual(manifest.read_bytes(), before["manifest"])


if __name__ == "__main__":
    unittest.main()
