"""Adversarial model and source contract for A02 S3.

The two-phase candidate records a CMSG_PET_SPELL_AUTOCAST attempt in
CanPacketReceive, then on a later OnPlayerUpdate or OnSessionUpdate treats
"live autocast state equals the requested state" as an accepted explicit
choice. This module shows that predicate is unsound for explicit OFF.

It does not restore a pet, does not edit core or Individual Progression,
and does not claim in-game behaviour. Citation checks refetch the pinned
SHAs. A pass is not a worldserver run.
"""

from __future__ import annotations

import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from a02_s3_hook_manifest import HOOKS

CORE_REPO = "Grimfeather/azerothcore-wotlk"
IP_REPO = "Grimfeather/mod-individual-progression"
CORE_OLD = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7"
CORE_NEW = "8daffdabe9202c228e45d833c9a1d399597a15cd"
IP_SHA = "4ff4b5fcc1480348f058c632573143e62d4e3a41"

ACT_DISABLED = 0x81
ACT_ENABLED = 0xC1

# ServerScript virtual methods at both pinned cores. There is no
# post-handler receive hook in this list.
SERVER_SCRIPT_HOOKS = (
    (45, "OnNetworkStart"),
    (46, "OnNetworkStart"),
    (49, "OnNetworkStop"),
    (52, "OnSocketOpen"),
    (56, "OnSocketClose"),
    (65, "CanPacketSend"),
    (75, "CanPacketReceive"),
    (85, "OnPacketSent"),
)

