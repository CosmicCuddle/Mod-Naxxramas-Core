"""P6: Touch of the Grave reads Individual Progression settings only on the world thread.

Source contract; the maths and snapshot are tested natively in
touch_of_the_grave_settings_tests.cpp. Needs git history for BASE_MAIN.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE_MAIN = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CPP_PATH = "src/Racials/Forsaken/TouchOfTheGrave.cpp"
CPP = (ROOT / CPP_PATH).read_text()


def code(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def block(text, start_token):
    """Brace-matched block that starts at the first '{' after start_token."""
    at = text.index(start_token)
    open_at = text.index("{", at)
    depth = 0
    for i in range(open_at, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[at:i + 1]
    raise AssertionError(start_token)


def main_source(path):
    return subprocess.run(["git", "show", f"{BASE_MAIN}:{path}"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


class ConfigReadsOnlyOnWorldThread(unittest.TestCase):
    def test_sconfigmgr_only_inside_the_config_hook(self):
        c = code(CPP)
        hook = block(c, "void OnAfterConfigLoad(bool ) override")
        self.assertEqual(c.count("sConfigMgr"), hook.count("sConfigMgr"))
        self.assertEqual(hook.count("sConfigMgr->GetOption"), 6)

    def test_same_keys_types_and_defaults_as_before(self):
        hook = block(code(CPP), "void OnAfterConfigLoad(bool ) override")
        compact = re.sub(r"\s+", "", hook)
        for t, key, default in (
                ("bool", "IndividualProgression.Enable", "true"),
                ("uint8", "IndividualProgression.ProgressionLimit", "0"),
                ("float", "IndividualProgression.VanillaPowerAdjustment", "1.0f"),
                ("float", "IndividualProgression.TBCPowerAdjustment", "1.0f"),
                ("float", "IndividualProgression.VanillaHealingAdjustment", "1.0f"),
                ("float", "IndividualProgression.TBCHealingAdjustment", "1.0f")):
            with self.subTest(key=key):
                self.assertIn(f'sConfigMgr->GetOption<{t}>("{key}",{default})', compact)
                old = re.sub(r"\s+", "", code(main_source(CPP_PATH)))
                self.assertIn(f'sConfigMgr->GetOption<{t}>("{key}",{default})', old)
        self.assertIn("NaxxramasTouchOfTheGrave::Settings.Store(s);", hook)

    def test_hook_is_world_config_load_and_registered(self):
        c = code(CPP)
        self.assertIn("{ WORLDHOOK_ON_AFTER_CONFIG_LOAD }", c)
        reg = block(c, "void AddTouchOfTheGraveScripts()")
        self.assertIn("new NaxxramasTouchOfTheGraveConfig();", reg)
        self.assertIn("RegisterSpellScript(", reg)
        self.assertIn("new NaxxramasTouchOfTheGraveHealingScript();", reg)

    def test_power_and_healing_use_their_own_adjustments(self):
        c = re.sub(r"\s+", " ", code(CPP))
        self.assertIn("healing ? s.vanillaHealing : s.vanillaPower", c)
        self.assertIn("healing ? s.tbcHealing : s.tbcPower", c)
        self.assertIn("float GetPowerMultiplier(Player* player) { return GetMultiplier(player, false); }", c)
        self.assertIn("float GetHealingMultiplier(Player* player) { return GetMultiplier(player, true); }", c)


class EverythingElseUnchanged(unittest.TestCase):
    def test_damage_heal_and_progression_code_identical_to_main(self):
        old = code(main_source(CPP_PATH))
        new = code(CPP)
        for start in ("uint8 GetProgression(Player* player)",
                      "int32 GetDesiredDamage(uint8 level)",
                      "int32 CompensateAmount(",
                      "class spell_naxxramas_touch_of_the_grave : public SpellScript",
                      "class NaxxramasTouchOfTheGraveHealingScript : public UnitScript"):
            with self.subTest(block=start):
                self.assertEqual(block(new, start), block(old, start))

    def test_loader_and_config_untouched(self):
        for path in ("src/NaxxramasCore_loader.cpp", "conf/mod_naxxramas_core.conf.dist"):
            with self.subTest(path=path):
                self.assertEqual((ROOT / path).read_text(), main_source(path))

    def test_header_is_pure_standard_cpp(self):
        h = (ROOT / "src/Racials/Forsaken/TouchOfTheGraveSettings.h").read_text()
        self.assertEqual(re.findall(r"#include\s+(\S+)", h), ["<atomic>", "<cmath>", "<cstdint>"])
        for name in ("sConfigMgr", "Player", "ScriptMgr"):
            self.assertNotIn(name, code(h))


if __name__ == "__main__":
    unittest.main()
