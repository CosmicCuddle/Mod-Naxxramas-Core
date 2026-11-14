import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cp = load("cp", "scripts/f15_incident_checkpoint.py")
topology = load("topology", "scripts/f15_topology_evidence.py")


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


def pm(pid, restarts, up=1000, status="online", exit_code=0):
    return json.dumps([{"name":"worldserver","pid":pid,"pm_id":0,"pm2_env":{
        "status":status,"restart_time":restarts,"pm_uptime":up,
        "unstable_restarts":0,"created_at":0,"exit_code":exit_code}}])


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
        self.assertIsNone(c.process_auth({"pid":30,"start_ticks":100}, True, normalize_auth, seen.append))
        self.assertEqual(seen, [])

    def test_auth_disappearance_emits_once(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        seen=[]
        c.process_auth({"pid":30,"start_ticks":100}, True, normalize_auth, seen.append)
        event=c.process_auth({"pid":None,"start_ticks":None}, True, normalize_auth, seen.append)
        self.assertEqual(event["incident_id"], "authserver-00000001")
        self.assertEqual(len(seen),1)
        self.assertIsNone(c.process_auth({"pid":None,"start_ticks":None}, True, normalize_auth, seen.append))
        self.assertEqual(len(seen),1)

    def test_auth_replacement_is_new_incident(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        seen=[]
        c.process_auth({"pid":30,"start_ticks":100}, True, normalize_auth, seen.append)
        c.process_auth({"pid":31,"start_ticks":200}, True, normalize_auth, seen.append)
        self.assertEqual(seen[-1]["incident_id"], "authserver-00000001")

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
            c.process_auth({"pid":30,"start_ticks":None},True,normalize_auth,lambda x:None)

    def test_legacy_fixed_pending_file_does_not_wedge_later_commit(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        c.process_world(pm(10, 1), "worldserver", "", parse_pm2, normalize_world, lambda x: None)
        legacy = self.root / "Worldserver.checkpoint.json.pending"
        legacy.write_text("interrupted-old-writer")
        legacy.chmod(0o600)
        seen = []
        event = c.process_world(pm(11, 2), "worldserver", "", parse_pm2, normalize_world, seen.append)
        self.assertEqual(event["incident_id"], "worldserver-00000001")
        self.assertEqual(len(seen), 1)
        self.assertTrue(legacy.exists())

    def test_world_same_counter_stop_is_not_silently_consumed(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        seen = []
        c.process_world(
            pm(10, 4, status="online"),
            "worldserver", "", topology._one_pm2, topology.world_incident, seen.append,
        )
        event = c.process_world(
            pm(0, 4, status="stopped"),
            "worldserver", "", topology._one_pm2, topology.world_incident, seen.append,
        )
        self.assertEqual(event["classification"], "PROCESS_DISAPPEARANCE_CAUSE_UNKNOWN")
        self.assertEqual(event["incident_id"], "worldserver-00000001")
        self.assertEqual(c.state()["identity"]["status"], "stopped")

    def test_auth_disappearance_then_recovery_advances_without_refusal(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        seen = []
        c.process_auth({"pid": 30, "start_ticks": 100}, True, topology.auth_incident, seen.append)
        event = c.process_auth({"pid": None, "start_ticks": None}, True, topology.auth_incident, seen.append)
        self.assertEqual(event["incident_id"], "authserver-00000001")
        recovered = c.process_auth({"pid": 31, "start_ticks": 200}, True, topology.auth_incident, seen.append)
        self.assertIsNone(recovered)
        self.assertEqual(len(seen), 1)
        self.assertEqual(c.state()["identity"]["pid"], 31)

    def test_auth_baseline_absent_then_start_is_recovery(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        seen = []
        self.assertIsNone(c.process_auth(
            {"pid": None, "start_ticks": None}, True, topology.auth_incident, seen.append
        ))
        self.assertIsNone(c.process_auth(
            {"pid": 31, "start_ticks": 200}, True, topology.auth_incident, seen.append
        ))
        self.assertEqual(seen, [])
        self.assertEqual(c.state()["identity"]["pid"], 31)

    def test_concurrent_observers_emit_one_incident(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        c.process_world(pm(10, 1), "worldserver", "", parse_pm2, normalize_world, lambda x: None)
        seen = []
        results = []
        errors = []

        def run():
            try:
                results.append(c.process_world(
                    pm(11, 2), "worldserver", "", parse_pm2, normalize_world, seen.append
                ))
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(c.state()["sequence"], 1)

    def test_insecure_checkpoint_lock_is_refused(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        c.lock_path.write_text("lock")
        c.lock_path.chmod(0o644)
        with self.assertRaises(cp.Refused):
            c.process_world(pm(10, 1), "worldserver", "", parse_pm2, normalize_world, lambda x: None)

    def test_boolean_auth_identity_is_refused(self):
        c = cp.IncidentCheckpoint(self.root, "Authserver")
        with self.assertRaises(cp.Refused):
            c.process_auth({"pid": True, "start_ticks": 100}, True, normalize_auth, lambda x: None)
        with self.assertRaises(cp.Refused):
            c.process_auth({"pid": 30, "start_ticks": False}, True, normalize_auth, lambda x: None)

    def test_broken_checkpoint_symlink_is_refused(self):
        c = cp.IncidentCheckpoint(self.root, "Worldserver")
        c.path.symlink_to(self.root / "missing-target")
        with self.assertRaises(cp.Refused):
            c.process_world(pm(10, 1), "worldserver", "", parse_pm2, normalize_world, lambda x: None)

if __name__ == "__main__":
    unittest.main()
