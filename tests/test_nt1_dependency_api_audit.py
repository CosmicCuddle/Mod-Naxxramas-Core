"""Synthetic unit checks for read-only installed-source preflight.

These tests do NOT inspect the operator's host, build C++, or grant Apply.
"""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_nt1_dependency_apis as audit


PLAYER = """
struct PlayerTalent { uint8 specMask : 8; uint32 talentID; };
bool HasTalent(uint32 spell_id, uint8 spec) const;
PlayerTalentMap const& GetTalentMap() const;
PlayerSpellMap const& GetSpellMap() const;
uint8 GetActiveSpec() const;
uint8 GetSpecsCount() const;
uint32 GetGlyph(uint8 slot) const;
QuestStatus GetQuestStatus(uint32 quest_id) const;
Item* GetItemByPos(uint8 bag, uint8 slot) const;
bool CanTitanGrip() const;
"""
PLAYER_CPP = """
bool Player::HasTalent(uint32 spell_id, uint8 spec) const { return true; }
bool Player::resetTalents(bool noCost) {
    sScriptMgr->OnPlayerTalentsReset(this, noCost);
    RemovePet(nullptr); SetCanTitanGrip(false);
    SetCanDualWield(false); AutoUnequipOffhandIfNeed(); return true;
}
void Player::AutoUnequipOffhandIfNeed(bool force) {}
void Player::ActivateSpec(uint8 spec) {}
"""
UNIT = "bool CanDualWield() const;"
ITEM = "ItemTemplate const* GetTemplate() const;"
CHAT = "void PSendSysMessage(char const* fmt, Args&&... args);"


def write_fixture(root, name, text):
    target = root / audit.CORE_FILES[name]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