# (path, 1-based line, snippet). Checked at both core SHAs.
CORE_CITATIONS = (
    ("src/server/game/Handlers/PetHandler.cpp", 955, "HandlePetSpellAutocastOpcode"),
    ("src/server/game/Handlers/PetHandler.cpp", 991, "HasSpell(packet.SpellID)"),
    ("src/server/game/Handlers/PetHandler.cpp", 991, "IsAutocastable()"),
    ("src/server/game/Handlers/PetHandler.cpp", 1003, "ToggleAutocast(spellInfo, packet.AutocastEnabled)"),
    ("src/server/game/Handlers/PetHandler.cpp", 1007, "SetSpellAutocast(spellInfo, packet.AutocastEnabled)"),
    ("src/server/game/Handlers/PetHandler.cpp", 1009, "}"),
    ("src/server/game/Entities/Pet/Pet.cpp", 118, "OnPetAddToWorld(this)"),
    ("src/server/game/Entities/Pet/Pet.cpp", 659, "if (m_loading)"),
    ("src/server/game/Entities/Pet/Pet.cpp", 736, "Creature::Update(diff)"),
    ("src/server/game/Entities/Pet/Pet.cpp", 1572, "void Pet::_SaveSpells"),
    ("src/server/game/Entities/Pet/Pet.cpp", 1588, "PETSPELL_REMOVED"),
    ("src/server/game/Entities/Pet/Pet.cpp", 1810, "active == ACT_DECIDE"),
    ("src/server/game/Entities/Pet/Pet.cpp", 1813, "newspell.active = ACT_DISABLED"),
    ("src/server/game/Entities/Pet/Pet.cpp", 2247, "void Pet::ToggleAutocast"),
    ("src/server/game/Entities/Pet/Pet.cpp", 2276, "autospellItr != m_autospells.end()"),
    ("src/server/game/Entities/Pet/Pet.h", 167, "void SaveToDB(uint32, uint8, uint32) override"),
    ("src/server/game/Entities/Unit/CharmInfo.cpp", 291, "void CharmInfo::SetSpellAutocast"),
    ("src/server/game/Entities/Unit/CharmInfo.cpp", 297, "SetType(state ? ACT_ENABLED : ACT_DISABLED)"),
    ("src/server/game/Server/WorldSession.cpp", 71, "PROCESS_INPLACE"),
    ("src/server/game/Server/WorldSession.cpp", 93, "PROCESS_INPLACE"),
    ("src/server/game/Server/WorldSession.cpp", 412, "MAX_PROCESSED_PACKETS_IN_SAME_WORLDSESSION_UPDATE = 150"),
    ("src/server/game/Server/WorldSession.cpp", 461, "CanPacketReceive"),
    ("src/server/game/Server/WorldSession.cpp", 464, "opHandle->Call"),
    ("src/server/game/Server/WorldSession.cpp", 598, "OnSessionUpdate"),
    ("src/server/game/World/World.cpp", 1227, "UpdateSessions"),
    ("src/server/game/World/World.cpp", 1254, "sMapMgr->Update"),
    ("src/server/game/Maps/Map.cpp", 449, "MapSessionFilter"),
    ("src/server/game/Maps/Map.cpp", 453, "if (!t_diff)"),
    ("src/server/game/Maps/Map.cpp", 454, "player->Update(s_diff)"),
    ("src/server/game/Maps/Map.cpp", 489, "player->Update(s_diff)"),
    ("src/server/game/Maps/Map.cpp", 506, "UpdateNonPlayerObjects"),
    ("src/server/game/Entities/Player/PlayerUpdates.cpp", 58, "OnPlayerBeforeUpdate"),
    ("src/server/game/Entities/Player/PlayerUpdates.cpp", 314, "OnPlayerUpdate"),
    ("src/server/game/Entities/Player/PlayerUpdates.cpp", 431, "OnPlayerAfterUpdate"),
    ("src/server/game/Server/Protocol/Opcodes.cpp", 503, "CMSG_PET_SET_ACTION"),
    ("src/server/game/Server/Protocol/Opcodes.cpp", 503, "PROCESS_THREADUNSAFE"),
    ("src/server/game/Server/Protocol/Opcodes.cpp", 886, "CMSG_PET_SPELL_AUTOCAST"),
    ("src/server/game/Server/Protocol/Opcodes.cpp", 886, "PROCESS_INPLACE"),
    ("src/server/game/Server/Packets/PetPackets.cpp", 35, "PetSpellAutocast::Read"),
    ("src/server/game/Scripting/ScriptDefines/ServerScript.h", 75, "CanPacketReceive"),
    ("src/server/game/Scripting/ScriptDefines/ServerScript.h", 85, "OnPacketSent"),
    ("src/server/game/Scripting/ScriptDefines/SessionScript.h", 43, "OnSessionUpdate"),
    ("src/server/game/Scripting/ScriptDefines/PlayerScript.h", 300, "OnPlayerBeforeUpdate"),
    ("src/server/game/Scripting/ScriptDefines/PlayerScript.h", 301, "OnPlayerAfterUpdate"),
    ("src/server/game/Scripting/ScriptDefines/PlayerScript.h", 302, "OnPlayerUpdate"),
    ("src/server/game/Scripting/ScriptDefines/PlayerScript.h", 377, "OnPlayerSave"),
    ("src/server/game/Scripting/ScriptDefines/AllCreatureScript.h", 57, "OnCreatureSaveToDB"),
    ("src/server/game/Scripting/ScriptDefines/PetScript.h", 58, "OnPetAddToWorld"),
    ("src/server/game/Scripting/ScriptDefines/UnitScript.h", 104, "OnUnitUpdate"),
    ("src/server/game/Scripting/ScriptDefines/WorldObjectScript.h", 76, "OnWorldObjectUpdate"),
    ("src/server/game/Scripting/ScriptDefines/AllSpellScript.h", 106, "OnSpellCast"),
    ("src/server/game/Scripting/ScriptDefines/ModuleScript.h", 25, "class ModuleScript"),
    ("src/server/game/Scripting/ScriptMgrMacros.h", 76, "CALL_ENABLED_BOOLEAN_HOOKS"),
    ("src/server/game/Scripting/ScriptDefines/ServerScript.cpp", 62, "SERVERHOOK_CAN_PACKET_RECEIVE"),
    ("src/server/game/Entities/Creature/Creature.cpp", 748, "Unit::Update(diff)"),
    ("src/server/game/Entities/Creature/Creature.cpp", 970, "OnCreatureUpdate"),
    ("src/server/game/Entities/Creature/Creature.cpp", 1509, "OnCreatureSaveToDB"),
    ("src/server/game/Entities/Object/Object.cpp", 1076, "m_Events.Update(diff)"),
    ("src/server/game/Entities/Object/Object.cpp", 1085, "OnWorldObjectUpdate"),
    ("src/server/game/Entities/Unit/Unit.cpp", 512, "OnUnitUpdate"),
    ("src/server/game/Entities/Unit/Unit.cpp", 517, "WorldObject::Update"),
)

