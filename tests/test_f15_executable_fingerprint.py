import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import f15_executable_fingerprint as sample

class Fingerprint(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"binary";self.path.write_bytes(b"sample executable bytes");self.path.chmod(0o700)

    def test_regular_sample_is_exact_and_bounded(self):
        result=sample.sample_executable(str(self.path))
        self.assertEqual(result["status"],"SAMPLED")
        self.assertEqual(result["sha256"],hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result["size"],len(self.path.read_bytes()))

    def test_oversize_never_reads_or_returns_digest(self):
        with mock.patch.object(sample.os,"read",side_effect=AssertionError("must not read")):
            result=sample.sample_executable(str(self.path),max_bytes=2)
        self.assertEqual(result["reason"],"TOO_LARGE");self.assertNotIn("sha256",result)

    def test_unavailable_and_invalid_are_unknown_without_private_errors(self):
        for name in ("",None,"bad\0name",str(self.path.parent/"missing")):
            result=sample.sample_executable(name)
            self.assertEqual(result["status"],"UNKNOWN")
            self.assertNotIn(str(self.path.parent),str(result))

    def test_mutation_during_sample_discards_digest(self):
        real=sample.os.read;changed=False
        def mutate(fd,count):
            nonlocal changed
            data=real(fd,count)
            if not changed:
                changed=True
                with self.path.open("ab") as stream:stream.write(b" changed")
            return data
        with mock.patch.object(sample.os,"read",side_effect=mutate):result=sample.sample_executable(str(self.path))
        self.assertEqual(result["reason"],"CHANGED_DURING_SAMPLE")
        self.assertNotIn("sha256",result)

    @unittest.skipUnless(os.name=="posix","FIFO fixture requires POSIX")
    def test_fifo_is_refused_without_blocking(self):
        self.path.unlink();os.mkfifo(self.path,0o700)
        # which normally excludes non-regular files; force the path to test FD guard.
        with mock.patch.object(sample.shutil,"which",return_value=str(self.path)):
            self.assertEqual(sample.sample_executable(str(self.path))["reason"],"NOT_REGULAR")

    @unittest.skipUnless(os.name=="posix","real supervised filesystem composition requires POSIX")
    def test_supervised_report_preserves_fingerprint_artifact_and_unknown_gap(self):
        import json
        import f15_supervised_incident as incident
        for index,status in enumerate(("SAMPLED","UNKNOWN")):
            root=Path(self.tmp.name)/str(index);root.mkdir(mode=0o700)
            fingerprint=({"kind":"prelaunch_regular_file_sample","status":"SAMPLED","resolved_path":"/synthetic/python","size":2,"sha256":"a"*64}
                         if status=="SAMPLED" else {"status":"UNKNOWN","reason":"UNAVAILABLE"})
            with mock.patch.object(incident,"sample_executable",return_value=fingerprint):
                _,outcome,report=incident.supervise_and_report(root/"source",root/"archive",root/"Crash Logs",
                    root/"Crash Logs"/"Raw Evidence","Authserver",[sys.executable,"-c","pass"],execute=True)
            bundle=next((root/"Crash Logs"/"Raw Evidence").iterdir())
            self.assertEqual(json.loads((bundle/"executable-fingerprint.json").read_text()),fingerprint)
            self.assertEqual(outcome["exit_code"],0)
            self.assertIn("a"*64 if status=="SAMPLED" else "fingerprint UNKNOWN",report.read_text())
