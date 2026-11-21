"""Actual pure renderer projection tests: no fcntl shim or filesystem backend.

The AST selects the checked-in pure functions/constants; it does not import or
mock POSIX storage. Windows execution is not permission/locking evidence.
"""
import ast
from datetime import datetime, timezone
from pathlib import Path
import re
import signal
import subprocess
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "scripts/f15_crash_report_renderer.py"
PARENT = "64e06361e1daaf5db6cfcfd2b07bc7375650c675"


def projection(source):
    names = {"_unknown", "_clean", "sanitize_context", "_signal_number", "_signal_name",
             "classification", "validate_incident", "render_report", "_history_line",
             "_quoted_value_closed", "_sensitive_key", "redact_text"}
    constants = {"SERVICES", "INCIDENT_RE", "STAMP_RE", "MAX_CONTEXT_BYTES", "MAX_FIELD_CHARS",
                 "SECRET_RE", "FLAG_SECRET_RE", "URI_SECRET_RE", "PRIVATE_KEY_RE"}
    nodes = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "Refused":
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            nodes.append(node)
    scope = {"re": re, "signal": signal, "datetime": datetime, "timezone": timezone}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), SOURCE + "[pure-projection]", "exec"), scope)
    return types.SimpleNamespace(**scope)


class ReportPrivacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = projection((ROOT / SOURCE).read_text(encoding="utf-8"))

    def test_frozen_parent_reproduces_real_value_leaks(self):
        source = subprocess.run(["git", "show", PARENT + ":" + SOURCE], cwd=ROOT,
                                check=True, capture_output=True).stdout.decode("utf-8")
        old = projection(source)
        for text in ('password="first SENTINEL_TAIL"', "Authorization: Bearer SENTINEL_AUTH",
                     'LoginDatabaseInfo="host;3306;user;SENTINEL_DATABASE;auth"',
                     "mysql://user:SENTINEL_URI@localhost/db"):
            with self.subTest(text=text):
                self.assertIn("SENTINEL", old.sanitize_context(text))
                self.assertNotIn("SENTINEL", self.renderer.sanitize_context(text))

    def test_sensitive_keys_values_and_quotes(self):
        keys = ["password", "passwd", "pwd", "token", "Authorization", "api_key", "api key",
                "secret", "clientSecret", "refresh_token", "db.password", "Cookie", "X-Amz-Signature"]
        for key in keys:
            for separator in ("=", ": "):
                for value in ("SENTINEL_VALUE", '"first SENTINEL_VALUE"', "'first SENTINEL_VALUE'"):
                    with self.subTest(key=key, separator=separator, value=value):
                        result = self.renderer.sanitize_context(key + separator + value + "\nsafe diagnostic")
                        self.assertNotIn("SENTINEL", result)
                        self.assertIn("[REDACTED]", result)
                        self.assertIn("safe diagnostic", result)

    def test_database_info_and_json_key(self):
        for service in ("Login", "World", "Character"):
            result = self.renderer.sanitize_context(service + 'DatabaseInfo="host;3306;user;SENTINEL_DB;schema"')
            self.assertNotIn("SENTINEL", result)
        self.assertNotIn("SENTINEL", self.renderer.sanitize_context('{"password": "first SENTINEL_JSON"}'))

    def test_uri_userinfo_and_command_flags(self):
        for value in ("mysql://user:first@SENTINEL_SECRET@dbhost:3306/schema",
                      "https://user:SENTINEL%20SECRET@host/path", "--password 'first SENTINEL_VALUE'",
                      "--api-key=SENTINEL_KEY"):
            self.assertNotIn("SENTINEL", self.renderer.sanitize_context(value))
        self.assertIn("dbhost:3306/schema", self.renderer.sanitize_context("mysql://u:SENTINEL@dbhost:3306/schema"))

    def test_private_keys_and_ambiguous_multiline_values(self):
        for value in ("-----BEGIN PRIVATE KEY-----\nSENTINEL_KEY\n-----END PRIVATE KEY-----",
                      "-----BEGIN RSA PRIVATE KEY-----\nSENTINEL_UNFINISHED",
                      'password="first\nSENTINEL_MULTILINE"\ntrailing',
                      "Authorization:\n Bearer SENTINEL_FOLDED", "token='unfinished\\\nSENTINEL_ESCAPE"):
            self.assertNotIn("SENTINEL", self.renderer.sanitize_context(value))

    def test_safe_database_reason_and_fingerprints_survive(self):
        text = "database connection failed: network timeout\nsource=abc123\nPID=42\nframe #2"
        self.assertEqual(self.renderer.sanitize_context(text), text)
        self.assertEqual(self.renderer._clean("AC dev abc123"), "AC dev abc123")

    def test_all_untrusted_report_fields_pass_through_redaction(self):
        for field in ("classification_evidence", "executable", "build_version", "source_revision",
                      "last_checkpoint", "capture_gaps", "restart_evidence", "native_crash_evidence",
                      "raw_evidence_ref", "notes", "supervisor_probe_status"):
            incident = {"service": "Worldserver", "incident_id": "fixture-privacy", "exit_code": 7,
                        field: 'password="first SENTINEL_FIELD"'}
            with self.subTest(field=field):
                text = self.renderer.render_report(incident)
                self.assertNotIn("SENTINEL", text)
                self.assertIn("NONZERO_EXIT", text)

    def test_redacts_before_selecting_context_tail(self):
        text = "password=" + "A" * 33000 + "SENTINEL_TAIL_SECRET\nRECENT_DIAGNOSTIC"
        result = self.renderer.sanitize_context(text)
        self.assertNotIn("SENTINEL", result)
        self.assertNotIn("A" * 32, result)
        self.assertIn("RECENT_DIAGNOSTIC", result)

    def test_context_is_recent_utf8_and_includes_marker_in_byte_bound(self):
        text = "OLD_DIAGNOSTIC\n" + "\u00e9" * 70000 + "\nMOST_RECENT_DIAGNOSTIC"
        result = self.renderer.sanitize_context(text)
        self.assertIn("MOST_RECENT_DIAGNOSTIC", result)
        self.assertNotIn("OLD_DIAGNOSTIC", result)
        self.assertIn("TRUNCATED", result)
        self.assertLessEqual(len(result.encode("utf-8")), self.renderer.MAX_CONTEXT_BYTES)
        self.assertNotIn("\ufffd", result)

    def test_history_is_redacted_and_single_record(self):
        incident = {"service": "Authserver", "incident_id": "fixture-index",
                    "classification": "EXIT\tpassword=SENTINEL_CLASS\nextra",
                    "exit_code": "password=SENTINEL_EXIT\nextra"}
        line = self.renderer._history_line(incident, "fixture.txt", "20261121T120000Z")
        self.assertNotIn("SENTINEL", line)
        self.assertEqual(line.count("\n"), 1)
        self.assertEqual(line.count("\t"), 6)

    def test_idempotence_and_oversized_secret(self):
        for text in ('password="first SENTINEL"', "https://u:SENTINEL@host/path",
                     "token='unterminated\nSENTINEL", "database connection failed"):
            result = self.renderer.redact_text(text)
            self.assertEqual(self.renderer.redact_text(result), result)
        text = self.renderer._clean("password=" + "A" * 10000 + "SENTINEL")
        self.assertNotIn("A" * 32, text)
        self.assertNotIn("SENTINEL", text)

    def test_untrusted_surrogates_cannot_break_report_encoding(self):
        text = self.renderer.render_report({"service": "Worldserver", "incident_id": "encoding-fixture",
                                            "notes": "invalid\ud800 note"})
        text.encode("utf-8")
        self.assertIn("invalid", text)

    def test_long_non_secret_word_and_other_assignments_are_unchanged(self):
        text = "token" * 20000 + "\nerror_code=1045\nsource_revision=abc123"
        self.assertEqual(self.renderer.redact_text(text), text)

    def test_projection_does_not_import_or_fake_posix_storage(self):
        self.assertFalse(hasattr(self.renderer, "fcntl"))
        self.assertFalse(hasattr(self.renderer, "write_report"))
        self.assertFalse(hasattr(self.renderer, "_exclusive_write"))

    def test_existing_storage_functions_are_unchanged(self):
        parent = subprocess.run(["git", "show", PARENT + ":" + SOURCE], cwd=ROOT,
                                check=True, capture_output=True).stdout.decode("utf-8")
        def functions(source):
            return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef)}
        old = functions(parent)
        current = functions((ROOT / SOURCE).read_text(encoding="utf-8"))
        for name in old.keys() - {"_clean", "sanitize_context", "_history_line"}:
            self.assertEqual(current[name], old[name], name)
        self.assertIn("import fcntl", (ROOT / SOURCE).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