# PlayerStorage.cpp is not byte-identical. An aura-load guard inserted near
# line 5863 on 8daffda shifts the save function by 7 lines. The order is the
# same: OnPlayerSave, then pet->SavePetToDB. Object.cpp and Unit.cpp also
# differ outside the update hooks; those hook lines are in CORE_CITATIONS
# and are checked at both SHAs without requiring the whole file to match.
PLAYER_STORAGE_CITATIONS = (
    (CORE_OLD, 7263, "sScriptMgr->OnPlayerSave(this)"),
    (CORE_OLD, 7298, "pet->SavePetToDB(PET_SAVE_AS_CURRENT)"),
    (CORE_NEW, 7270, "sScriptMgr->OnPlayerSave(this)"),
    (CORE_NEW, 7305, "pet->SavePetToDB(PET_SAVE_AS_CURRENT)"),
)

# Whole-file equality is the wrong pin for these three. Their cited lines
# are still checked.
DIVERGED_LINE_PINS = {
    "src/server/game/Entities/Object/Object.cpp",
    "src/server/game/Entities/Unit/Unit.cpp",
    "src/server/game/Entities/Player/PlayerStorage.cpp",
}

IP_CITATIONS = (
    ("src/IndividualProgression.h", 430, "void checkHunterPetSpells(Player* player)"),
    ("src/IndividualProgressionSpells.cpp", 86, "pet->unlearnSpell(id, false, true)"),
    ("src/IndividualProgressionSpells.cpp", 90, "pet->learnSpell(keepId)"),
    ("src/IndividualProgressionSpells.cpp", 1252, "class PendingPetSpellCheck"),
    ("src/IndividualProgressionSpells.cpp", 1342, "checkHunterPetSpells(player)"),
)

IDENTICAL_CORE_PATHS = tuple(
    dict.fromkeys(
        [path for path, _line, _snippet in CORE_CITATIONS]
        + [f"src/server/game/Scripting/ScriptDefines/{name}" for name, _line, _hook in HOOKS]
    )
)


def extract_virtual_hooks(text: str) -> list[tuple[int, str]]:
    """Textual pin of virtual methods. A comment that looks like a method fails closed."""
    lines = text.splitlines()
    buf = ""
    start = 0
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines, 1):
        if "virtual " in line or buf:
            if not buf:
                start = index
            buf += " " + line.strip()
            if "{" in line or line.strip().endswith(";") or "= 0;" in line:
                tail = buf.split("virtual", 1)[-1][:40]
                if "virtual " in buf and "~" not in tail:
                    matched = re.search(r"virtual\s+(?:[\w:<>,\s\*&]+?)\s+(\w+)\s*\(", buf)
                    if matched:
                        found.append((start, matched.group(1)))
                buf = ""
            elif len(buf) > 800:
                buf = ""
    return found


def hooks_for(header_name: str) -> list[tuple[int, str]]:
    return [(line, name) for filename, line, name in HOOKS if filename == header_name]


def header_matches_manifest(header_name: str, text: str) -> list[str]:
    expected = hooks_for(header_name)
    actual = extract_virtual_hooks(text)
    if actual != expected:
        return [f"HOOKS {header_name} expected {len(expected)} got {len(actual)}"]
    return []


@dataclass(frozen=True)
class SpellView:
    """Public autocast triple. Learn-default OFF is disabled, not in m_autospells, bar disabled."""

    active: int
    in_autospells: bool
    bar: int | None


def learn_default() -> SpellView:
    return SpellView(ACT_DISABLED, False, ACT_DISABLED)


