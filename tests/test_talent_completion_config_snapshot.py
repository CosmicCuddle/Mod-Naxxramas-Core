"""P7: BotTalentCompletion reads its Enabled setting only on the world thread.

Enabled() runs every OnPlayerBeforeUpdate on map threads. Source contract
only; ConfigFlagSnapshot is tested natively. Needs git history for BASE_MAIN.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE_MAIN = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
PATH = "src/Systems/BotTalentCompletion.cpp"
CPP = (ROOT / PATH).read_text()


def code(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def main_source(path):
    return subprocess.run(["git", "show", f"{BASE_MAIN}:{path}"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


def block(text, start):
    at = text.index(start)
    open_at = text.index("{", at)
    depth = 0
    for i in range(open_at, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[at:i + 1]
    raise AssertionError(start)


class TalentCompletionConfigSnapshot(unittest.TestCase):
    def test_sconfigmgr_only_in_the_config_hook(self):
        c = code(CPP)
        hook = block(c, "void OnAfterConfigLoad(bool ) override")
        self.assertEqual(c.count("sConfigMgr"), 1)
        self.assertEqual(hook.count("sConfigMgr"), 1)
        compact = re.sub(r"\s+", "", hook)
        self.assertIn('sConfigMgr->GetOption<bool>("NaxxramasCore.BotTalentCompletion.Enabled",false)',
                      compact)
        self.assertIn("NaxxramasBotTalentCompletion::EnabledSetting.Store(", compact)
        old = re.sub(r"\s+", "", code(main_source(PATH)))
        self.assertIn('sConfigMgr->GetOption<bool>("NaxxramasCore.BotTalentCompletion.Enabled",false)', old)

    def test_enabled_reads_only_the_snapshot_and_defaults_off(self):
        c = code(CPP)
        self.assertIn("NaxxramasConfigSnapshot::Flag EnabledSetting{false};", c)
        self.assertEqual(re.sub(r"\s+", " ", block(c, "bool Enabled()")),
                         "bool Enabled() { return EnabledSetting.Load(); }")

    def test_hook_registered_before_the_player_script(self):
        reg = block(code(CPP), "void AddBotTalentCompletionScripts()")
        self.assertLess(reg.index("new NaxxramasCoreBotTalentCompletionConfig();"),
                        reg.index("new NaxxramasCoreBotTalentCompletion();"))
        self.assertIn("{ WORLDHOOK_ON_AFTER_CONFIG_LOAD }", code(CPP))

    def test_rest_of_file_identical_to_main(self):
        old = main_source(PATH)
        new = CPP
        new = new.replace('#include "ConfigFlagSnapshot.h"\n', "", 1)
        start = new.index("    // Read on the world thread by NaxxramasCoreBotTalentCompletionConfig;")
        end = new.index("    bool IsSupportedBot(Player* player)")
        old_start = old.index("    bool Enabled()")
        old_end = old.index("    bool IsSupportedBot(Player* player)")
        self.assertEqual(new[:start], old[:old_start])
        reg_new = new.index("// Startup and every .reload config; same key and default as before.")
        reg_old = old.index("void AddBotTalentCompletionScripts()")
        self.assertEqual(new[end:reg_new], old[old_end:reg_old])

    def test_loader_and_config_untouched(self):
        for path in ("src/NaxxramasCore_loader.cpp", "conf/mod_naxxramas_core.conf.dist"):
            with self.subTest(path=path):
                self.assertEqual((ROOT / path).read_text(), main_source(path))


if __name__ == "__main__":
    unittest.main()
