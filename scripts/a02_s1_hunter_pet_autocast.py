"""Source-faithful model and citation pins for A02 S1.

This module does not restore pet autocast, does not talk to a database, and
does not claim in-game behaviour. The model restates control flow that was
read at the pinned SHAs. Tests use it so a later edit cannot quietly turn
"explicit ON is lost" into "explicit ON is copied" without a failing test.
"""

from __future__ import annotations

import hashlib
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

CORE_REPO = "Grimfeather/azerothcore-wotlk"
IP_REPO = "Grimfeather/mod-individual-progression"
PLAYERBOTS_REPO = "mod-playerbots/mod-playerbots"

CORE_OLD = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
CORE_NEW = "8daffdabe9202c228e45d833c9a1d399597a15cd"
IP_SHA = "4ff4b5fcc1480348f058c632573143e62d4e3a41"
PLAYERBOTS_SHA = "037c01418b5d01506917a3db9b44fd56ac5f965c"

# Byte-identical at both core SHAs. Recorded from the local checkouts on
# 2026-10-20. The citation checker recomputes them.
PET_CPP_SHA256 = "825a9d66238d3dc2a3f5d8cb700b241b4c8b2e613aa030c78a9e31809ce1a356"
IP_SPELLS_SHA256 = "8ed6792bacf80a5c7fa23b05142f48f90ae71c9f069862a6c151c90e7d9f8456"

ACT_PASSIVE = 0x01
ACT_DISABLED = 0x81
ACT_ENABLED = 0xC1
ACT_DECIDE = 0x00

# Real PetScript hook enum at both pinned cores. No other PetScript hook exists.
PET_SCRIPT_HOOKS = (
    "OnInitStatsForLevel",
    "OnCalculateMaxTalentPointsForLevel",
    "CanUnlearnSpellSet",
    "CanUnlearnSpellDefault",
    "CanResetTalents",
    "OnPetAddToWorld",
)

# Ordered events for one saved-pet summon. Names in this list are either a
# real ScriptMgr hook or a core/IP step. Nothing in PET_SCRIPT_HOOKS sits
# between the two IP steps.
SUMMON_EVENT_ORDER = (
    "OnPlayerBeforeLoadPetFromDB",
    "OnPlayerBeforeGuardianInitStatsForLevel",
    "OnInitStatsForLevel",
    "OnPlayerAfterGuardianInitStatsForLevel",
    "OnPetAddToWorld",
    "async_callback_starts",
    "OnCalculateMaxTalentPointsForLevel_before_spells",
    "_LoadSpells",
    "OnCalculateMaxTalentPointsForLevel_after_spells",
    "InitLevelupSpellsForLevel",
    "CleanupActionBar",
    "PetSpellInitialize",
    "m_loading_false",
    "ip_delayed_event_unlearn",
    "ip_delayed_event_learn",
)

GROWL_IDS = (2649, 14916, 14917, 14918, 14919, 14920, 14921, 27047, 61676)
EXPECTED_FAMILY_COUNT = 26
EXPECTED_ACTIVE_RECONCILES = 89
EXPECTED_COMMENTED_RECONCILES = 22