def explicit_on() -> SpellView:
    return SpellView(ACT_ENABLED, True, ACT_ENABLED)


def apply_accepted_toggle(view: SpellView, requested_on: bool) -> tuple[SpellView, str]:
    """ToggleAutocast then SetSpellAutocast after the handler has already accepted.

    OFF with the id absent from m_autospells does not change active. SetSpellAutocast
    rewrites the bar to the requested type, which is already ACT_DISABLED for a
    learn-default spell.
    """
    active = view.active
    in_autospells = view.in_autospells
    changed = False
    if requested_on and not in_autospells:
        in_autospells = True
        active = ACT_ENABLED
        changed = True
    elif (not requested_on) and in_autospells:
        in_autospells = False
        active = ACT_DISABLED
        changed = True
    bar = view.bar
    if bar is not None:
        new_bar = ACT_ENABLED if requested_on else ACT_DISABLED
        if new_bar != bar:
            changed = True
        bar = new_bar
    return SpellView(active, in_autospells, bar), ("accepted_changed" if changed else "accepted_noop")


@dataclass(frozen=True)
class Book:
    guid: int
    owner: int
    spells: dict[int, SpellView]


@dataclass(frozen=True)
class Packet:
    pet_guid: int
    spell_id: int
    requested_on: bool
    arrival: str
    reject: str | None = None


@dataclass(frozen=True)
class Attempt:
    pet_guid: int
    spell_id: int
    requested_on: bool
    handler: str


def _copy_book(book: Book, spells: dict[int, SpellView] | None = None, guid: int | None = None) -> Book:
    return Book(book.guid if guid is None else guid, book.owner, dict(book.spells if spells is None else spells))


def apply_packet(book: Book | None, packet: Packet) -> tuple[Book | None, str]:
    """CanPacketReceive has already returned. This is only the handler.

    A reject reason means the handler returned or continued before either write.
    The attempt itself is recorded by the caller whether or not this accepts.
    """
    if packet.reject:
        return book, f"rejected_{packet.reject}"
    if book is None or book.guid != packet.pet_guid or packet.spell_id not in book.spells:
        return book, "rejected_missing"
    updated, how = apply_accepted_toggle(book.spells[packet.spell_id], packet.requested_on)
    spells = dict(book.spells)
    spells[packet.spell_id] = updated
    return _copy_book(book, spells), how


def apply_set_action(book: Book | None, spell_id: int, enabled: bool) -> Book | None:
    """CMSG_PET_SET_ACTION's autocast branch. Not an autocast-opcode attempt."""
    if book is None or spell_id not in book.spells:
        return book
    updated, _how = apply_accepted_toggle(book.spells[spell_id], enabled)
    spells = dict(book.spells)
    spells[spell_id] = updated
    return _copy_book(book, spells)


def equality_records(attempt: Attempt, book: Book | None) -> bool:
    """The candidate: same pet, spell still present, live ON/OFF equals the request.

    The handler result is not an input. A learn-default OFF and an accepted
    no-op OFF therefore record the same choice as a rejected OFF packet.
    """
    if book is None or book.guid != attempt.pet_guid:
        return False
    view = book.spells.get(attempt.spell_id)
    if view is None:
        return False
    return (view.active == ACT_ENABLED) == attempt.requested_on


def unguarded_equality_records(attempt: Attempt, book: Book | None) -> bool:
    """Wrong store: player-scoped, ignoring the pet GUID. Cross-pet false confirm."""
    if book is None:
        return False
    view = book.spells.get(attempt.spell_id)
    if view is None:
        return False
    return (view.active == ACT_ENABLED) == attempt.requested_on


def delta_records(attempt: Attempt, before: SpellView, book: Book | None) -> bool:
    """Require a visible change as well as equality. A no-op OFF never changes."""
    if book is None or book.guid != attempt.pet_guid:
        return False
    after = book.spells.get(attempt.spell_id)
    if after is None or after == before:
        return False
    return (after.active == ACT_ENABLED) == attempt.requested_on


