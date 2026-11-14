import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("bundle",ROOT/"scripts/f15_raw_evidence_bundle.py")
bundle=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)

OLD=datetime(2026,10,1,12,0,0,tzinfo=timezone.utc)

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)/"Raw Evidence"

    def test_bundle_writes_private_hashed_artifacts_and_manifest(self):
        path=bundle.write_bundle(
            self.root,"worldserver-00000001",
            {"pm2.json":{"restart_time":4},"stderr.txt":"fatal\n"},
            OLD,{"source":"fixture"}
        )
        meta=json.loads((path/"manifest.json").read_text())
        self.assertEqual(meta["retention_days"],30)
        self.assertEqual(meta["incident_id"],"worldserver-00000001")
        self.assertEqual({x["name"] for x in meta["artifacts"]},{"pm2.json","stderr.txt"})

    def test_exact_30_day_boundary_kept_then_removed(self):
        path=bundle.write_bundle(self.root,"worldserver-00000002",{"a.txt":"x"},OLD)
        self.assertEqual(bundle.retain_bundles(self.root,OLD+timedelta(days=30)),0)
        self.assertTrue(path.exists())
        self.assertEqual(bundle.retain_bundles(self.root,OLD+timedelta(days=30,seconds=1)),1)
        self.assertFalse(path.exists())

    def test_tampered_artifact_refuses_retention(self):
        path=bundle.write_bundle(self.root,"authserver-00000001",{"a.txt":"x"},OLD)
        (path/"a.txt").write_text("tampered")
        with self.assertRaises(bundle.Refused):
            bundle.retain_bundles(self.root,OLD+timedelta(days=31))
        self.assertTrue(path.exists())

    def test_unknown_extra_file_refuses_retention(self):
        path=bundle.write_bundle(self.root,"authserver-00000002",{"a.txt":"x"},OLD)
        extra=path/"manual.txt"
        extra.write_text("keep")
        extra.chmod(0o600)
        with self.assertRaises(bundle.Refused):
            bundle.retain_bundles(self.root,OLD+timedelta(days=31))
        self.assertTrue(extra.exists())

    def test_foreign_root_file_preserved(self):
        self.root.mkdir(mode=0o700)
        foreign=self.root/"manual-note.txt"
        foreign.write_text("keep")
        foreign.chmod(0o600)
        self.assertEqual(bundle.retain_bundles(self.root,OLD+timedelta(days=31)),0)
        self.assertEqual(foreign.read_text(),"keep")

    def test_invalid_incident_or_artifact_names_refused(self):
        with self.assertRaises(bundle.Refused):
            bundle.write_bundle(self.root,"../bad",{"a.txt":"x"},OLD)
        with self.assertRaises(bundle.Refused):
            bundle.write_bundle(self.root,"ok",{"../a":"x"},OLD)

    def test_oversized_artifact_refused_and_partial_not_claimed_complete(self):
        with self.assertRaises(bundle.Refused):
            bundle.write_bundle(
                self.root,"worldserver-00000003",
                {"huge.bin":b"x"*(bundle.MAX_ARTIFACT_BYTES+1)},OLD
            )
        dirs=[p for p in self.root.iterdir() if p.is_dir()]
        self.assertEqual(len(dirs),1)
        self.assertFalse((dirs[0]/"manifest.json").exists())

    def test_unfinished_retention_intent_blocks(self):
        bundle.write_bundle(self.root,"worldserver-00000004",{"a.txt":"x"},OLD)
        intent=self.root/"retention-intent.json"
        intent.write_text("{}")
        intent.chmod(0o600)
        with self.assertRaises(bundle.Refused):
            bundle.retain_bundles(self.root,OLD+timedelta(days=31))


    def test_raw_root_parent_symlink_refused(self):
        base = Path(self.t.name)
        real = base / "real-parent"
        real.mkdir()
        link = base / "linked-parent"
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaises(bundle.Refused):
            bundle.write_bundle(
                link / "Raw Evidence", "inc-parent-link",
                {"a.txt": "x"}, OLD, {"service": "Worldserver"}
            )

if __name__=="__main__":
    unittest.main()