# (repo, sha, path, 1-based line, exact substring of that line)
CITATIONS = (
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 118, "sScriptMgr->OnPetAddToWorld(this);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 241, "OnPlayerBeforeLoadPetFromDB"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 408, "LoadPetActionBar(petInfo->ActionBar)"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 416, "AddQueryHolderCallback"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 435, "_LoadSpells(holder.GetPreparedResult(PetLoadQueryHolder::SPELLS))"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 439, "InitLevelupSpellsForLevel()"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 446, "CleanupActionBar()"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 496, "m_loading = false;"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 510, "if (!owner || m_loading || !GetEntry() || !isControlled())"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 536, "_SaveSpells(trans);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1567, "ActiveStates(fields[1].Get<uint8>()"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1574, "pet numbers are recycled"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1597, "itr->second.active"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1812, "spellInfo->IsAutocastable()"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1813, "newspell.active = ACT_DISABLED;"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1855, "newspell.active = petSpell.active;"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1860, "unlearnSpell(spellID, false, false);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1865, "return false;"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1889, "ToggleAutocast(spellInfo, (newspell.active == ACT_ENABLED))"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1906, "if (!addSpell(spell_id))"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1930, "CanUnlearnSpellSet"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 1934, "learnSpell(itr->second);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 2013, "RemoveSpellFromActionBar"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 2036, "ab->GetType() == ACT_ENABLED"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 2251, "if (!spellInfo->IsAutocastable())"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 2268, "itr->second.active = ACT_ENABLED;"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp", 2281, "itr->second.active = ACT_DISABLED;"),
    (CORE_REPO, CORE_NEW, "src/server/game/Entities/Pet/Pet.cpp", 1567, "ActiveStates(fields[1].Get<uint8>()"),
    (CORE_REPO, CORE_NEW, "src/server/game/Entities/Pet/Pet.cpp", 1855, "newspell.active = petSpell.active;"),
    (CORE_REPO, CORE_NEW, "src/server/game/Entities/Pet/Pet.cpp", 1930, "CanUnlearnSpellSet"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.h", 62, "ACT_DISABLED = 0x81"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.h", 63, "ACT_ENABLED  = 0xC1"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.h", 66, "ACT_DECIDE   = 0x00"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.cpp", 164, "GetFirstSpellInChain(action) == first_id"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.cpp", 166, "PetActionBar[i].SetAction(spell_id);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.cpp", 183, "autocastable ? ACT_DISABLED : ACT_PASSIVE"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.cpp", 219, "GetFirstSpellInChain(action) == first_id"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.cpp", 221, "SetActionBar(i, 0, ACT_DISABLED);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Unit/CharmInfo.cpp", 297, "SetType(state ? ACT_ENABLED : ACT_DISABLED);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Handlers/PetHandler.cpp", 801, "ToggleAutocast(spellInfo, true);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Handlers/PetHandler.cpp", 819, "ToggleAutocast(spellInfo, false);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Handlers/PetHandler.cpp", 1003, "summon->ToggleAutocast(spellInfo, packet.AutocastEnabled);"),
    (CORE_REPO, CORE_OLD, "src/server/game/Handlers/PetHandler.cpp", 1007, "charmInfo->SetSpellAutocast(spellInfo, packet.AutocastEnabled);"),
    (CORE_REPO, CORE_OLD, "src/server/database/Database/Implementation/CharacterDatabase.cpp", 575, "SELECT spell, active FROM pet_spell WHERE guid = ?"),
    (CORE_REPO, CORE_OLD, "src/server/database/Database/Implementation/CharacterDatabase.cpp", 581, "INSERT INTO pet_spell (guid, spell, active)"),
    (CORE_REPO, CORE_OLD, "src/server/game/Spells/SpellInfo.cpp", 1150, "SPELL_ATTR0_PASSIVE"),
    (CORE_REPO, CORE_OLD, "src/server/game/Spells/SpellInfo.cpp", 1152, "SPELL_ATTR1_NO_AUTOCAST_AI"),
    (CORE_REPO, CORE_NEW, "src/server/game/Spells/SpellInfo.cpp", 1150, "SPELL_ATTR0_PASSIVE"),
    (CORE_REPO, CORE_NEW, "src/server/game/Spells/SpellInfo.cpp", 1152, "SPELL_ATTR1_NO_AUTOCAST_AI"),
    (CORE_REPO, CORE_OLD, "src/server/game/Scripting/ScriptDefines/PetScript.h", 28, "PETHOOK_CAN_UNLEARN_SPELL_SET"),
    (CORE_REPO, CORE_OLD, "src/server/game/Scripting/ScriptDefines/PetScript.h", 31, "PETHOOK_ON_PET_ADD_TO_WORLD"),
    (CORE_REPO, CORE_OLD, "src/server/game/Scripting/ScriptDefines/PetScript.h", 32, "PETHOOK_END"),
    (CORE_REPO, CORE_NEW, "src/server/game/Scripting/ScriptDefines/PetScript.h", 32, "PETHOOK_END"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Player/Player.cpp", 3428, "OnPlayerCanLearnSpell"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Player/Player.cpp", 3443, "OnPlayerLearnSpell"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Player/Player.cpp", 9796, "itr->second.active"),
    (CORE_REPO, CORE_OLD, "src/server/game/AI/CoreAI/PetAI.cpp", 247, "GetPetAutoSpellSize()"),
    (CORE_REPO, CORE_OLD, "src/server/game/Globals/ObjectMgr.cpp", 8104, "void ObjectMgr::LoadPetNumber()"),
    (CORE_REPO, CORE_OLD, "src/server/game/Globals/ObjectMgr.cpp", 8108, "SELECT MAX(id) FROM character_pet"),
    (CORE_REPO, CORE_NEW, "src/server/game/Globals/ObjectMgr.cpp", 8117, "void ObjectMgr::LoadPetNumber()"),
    (CORE_REPO, CORE_NEW, "src/server/game/Globals/ObjectMgr.cpp", 8121, "SELECT MAX(id) FROM character_pet"),
    (CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.h", 121, "PetSpellMap     m_spells;"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 41, "isBotAccount(player)"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 47, "PROGRESSION_TBC_TIER_5"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 50, "Pet* pet = player->GetPet();"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 78, "keepId = *it - 600000;"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 86, "pet->unlearnSpell(id, false, true);"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 90, "pet->learnSpell(keepId);"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 1276, "OnPetAddToWorld"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 1286, "CalculateTime(200)"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 1315, "ObjectGuid ownerGuid"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 1324, "Pet* pet = player->GetPet();"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 1330, "_attempts < 10"),
    (IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp", 1339, "pending = false;"),
    (IP_REPO, IP_SHA, "src/IndividualProgression.cpp", 360, "std::regex_match(accountName, botAccountsRegex)"),
    (IP_REPO, IP_SHA, "src/IndividualProgression.cpp", 1028, "IndividualProgression.VanillaHunterPets"),
    (IP_REPO, IP_SHA, "src/IndividualProgression.cpp", 1070, '^RNDBOT.*'),
    (PLAYERBOTS_REPO, PLAYERBOTS_SHA, "src/Ai/Base/Actions/PetsAction.cpp", 342, "TogglePetSpellAutoCastAction::Execute"),
    (PLAYERBOTS_REPO, PLAYERBOTS_SHA, "src/Ai/Base/Actions/PetsAction.cpp", 395, "pet->ToggleAutocast(spellInfo, shouldApply);"),
)


@dataclass
class KnownSpell:
    spell_id: int
    chain: int
    autocastable: bool
    active: int
    state: str = "unchanged"


@dataclass
class BarSlot:
    action: int = 0
    kind: int = ACT_PASSIVE
    chain: int = 0


@dataclass
class SavedPet:
    pet_number: int
    spells: dict[int, KnownSpell] = field(default_factory=dict)
    autospells: list[int] = field(default_factory=list)
    bar: list[BarSlot] = field(default_factory=list)

    def __post_init__(self):
        if not self.bar:
            self.bar = [BarSlot() for _ in range(10)]


def _toggle(pet: SavedPet, spell: KnownSpell, apply: bool) -> None:
    """Pet::ToggleAutocast. A false apply is a no-op when the id is absent."""
    if not spell.autocastable:
        return
    present = spell.spell_id in pet.autospells
    if apply and not present:
        pet.autospells.append(spell.spell_id)
        spell.active = ACT_ENABLED
    elif (not apply) and present:
        pet.autospells.remove(spell.spell_id)
        spell.active = ACT_DISABLED


def learn_with_rank_inheritance(pet: SavedPet, spell: KnownSpell) -> str:
    """Pet::addSpell rank branch plus the following ToggleAutocast.

    Returns "copied", "default_off", "default_passive", or "rejected_lower".
    """
    for old in list(pet.spells.values()):
        if old.chain != spell.chain or old.spell_id == spell.spell_id:
            continue
        if spell.spell_id > old.spell_id:
            spell.active = old.active
            if spell.active == ACT_ENABLED:
                _toggle(pet, old, False)
            _unlearn(pet, old.spell_id, clear_bar=False)
            pet.spells[spell.spell_id] = spell
            _toggle(pet, spell, spell.active == ACT_ENABLED)
            _place_existing_chain(pet, spell)
            return "copied"
        return "rejected_lower"
    if spell.active == ACT_DECIDE:
        spell.active = ACT_DISABLED if spell.autocastable else ACT_PASSIVE
        origin = "default_off" if spell.autocastable else "default_passive"
    else:
        origin = "loaded"
    bar_kind = spell.active if spell.autocastable else ACT_PASSIVE
    pet.spells[spell.spell_id] = spell
    _toggle(pet, spell, spell.active == ACT_ENABLED)
    _place_new(pet, spell, bar_kind)
    return origin


def cleanup_action_bar(pet: SavedPet) -> None:
    """Pet::CleanupActionBar. The bar type is reapplied onto PetSpell.active."""
    for slot in pet.bar:
        if not slot.action:
            continue
        spell = pet.spells.get(slot.action)
        if spell is None:
            slot.action = 0
            slot.chain = 0
            slot.kind = ACT_PASSIVE
            continue
        _toggle(pet, spell, slot.kind == ACT_ENABLED)


def _unlearn(pet: SavedPet, spell_id: int, clear_bar: bool) -> None:
    """Pet::removeSpell. Does not erase m_autospells."""
    spell = pet.spells.pop(spell_id, None)
    if spell and clear_bar:
        for slot in pet.bar:
            if slot.action and slot.chain == spell.chain:
                slot.action = 0
                slot.chain = 0
                slot.kind = ACT_DISABLED


def _place_existing_chain(pet: SavedPet, spell: KnownSpell) -> None:
    for slot in pet.bar:
        if slot.action and slot.chain == spell.chain:
            slot.action = spell.spell_id
            return
    kind = spell.active if spell.autocastable else ACT_PASSIVE
    _place_new(pet, spell, kind)


def _place_new(pet: SavedPet, spell: KnownSpell, kind: int) -> None:
    """First empty spell slot. A cleared slot (action 0, ACT_DISABLED) counts."""
    for slot in pet.bar:
        if slot.action == 0 and slot.kind in (ACT_PASSIVE, ACT_DISABLED, ACT_ENABLED):
            slot.action = spell.spell_id
            slot.chain = spell.chain
            slot.kind = kind
            return


def native_rank_up(pet: SavedPet, new_id: int, chain: int, autocastable: bool = True) -> str:
    spell = KnownSpell(new_id, chain, autocastable, ACT_DECIDE, "new")
    return learn_with_rank_inheritance(pet, spell)


def load_saved_spell(pet: SavedPet, spell_id: int, chain: int, active: int, autocastable: bool = True) -> str:
    spell = KnownSpell(spell_id, chain, autocastable, active, "unchanged")
    return learn_with_rank_inheritance(pet, spell)


def ip_reconcile(pet: SavedPet, wipe_ids: list[int], dummy_ids: list[int], *,
                 knows_dummy: set[int], chains: dict[int, int],
                 autocastable: set[int], is_bot: bool, is_hunter: bool,
                 vanilla_pets: bool, passed_t5: bool) -> str:
    """IP checkHunterPetSpells reconcile lambda. No script hook is called."""
    if not vanilla_pets or is_bot or not is_hunter or passed_t5:
        return "skipped"
    keep_id = 0
    for dummy in reversed(dummy_ids):
        if dummy in knows_dummy:
            keep_id = dummy - 600000
            break
    for spell_id in wipe_ids:
        if spell_id != keep_id and spell_id in pet.spells:
            _unlearn(pet, spell_id, clear_bar=True)
    if keep_id and keep_id not in pet.spells:
        chain = chains.get(keep_id, keep_id)
        spell = KnownSpell(keep_id, chain, keep_id in autocastable, ACT_DECIDE, "new")
        return learn_with_rank_inheritance(pet, spell)
    if keep_id:
        return "already_known"
    return "removed_without_keep"


def levelup_decision(levelup_level: int, pet_level: int, hook_returns_true: bool) -> str:
    """InitLevelupSpellsForLevel if/else. A false hook does not block learn."""
    if levelup_level > pet_level and hook_returns_true:
        return "unlearn"
    return "learn"


def hook_between_ip_unlearn_and_learn() -> tuple[str, ...]:
    start = SUMMON_EVENT_ORDER.index("ip_delayed_event_unlearn")
    end = SUMMON_EVENT_ORDER.index("ip_delayed_event_learn")
    between = SUMMON_EVENT_ORDER[start + 1:end]
    return tuple(name for name in between if name in PET_SCRIPT_HOOKS)


def parse_hunter_function(source: str) -> dict:
    start = source.find("void IndividualProgression::checkHunterPetSpells")
    end = source.find("void IndividualProgression::checkWarlockPetSpells")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("hunter pet function bounds not found")
    body = source[start:end]
    families = re.findall(r'familyName == "([^"]+)"', body)
    active = commented = 0
    for line in body.splitlines():
        if "reconcile(" not in line:
            continue
        if line.lstrip().startswith("//"):
            commented += 1
        else:
            active += 1
    growl_present = [spell_id for spell_id in GROWL_IDS if re.search(rf"\b{spell_id}\b", body)]
    return {
        "families": families,
        "active": active,
        "commented": commented,
        "growl_present": growl_present,
        "body": body,
    }


def _cache_root(repo: str, sha: str) -> Path | None:
    mapping = {
        (CORE_REPO, CORE_OLD): os.environ.get("A02_CORE_OLD"),
        (CORE_REPO, CORE_NEW): os.environ.get("A02_CORE_NEW"),
        (IP_REPO, IP_SHA): os.environ.get("A02_IP"),
        (PLAYERBOTS_REPO, PLAYERBOTS_SHA): os.environ.get("A02_PLAYERBOTS"),
    }
    raw = mapping.get((repo, sha))
    return Path(raw) if raw else None


def read_pinned_text(repo: str, sha: str, path: str) -> str:
    cached = _cache_root(repo, sha)
    if cached:
        return (cached / path).read_text(encoding="utf-8", errors="replace")
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "a02-s1-citation-check"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def verify_citations() -> list[str]:
    """Return human-readable failures. Empty means every pin matched."""
    failures: list[str] = []
    loaded: dict[tuple[str, str, str], list[str]] = {}
    needed = {(repo, sha, path) for repo, sha, path, _line, _text in CITATIONS}
    needed.add((CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp"))
    needed.add((CORE_REPO, CORE_NEW, "src/server/game/Entities/Pet/Pet.cpp"))
    needed.add((IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp"))
    for repo, sha, path in sorted(needed):
        try:
            text = read_pinned_text(repo, sha, path)
        except Exception as exc:  # noqa: BLE001 — surface the fetch error as a failure
            failures.append(f"FETCH {repo}@{sha[:12]} {path}: {exc}")
            continue
        loaded[(repo, sha, path)] = text.splitlines()
        if path.endswith("Pet.cpp"):
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest != PET_CPP_SHA256:
                failures.append(f"HASH Pet.cpp {sha[:12]} {digest}")
        if path.endswith("IndividualProgressionSpells.cpp"):
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest != IP_SPELLS_SHA256:
                failures.append(f"HASH IndividualProgressionSpells.cpp {digest}")

    for repo, sha, path, line, snippet in CITATIONS:
        rows = loaded.get((repo, sha, path))
        if rows is None:
            continue
        if line < 1 or line > len(rows):
            failures.append(f"RANGE {path}:{line}")
            continue
        if snippet not in rows[line - 1]:
            failures.append(f"MISS {sha[:12]} {path}:{line} expected {snippet!r} got {rows[line - 1].strip()!r}")

    ip_rows = loaded.get((IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp"))
    if ip_rows:
        window = "\n".join(ip_rows[82:90])
        if "sScriptMgr" in window:
            failures.append("IP unlearn/learn window calls sScriptMgr")
        parsed = parse_hunter_function("\n".join(ip_rows))
        if parsed["families"] != sorted(set(parsed["families"]), key=parsed["families"].index):
            failures.append("duplicate family names")
        if len(parsed["families"]) != EXPECTED_FAMILY_COUNT:
            failures.append(f"family count {len(parsed['families'])}")
        if parsed["active"] != EXPECTED_ACTIVE_RECONCILES:
            failures.append(f"active reconciles {parsed['active']}")
        if parsed["commented"] != EXPECTED_COMMENTED_RECONCILES:
            failures.append(f"commented reconciles {parsed['commented']}")
        if parsed["growl_present"]:
            failures.append(f"growl ids inside hunter function {parsed['growl_present']}")
        if "623099, 623109, 623110" not in parsed["body"]:
            failures.append("dash sibling ids missing from the source comment")

    old_pet = loaded.get((CORE_REPO, CORE_OLD, "src/server/game/Entities/Pet/Pet.cpp"))
    new_pet = loaded.get((CORE_REPO, CORE_NEW, "src/server/game/Entities/Pet/Pet.cpp"))
    if old_pet and new_pet and old_pet != new_pet:
        failures.append("Pet.cpp differs between a66f1be and 8daffda")

    remove = None
    if old_pet:
        remove = "\n".join(old_pet[1975:2025])
        if "m_autospells" in remove:
            failures.append("Pet::removeSpell touches m_autospells")
    return failures


def main() -> None:
    failures = verify_citations()
    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit(1)
    print(f"citations {len(CITATIONS)} OK")
    print(f"families {EXPECTED_FAMILY_COUNT} active {EXPECTED_ACTIVE_RECONCILES} commented {EXPECTED_COMMENTED_RECONCILES}")


if __name__ == "__main__":
    main()