def observation_inputs_match(left: Attempt, left_view: SpellView | None, right: Attempt, right_view: SpellView | None) -> bool:
    """True when a pre-handler attempt plus the public view cannot tell two cases apart."""
    return (
        left.pet_guid == right.pet_guid
        and left.spell_id == right.spell_id
        and left.requested_on == right.requested_on
        and left_view == right_view
    )


def replace_rank(book: Book | None, old_id: int, new_id: int) -> Book | None:
    """IP unlearn then learnSpell: the new id is stored learn-default OFF."""
    if book is None:
        return None
    spells = {spell_id: view for spell_id, view in book.spells.items() if spell_id != old_id}
    spells[new_id] = learn_default()
    return _copy_book(book, spells)


@dataclass(frozen=True)
class TickResult:
    attempts: tuple[Attempt, ...]
    session_book: Book | None
    player_book: Book | None
    after_pet: Book | None
    session_confirmed: tuple[Attempt, ...]
    player_confirmed: tuple[Attempt, ...]
    next_session_confirmed: tuple[Attempt, ...]


def run_world_tick(
    book: Book | None,
    packets: list[Packet],
    *,
    full_map_step: bool = True,
    ip_swap: tuple[int, int] | None = None,
    dismiss_at: str | None = None,
    swap_at: tuple[str, int] | None = None,
    extra_set_action: tuple[str, int, bool] | None = None,
) -> TickResult:
    """One world tick, in the pinned order.

    UpdateSessions (PROCESS_INPLACE and PROCESS_THREADUNSAFE) runs first and
    then calls OnSessionUpdate. Map::Update may then process a PROCESS_INPLACE
    packet that arrived after that drain, then OnPlayerUpdate, then pet
    m_Events on a full map step. IP's DelayedPetSpellCheck is one of those
    pet events, so it runs after both observation hooks in this tick.
    """
    attempts: list[Attempt] = []

    def mutate(phase: str) -> None:
        nonlocal book
        if dismiss_at == phase:
            book = None
        if swap_at and swap_at[0] == phase and book is not None:
            book = _copy_book(book, guid=swap_at[1])
        if extra_set_action and extra_set_action[0] == phase and book is not None:
            _phase, spell_id, enabled = extra_set_action
            book = apply_set_action(book, spell_id, enabled)

    def take(arrival: str) -> None:
        nonlocal book
        for packet in packets:
            if packet.arrival != arrival:
                continue
            book, handler = apply_packet(book, packet)
            attempts.append(Attempt(packet.pet_guid, packet.spell_id, packet.requested_on, handler))

    mutate("before_world_session")
    take("before_sessions")
    mutate("after_world_packets")
    session_book = book
    session_confirmed = tuple(attempt for attempt in attempts if equality_records(attempt, session_book))

    mutate("before_map")
    take("during_map")
    player_book = book
    player_confirmed = tuple(attempt for attempt in attempts if equality_records(attempt, player_book))

    if full_map_step:
        mutate("before_pet_events")
        if ip_swap is not None:
            book = replace_rank(book, ip_swap[0], ip_swap[1])
    after_pet = book
    next_session_confirmed = tuple(attempt for attempt in attempts if equality_records(attempt, after_pet))
    return TickResult(
        tuple(attempts),
        session_book,
        player_book,
        after_pet,
        session_confirmed,
        player_confirmed,
        next_session_confirmed,
    )


def explicit_off_collision() -> tuple[TickResult, TickResult]:
    """Accepted no-op OFF and rejected OFF. Public views match. Both confirm."""
    book = Book(100, 7, {17255: learn_default()})
    accepted = run_world_tick(book, [Packet(100, 17255, False, "before_sessions")])
    rejected = run_world_tick(book, [Packet(100, 17255, False, "before_sessions", reject="not_autocastable")])
    return accepted, rejected


