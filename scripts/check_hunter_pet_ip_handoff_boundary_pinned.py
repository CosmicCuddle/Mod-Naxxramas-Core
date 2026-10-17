#!/usr/bin/env python3
"""Source-only guard that no existing IP completion handoff has been proven.

This documents the exact source boundary, not a fake implementation.
"""
import argparse
from pathlib import Path


def check(ip):
    code = (ip / "src/IndividualProgressionSpells.cpp").read_text("utf-8")
    start = "class DelayedPetSpellCheck : public BasicEvent"
    stop = "class IndividualPlayerProgression_UnitScript"
    assert code.count(start) == 1
    scope = code.split(start, 1)[1].split(stop, 1)[0]

    assert "explicit DelayedPetSpellCheck(ObjectGuid ownerGuid, uint8 attempts = 0)" in scope
    assert "Player* player = ObjectAccessor::FindPlayer(_ownerGuid);" in scope
    assert "Pet* pet = player->GetPet();" in scope
    assert "_ownerGuid;" in scope
    # Current delayed event only captures owner identity and attempts;
    # a hypothetical future after-return callback needs the original
    # pet-instance identity and event generation, not petnumber alone.
    assert "_petGuid" not in scope
    assert "_petEventGeneration" not in scope

    assert "if (pet->isBeingLoaded() && _attempts < 10)" in scope
    assert "new DelayedPetSpellCheck(_ownerGuid, _attempts + 1)" in scope
    assert 'pet->CustomData.GetDefault<PendingPetSpellCheck>(PENDING_CHECK_KEY)->pending = false;' in scope
    marker = "pet->CustomData.GetDefault<PendingPetSpellCheck>(PENDING_CHECK_KEY)->pending = false;"
    actual = "sIndividualProgression->checkHunterPetSpells(player);"
    assert scope.index(marker) < scope.index(actual)
    assert "return true;" in scope
    assert "OnHunterPetSpellsReconciled" not in scope
    assert "AfterHunterPetReconciliation" not in scope
    print("PASS: IP delayed event uses owner GUID, not a pet-instance token.")
    print("PASS: IP clears private pending flag BEFORE running Hunter reconciliation.")
    print("BLOCKED: no authenticated post-IP-return handoff exists for Naxx Core.")
    print("A hypothetical trusted callback must validate owner, Pet object, generation and outcome.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=Path, required=True)
    args = parser.parse_args()
    check(args.ip.resolve())
