import sys, tempfile, hashlib, json, os, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import f15_preoverwrite_log_snapshot as s
class Review(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.root=Path(t.name); self.src=self.root/'world.log'; self.payload=b'A'*4096; self.src.write_bytes(self.payload); self.archive=self.root/'archive'
    def test_short_write_completed(self):
        real=os.write
        def short(fd,data): return real(fd,data[:max(1,len(data)//2)])
        with patch.object(s.os,'write',side_effect=short): data,manifest=s.snapshot_file(self.src,self.archive)
        self.assertEqual(data.read_bytes(),self.payload); self.assertEqual(json.loads(manifest.read_text())['sha256'],hashlib.sha256(data.read_bytes()).hexdigest()); self.assertEqual(self.src.read_bytes(),self.payload)
    def test_zero_write_refused(self):
        with patch.object(s.os,'write',return_value=0):
            with self.assertRaises(s.Refused): s.snapshot_file(self.src,self.archive)
        self.assertFalse(list(self.archive.glob('*.json'))); self.assertFalse(list(self.archive.glob('*.log'))); self.assertEqual(self.src.read_bytes(),self.payload)
    def test_source_ancestor_symlink_refused(self):
        link=self.root/'link'; link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(s.Refused): s.snapshot_file(link/'world.log',self.archive)
        self.assertFalse(self.archive.exists())
    def test_source_symlink_refused(self):
        link=self.root/'link.log'; link.symlink_to(self.src)
        with self.assertRaises(s.Refused): s.snapshot_file(link,self.archive)
        self.assertFalse(self.archive.exists())
    def test_normal_copy(self):
        data,manifest=s.snapshot_file(self.src,self.archive); self.assertEqual(data.read_bytes(),self.payload); self.assertEqual(json.loads(manifest.read_text())['source_size'],len(self.payload))
if __name__=='__main__': unittest.main()
