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
    "NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName": '""',
    "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Debug": "0",
    "NaxxramasCore.BotConsumables.CrossMapAuraSafety": "0",
    "NaxxramasCore.ScarletExits.Enabled": "0",
    "NaxxramasCore.ScarletExits.RouteDungeonFinderExits": "0",
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


# A04 #129 is only a hypothesis, NOT a required first-test fix. If a
# future integration deliberately includes its separate experimental switch,
# keep it OFF. Importing its production reader without its config declaration
# is also a mismatch; do not silently permit a half-integrated candidate.
OPTIONAL_A04_KEY = "NaxxramasCore.QuestLootProtection.RestrictHiddenOrdinarySlots"


def optional_a04_errors(config, quest_source):
    present = OPTIONAL_A04_KEY in quest_source
    assignments = re.findall(
        r"(?m)^[ \\t]*" + re.escape(OPTIONAL_A04_KEY) +
        r"[ \\t]*=[ \\t]*([^#\\r\\n]+)", config)
    if not present and not assignments:
        return []
    if len(assignments) != 1 or assignments[0].strip() != "0":
        return ["%s: expected one default 0 when A04 pilot source/config is present, got %r" %
                (OPTIONAL_A04_KEY, assignments)]
    if not present:
        return ["%s: config present without corresponding A04 pilot reader" %
                OPTIONAL_A04_KEY]
    return []


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
            r"(?m)^[ \t]*void[ \t]+" + re.escape(symbol) + r"\(\)\s*\{", source)
        if len(definitions) != 1:
            errors.append("%s: expected one definition of %s, found %d" %
                          (path, symbol, len(definitions)))
    return errors


def tree_implementations():
    """Never fetch or mutate dependencies; read only our checked-out module."""
    return {path: (ROOT / path).read_text(encoding="utf-8")
            if (ROOT / path).is_file() else None
            for path, _symbol in IMPLEMENTATIONS}


def strip_draft_loader_extras(source):
    """Independent synthetic baseline from either main or an assembled union.

    Remove only exact complete declaration/call lines for the four draft
    registrations. This prevents the model double-appending on a real union.
    --check-tree always inspects the unmodified actual source instead.
    """
    extra_lines = set()
    for name in EXTRAS:
        extra_lines.add("void %s();" % name)
        extra_lines.add("%s();" % name)
    return "\n".join(line for line in source.split("\n")
                     if line.strip() not in extra_lines)


