"""Offline tests for real F15 operator CLI using only temporary fake log files."""
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

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

    def test_opt_in_backfill_reads_existing_bytes_exactly_once(self):
        existing = self.src.read_bytes()
        f15.collect_once(self.root, self.sources, now=1720000000, include_existing=True)
        self.assertEqual(self.archives()[0].read_bytes(), existing)
        self.poll()
        self.assertEqual(self.archives()[0].read_bytes(), existing)
        self.assertEqual(len(list((self.root/'records'/'Worldserver-out').glob('*.bin'))), 1)

    def test_backfill_switch_cannot_rewind_existing_eof_cursor(self):
        self.poll()
        f15.collect_once(self.root, self.sources, now=1720000000, include_existing=True)
        self.assertEqual(self.archives(), [])
        with self.src.open('ab') as fp: fp.write(b'new only')
        f15.collect_once(self.root, self.sources, now=1720000000, include_existing=True)
        self.assertEqual(self.archives()[0].read_bytes(), b'new only')

    def test_explicit_cli_backfill_fake_file(self):
        code = f15.main(['--root', str(self.root), '--source', f'Worldserver-out={self.src}', '--capture', '--once', '--include-existing-on-first-poll'])
        self.assertEqual(code, 0)
        self.assertEqual(self.archives()[0].read_bytes(), self.src.read_bytes())

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

    def test_copytruncate_regrow_same_inode_never_claims_continuity(self):
        self.poll()
        original = b"authenticated-journal-tail"
        with self.src.open("ab") as fp:
            fp.write(original)
        self.poll()
        old_archive = self.archives()[0].read_bytes()
        # Same path and inode; replacement has already regrown beyond the
        # old cursor, so size and inode checks alone would miss the loss.
        previous_inode = self.src.stat().st_ino
        self.src.write_bytes(b"Z" * (self.src.stat().st_size + 19))
        self.assertEqual(self.src.stat().st_ino, previous_inode)
        with self.assertRaisesRegex(f15.Refused, "source rewritten in place"):
            self.poll()
        self.assertEqual(self.archives()[0].read_bytes(), old_archive)
        self.assertEqual(len(list((self.root/"records"/"Worldserver-out").glob("*.bin"))), 1)

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

    def test_cli_refusal_never_exposes_private_paths_or_mutates_files(self):
        # Simulate a failure before the real collector touches any sources.
        # OSError/Refused text can contain private host paths and must never
        # be copied into operator stderr or CI logs.
        private = str(self.home / "PRIVATE_WORLD_AUTH_LOG_PATH")
        errors = [
            f15.Refused("private source: " + private),
            FileNotFoundError(2, "not found", private),
            PermissionError(13, "permission denied", private),
            ValueError("private root: " + private),
        ]
        original = self.src.read_bytes()
        for error in errors:
            with self.subTest(error=type(error).__name__):
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(f15, 'collect_once', side_effect=error):
                    with redirect_stdout(out), redirect_stderr(err):
                        code = f15.main([
                            '--root', str(self.root), '--source',
                            f'Worldserver-out={self.src}', '--capture', '--once'])
                self.assertEqual(code, 2)
                self.assertEqual(out.getvalue(), '')
                self.assertIn('F15 capture REFUSED:', err.getvalue())
                self.assertNotIn(private, err.getvalue())
                self.assertEqual(self.src.read_bytes(), original)
                self.assertFalse(self.root.exists())

    def test_cli_requires_explicit_capture(self):
        with self.assertRaises(SystemExit):
            f15.main(['--root',str(self.root),'--source',f'Worldserver-out={self.src}','--once'])

if __name__ == '__main__': unittest.main()
