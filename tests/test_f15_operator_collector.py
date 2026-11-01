"""Offline tests for real F15 operator CLI using only temporary fake log files."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'f15_operator_collector.py'
spec = importlib.util.spec_from_file_location('f15_operator_collector', MODULE)
f15 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f15)

class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'private_archive'
        self.src = self.home / 'world.log'
        self.src.write_bytes(b'existing data ignored\n')
        self.sources = {'Worldserver-out': str(self.src)}

    def poll(self, when=1720000000):
        return f15.collect_once(self.root, self.sources, now=when)

    def archives(self):
        return list((self.root / 'archives' / 'Worldserver-out').glob('*.txt'))

    def test_explicit_initial_tail_bootstrap_and_exact_bytes(self):
        before = self.src.read_bytes()
        self.poll()
        self.assertEqual(self.archives(), [])
        with self.src.open('ab') as fp: fp.write(b'hello \xff\n')
        self.poll()
        self.assertEqual(self.archives()[0].read_bytes(), b'hello \xff\n')
        self.assertEqual(self.src.read_bytes(), before + b'hello \xff\n')
        self.poll()
        self.assertEqual(len(self.archives()), 1)
        self.assertEqual(self.archives()[0].read_bytes(), b'hello \xff\n')

    def test_restart_and_day_split(self):
        self.poll()
        with self.src.open('ab') as fp: fp.write(b'first')
        self.poll()
        with self.src.open('ab') as fp: fp.write(b'second')
        self.poll(1720086400)
        self.assertEqual(sorted(p.read_bytes() for p in self.archives()), [b'first', b'second'])
        self.assertEqual(len(list((self.root/'records'/'Worldserver-out').glob('*.bin'))), 2)

    def test_reject_source_replacement(self):
        self.poll()
        self.src.unlink()
        self.src.write_bytes(b'other file')
        with self.assertRaises(f15.Refused): self.poll()

    def test_reject_truncate(self):
        self.poll()
        with self.src.open('ab') as fp: fp.write(b'longer')
        self.poll()
        self.src.write_bytes(b'')
        with self.assertRaises(f15.Refused): self.poll()

    def test_reject_hardlink_and_symlink(self):
        other = self.home/'linked'
        os.link(self.src,other)
        with self.assertRaises(f15.Refused): self.poll()
        other.unlink()
        other.symlink_to(self.src)
        self.sources={'Worldserver-out':str(other)}
        with self.assertRaises((f15.Refused, OSError)): self.poll()

    def test_reject_foreign_output_and_tamper(self):
        self.poll()
        with self.src.open('ab') as fp: fp.write(b'record')
        self.poll()
        self.archives()[0].write_bytes(b'tamper')
        with self.assertRaises(f15.Refused): self.poll()

    def test_reject_duplicated_physical_source(self):
        self.sources['Authserver-out']=str(self.src)
        with self.assertRaises(f15.Refused): self.poll()

    def test_private_directory_and_no_delete(self):
        self.poll()
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        foreign=self.root/'notes.txt'
        foreign.write_bytes(b'keep')
        with self.src.open('ab') as fp: fp.write(b'hello')
        self.poll()
        self.assertEqual(foreign.read_bytes(),b'keep')

    def test_cli_requires_explicit_capture(self):
        with self.assertRaises(SystemExit):
            f15.main(['--root',str(self.root),'--source',f'Worldserver-out={self.src}','--once'])

if __name__ == '__main__': unittest.main()
