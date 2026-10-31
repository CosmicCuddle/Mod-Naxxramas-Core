import json
import os
from pathlib import Path
import tempfile
import unittest
from f15_source_admission import AdmissionError, admit_sources, compare_sample


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = self.root / 'pm2'
        self.auth = self.root / 'auth'
        self.world.mkdir(); self.auth.mkdir()
        self.out = self.world / 'world-out.log'
        self.err = self.world / 'world-err.log'
        self.native = self.auth / 'auth.log'
        for p in (self.out, self.err, self.native):
            p.write_bytes(b'sensitive bytes should not appear in results')
        self.entry = {'name': 'world', 'pm2_env': {'status': 'online',
                      'pm_exec_path': '/srv/bin/worldserver',
                      'pm_out_log_path': str(self.out), 'pm_err_log_path': str(self.err)}}

    def run_probe(self, entry=None, native=None, wr=None, ar=None):
        return admit_sources(json.dumps([self.entry if entry is None else entry]),
                             'world', 'worldserver', str(self.native if native is None else native),
                             str(self.world if wr is None else wr), str(self.auth if ar is None else ar))

    def test_reads_metadata_only_and_distinct_streams(self):
        got = self.run_probe()
        self.assertEqual([s.stream for s in got], ['world-out', 'world-err', 'auth-native'])
        self.assertEqual(len({(s.dev, s.ino) for s in got}), 3)
        self.assertNotIn('sensitive', str(got))
        self.assertNotIn(str(self.out), str(got))

    def test_status_requires_online_process(self):
        p = json.loads(json.dumps(self.entry)); p['pm2_env']['status'] = 'stopped'
        with self.assertRaises(AdmissionError): self.run_probe(entry=p)

    def test_executable_must_match(self):
        p = json.loads(json.dumps(self.entry)); p['pm2_env']['pm_exec_path'] = '/srv/bin/other'
        with self.assertRaises(AdmissionError): self.run_probe(entry=p)

    def test_missing_or_ambiguous_process(self):
        with self.assertRaises(AdmissionError):
            admit_sources('[]', 'world', 'worldserver', str(self.native), str(self.world), str(self.auth))
        with self.assertRaises(AdmissionError):
            admit_sources(json.dumps([self.entry, self.entry]), 'world', 'worldserver', str(self.native), str(self.world), str(self.auth))

    def test_same_stdout_stderr_is_rejected(self):
        p = json.loads(json.dumps(self.entry)); p['pm2_env']['pm_err_log_path'] = str(self.out)
        with self.assertRaises(AdmissionError): self.run_probe(entry=p)

    def test_auth_alias_to_world_source_rejected(self):
        with self.assertRaises(AdmissionError): self.run_probe(native=self.out, ar=self.world)

    def test_symlink_file_rejected(self):
        self.native.unlink(); self.native.symlink_to(self.out)
        with self.assertRaises(AdmissionError): self.run_probe()

    def test_symlink_directory_rejected(self):
        alias = self.root / 'link-world'; alias.symlink_to(self.world, target_is_directory=True)
        p = json.loads(json.dumps(self.entry)); p['pm2_env']['pm_out_log_path'] = str(alias / 'world-out.log')
        with self.assertRaises(AdmissionError): self.run_probe(entry=p, wr=self.root)

    def test_hardlinked_source_rejected(self):
        self.native.unlink(); os.link(self.out, self.native)
        with self.assertRaises(AdmissionError): self.run_probe()

    def test_outside_approved_root_rejected(self):
        with self.assertRaises(AdmissionError): self.run_probe(wr=self.auth)

    def test_path_prefix_confusion_rejected(self):
        w = self.root / 'pm2-extra'; w.mkdir()
        p = w / 'p.log'; p.write_bytes(b'')
        e = json.loads(json.dumps(self.entry)); e['pm2_env']['pm_out_log_path'] = str(p)
        with self.assertRaises(AdmissionError): self.run_probe(entry=e)

    def test_directory_instead_of_file_rejected(self):
        self.native.unlink(); self.native.mkdir()
        with self.assertRaises(AdmissionError): self.run_probe()

    def test_source_mutations_are_detected_but_not_guaranteed(self):
        a = self.run_probe()[0]
        with self.out.open('ab') as f: f.write(b'new')
        b = self.run_probe()[0]
        self.assertEqual(compare_sample(a, b), 'grown: appended bytes unverified')
        self.out.write_bytes(b'x')
        c = self.run_probe()[0]
        self.assertEqual(compare_sample(b, c), 'truncated: missing bytes unknown')

    def test_inplace_same_size_rewrite_flagged_if_metadata_changes(self):
        a = self.run_probe()[0]
        self.out.write_bytes(b'x' * a.size)
        b = self.run_probe()[0]
        self.assertIn(compare_sample(a, b), (
            'same-size-write-suspected: no completeness guarantee',
            'unchanged-observation: no completeness guarantee'))

    def test_no_files_added_or_source_bytes_modified(self):
        before = {(str(p), p.read_bytes()) for p in (self.out, self.err, self.native)}
        self.run_probe(); self.run_probe()
        after = {(str(p), p.read_bytes()) for p in (self.out, self.err, self.native)}
        self.assertEqual(before, after)
        self.assertEqual({x.name for x in self.world.iterdir()}, {'world-out.log', 'world-err.log'})


if __name__ == '__main__':
    unittest.main()
