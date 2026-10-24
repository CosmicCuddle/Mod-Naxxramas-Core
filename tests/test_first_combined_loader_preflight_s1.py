"""Source-only first-combined-build loader/config safety preflight.

This is intentionally NOT an integration build or a functioning A02/A04 fix.
Run unittest for synthetic negative witnesses on the separated main-based PR.
Run --check-tree on a future actual integrated candidate; on main it MUST fail
because registrations for unmerged draft features have not yet been added.
No network/database/user files or upstream components are read.
"""
from collections import Counter
from pathlib import Path
import argparse
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "src/NaxxramasCore_loader.cpp"
CONFIG = ROOT / "conf/mod_naxxramas_core.conf.dist"

# Verbatim function declarations from protected main at 80e9de1 (24 Oct 2026).
# Preserve all of them; checking only new registrations risks dropping old ones.
BASELINE = (
    "AddWarriorRendFlurryScripts",
    "AddWarriorRendFlurryBotScripts",
    "AddWarriorImprovedRendScripts",
    "AddMageArcaneMomentumScripts",
    "AddWarlockWrackScripts",
    "AddWarlockWrackBotScripts",
    "AddShamanRockbiterScripts",
    "AddOrcBloodFuryScripts",
    "AddTrollBerserkingScripts",
    "AddBloodElfArcaneTorrentScripts",
    "AddTouchOfTheGraveScripts",
    "AddBrewfestDarkIronAttackScripts",
    "AddBrewfestSoberGossipScripts",
    "AddHallowsEndShadeOfTheHorsemanScripts",
    "AddElementalInvasionCalendarScripts",
    "AddNaxxramasItemSpellScripts",
    "AddBotTalentImportScripts",
    "AddHonorOverflowScripts",
    "AddHonorResetScripts",
    "AddForcedPvPScripts",
    "AddAltMailDelayScripts",
    "AddBotRaidConsumablesScripts",
    "AddBotTalentExpansionLimitsScripts",
    "AddBotTalentCompletionScripts",
    "AddMeetingStoneProgressionScripts",
    "AddBattlemasterQueueProgressionScripts",
    "AddNaxxramasEasternPlaguelandsTowerLockScripts",
    "AddQuestLootProtectionScripts",
    "AddBotGolemaggActionAuditScripts",
)
# All four are separately present exactly once in #120, #125, #127, #130.
# A04 #129 does not introduce a loader function and is NOT accepted as the
# owner's functional quest-loot correction merely because these pass.
EXTRAS = (
    "AddBotGolemaggReachGuardScripts",  # foundation #120
    "AddScarletMonasteryExitScripts",   # F12 #125
    "AddAtieshKarazhanPortalScripts",   # F13 #127
    "AddHunterPetAutocastScripts",      # A02 #130
)
# Require the actual new source translation units alongside loader registrations.
# A loader-only union can pass source registration tests while omitting a script
# implementation. Real compilation/linkage is still a separate mandatory stage.
IMPLEMENTATIONS = (
    ("src/Systems/BotGolemaggReachGuard.cpp", "AddBotGolemaggReachGuardScripts"),
    ("src/Systems/ScarletMonasteryExits.cpp", "AddScarletMonasteryExitScripts"),
    ("src/Systems/AtieshKarazhanPortal.cpp", "AddAtieshKarazhanPortalScripts"),
    ("src/Systems/HunterPetAutocast.cpp", "AddHunterPetAutocastScripts"),
)
REQUIRED_FLAGS = {
    "NaxxramasCore.QuestLootProtection.Enabled": "0",  # legacy OFF
    "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled": "0",
    "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled": "0",
    "NaxxramasCore.ScarletExits.Enabled": "0",
    "NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled": "0",
    "NaxxramasCore.HunterPetAutocast.RestoreHumanChain": "0",
}


def declarations(source):
    return re.findall(r"(?m)^[ \t]*void[ \t]+(Add\w+Scripts)\(\);[ \t]*$", source)


