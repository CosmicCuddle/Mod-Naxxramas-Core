import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE=Path(__file__).resolve().parents[1]/"scripts/f15_operator_adapter.py"
spec=importlib.util.spec_from_file_location("adapter_plan",SOURCE)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

class Plans(unittest.TestCase):
    def test_pm2_argv_is_literal_and_stops_do_not_target_tree(self):
        app=adapter.pm2_plan(Path(tempfile.gettempdir()).resolve(), ["/fixture/world", "$(touch nope); literal"])["apps"][0]
        self.assertEqual(app["args"][-2:], ["/fixture/world", "$(touch nope); literal"])
        self.assertFalse(app["treekill"]);self.assertFalse(app["autorestart"])
        self.assertNotIn("--stop-timeout",app["args"])
        self.assertEqual(app["interpreter"],"none")

    def test_tmux_uses_dedicated_socket_and_direct_argv(self):
        plan=adapter.tmux_plan(Path(tempfile.gettempdir()).resolve(), ["/fixture/auth", "a b"], "f15-test-123")
        self.assertEqual(plan["argv"][:5],["tmux","-L","f15-test-123","-f","/dev/null"])
        self.assertEqual(plan["argv"][-2:],["/fixture/auth","a b"])
        with self.assertRaises(ValueError):adapter.tmux_plan("/tmp",["auth"],"bad;socket")

    @unittest.skipUnless(os.name=="posix","private permissions require POSIX")
    def test_plan_writer_is_private_no_overwrite_and_never_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with mock.patch("subprocess.Popen",side_effect=AssertionError("must not launch")):
                self.assertEqual(adapter.main(["--root",tmp,"--manager","pm2","--","/fixture/world"]),0)
            plan=root/"pm2-proposed.json"
            self.assertEqual(plan.stat().st_mode & 0o777,0o600)
            before=plan.read_bytes()
            self.assertEqual(adapter.main(["--root",tmp,"--manager","pm2","--","other"]),2)
            self.assertEqual(before,plan.read_bytes())
            self.assertEqual(json.loads(before)["apps"][0]["name"],"f15-proposed-worldserver")

    def test_bad_input_has_no_command_or_root_side_effect(self):
        with self.assertRaises(ValueError):adapter.wrapper_argv("relative","Worldserver",["test"])
        with self.assertRaises(ValueError):adapter.wrapper_argv("/tmp","Authserver",[])
