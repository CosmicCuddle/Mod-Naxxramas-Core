#!/usr/bin/env python3
"""PINNED IP Hunter pet reconciliation fixed-point precondition audit.

This does NOT implement IP, inspect live player stage, complete a delayed
event, prove human intent, change spells, or authorize any restoration.
It fails if the pinned source no longer matches our synthetic model.
"""
import argparse
from pathlib import Path


def check(ip_root):
    code = (ip_root / "src/IndividualProgressionSpells.cpp").read_text("utf-8")
    start = "void IndividualProgression::checkHunterPetSpells("
    end = "void IndividualProgression::checkWarlockPetSpells("
    assert code.count(start) == 1 and code.count(end) == 1
    scope = code.split(start, 1)[1].split(end, 1)[0]

    start_lambda = "auto reconcile = [pet, player]"
    first_family = 'if (familyName == "Wolf")'
    assert scope.count(start_lambda) == 1
    assert scope.count(first_family) == 1
    reconcile = scope.split(start_lambda, 1)[1].split(first_family, 1)[0]

    guards = (
        "if (!player || !player->IsInWorld() || !VanillaHunterPets)",
        "if (sIndividualProgression->isBotAccount(player))",
        "if (player->getClass() != CLASS_HUNTER)",
        "if (sIndividualProgression->hasPassedProgression(player, PROGRESSION_TBC_TIER_5))",
    )
    assert all(s in scope for s in guards), "IP eligibility guards changed"
    assert "std::rbegin(dummyIds)" in reconcile
    assert "std::rend(dummyIds)" in reconcile
    assert "if (player->HasSpell(*it))" in reconcile
    assert "keepId = *it - 600000;" in reconcile
    assert "if (id != keepId && pet->HasSpell(id))" in reconcile
    assert "pet->unlearnSpell(id, false, true);" in reconcile
    assert "if (keepId && !pet->HasSpell(keepId))" in reconcile
    assert "pet->learnSpell(keepId);" in reconcile

    positions = [
        reconcile.index("keepId = *it - 600000;"),
        reconcile.index("if (id != keepId && pet->HasSpell(id))"),
        reconcile.index("pet->unlearnSpell(id, false, true);"),
        reconcile.index("if (keepId && !pet->HasSpell(keepId))"),
        reconcile.index("pet->learnSpell(keepId);"),
    ]
    assert positions == sorted(positions), "IP rank mutation ordering changed"
    assert 'if (familyName == "Boar")' in scope
    assert "hasPassedProgression(player, PROGRESSION_PRE_TBC)" in scope

    print("PASS: selected dummy is reverse-order first learned dummy minus 600000.")
    print("PASS: IP only unlearns known ranks different from keepId.")
    print("PASS: IP learns keepId only when selected and currently missing.")
    print("GATE BLOCKED: theoretical per-family no-op is NOT an IP completion callback.")
    print("Frozen rank/stage inputs, actual human intent and pet identity are NOT proven.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=Path, required=True)
    args = parser.parse_args()
    check(args.ip.resolve())