def two_phase_verdict() -> str:
    """Unsound: the candidate's inputs are identical for explicit OFF and a rejected OFF."""
    accepted, rejected = explicit_off_collision()
    left = accepted.attempts[0]
    right = rejected.attempts[0]
    left_view = accepted.session_book.spells[left.spell_id] if accepted.session_book else None
    right_view = rejected.session_book.spells[right.spell_id] if rejected.session_book else None
    if not observation_inputs_match(left, left_view, right, right_view):
        return "distinguishable"
    if not accepted.session_confirmed or not rejected.session_confirmed:
        return "predicate_disagrees"
    if left.handler == right.handler:
        return "model_error"
    return "unsound"


def two_phase_is_sound() -> bool:
    return two_phase_verdict() == "sound"


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end <= start:
        raise ValueError(f"bounds missing: {start_marker}")
    return text[start:end]


def handler_calls_script(body: str) -> bool:
    return "sScriptMgr" in body


def autocast_handler_body(pet_handler: str) -> str:
    return _between(
        pet_handler,
        "void WorldSession::HandlePetSpellAutocastOpcode",
        "void WorldSession::HandlePetCastSpellOpcode",
    )


def _cache_root(repo: str, sha: str) -> Path | None:
    if repo == CORE_REPO and sha == CORE_OLD:
        raw = os.environ.get("A02_CORE_OLD")
    elif repo == CORE_REPO and sha == CORE_NEW:
        raw = os.environ.get("A02_CORE_NEW")
    elif repo == IP_REPO and sha == IP_SHA:
        raw = os.environ.get("A02_IP")
    else:
        raw = None
    return Path(raw) if raw else None