class NT1DependencyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.core = self.path / "core"
        for name, text in (("Player.h", PLAYER), ("Player.cpp", PLAYER_CPP),
                           ("Unit.h", UNIT), ("Item.h", ITEM),
                           ("Chat.h", CHAT)):
            write_fixture(self.core, name, text)

    def test_reference_shaped_core_detected(self):
        checks = audit.check_core(self.core)
        missing = [x for x in checks if x["status"] == "MISSING"]
        self.assertEqual(missing, [], missing)
        self.assertTrue(any(x["scope"] == "reset-risk" for x in checks))
        self.assertTrue(any("per-spec HasTalent" in x["detail"] for x in checks))

    def test_missing_critical_getter_fails_closed(self):
        file = self.core / audit.CORE_FILES["Player.h"]
        file.write_text(PLAYER.replace("GetTalentMap", "UnavailableMap"),
                        encoding="utf-8")
        result = audit.check_core(self.core)
        self.assertTrue(any(x["status"] == "MISSING" and
                            "const talent map" in x["detail"] for x in result))

    def test_unreadable_core_file_flags_missing(self):
        (self.core / audit.CORE_FILES["Chat.h"]).unlink()
        result = audit.check_core(self.core)
        self.assertTrue(any(x["status"] == "MISSING" and
                            "Chat.h is absent" in x["detail"] for x in result))

    def test_oversized_source_not_parsed(self):
        file = self.core / audit.CORE_FILES["Item.h"]
        self.assertIsNone(audit.read_text(file, max_bytes=2))

    def test_nested_playerbots_headers_are_located(self):
        bot = self.path / "playerbots"
        folder = bot / "src" / "Bot"
        folder.mkdir(parents=True)
        for name, methods in audit.PLAYERBOT_HEADERS.items():
            (folder / name).write_text(" ".join(
                "bool {}();".format(m) for m in methods), encoding="utf-8")
        self.assertTrue(all(x["status"] == "FOUND"
                            for x in audit.check_playerbots(bot)))

    def test_missing_random_bot_gate_fails(self):
        bot = self.path / "bot"
        bot.mkdir()
        found = audit.check_playerbots(bot)
        self.assertTrue(any(x["status"] == "MISSING" and
                            "RandomPlayerbotMgr.h" in x["detail"] for x in found))

    def test_ip_is_manual_semantic_review_even_when_header_exists(self):
        ip = self.path / "ip"
        ip.mkdir()
        absent = audit.check_ip(ip)
        self.assertEqual(absent[0]["status"], "REVIEW")
        (ip / "IndividualProgression.h").write_text(
            "class IndividualProgression;", encoding="utf-8")
        present = audit.check_ip(ip)
        self.assertEqual(present[0]["status"], "REVIEW")
        self.assertIn("stage 8/13", present[0]["detail"])

    def test_older_installed_naxxramas_is_review_not_false_compile_pass(self):
        module = self.path / "module"
        module.mkdir()
        self.assertEqual(audit.check_module(module)[0]["status"], "REVIEW")

    def test_git_calls_readonly_no_optional_locks_or_network(self):
        called = []
        def runner(args, **kwargs):
            called.append((args, kwargs))
            subcommand = args[4]
            output = {
                "rev-parse": "a" * 40 if args[-1] == "HEAD" else str(self.core),
                "status": "",
                "remote": "git@github.com:mod-playerbots/azerothcore-wotlk.git",
            }[subcommand]
            return SimpleNamespace(returncode=0, stdout=output, stderr="")
        info = audit.inspect_git(self.core, "core", runner=runner)
        self.assertEqual(info["head"], "a" * 40)
        self.assertFalse(info["dirty"])
        self.assertEqual(len(called), 4)
        for args, kw in called:
            self.assertEqual(args[:4], ["git", "--no-optional-locks",
                                        "-C", str(self.core)])
            self.assertEqual(kw["env"]["GIT_OPTIONAL_LOCKS"], "0")
            self.assertEqual(kw["env"]["GIT_TERMINAL_PROMPT"], "0")
            self.assertFalse(kw["check"])
            self.assertNotIn("shell", kw)

    def test_untracked_files_mark_git_checkout_dirty(self):
        def runner(args, **kwargs):
            name = args[4]
            value = (
                "b" * 40 if name == "rev-parse" and args[-1] == "HEAD"
                else str(self.core) if name == "rev-parse"
                else "?? untracked-custom-module.cpp"
            )
            if name == "status":
                self.assertIn("--untracked-files=normal", args)
            return SimpleNamespace(returncode=0, stdout=value, stderr="")
        info = audit.inspect_git(self.core, "core", runner=runner)
        self.assertTrue(info["dirty"])
        self.assertEqual(info["head"], "b" * 40)

    def test_bad_git_sha_not_accepted(self):
        def runner(args, **kwargs):
            name = args[4]
            value = ("short-hash" if args[-1] == "HEAD" else
                     str(self.core) if name == "rev-parse" else "")
            return SimpleNamespace(returncode=0, stdout=value, stderr="")
        self.assertIsNone(audit.inspect_git(
            self.core, "core", runner=runner)["head"])

    def test_existing_module_with_old_features_needs_manual_review(self):
        module = self.path / "module"
        source = module / "src" / "Systems" / "BotTalentImport.cpp"
        source.parent.mkdir(parents=True)
        source.write_text("void HandleSafetyPreview() {}\n", encoding="utf-8")
        findings = audit.check_module(module)
        self.assertTrue(any(x["status"] == "REVIEW" and
                            "PrintAltBotTalentMapIntegrity(" in x["detail"]
                            for x in findings))

    def test_no_findings_can_claim_runtime_compilation_verified(self):
        paths = {k: self.path / ("missing-" + k)
                 for k in ("core", "playerbots", "ip", "module")}
        report = audit.audit(paths)
        self.assertTrue(any("real C++ compilation NOT verified" in x["detail"]
                            for x in report["findings"]))
        self.assertTrue(any("no result permits talent Apply" in x["detail"]
                            for x in report["findings"]))

    def test_commented_out_core_api_is_missing_not_found(self):
        file = self.core / audit.CORE_FILES["Player.h"]
        file.write_text(PLAYER.replace(
            "bool HasTalent(uint32 spell_id, uint8 spec) const;",
            "// bool HasTalent(uint32 spell_id, uint8 spec) const;"),
            encoding="utf-8")
        self.assertTrue(any(
            x["status"] == "MISSING" and "per-spec HasTalent" in x["detail"]
            for x in audit.check_core(self.core)))

    def test_string_containing_fake_api_is_not_counted(self):
        file = self.core / audit.CORE_FILES["Player.h"]
        file.write_text(PLAYER.replace(
            "PlayerTalentMap const& GetTalentMap() const;",
            'char const* fake = "PlayerTalentMap const& GetTalentMap() const;";'),
            encoding="utf-8")
        self.assertTrue(any(
            x["status"] == "MISSING" and "const talent map" in x["detail"]
            for x in audit.check_core(self.core)))

    def test_reset_risk_never_borrowed_from_other_cpp_method(self):
        file = self.core / audit.CORE_FILES["Player.cpp"]
        source = PLAYER_CPP.replace("RemovePet(nullptr);", "/* no pet removal here */")
        file.write_text(source + "\nvoid Player::Unrelated() { RemovePet(nullptr); }\n",
                        encoding="utf-8")
        self.assertTrue(any(
            x["status"] == "MISSING" and "pet removal" in x["detail"]
            for x in audit.check_core(self.core)))

    def test_nested_reset_body_is_bounded(self):
        sample = ('bool Player::resetTalents(bool noCost) {'
                  'if (noCost) { RemovePet(nullptr); } return false; }'
                  'void Player::Unrelated() { SetCanTitanGrip(false); }')
        body = audit.function_body(
            sample, r"\bbool\s+Player::resetTalents\s*\([^)]*\)")
        self.assertIn("RemovePet(", body)
        self.assertNotIn("SetCanTitanGrip(", body)

    def test_fork_origin_family_is_classified_without_exposing_token(self):
        origin = "https://SECRET-CREDENTIAL@github.com/mod-playerbots/azerothcore-wotlk.git"
        self.assertEqual(audit.origin_family(origin), "PLAYERBOTS_FORK")
        self.assertEqual(audit.origin_family(
            "git@github.com:azerothcore/azerothcore-wotlk.git"),
            "STANDARD_AZEROTHCORE")
        self.assertEqual(audit.origin_family(
            "ssh://github.com/CosmicCuddle/private-core.git"),
            "CUSTOM_OR_OTHER")
        self.assertEqual(audit.origin_family(None), "UNKNOWN")
        self.assertNotIn("SECRET-CREDENTIAL", audit.origin_family(origin))

    def test_core_origin_is_review_when_standard_or_custom(self):
        for origin in ("STANDARD_AZEROTHCORE", "CUSTOM_OR_OTHER", "UNKNOWN"):
            paths = {"core": self.core,
                     "playerbots": self.path / "none-bot",
                     "ip": self.path / "none-ip",
                     "module": self.path / "none-module"}
            with mock.patch.object(audit, "inspect_git", return_value={
                "head": "c" * 40, "toplevel": str(self.core), "dirty": False,
                "origin_family": origin, "label": "core"}):
                report = audit.audit(paths)
            self.assertTrue(any(
                x["scope"] == "core-origin" and x["status"] == "REVIEW"
                for x in report["findings"]))

    def test_git_failures_do_not_invent_revision(self):
        def runner(args, **kwargs):
            raise FileNotFoundError("git unavailable")
        info = audit.inspect_git(self.core, "core", runner=runner)
        self.assertIsNone(info["head"])
        self.assertIsNone(info["dirty"])

    def test_symlinks_not_followed_during_header_search(self):
        bot = self.path / "bot"
        external = self.path / "external"
        bot.mkdir()
        external.mkdir()
        (external / "PlayerbotAI.h").write_text("GetMaster();", encoding="utf-8")
        (bot / "src").symlink_to(external, target_is_directory=True)
        self.assertEqual(audit.find_named_headers(bot, {"PlayerbotAI.h"}), {})

    def test_audit_fails_when_paths_missing_even_if_other_checks_good(self):
        paths = {k: self.path / ("missing-" + k)
                 for k in ("core", "playerbots", "ip", "module")}
        report = audit.audit(paths)
        self.assertTrue(report["failed"])
        self.assertEqual(len(report["repositories"]), 0)
        self.assertTrue(any(x["status"] == "MISSING" for x in report["findings"]))
        self.assertTrue(any(x["scope"] == "safety" for x in report["findings"]))

    def test_cli_json_is_stdout_only_and_missing_paths_exit_one(self):
        paths = ["--core", str(self.path / "missing-core"),
                 "--playerbots", str(self.path / "missing-bot"),
                 "--ip", str(self.path / "missing-ip"),
                 "--module", str(self.path / "missing-module"), "--json"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = audit.main(paths)
        self.assertEqual(code, 1)
        import json
        obj = json.loads(buffer.getvalue())
        self.assertTrue(obj["failed"])
        self.assertIn("findings", obj)

    def test_checker_source_contains_no_write_or_deployment_operations(self):
        source = (ROOT / "scripts" / "audit_nt1_dependency_apis.py").read_text(
            encoding="utf-8")
        for suspicious in (
            "write_text(", "mkdir(", "unlink(", "shutil.", "shell=True",
            "git pull", "git checkout", "git reset", "cmake --build",
            "mysql ", "CharacterDatabase.Query(",
        ):
            self.assertNotIn(suspicious, source)


if __name__ == "__main__":
    unittest.main()
