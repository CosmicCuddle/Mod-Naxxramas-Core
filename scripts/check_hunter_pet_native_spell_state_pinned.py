#!/usr/bin/env python3
"""Read-only pinned upstream core/IP Hunter pet autocast loss-path proof.

This validates source ordering and native storage behavior. It cannot
establish that a particular owner's live pet lost any particular spell,
or whether a saved disabled value came from player intent.
"""
import argparse
from pathlib import Path


def part(code, a, b):
    assert code.count(a) == 1, "Expected unique pinned source: " + a
    return code.split(a, 1)[1].split(b, 1)[0]


def check(core, ip):
    code = (core / "src/server/game/Entities/Pet/Pet.cpp").read_text("utf-8")
    added = part(code, "bool Pet::addSpell(", "bool Pet::learnSpell(")
    assert "if (active == ACT_DECIDE)" in added
    assert "spellInfo->IsAutocastable()" in added
    assert "newspell.active = ACT_DISABLED;" in added
    assert "newspell.active = ACT_PASSIVE;" in added
    assert "newspell.active = petSpell.active;" in added, (
        "Rank upgrade inheritance path changed")
    assert "ToggleAutocast(spellInfo, (newspell.active == ACT_ENABLED));" in added

    learned = part(code, "bool Pet::learnSpell(", "void Pet::InitLevelupSpellsForLevel()")
    assert "if (!addSpell(spell_id))" in learned

    removed = part(code, "bool Pet::removeSpell(", "void Pet::CleanupActionBar()")
    assert "m_spells.erase(itr);" in removed
    assert "itr->second.state = PETSPELL_REMOVED;" in removed
    assert "RemoveSpellFromActionBar(spell_id)" in removed

    saved = part(code, "void Pet::_SaveSpells(", "void Pet::_LoadAuras(")
    assert "CHAR_DEL_PET_SPELLS" in saved
    assert "CHAR_INS_PET_SPELL" in saved
    assert "stmt->SetData(2, itr->second.active);" in saved
    assert "pet numbers are recycled" in saved
    loaded = part(code, "void Pet::_LoadSpells(", "void Pet::_SaveSpells(")
    assert "ActiveStates(fields[1].Get<uint8>())" in loaded

    toggled = part(code, "void Pet::ToggleAutocast(", "bool Pet::IsPermanentPetFor(")
    assert "itr->second.active = ACT_ENABLED;" in toggled
    assert "itr->second.active = ACT_DISABLED;" in toggled
    assert "m_autospells.push_back(spellInfo->Id);" in toggled

    ip_code = (ip / "src/IndividualProgressionSpells.cpp").read_text("utf-8")
    reconcile = part(ip_code,
                     "void IndividualProgression::checkHunterPetSpells(",
                     "void IndividualProgression::checkWarlockPetSpells(")
    assert "if (!player || !player->IsInWorld() || !VanillaHunterPets)" in reconcile
    assert "if (sIndividualProgression->isBotAccount(player))" in reconcile
    assert "pet->unlearnSpell(id, false, true);" in reconcile
    assert "if (keepId && !pet->HasSpell(keepId))" in reconcile
    assert "pet->learnSpell(keepId);" in reconcile
    assert (reconcile.index("pet->unlearnSpell(id, false, true);") <
            reconcile.index("pet->learnSpell(keepId);")), (
        "IP removal/relearning source order changed")

    print("PASS: native spell active flags are stored and reloaded per learned spell.")
    print("PASS: fresh autocast-capable addSpell uses ACT_DISABLED by default.")
    print("PASS: higher-rank replacement can inherit existing active state.")
    print("PASS: IP may unlearn unwanted ranks BEFORE relearning legal keepId.")
    print("BLOCKED: default disabled is NOT proof of deliberate user OFF.")
    print("Source evidence only; no pet mutating, no character DB access.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--ip", type=Path, required=True)
    args = parser.parse_args()
    check(args.core.resolve(), args.ip.resolve())
