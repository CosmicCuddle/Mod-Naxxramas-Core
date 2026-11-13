import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("probe",ROOT/"scripts/f15_readonly_host_probe.py")
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class FakeRunner:
    def __init__(self, responses):
        self.responses=responses
        self.calls=[]
    def __call__(self, argv):
        self.calls.append(argv)
        key=tuple(argv)
        if key not in self.responses:
            raise AssertionError(f"unexpected command {argv}")
        return self.responses[key]

class ProbeTests(unittest.TestCase):
    def test_pm2_exact_readonly_command_and_fields(self):
        payload=json.dumps([{"name":"worldserver","pid":123,"pm_id":0,"pm2_env":{
            "status":"online","restart_time":4,"unstable_restarts":1,"pm_uptime":1000,
            "created_at":900,"exit_code":0,"pm_out_log_path":"/tmp/out.log","pm_err_log_path":"/tmp/err.log"}}])
        r=FakeRunner({("pm2","jlist"):(0,payload,"")})
        raw,info=probe.probe_pm2("worldserver",r)
        self.assertEqual(raw,payload)
        self.assertEqual(info["restart_time"],4)
        self.assertEqual(info["out_log"],"/tmp/out.log")
        self.assertEqual(r.calls,[["pm2","jlist"]])

    def test_pm2_ambiguous_process_refused(self):
        payload=json.dumps([{"name":"worldserver","pm2_env":{}},{"name":"worldserver","pm2_env":{}}])
        r=FakeRunner({("pm2","jlist"):(0,payload,"")})
        with self.assertRaises(probe.Refused):
            probe.probe_pm2("worldserver",r)

    def test_tmux_auth_tree_and_proc_start_ticks(self):
        ps="10 1 tmux tmux\n20 10 bash bash\n30 20 authserver /root/bin/authserver\n"
        r=FakeRunner({
            ("tmux","display-message","-p","-t","auth","#{pane_pid}"):(0,"10\n",""),
            ("ps","-eo","pid=,ppid=,comm=,args="):(0,ps,"")})
        stat_text="30 (authserver) S " + " ".join(["0"]*18 + ["777", "0", "0"])
        info,alive=probe.probe_auth_tmux("auth",r,lambda p:stat_text)
        self.assertTrue(alive)
        self.assertEqual(info["pid"],30)
        self.assertEqual(info["start_ticks"],777)
        self.assertEqual(len(r.calls),2)

    def test_tmux_multiple_auth_descendants_refused(self):
        ps="10 1 tmux tmux\n20 10 authserver authserver\n21 10 authserver authserver\n"
        r=FakeRunner({
            ("tmux","display-message","-p","-t","auth","#{pane_pid}"):(0,"10\n",""),
            ("ps","-eo","pid=,ppid=,comm=,args="):(0,ps,"")})
        with self.assertRaises(probe.Refused):
            probe.probe_auth_tmux("auth",r,lambda p:"")

    def test_tmux_command_failure_refused_without_fallback_mutation(self):
        r=FakeRunner({("tmux","display-message","-p","-t","auth","#{pane_pid}"):(1,"","no session")})
        with self.assertRaises(probe.Refused):
            probe.probe_auth_tmux("auth",r,lambda p:"")
        self.assertEqual(len(r.calls),1)

    def test_tail_reads_only_last_bounded_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"log"
            p.write_bytes(b"A"*100+b"TAIL")
            self.assertEqual(probe.tail_private_source(p,4),"TAIL")

    def test_tail_symlink_refused(self):
        if os.name != "posix":
            self.skipTest("O_NOFOLLOW POSIX behavior")
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/"target"
            target.write_text("secret")
            link=Path(t)/"link"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                probe.tail_private_source(link,4)

    def test_invalid_names_do_not_execute_commands(self):
        r=FakeRunner({})
        for bad in ["", "world server", "x\n"]:
            with self.subTest(bad=bad):
                with self.assertRaises(probe.Refused):
                    probe.probe_pm2(bad,r)
        self.assertEqual(r.calls,[])

if __name__=="__main__":
    unittest.main()