def gfpp_timer_errors(source):
    needle = "NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};"
    count = source.count(needle)
    return [] if count == 1 else [
        "BotRaidConsumables.cpp: expected one 120-second GFPP one-shot, found %d" % count
    ]


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
        cls.base = strip_draft_loader_extras(LOADER.read_text(encoding="utf-8"))
        cls.conf = CONFIG.read_text(encoding="utf-8")
        cls.union = simulated_loader(cls.base)
        cls.config_union = simulated_config(cls.conf)

    def test_main_baseline_still_retains_all_original_symbols(self):
        d, c = Counter(declarations(self.base)), Counter(registrations(self.base))
        for name in BASELINE:
            self.assertEqual((d[name], c[name]), (1, 1), name)

    def test_model_is_idempotent_on_preintegrated_loader(self):
        # Synthetic insertion leaves harmless blank lines. Compare the
        # actual declarations and call order, not whitespace in C++ text.
        stripped = strip_draft_loader_extras(self.union)
        self.assertEqual(declarations(stripped), declarations(self.base))
        self.assertEqual(registrations(stripped), registrations(self.base))
        reassembled = simulated_loader(stripped)
        self.assertEqual(loader_errors(reassembled), [])
        self.assertEqual(declarations(reassembled), declarations(self.union))
        self.assertEqual(registrations(reassembled), registrations(self.union))

    def test_all_hazardous_integration_flags_are_default_off(self):
        self.assertEqual(config_errors(self.config_union), [])
        for key in (
            "NaxxramasCore.ScarletExits.RouteDungeonFinderExits",
            "NaxxramasCore.BotConsumables.CrossMapAuraSafety",
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName",
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Debug",
        ):
            self.assertIn(key, REQUIRED_FLAGS)
            self.assertIn(key + " = " + REQUIRED_FLAGS[key], self.config_union)

    def test_dungeon_finder_flag_accidentally_enabled_is_detected(self):
        mutant = self.config_union.replace(
            "NaxxramasCore.ScarletExits.RouteDungeonFinderExits = 0",
            "NaxxramasCore.ScarletExits.RouteDungeonFinderExits = 1", 1)
        self.assertIn("RouteDungeonFinderExits", "\n".join(config_errors(mutant)))

    def test_golemagg_allowlist_accidentally_populated_is_detected(self):
        mutant = self.config_union.replace(
            'NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName = ""',
            'NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName = "Someone"', 1)
        self.assertIn("AllowedBotName", "\n".join(config_errors(mutant)))

    def test_optional_a04_switch_absent_does_not_block_first_union(self):
        self.assertEqual(optional_a04_errors(self.config_union, ""), [])

    def test_optional_a04_switch_included_off_is_allowed(self):
        cfg = self.config_union + "\\n" + OPTIONAL_A04_KEY + " = 0\\n"
        reader = 'sConfigMgr->GetOption<bool>("' + OPTIONAL_A04_KEY + '", false);'
        self.assertEqual(optional_a04_errors(cfg, reader), [])

    def test_optional_a04_switch_on_duplicate_or_unpaired_fails(self):
        reader = 'sConfigMgr->GetOption<bool>("' + OPTIONAL_A04_KEY + '", false);'
        off = self.config_union + "\\n" + OPTIONAL_A04_KEY + " = 0\\n"
        enabled = self.config_union + "\\n" + OPTIONAL_A04_KEY + " = 1\\n"
        for config, source in (
            (enabled, reader),
            (self.config_union, reader),
            (off + OPTIONAL_A04_KEY + " = 0\\n", reader),
            (off, ""),
        ):
            with self.subTest(config=config[-90:], source=bool(source)):
                self.assertIn(OPTIONAL_A04_KEY, "\\n".join(
                    optional_a04_errors(config, source)))

    def test_120_second_gfpp_timer_gate_rejects_90_seconds(self):
        valid = "NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};"
        self.assertEqual(gfpp_timer_errors(valid), [])
        self.assertIn("120-second GFPP", "\n".join(
            gfpp_timer_errors("NaxxramasOneShotTimer Timer{90 * IN_MILLISECONDS};")))
        self.assertTrue(gfpp_timer_errors(valid + "\n" + valid))

    def test_complete_synthetic_union_passes(self):
        self.assertEqual(loader_errors(self.union), [])

    def test_complete_synthetic_implementation_set_passes(self):
        sources = {path: "void %s()\n{\n}\n" % symbol
                   for path, symbol in IMPLEMENTATIONS}
        self.assertEqual(implementation_errors(sources), [])

    def test_missing_implementation_is_detected_even_with_loader_union(self):
        sources = {path: "void %s()\n{\n}\n" % symbol
                   for path, symbol in IMPLEMENTATIONS}
        sources.pop("src/Systems/AtieshKarazhanPortal.cpp")
        self.assertEqual(loader_errors(self.union), [])
        self.assertIn("AtieshKarazhanPortal.cpp", "\n".join(implementation_errors(sources)))

    def test_wrong_translation_unit_symbol_is_detected(self):
        sources = {path: "void %s()\n{\n}\n" % symbol
                   for path, symbol in IMPLEMENTATIONS}
        sources["src/Systems/HunterPetAutocast.cpp"] = "void UnrelatedScript()\n{\n}\n"
        self.assertIn("AddHunterPetAutocastScripts", "\n".join(implementation_errors(sources)))

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
        gfpp = ROOT / "src/Systems/BotRaidConsumables.cpp"
        errors += gfpp_timer_errors(gfpp.read_text(encoding="utf-8") if gfpp.is_file() else "")
        quest_source = ROOT / "src/Systems/QuestLootProtection.cpp"
        errors += optional_a04_errors(
            CONFIG.read_text(encoding="utf-8"),
            quest_source.read_text(encoding="utf-8") if quest_source.is_file() else "")
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