def registrations(source):
    marker = "void Addmod_naxxramas_coreScripts()"
    if source.count(marker) != 1:
        return []
    body = source.split(marker, 1)[1]
    return re.findall(r"(?m)^[ \t]*(Add\w+Scripts)\(\);[ \t]*$", body)


def loader_errors(source):
    d, c = Counter(declarations(source)), Counter(registrations(source))
    problems = []
    for name in BASELINE + EXTRAS:
        if d[name] != 1 or c[name] != 1:
            problems.append("%s: declarations=%d registrations=%d" % (name, d[name], c[name]))
    for name in sorted(set(d) | set(c)):
        if d[name] != 1 or c[name] != 1:
            msg = "%s: declarations=%d registrations=%d" % (name, d[name], c[name])
            if msg not in problems:
                problems.append(msg)
    return problems


def config_errors(source):
    failures = []
    for key, expected in REQUIRED_FLAGS.items():
        values = re.findall(r"(?m)^[ \t]*" + re.escape(key) +
                            r"[ \t]*=[ \t]*([^#\r\n]+)", source)
        if len(values) != 1 or values[0].strip() != expected:
            failures.append("%s: expected one default %s, got %r" % (key, expected, values))
    return failures


def implementation_errors(sources):
    """Check all new translation units, not merely their loader references."""
    errors = []
    for path, symbol in IMPLEMENTATIONS:
        source = sources.get(path)
        if not source:
            errors.append("%s: missing implementation for %s" % (path, symbol))
            continue
        definitions = re.findall(
            r"(?m)^[ \\t]*void[ \\t]+" + re.escape(symbol) + r"\\(\\)\\s*\\{", source)
        if len(definitions) != 1:
            errors.append("%s: expected one definition of %s, found %d" %
                          (path, symbol, len(definitions)))
    return errors


def tree_implementations():
    """Never fetch or mutate dependencies; read only our checked-out module."""
    return {path: (ROOT / path).read_text(encoding="utf-8")
            if (ROOT / path).is_file() else None
            for path, _symbol in IMPLEMENTATIONS}


def simulated_loader(main_source, extras=EXTRAS):
    marker = "void Addmod_naxxramas_coreScripts()"
    if main_source.count(marker) != 1 or not main_source.rstrip().endswith("}"):
        raise ValueError("Loader structure changed; do not synthesize it")
    decls = "".join("void %s();\n" % s for s in extras)
    result = main_source.replace(marker, decls + "\n" + marker, 1)
    before, last = result.rsplit("\n}", 1)
    return before + "".join("\n    %s();" % s for s in extras) + "\n}" + last


def simulated_config(main_source):
    new = [key + " = " + val for key, val in REQUIRED_FLAGS.items()
           if not re.search(r"(?m)^[ \t]*" + re.escape(key) + r"[ \t]*=", main_source)]
    return main_source + "\n" + "\n".join(new) + "\n"


class UnionContractModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = LOADER.read_text(encoding="utf-8")
        cls.conf = CONFIG.read_text(encoding="utf-8")
        cls.union = simulated_loader(cls.base)
        cls.config_union = simulated_config(cls.conf)

    def test_main_baseline_still_retains_all_original_symbols(self):
        d, c = Counter(declarations(self.base)), Counter(registrations(self.base))
        for name in BASELINE:
            self.assertEqual((d[name], c[name]), (1, 1), name)

    def test_complete_synthetic_union_passes(self):
        self.assertEqual(loader_errors(self.union), [])

    def test_complete_synthetic_implementation_set_passes(self):
        sources = {path: "void %s()\\n{\\n}\\n" % symbol
                   for path, symbol in IMPLEMENTATIONS}
        self.assertEqual(implementation_errors(sources), [])

    def test_missing_implementation_is_detected_even_with_loader_union(self):
        sources = {path: "void %s()\\n{\\n}\\n" % symbol
                   for path, symbol in IMPLEMENTATIONS}
        sources.pop("src/Systems/AtieshKarazhanPortal.cpp")
        self.assertEqual(loader_errors(self.union), [])
        self.assertIn("AtieshKarazhanPortal.cpp", "\\n".join(implementation_errors(sources)))

    def test_wrong_translation_unit_symbol_is_detected(self):
        sources = {path: "void %s()\\n{\\n}\\n" % symbol
                   for path, symbol in IMPLEMENTATIONS}
        sources["src/Systems/HunterPetAutocast.cpp"] = "void UnrelatedScript()\\n{\\n}\\n"
        self.assertIn("AddHunterPetAutocastScripts", "\\n".join(implementation_errors(sources)))

    def test_individual_branch_loader_is_not_a_combined_candidate(self):
        for extra in EXTRAS:
            with self.subTest(only=extra):
                self.assertTrue(loader_errors(simulated_loader(self.base, (extra,))))

    def test_dropping_foundation_is_detected(self):
        incomplete = simulated_loader(self.base, EXTRAS[1:])
        self.assertIn("AddBotGolemaggReachGuardScripts", "\n".join(loader_errors(incomplete)))

    def test_dropping_existing_audit_is_detected(self):
        mutant = self.union.replace("    AddBotGolemaggActionAuditScripts();", "", 1)
        self.assertIn("AddBotGolemaggActionAuditScripts", "\n".join(loader_errors(mutant)))

    def test_duplicate_registration_is_detected(self):
        mutant = self.union.replace(
            "    AddScarletMonasteryExitScripts();",
            "    AddScarletMonasteryExitScripts();\n    AddScarletMonasteryExitScripts();", 1)
        self.assertIn("AddScarletMonasteryExitScripts", "\n".join(loader_errors(mutant)))

    def test_duplicate_declaration_is_detected(self):
        mutant = self.union.replace("void AddAtieshKarazhanPortalScripts();",
                                   "void AddAtieshKarazhanPortalScripts();\n"
                                   "void AddAtieshKarazhanPortalScripts();", 1)
        self.assertIn("AddAtieshKarazhanPortalScripts", "\n".join(loader_errors(mutant)))

    def test_synthetic_config_union_preserves_default_off(self):
        self.assertEqual(config_errors(self.config_union), [])

    def test_config_duplicate_assignment_fails(self):
        mutant = self.config_union + "\nNaxxramasCore.HunterPetAutocast.RestoreHumanChain = 0\n"
        self.assertIn("RestoreHumanChain", "\n".join(config_errors(mutant)))

    def test_config_enabled_by_accident_fails(self):
        mutant = self.config_union.replace(
            "NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled = 0",
            "NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled = 1", 1)
        self.assertIn("Atiesh.VanillaOutdoorArrival.Enabled", "\n".join(config_errors(mutant)))

    def test_historical_gfpp_and_legacy_quest_flags_retained(self):
        for key in ("NaxxramasCore.QuestLootProtection.Enabled",
                    "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled"):
            self.assertIn(key + " = 0", self.config_union)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-tree", action="store_true",
                    help="Gate an ACTUAL integrated tree; must fail on main/source-only draft.")
    args = ap.parse_args()
    if args.check_tree:
        errors = loader_errors(LOADER.read_text(encoding="utf-8"))
        errors += config_errors(CONFIG.read_text(encoding="utf-8"))
        errors += implementation_errors(tree_implementations())
        for err in errors:
            print("BLOCKED: " + err)
        if errors:
            print("Not a combined candidate. NO deployment or test build authorised.")
            return 1
        print("Loader/default-config source gate PASS ONLY; still need CMake, pinned full link, "
              "functional A02/A04, reviews, owner backup/approval.")
        return 0
    result = unittest.main(module=__name__, argv=[sys.argv[0]], exit=False).result
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
