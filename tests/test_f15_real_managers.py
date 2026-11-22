"""Opt-in real PM2/tmux fixtures; isolated manager home/socket, finite Python children."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import f15_operator_adapter as adapter

@unittest.skipUnless(os.name=="posix" and os.environ.get("F15_REAL_MANAGERS")=="1", "explicit disposable Linux manager gate only")
class RealManagers(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"Crash Logs").mkdir(mode=0o700)
        (self.root/"Crash Logs"/"Raw Evidence").mkdir(mode=0o700)
        self.env=dict(os.environ,PM2_HOME=str(self.root/"pm2-home"),PM2_DISABLE_VERSION_CHECK="true")
        self.pm2=os.environ["F15_PM2_BIN"]
        self.socket="f15-"+uuid.uuid4().hex
        self.old_mask=os.umask(0o077);self.addCleanup(os.umask,self.old_mask)
        self.addCleanup(self.cleanup_managers)
        self.assertTrue(shutil.which("tmux"));self.assertTrue(Path(self.pm2).is_file())

    def command(self,argv,check=True):
        return subprocess.run(argv,env=self.env,cwd=self.root,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,text=True,timeout=20,check=check)

    def cleanup_managers(self):
        self.command([self.pm2,"kill"],check=False)
        self.command(["tmux","-L",self.socket,"kill-server"],check=False)

    def wait(self,predicate):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(0.05)
        self.fail("disposable manager fixture did not reach expected state")

    def reports(self,service):
        return list((self.root/"Crash Logs").glob("*-"+service+"-*.txt"))

    def pm2_start(self,source):
        plan=adapter.pm2_plan(self.root,[sys.executable,"-c",source])
        path=self.root/"ecosystem.json";path.write_text(json.dumps(plan))
        self.command([self.pm2,"start",str(path)])

    def test_pm2_nonzero_clean_and_rapid_new_runs(self):
        for index,code in enumerate((7,0)):
            self.pm2_start("print('password=SYNTHETIC_SECRET'); raise SystemExit("+str(code)+")")
            self.wait(lambda:len(self.reports("Worldserver"))==index+1)
            def stopped():
                rows=json.loads(self.command([self.pm2,"jlist"]).stdout)
                return rows and rows[0]["pm2_env"]["status"]=="stopped"
            self.wait(stopped)
            row=json.loads(self.command([self.pm2,"jlist"]).stdout)[0]
            self.assertEqual(row["pm2_env"]["restart_time"],0)
            self.assertEqual(row["pm2_env"]["exit_code"],code)
            self.command([self.pm2,"delete","f15-proposed-worldserver"])
        for path in self.reports("Worldserver"):
            self.assertNotIn("SYNTHETIC_SECRET",path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(len((self.root/"Crash Logs"/"Crash-History.txt").read_text().splitlines()),2)

    def stop_source(self,ready):
        return "import signal,sys,time; from pathlib import Path; signal.signal(signal.SIGINT,lambda *a:sys.exit(0)); Path("+repr(str(ready))+").touch(); time.sleep(10)"

    def test_pm2_stop_reaches_owned_child_and_report(self):
        ready=self.root/"ready";self.pm2_start(self.stop_source(ready))
        self.wait(ready.exists)
        self.command([self.pm2,"stop","f15-proposed-worldserver"])
        self.wait(lambda:len(self.reports("Worldserver"))==1)
        self.assertIn("Exit code: 0",self.reports("Worldserver")[0].read_text())

    def test_tmux_direct_wrapper_child_stop_and_receipt(self):
        ready=self.root/"ready"
        argv=adapter.tmux_plan(self.root,[sys.executable,"-c",self.stop_source(ready)],self.socket)["argv"]
        self.command(argv);self.wait(ready.exists)
        self.command(["tmux","-L",self.socket,"send-keys","-t","f15-proposed-authserver","C-c"])
        self.wait(lambda:len(self.reports("Authserver"))==1)
        self.assertIn("Exit code: 0",self.reports("Authserver")[0].read_text())
        run=next((self.root/"Authserver-source"/"runs").iterdir())
        self.assertEqual(json.loads((run/"exit.json").read_text())["exit_code"],0)

    def test_simultaneous_separate_services_share_private_report_sink(self):
        source="import time; time.sleep(0.3); print('checkpoint')"
        self.pm2_start(source)
        self.command(adapter.tmux_plan(self.root,[sys.executable,"-c",source],self.socket)["argv"])
        self.wait(lambda:len(self.reports("Authserver"))==1 and len(self.reports("Worldserver"))==1)
        self.wait(lambda:(self.root/"Crash Logs"/"Crash-History.txt").exists())
        def rows():return (self.root/"Crash Logs"/"Crash-History.txt").read_text().splitlines()
        self.wait(lambda:len(rows())==2)
        self.assertEqual({row.split("\t")[1] for row in rows()},{"Authserver","Worldserver"})
