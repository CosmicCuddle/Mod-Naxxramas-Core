"""Actual launcher receipt compatibility with existing archive/audit/retention."""
import ast
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import f15_process_supervisor as supervisor
import f15_supervised_retention as retention
import f15_raw_archive as archive
import f15_supervised_storage_audit as audit

@unittest.skipUnless(os.name=="posix","real private filesystem fixture")
class LauncherRetention(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/"source";self.capture=self.root/"capture"
        self.run,self.outcome=supervisor.supervise(self.source,self.capture,"Worldserver",
             [sys.executable,"-c","print('checkpoint')"],forward_stops=True,poll_seconds=0.02)

    def test_real_launcher_archive_audit_and_expiry_preserve_raw(self):
        self.assertIs(self.outcome["stop_escalated"],False)
        original=(self.run/"stdout.raw").read_bytes()
        archive.validate_completed_run(self.source,self.capture,self.run.name,datetime.now(timezone.utc))
        audit.inspect_raw_storage(self.source,self.capture)
        (self.root/"raw-archive").mkdir(mode=0o700)
        archive.archive_run(self.source,self.capture,self.root/"raw-archive",self.run.name,datetime.now(timezone.utc))
        result=retention.expire_completed_runs_once(self.source,self.capture,
            now=(datetime.now(timezone.utc)+timedelta(days=33)).timestamp())
        self.assertEqual(result["completed_runs"],1)
        self.assertEqual((self.run/"stdout.raw").read_bytes(),original)
        self.assertTrue((self.run/"exit.json").exists())

    def test_actual_previous_reader_reproduces_rejection(self):
        source=subprocess.check_output(["git","show","061a22a4ac6a6b8a5c570b0c6c81a2789fcbe898:scripts/f15_supervised_retention.py"],cwd=Path(__file__).resolve().parents[1]).decode()
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="_receipt")
        scope={"stat":stat,"json":json,"Refused":retention.Refused}
        exec(compile(ast.Module(body=[node],type_ignores=[]),"historical-receipt-reader","exec"),scope)
        with self.assertRaises(retention.Refused):scope["_receipt"](self.run/"exit.json",retention.EXIT_FIELDS)
        self.assertIs(retention._receipt(self.run/"exit.json",retention.EXIT_FIELDS)["stop_escalated"],False)

    def test_unapproved_fields_or_non_boolean_escalation_refused(self):
        path=self.run/"exit.json";data=json.loads(path.read_text())
        for key,value in (("stop_escalated",1),("stop_escalated","false"),("foreign",False)):
            changed=dict(data);changed[key]=value;path.write_text(json.dumps(changed))
            with self.assertRaises(retention.Refused):retention.expire_completed_runs_once(self.source,self.capture)
            self.assertIn(b"checkpoint",(self.run/"stdout.raw").read_bytes())
