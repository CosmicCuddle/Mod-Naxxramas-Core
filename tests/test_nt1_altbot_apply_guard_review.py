"""Source + extracted C++ regression for a review-only NT1 Altbot hard stop.

This is NOT a Worldserver build, equipment-preservation proof or in-game Apply.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SRC = (Path(__file__).resolve().parents[1] / "src/Systems/BotTalentImport.cpp").read_text(encoding="utf-8")
READINESS = SRC.split("    bool CheckApplyReadiness(", 1)[1].split("    bool ApplyValidated(", 1)[0]
APPLY = SRC.split("    bool ApplyValidated(", 1)[1].split("    bool ReadArguments(", 1)[0]
RANDOM = "bool const randomBot = sRandomPlayerbotMgr.IsRandomBot(bot);"
SPEC = "uint8 const spec = bot->GetActiveSpec();"
PREFIX = APPLY.split(RANDOM, 1)[1].split(SPEC, 1)[0]
GUARD = "        " + RANDOM + PREFIX


class AltBotApplyResetGate(unittest.TestCase):
    def test_guard_precedes_every_mutation(self):
        self.assertIn("CheckApplyReadiness(issuer, bot, requested, error, &snapshot)", APPLY)
        self.assertRegex(PREFIX, r"if\s*\(!randomBot\)\s*\{[\s\S]*?return false;\s*\}")
        self.assertIn("zero-equipment-", PREFIX)
        self.assertEqual(APPLY.count(RANDOM), 1)
        self.assertLess(APPLY.index("CheckApplyReadiness(issuer, bot, requested, error, &snapshot)"), APPLY.index(RANDOM))
        for mutating in ("ImportScope const scope(bot)", "bot->resetTalents(true)",
                         "LearnValidated(bot, requested", "bot->SaveToDB(",
                         "CharacterDatabase.DirectExecute("):
            self.assertLess(APPLY.index("if (!randomBot)"), APPLY.index(mutating), mutating)

    def test_preflight_still_checks_ownership_era_offhand_pet_and_db(self):
        for required in ("CanApplyToAltBot(issuer, error)", "CanControlBot(issuer, bot,",
                         "CheckPlayerProgressionEra(issuer, requested.Progression, error)",
                         "EQUIPMENT_SLOT_OFFHAND", "bot->GetPet() != nullptr",
                         "CharacterDatabase.Query("):
            self.assertIn(required, READINESS, required)
        self.assertLess(APPLY.index("if (IsReadOnlyAccessMode())"), APPLY.index("if (!randomBot)"))

    def test_random_bot_legacy_flow_retained(self):
        self.assertIn("ImportScope const scope(bot)", APPLY)
        self.assertIn("if (LearnValidated(bot, requested, error))", APPLY)
        self.assertIn("bot->resetTalents(true)", APPLY)

    @unittest.skipUnless(shutil.which("g++"), "Requires C++ compiler")
    def test_extracted_production_cpp_denies_before_mutation(self):
        preamble = """
#include <cassert>
#include <string>
#include <iostream>
struct Bot { bool random; };
struct RandomManager {
    bool IsRandomBot(Bot* bot) const { return bot && bot->random; }
} sRandomPlayerbotMgr;
bool Attempt(Bot* bot, std::string& error, int& mutations)
{
"""
        suffix = """
    ++mutations;
    return true;
}
int main()
{
    Bot alt{false}, random{true};
    std::string err;
    int mutations=0;
    assert(!Attempt(&alt, err, mutations));
    assert(mutations==0);
    assert(err.find("zero-equipment") != std::string::npos);
    err.clear();
    assert(Attempt(&random, err, mutations));
    assert(mutations==1);
    assert(err.empty());
    std::cout << "PASS extracted original C++ reset guard\\n";
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nt1_guard.cpp"
            exe = Path(tmp) / "nt1_guard"
            path.write_text(preamble + GUARD + suffix, encoding="utf-8")
            compile_result = subprocess.run(
                ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 str(path), "-o", str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("PASS extracted original C++", run.stdout)


if __name__ == "__main__":
    unittest.main()
