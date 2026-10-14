"""Require a conservative, pinned and non-deploying Worldserver link gate.

These are structural workflow checks only. The actual compile/link runs
on a disposable GitHub runner and its status must be independently reviewed.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" /
            "nt1-pinned-worldserver-link.yml").read_text(encoding="utf-8")
NT1 = (ROOT / "src" / "Systems" /
       "BotTalentImport.cpp").read_text(encoding="utf-8")


class PinnedWorldserverLinkContractTests(unittest.TestCase):
    def test_uses_exact_pinned_dependencies(self):
        for ref in (
            "b7f06a16ac7120b5abc2e8d3f96a94265a363224",
            "037c01418b5d01506917a3db9b44fd56ac5f965c",
            "283abe12774801e5671da746ea8bf535cc0252e0",
        ):
            self.assertIn("ref: " + ref, WORKFLOW)
            self.assertIn('= "' + ref + '"', WORKFLOW)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", WORKFLOW)
        self.assertIn('rev-parse HEAD)" = "${{ github.event.pull_request.head.sha || github.sha }}"', WORKFLOW)

    def test_compiles_fully_linked_worldserver_not_just_syntax(self):
        for token in (
            "cmake -S acore -B acore-build -G Ninja",
            "-DMODULES=static",
            "-DSCRIPTS=static",
            "-DAPPS_BUILD=world-only",
            "cmake --build acore-build --target worldserver --parallel 2",
            "find acore-build -type f -name worldserver",
            "file \"$binary\"",
        ):
            self.assertIn(token, WORKFLOW)
        self.assertIn('grep -aFq "NT1 ACTIVE TALENT MATCH: EXACT"', WORKFLOW)
        self.assertIn('grep -aFq "Alt Bot NT1 Apply blocked: an offhand item is"', WORKFLOW)
        self.assertNotIn("-fsyntax-only", WORKFLOW)

    def test_no_live_database_or_runtime_operations(self):
        run_lines = re.sub(r"(?m)^\s*#.*$", "", WORKFLOW)
        for token in (
            "mysqldump", "mysql --", "mysql -u",
            ".naxxbot talents apply",
            "systemctl", "git push", "git pull", "DROP TABLE",
            "deploy:", "upload-artifact", "download-artifact",
        ):
            self.assertNotIn(token, run_lines)
        # Do not mistake the compiler's "worldserver --parallel" target flag
        # for a command starting a game server.
        self.assertNotRegex(
            run_lines, r"(?m)^\s*(?:\./)?worldserver(?:\s|$)"
        )
        self.assertIn("persist-credentials: false", WORKFLOW)

    def test_build_isolated_from_server_and_missing_build_fails(self):
        self.assertIn("runs-on: ubuntu-24.04", WORKFLOW)
        self.assertIn("timeout-minutes: 100", WORKFLOW)
        self.assertIn('if [[ -z "$binary" || ! -s "$binary" || ! -x "$binary" ]]', WORKFLOW)
        self.assertIn("exit 1", WORKFLOW)
        self.assertIn("No Worldserver startup", WORKFLOW)

    def test_existing_equipment_and_mode_protections_unchanged(self):
        readiness = NT1.split("    bool CheckApplyReadiness(", 1)[1].split(
            "    bool ApplyValidated(", 1
        )[0]
        apply = NT1.split("    bool ApplyValidated(", 1)[1].split(
            "    bool ReadArguments(", 1
        )[0]
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", readiness)
        self.assertIn("bot->GetPet() != nullptr", readiness)
        self.assertIn("CanApplyToAltBot(issuer, error)", readiness)
        self.assertIn("CheckPlayerProgressionEra(issuer, requested.Progression, error)", readiness)
        self.assertIn("IsReadOnlyAccessMode()", apply)
        self.assertEqual(apply.count("bot->resetTalents(true);"), 2)


if __name__ == "__main__":
    unittest.main()
