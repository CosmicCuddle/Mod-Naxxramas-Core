#!/usr/bin/env python3
"""Generate a review-only, fail-closed first-test config from committed .conf.dist.

This never touches the owner's installed config or the repository config.
Usage:
  python3 scripts/check_first_controlled_test_build.py --output /tmp/naxx-test/mod_naxxramas_core.conf
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONF = ROOT / "conf/mod_naxxramas_core.conf.dist"

# Separate controlled feature pilots can change exactly ONE switch after
# dated/restorable backups, restore exercise and explicit owner approval.
# This baseline deliberately tests compilation and read-only behaviour only.
SAFE_SWITCHES = {
    "NaxxramasCore.HonorOverflow.Enabled": "0",
    "NaxxramasCore.HonorReset.Enabled": "0",
    "NaxxramasCore.ForcedPvP.Enabled": "0",
    "NaxxramasCore.ForcedPvP.Silithus": "0",
    "NaxxramasCore.ForcedPvP.EasternPlaguelands": "0",
    "NaxxramasCore.MeetingStones.ClassicMode.Enabled": "0",
    "NaxxramasCore.BotTalentImport.AccessMode": "0",
    "NaxxramasCore.BotTalentCompletion.Enabled": "0",
    "NaxxramasCore.ElementalInvasion.Enabled": "0",
    "NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled": "0",
    "NaxxramasCore.HallowsEnd.SoloFire.Enabled": "0",
    "NaxxramasCore.HallowsEnd.SoloFire.OneBucket": "0",
    "NaxxramasCore.HallowsEnd.SoloFire.DisableSpread": "0",
    "NaxxramasCore.BotConsumables.HunterAmmo.Enabled": "0",
    "NaxxramasCore.BotConsumables.HunterAmmo.AllowSelectedNonVendor": "0",
    "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled": "0",
    "NaxxramasCore.QuestLootProtection.Enabled": "0",
    "NaxxramasCore.QuestLootProtection.Debug": "0",
    "NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled": "0",
}
SAFE_LITERALS = {
    "NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName": '""',
    "NaxxramasCore.BotTalentImport.AltBotAllowedPlayers": '""',
}
SOURCE_REQUIREMENTS = {
    "src/Systems/HunterAmmoProvision.cpp": (
        "NaxxramasHunterAmmo", "TopUpHunterAmmo(", "CanStoreNewItem(", "GetItemCount(",
    ),
    "src/Systems/BotRaidConsumables.cpp": (
        "SupplyHunterAmmoForBot(", "PrepareHunter(", "PrepareDungeonBot(",
    ),
    "src/Systems/HonorOverflow.cpp": (
        "NaxxramasCore.HonorOverflow.Enabled", "StoreHonorSnapshot(",
    ),
    "src/Systems/QuestLootProtection.cpp": (
        "AddQuestLootProtectionScripts(", 
    ),
    "src/Systems/MeetingStoneProgression.cpp": (
        "NaxxramasCore.MeetingStones.ClassicMode.Enabled",
    ),
    "src/NaxxramasCore_loader.cpp": (
        "AddHonorOverflowScripts();", "AddBotRaidConsumablesScripts();",
        "AddQuestLootProtectionScripts();",
    ),
}

def active_lines(content: str, key: str):
    expression = re.compile(r"^(?P<prefix>[ \t]*" + re.escape(key) +
                            r"[ \t]*=[ \t]*)(?P<value>[^#\r\n]*?)(?P<tail>[ \t]*(?:#.*)?)$", re.M)
    return list(expression.finditer(content))

def replace_strict(content: str, key: str, value: str) -> str:
    positions = active_lines(content, key)
    if len(positions) != 1:
        raise ValueError(f"FAIL: expected one active config setting {key}, found {len(positions)}")
    m=positions[0]
    return content[:m.start()] + m.group("prefix") + value + m.group("tail") + content[m.end():]

def main(args):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=pathlib.Path,required=True)
    opts=parser.parse_args(args)
    destination=opts.output.resolve()
    # Prevent a CI user invoking a generator over repository or owner config.
    if destination == CONF or destination.is_relative_to(ROOT):
        raise ValueError("FAIL: output must be outside the checkout (review-only)")
    source=CONF.read_text(encoding="utf-8")
    required=set(SAFE_SWITCHES)|set(SAFE_LITERALS)
    for name,phrases in SOURCE_REQUIREMENTS.items():
        path=ROOT/name
        if not path.is_file():
            raise ValueError("FAIL: missing expected main-branch implementation "+name)
        content=path.read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in content:
                raise ValueError("FAIL: expected source anchor missing "+name+": "+phrase)
    # Record the source baseline is NOT all safe defaults.
    original_on={k for k in SAFE_SWITCHES
                 if active_lines(source,k) and active_lines(source,k)[0].group("value").strip()=="1"}
    assert {
      "NaxxramasCore.HonorOverflow.Enabled",
      "NaxxramasCore.HonorReset.Enabled",
      "NaxxramasCore.ForcedPvP.Enabled",
      "NaxxramasCore.MeetingStones.ClassicMode.Enabled"
    }.issubset(original_on), "main config default-ON features changed: re-audit"
    staged=source
    for key,value in {**SAFE_SWITCHES,**SAFE_LITERALS}.items():
        staged=replace_strict(staged,key,value)
    for key in sorted(required):
        matches=active_lines(staged,key)
        assert len(matches)==1, ("staged setting duplicated/missing",key)
        expected=SAFE_SWITCHES.get(key,SAFE_LITERALS.get(key))
        assert matches[0].group("value").strip()==expected, ("unsafe staged setting",key)
    # No unapproved race concealment can sneak into a "main" baseline:
    # F14 is only on separate draft PRs; NEVER synthesize F14 enablement.
    assert "NaxxramasCore.WhoListing.HideTbcRaces" not in staged
    assert "NaxxramasCore.F14" not in staged

    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(staged,encoding="utf-8")
    assert CONF.read_text(encoding="utf-8")==source, "source config was modified"
    print("PASS: first-build registered main source anchors verified (Hunter ammo, HonorOverflow, QuestLoot, Meeting Stones)")
    print("PASS: safe test template has all "+str(len(required))+" explicitly pinned OFF/empty settings")
    print("PASS: source config remains unchanged; review-only output OUTSIDE checkout")
    print("LIMIT: template is NOT installed or loaded; active server configuration and runtime are UNKNOWN")
    print("LIMIT: no DBC, SQL, backup restore, Playerbots/IP compatibility or in-game behavior tested")
    return 0

if __name__=="__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (AssertionError,ValueError,OSError) as exc:
        print("FAIL: "+str(exc))
        sys.exit(1)
