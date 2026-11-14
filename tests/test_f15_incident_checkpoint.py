import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cp = load("cp", "scripts/f15_incident_checkpoint.py")


def parse_pm2(snapshot, name):
    data = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
    rows = [x for x in data if x.get("name") == name]
    if len(rows) != 1:
        raise cp.Refused("bad pm2")
    x = rows[0]
    e = x["pm2_env"]
    return {
        "pid": x.get("pid"), "status": e.get("status"),
        "restart_time": e.get("restart_time"), "pm_uptime": e.get("pm_uptime"),
    }


def pm(pid, restarts, up=1000):
    return json.dumps([{"name":"worldserver","pid":pid,"pm2_env":{
        "status":"online","restart_time":restarts,"pm_uptime":up,
        "unstable_restarts":0,"created_at":0,"exit_code":0}}])


def normalize_world(prev, cur, name, manager):
    p, c = parse_pm2(prev, name), parse_pm2(cur, name)
    if c["restart_time"] == p["restart_time"]:
        return None
    return {"service":"Worldserver","classification":"PM2_RESTART_OBSERVED",
            "classification_evidence":f"restart {p['restart_time']}->{c['restart_time']}"}


def normalize_auth(prev, cur, tmux_alive):
    if prev == cur:
        return None
    return {"service":"Authserver","classification":"PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN",
            "classification_evidence":f"tmux={tmux_alive}"}


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name) / "state"

    def test_first_world_observation_is_baseline_only(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        seen=[]
        self.assertIsNone(c.process_world(pm(10,1),"worldserver","",parse_pm2,normalize_world,seen.append))
        self.assertEqual(seen, [])
        self.assertEqual(c.state()["sequence"], 0)

    def test_world_restart_emits_once_and_advances_after_success(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        seen=[]
        c.process_world(pm(10,1),"worldserver","",parse_pm2,normalize_world,seen.append)
        event=c.process_world(pm(11,2),"worldserver","",parse_pm2,normalize_world,seen.append)
        self.assertEqual(event["incident_id"], "worldserver-00000001")
        self.assertEqual(len(seen), 1)
        self.assertIsNone(c.process_world(pm(11,2),"worldserver","",parse_pm2,normalize_world,seen.append))
        self.assertEqual(len(seen), 1)
        self.assertEqual(c.state()["sequence"], 1)


    def test_world_pm2_counter_reset_rebaselines_without_incident(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        seen=[]
        c.process_world(pm(10,5,up=5000),"worldserver","",parse_pm2,normalize_world,seen.append)
        self.assertIsNone(
            c.process_world(pm(20,0,up=100),"worldserver","",parse_pm2,normalize_world,seen.append)
        )
        self.assertEqual(seen, [])
        self.assertEqual(c.state()["identity"]["restart_time"], 0)
        self.assertEqual(c.state()["sequence"], 0)

    def test_world_pm2_counter_reset_then_later_restart_is_incident_one(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        seen=[]
        c.process_world(pm(10,5,up=5000),"worldserver","",parse_pm2,normalize_world,seen.append)
        c.process_world(pm(20,0,up=100),"worldserver","",parse_pm2,normalize_world,seen.append)
        event=c.process_world(pm(21,1,up=200),"worldserver","",parse_pm2,normalize_world,seen.append)
        self.assertEqual(event["incident_id"], "worldserver-00000001")
        self.assertEqual(c.state()["sequence"], 1)
        self.assertEqual(len(seen), 1)

    def test_world_missing_restart_counter_refused_at_checkpoint_boundary(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        bad=json.dumps([{"name":"worldserver","pid":10,"pm2_env":{
            "status":"online","restart_time":None,"pm_uptime":1000
        }}])
        with self.assertRaises(cp.Refused):
            c.process_world(bad,"worldserver","",parse_pm2,normalize_world,lambda x:None)

    def test_report_failure_does_not_consume_world_incident(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        c.process_world(pm(10,1),"worldserver","",parse_pm2,normalize_world,lambda x:None)
        def fail(_):
            raise OSError("disk full")
        with self.assertRaises(OSError):
            c.process_world(pm(11,2),"worldserver","",parse_pm2,normalize_world,fail)
        self.assertEqual(c.state()["identity"]["restart_time"], 1)
        seen=[]
        event=c.process_world(pm(11,2),"worldserver","",parse_pm2,normalize_world,seen.append)
        self.assertEqual(event["incident_id"], "worldserver-00000001")
        self.assertEqual(len(seen), 1)

    def test_auth_first_observation_baseline_only(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        seen=[]
        self.assertIsNone(c.process_auth({"pid":30,"start_ticks":100,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"}, True, normalize_auth, seen.append))
        self.assertEqual(seen, [])

    def test_auth_disappearance_emits_once(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        seen=[]
        c.process_auth({"pid":30,"start_ticks":100,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"}, True, normalize_auth, seen.append)
        event=c.process_auth({"pid":None,"start_ticks":None,"pane_pid":10,"tmux_probe_status":"session_present_auth_absent"}, True, normalize_auth, seen.append)
        self.assertEqual(event["incident_id"], "authserver-00000001")
        self.assertEqual(len(seen),1)
        self.assertIsNone(c.process_auth({"pid":None,"start_ticks":None,"pane_pid":10,"tmux_probe_status":"session_present_auth_absent"}, True, normalize_auth, seen.append))
        self.assertEqual(len(seen),1)

    def test_auth_replacement_is_new_incident(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        seen=[]
        c.process_auth({"pid":30,"start_ticks":100,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"}, True, normalize_auth, seen.append)
        c.process_auth({"pid":31,"start_ticks":200,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"}, True, normalize_auth, seen.append)
        self.assertEqual(seen[-1]["incident_id"], "authserver-00000001")



    def test_auth_initial_absence_then_recovery_updates_baseline_without_incident(self):
        c=cp.IncidentCheckpoint(self.root,"Authserver")
        seen=[]
        self.assertIsNone(c.process_auth(
            {"pid":None,"start_ticks":None,"pane_pid":None,"tmux_probe_status":"session_absent"},
            False, normalize_auth, seen.append,
        ))
        self.assertEqual(seen, [])
        self.assertIsNone(c.process_auth(
            {"pid":31,"start_ticks":200,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"},
            True, normalize_auth, seen.append,
        ))
        self.assertEqual(seen, [])
        self.assertEqual(c.state()["identity"]["pid"], 31)
        self.assertEqual(c.state()["sequence"], 0)

    def test_auth_live_tmux_without_auth_then_auth_appears_is_not_crash(self):
        c=cp.IncidentCheckpoint(self.root,"Authserver")
        seen=[]
        c.process_auth(
            {"pid":None,"start_ticks":None,"pane_pid":10,"tmux_probe_status":"session_present_auth_absent"},
            True, normalize_auth, seen.append,
        )
        self.assertIsNone(c.process_auth(
            {"pid":31,"start_ticks":200,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"},
            True, normalize_auth, seen.append,
        ))
        self.assertEqual(seen, [])
        self.assertEqual(c.state()["identity"]["pid"], 31)


    def test_auth_absent_recovery_then_later_disappearance_is_incident_one(self):
        c=cp.IncidentCheckpoint(self.root,"Authserver")
        seen=[]
        c.process_auth(
            {"pid":None,"start_ticks":None,"pane_pid":None,"tmux_probe_status":"session_absent"},
            False, normalize_auth, seen.append,
        )
        c.process_auth(
            {"pid":31,"start_ticks":200,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"},
            True, normalize_auth, seen.append,
        )
        event=c.process_auth(
            {"pid":None,"start_ticks":None,"pane_pid":None,"tmux_probe_status":"session_absent"},
            False, normalize_auth, seen.append,
        )
        self.assertEqual(event["incident_id"], "authserver-00000001")
        self.assertEqual(c.state()["sequence"], 1)
        self.assertEqual(len(seen), 1)

    def test_auth_tmux_session_disappearance_emits_incident(self):
        c=cp.IncidentCheckpoint(self.root,"Authserver")
        seen=[]
        c.process_auth(
            {"pid":30,"start_ticks":100,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"},
            True, normalize_auth, seen.append,
        )
        event=c.process_auth(
            {"pid":None,"start_ticks":None,"pane_pid":None,"tmux_probe_status":"session_absent"},
            False, normalize_auth, seen.append,
        )
        self.assertEqual(event["incident_id"], "authserver-00000001")

    def test_insecure_state_root_refused(self):
        self.root.mkdir()
        self.root.chmod(0o755)
        with self.assertRaises(cp.Refused):
            cp.IncidentCheckpoint(self.root, "Worldserver")

    def test_corrupt_checkpoint_refused(self):
        self.root.mkdir(mode=0o700)
        p=self.root/"Worldserver.checkpoint.json"
        p.write_text("not-json")
        p.chmod(0o600)
        c=cp.IncidentCheckpoint(self.root,"Worldserver")
        with self.assertRaises(cp.Refused):
            c.state()

    def test_invalid_auth_partial_identity_refused(self):
        c=cp.IncidentCheckpoint(self.root,"Authserver")
        with self.assertRaises(cp.Refused):
            c.process_auth({"pid":30,"start_ticks":None,"pane_pid":10,"tmux_probe_status":"session_present_auth_present"},True,normalize_auth,lambda x:None)

    def test_invalid_auth_missing_pane_identity_refused(self):
        c=cp.IncidentCheckpoint(self.root,"Authserver")
        with self.assertRaises(cp.Refused):
            c.process_auth({"pid":30,"start_ticks":100,"tmux_probe_status":"session_present_auth_present"},True,normalize_auth,lambda x:None)

if __name__ == "__main__":
    unittest.main()