def read_pinned_text(repo: str, sha: str, path: str) -> str:
    git_root = os.environ.get("A02_CORE_GIT") if repo == CORE_REPO else os.environ.get("A02_IP_GIT")
    if git_root:
        return subprocess.check_output(
            ["git", "-C", git_root, "show", f"{sha}:{path}"],
            text=True,
            errors="replace",
        )
    cached = _cache_root(repo, sha)
    if cached:
        return (cached / path).read_text(encoding="utf-8", errors="replace")
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "a02-s3-citation-check"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def verify_citations() -> list[str]:
    """Empty means the pinned trees still match this contract. Any miss fails closed."""
    failures: list[str] = []
    loaded: dict[tuple[str, str, str], str] = {}

    needed = {(CORE_REPO, sha, path) for sha in (CORE_OLD, CORE_NEW) for path in IDENTICAL_CORE_PATHS}
    needed.add((CORE_REPO, CORE_OLD, "src/server/game/Entities/Player/PlayerStorage.cpp"))
    needed.add((CORE_REPO, CORE_NEW, "src/server/game/Entities/Player/PlayerStorage.cpp"))
    needed.update((IP_REPO, IP_SHA, path) for path, _line, _snippet in IP_CITATIONS)
    for repo, sha, path in sorted(needed):
        try:
            loaded[(repo, sha, path)] = read_pinned_text(repo, sha, path)
        except Exception as exc:  # noqa: BLE001 — fetch errors fail the contract
            failures.append(f"FETCH {repo}@{sha[:12]} {path}: {exc}")

    for path in IDENTICAL_CORE_PATHS:
        old = loaded.get((CORE_REPO, CORE_OLD, path))
        new = loaded.get((CORE_REPO, CORE_NEW, path))
        if old is None or new is None:
            continue
        if path in DIVERGED_LINE_PINS:
            continue
        if old != new:
            failures.append(f"DIVERGED {path}")

    for path, line, snippet in CORE_CITATIONS:
        for sha in (CORE_OLD, CORE_NEW):
            text = loaded.get((CORE_REPO, sha, path))
            if text is None:
                continue
            rows = text.splitlines()
            if line < 1 or line > len(rows) or snippet not in rows[line - 1]:
                got = rows[line - 1].strip() if 0 < line <= len(rows) else "<range>"
                failures.append(f"MISS {sha[:12]} {path}:{line} {snippet!r} got {got!r}")

    storage_path = "src/server/game/Entities/Player/PlayerStorage.cpp"
    for sha, line, snippet in PLAYER_STORAGE_CITATIONS:
        text = loaded.get((CORE_REPO, sha, storage_path))
        if text is None:
            continue
        rows = text.splitlines()
        if line < 1 or line > len(rows) or snippet not in rows[line - 1]:
            got = rows[line - 1].strip() if 0 < line <= len(rows) else "<range>"
            failures.append(f"MISS {sha[:12]} {storage_path}:{line} {snippet!r} got {got!r}")

    for path, line, snippet in IP_CITATIONS:
        text = loaded.get((IP_REPO, IP_SHA, path))
        if text is None:
            continue
        rows = text.splitlines()
        if line < 1 or line > len(rows) or snippet not in rows[line - 1]:
            failures.append(f"MISS ip {path}:{line} {snippet!r}")

    ip_spells = loaded.get((IP_REPO, IP_SHA, "src/IndividualProgressionSpells.cpp"))
    ip_header = loaded.get((IP_REPO, IP_SHA, "src/IndividualProgression.h"))
    if ip_spells is not None:
        if "sScriptMgr" in ip_spells:
            failures.append("IP IndividualProgressionSpells.cpp calls sScriptMgr")
        if ip_spells.count("checkHunterPetSpells(") != 2:
            failures.append("checkHunterPetSpells count changed")
    if ip_header is not None:
        if "PendingPetSpellCheck" in ip_header:
            failures.append("PendingPetSpellCheck is in the IP public header")
        if ip_header.count("checkHunterPetSpells") != 1:
            failures.append("IP header hunter check count changed")

    header_names = sorted({name for name, _line, _hook in HOOKS})
    for header_name in header_names:
        path = f"src/server/game/Scripting/ScriptDefines/{header_name}"
        text = loaded.get((CORE_REPO, CORE_NEW, path))
        if text is None:
            continue
        failures.extend(header_matches_manifest(header_name, text))

    server = loaded.get((CORE_REPO, CORE_NEW, "src/server/game/Scripting/ScriptDefines/ServerScript.h"))
    if server is not None and extract_virtual_hooks(server) != list(SERVER_SCRIPT_HOOKS):
        failures.append("ServerScript virtual set changed")
    if server is not None and "OnPacketReceived" in server:
        failures.append("OnPacketReceived appeared")

    pet_handler = loaded.get((CORE_REPO, CORE_NEW, "src/server/game/Handlers/PetHandler.cpp"))
    pet_cpp = loaded.get((CORE_REPO, CORE_NEW, "src/server/game/Entities/Pet/Pet.cpp"))
    charm = loaded.get((CORE_REPO, CORE_NEW, "src/server/game/Entities/Unit/CharmInfo.cpp"))
    if pet_handler is not None:
        body = autocast_handler_body(pet_handler)
        if handler_calls_script(body):
            failures.append("HandlePetSpellAutocastOpcode calls sScriptMgr")
        if "Send" in body:
            failures.append("HandlePetSpellAutocastOpcode sends a packet")
    if pet_cpp is not None:
        if handler_calls_script(_between(pet_cpp, "void Pet::ToggleAutocast", "bool Pet::IsPermanentPetFor")):
            failures.append("ToggleAutocast calls sScriptMgr")
        if handler_calls_script(_between(pet_cpp, "void Pet::_SaveSpells", "void Pet::_LoadAuras")):
            failures.append("_SaveSpells calls sScriptMgr")
        if handler_calls_script(_between(pet_cpp, "void Pet::SavePetToDB", "void Pet::DeleteFromDB")):
            failures.append("SavePetToDB calls sScriptMgr")
    if charm is not None:
        if handler_calls_script(_between(charm, "void CharmInfo::SetSpellAutocast", "void CharmInfo::SetIsCommandAttack")):
            failures.append("SetSpellAutocast calls sScriptMgr")
    return failures


def main() -> None:
    failures = verify_citations()
    verdict = two_phase_verdict()
    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit(1)
    if verdict != "unsound":
        raise SystemExit(f"verdict {verdict}")
    print(f"A02_S3_CONTRACT_OK hooks={len(HOOKS)} citations={len(CORE_CITATIONS)} verdict={verdict}")


if __name__ == "__main__":
    main()
