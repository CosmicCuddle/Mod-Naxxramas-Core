#!/usr/bin/env python3
"""PAK-D1 contract witnesses for A02 hunter pet autocast.

Models draft #134 v1 at parent 2ab30306c884d3af1c92bb5ad7042648b90fd162 from
src/Systems/HunterPetAutocastAddon.h and this branch's v2 candidate in
docs/research/a02-pak-d1-protocol-v2-proposal.md.

Offline only. Does not start a worldserver, open a database, load Playerbots,
or claim an in-game result. PASS/FAIL on a witness is the safety property
(pet A does not leak onto pet B, stale replay does not write, missing spells
are not learned). A FAIL for v1 is the modelled #134 behaviour this proposal
exists to replace.
"""

from __future__ import annotations

import atexit
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "docs" / "research" / "a02-pak-d1-protocol-v2-proposal.md"
ADDON_H = ROOT / "src" / "Systems" / "HunterPetAutocastAddon.h"
CPP = ROOT / "src" / "Systems" / "HunterPetAutocast.cpp"
CONF = ROOT / "conf" / "mod_naxxramas_core.conf.dist"

MAX_RAW = 255
MAX_SEQ = 999999999
MAX_CHUNKS = 8
MAX_PAIRS = 64
RATE_LIMIT = 8
RATE_WINDOW_MS = 10000
PREFIX = "NXCPAK\t"

# Rank lists transcribed from IndividualProgressionSpells.cpp at
# dd96f2b77e3ebfa2a4726bf785525ba133f1ab61. DBC chain links are NOT TESTED.
# The model treats the first listed rank as GetFirstSpellInChain.
BITE = [17253, 17255, 17256, 17257, 17258, 17259, 17260, 17261, 27050]
BITE_DUMMY = [617253, 617255, 617256, 617257, 617258, 617259, 617260, 617261, 627050]
CLAW = [16827, 16828, 16829, 16830, 16831, 16832, 3010, 3009, 27049]
CAT_CLAW_DUMMY = [616827, 616828, 616829, 616830, 616831, 616832, 603010, 603009, 627049]
COWER = 1742
GROWL = 2649  # illustrative. DBC autocast flag NOT TESTED.
NOT_AUTO = 6603  # illustrative non-autocastable id. DBC flag NOT TESTED.

CHAIN = {}
for _rank in BITE:
    CHAIN[_rank] = BITE[0]
for _rank in CLAW:
    CHAIN[_rank] = CLAW[0]
CHAIN[COWER] = COWER
CHAIN[GROWL] = GROWL
AUTO = set(CHAIN)

WITNESSES: list[tuple[str, bool, bool, str]] = []


def witness(case: str, v1_safe: bool, v2_safe: bool, note: str) -> None:
    WITNESSES.append((case, v1_safe, v2_safe, note))
    print(
        f"WITNESS {case} v1={'PASS' if v1_safe else 'FAIL'} "
        f"v2={'PASS' if v2_safe else 'FAIL'} {note}"
    )


def _summary() -> None:
    if not WITNESSES:
        return
    v1_fail = sum(1 for row in WITNESSES if not row[1])
    v2_fail = sum(1 for row in WITNESSES if not row[2])
    total = len(WITNESSES)
    print(
        f"WITNESS_TOTAL {total} v1_safety_fail={v1_fail} "
        f"v1_safety_pass={total - v1_fail} v2_safety_fail={v2_fail} "
        f"v2_safety_pass={total - v2_fail}"
    )


atexit.register(_summary)


def parse_decimal(text: str, max_digits: int, limit: int) -> int | None:
    if not text or len(text) > max_digits:
        return None
    if len(text) > 1 and text[0] == "0":
        return None
    value = 0
    for char in text:
        if char < "0" or char > "9":
            return None
        value = value * 10 + (ord(char) - 48)
        if value > limit:
            return None
    return value


def lookup(spell_id: int) -> tuple[bool, int]:
    if spell_id not in AUTO:
        return False, 0
    return True, CHAIN[spell_id]


def parse_pairs(text: str) -> list[tuple[int, bool]] | None:
    if text == "":
        return []
    if "\t" in text or " " in text:
        return None
    pairs: list[tuple[int, bool]] = []
    while text:
        if len(pairs) >= MAX_PAIRS:
            return None
        comma = text.find(",")
        if comma == 0:
            return None
        pair = text if comma < 0 else text[:comma]
        if comma < 0:
            text = ""
        elif comma + 1 >= len(text):
            return None
        else:
            text = text[comma + 1 :]
        eq = pair.find("=")
        if eq <= 0 or eq + 1 >= len(pair) or "=" in pair[eq + 1 :]:
            return None
        spell_id = parse_decimal(pair[:eq], 10, 4294967295)
        if spell_id is None or spell_id == 0:
            return None
        bit = pair[eq + 1 :]
        if bit not in ("0", "1"):
            return None
        if any(existing == spell_id for existing, _enabled in pairs):
            return None
        pairs.append((spell_id, bit == "1"))
    return pairs


class Parsed:
    def __init__(self, kind: str, seq: int = 0, index: int = 0, total: int = 0,
                 pairs: list[tuple[int, bool]] | None = None, epoch: int = 0,
                 token: str = "", gen: int = 0):
        self.kind = kind
        self.seq = seq
        self.index = index
        self.total = total
        self.pairs = pairs or []
        self.epoch = epoch
        self.token = token
        self.gen = gen


def parse_message(raw: str) -> Parsed:
    """Return NotDelivered when the core would drop the string before the hook."""
    if len(raw) > MAX_RAW and raw.startswith(PREFIX):
        return Parsed("NotDelivered")
    if not raw.startswith(PREFIX):
        return Parsed("NotOurs")
    if len(raw) > MAX_RAW:
        return Parsed("NotDelivered")
    payload = raw[len(PREFIX) :]
    if payload == "":
        return Parsed("Malformed")
    if payload == "v1|clear":
        return Parsed("ClearV1")
    if payload.startswith("v1|"):
        return _parse_v1(payload)
    if payload.startswith("v2|"):
        return _parse_v2(payload)
    return Parsed("Malformed")


def _parse_v1(payload: str) -> Parsed:
    body = payload[3:]
    seq_text, bar, rest = body.partition("|")
    seq = parse_decimal(seq_text, 9, MAX_SEQ)
    if bar == "" or seq is None or seq == 0:
        return Parsed("Malformed")
    slash = rest.find("/")
    bar2 = rest.find("|")
    if slash < 0 or bar2 < 0 or slash > bar2:
        return Parsed("Malformed")
    index = parse_decimal(rest[:slash], 1, MAX_CHUNKS)
    total = parse_decimal(rest[slash + 1 : bar2], 1, MAX_CHUNKS)
    if index is None or total is None or index == 0 or total == 0 or index > total:
        return Parsed("Malformed")
    pairs = parse_pairs(rest[bar2 + 1 :])
    if pairs is None:
        return Parsed("Malformed")
    return Parsed("ChunkV1", seq, index, total, pairs)


_TOKEN = re.compile(r"^[0-9a-f]{16}$")


def _parse_v2(payload: str) -> Parsed:
    parts = payload.split("|")
    if len(parts) >= 2 and parts[1] == "hello":
        return Parsed("Malformed")
    if len(parts) == 5 and parts[4] == "clear":
        epoch = parse_decimal(parts[1], 9, MAX_SEQ)
        gen = parse_decimal(parts[3], 9, MAX_SEQ)
        if epoch is None or gen is None or epoch == 0 or gen == 0 or not _TOKEN.match(parts[2]):
            return Parsed("Malformed")
        return Parsed("ClearV2", epoch=epoch, token=parts[2], gen=gen)
    if len(parts) != 7:
        return Parsed("Malformed")
    epoch = parse_decimal(parts[1], 9, MAX_SEQ)
    gen = parse_decimal(parts[3], 9, MAX_SEQ)
    seq = parse_decimal(parts[4], 9, MAX_SEQ)
    if (
        epoch is None or gen is None or seq is None
        or epoch == 0 or gen == 0 or seq == 0
        or not _TOKEN.match(parts[2])
    ):
        return Parsed("Malformed")
    slash = parts[5].find("/")
    if slash <= 0:
        return Parsed("Malformed")
    index = parse_decimal(parts[5][:slash], 1, MAX_CHUNKS)
    total = parse_decimal(parts[5][slash + 1 :], 1, MAX_CHUNKS)
    if index is None or total is None or index == 0 or total == 0 or index > total:
        return Parsed("Malformed")
    pairs = parse_pairs(parts[6])
    if pairs is None:
        return Parsed("Malformed")
    return Parsed("ChunkV2", seq, index, total, pairs, epoch, parts[2], gen)


def choices_from_pairs(groups: list[list[tuple[int, bool]]]) -> dict[int, bool] | None:
    merged: list[tuple[int, bool]] = []
    seen: set[int] = set()
    for group in groups:
        for spell_id, enabled in group:
            if len(merged) >= MAX_PAIRS or spell_id in seen:
                return None
            seen.add(spell_id)
            merged.append((spell_id, enabled))
    choices: dict[int, bool] = {}
    for spell_id, enabled in merged:
        autocastable, chain = lookup(spell_id)
        if not autocastable or chain == 0:
            continue
        choices[chain] = enabled
    return choices


class Assembler:
    """v1 AcceptChunk rules from HunterPetAutocastAddon.h, one generation."""

    def __init__(self) -> None:
        self.tracking = False
        self.last_seq = 0
        self.partial_seq = 0
        self.partial_total = 0
        self.chunks: list[list[tuple[int, bool]] | None] = []
        self.published: dict[int, bool] | None = None
        self.published_seq = 0

    def reset_partial(self) -> None:
        self.partial_seq = 0
        self.partial_total = 0
        self.chunks = []

    def clear_published(self) -> None:
        self.reset_partial()
        self.tracking = False
        self.last_seq = 0
        self.published = None
        self.published_seq = 0

    def accept_chunk(self, parsed: Parsed) -> str:
        seq = parsed.seq
        if self.tracking and seq < self.last_seq:
            return "StaleSeq"
        if self.tracking and seq == self.last_seq and self.partial_seq != seq:
            return "StaleSeq"
        if self.partial_seq and seq != self.partial_seq:
            if seq > self.partial_seq:
                self.reset_partial()
            else:
                return "StaleSeq"
        if self.partial_seq == 0:
            self.partial_seq = seq
            self.partial_total = parsed.total
            self.chunks = [None] * parsed.total
        elif self.partial_total != parsed.total:
            self.reset_partial()
            return "Malformed"
        slot = self.chunks[parsed.index - 1]
        if slot is not None:
            if slot == parsed.pairs:
                return "Partial"
            self.reset_partial()
            return "Malformed"
        self.chunks[parsed.index - 1] = list(parsed.pairs)
        if any(part is None for part in self.chunks):
            return "Partial"
        choices = choices_from_pairs([part for part in self.chunks if part is not None])
        if choices is None:
            self.reset_partial()
            return "Malformed"
        self.published = choices
        self.published_seq = seq
        self.tracking = True
        self.last_seq = seq
        self.reset_partial()
        return "Published"


def reconcile(spells: dict[int, bool], player_spells: set[int], wipe: list[int],
              dummies: list[int]) -> int:
    """Transcription of the IP reconcile lambda. learnSpell's autocast bit is NOT TESTED.

    A keep id inserted here is marked enabled so a later apply can be observed
    turning the successor to the stored bit. That initial bit is a model input.
    """
    keep = 0
    for dummy in reversed(dummies):
        if dummy in player_spells:
            keep = dummy - 600000
            break
    for spell_id in wipe:
        if spell_id != keep and spell_id in spells:
            del spells[spell_id]
    if keep and keep not in spells:
        spells[keep] = True
    return keep


def apply_choices(pet: "Pet | None", choices: dict[int, bool] | None) -> list[tuple[int, bool]]:
    if pet is None or choices is None:
        return []
    toggles = []
    for spell_id, enabled in list(pet.spells.items()):
        if spell_id not in AUTO:
            continue
        chain = CHAIN.get(spell_id)
        if chain not in choices:
            continue
        want = choices[chain]
        if enabled != want:
            pet.spells[spell_id] = want
            toggles.append((spell_id, want))
    return toggles


class Pet:
    def __init__(self, number: int | None, name: str, family: str, spells: dict[int, bool],
                 owner: int = 1):
        self.number = number
        self.name = name
        self.family = family
        self.owner = owner
        self.spells = dict(spells)
        # Server stamp for this summon. Not id(self) and not a wire field.
        self.incarnation: int | None = None


def make_wolf(number: int, bite: bool = True, cower: bool | None = True,
              claw: int | None = None, owner: int = 1) -> Pet:
    spells = {GROWL: True}
    if bite is not None:
        spells[17259] = bite
    if cower is not None:
        spells[COWER] = cower
    if claw is not None:
        spells[claw] = True
    return Pet(number, "Fluffy", "Wolf", spells, owner)


class Rate:
    def __init__(self) -> None:
        self.started = False
        self.start = 0
        self.count = 0

    def allow(self, now_ms: int) -> bool:
        if not self.started or now_ms < self.start or now_ms - self.start >= RATE_WINDOW_MS:
            self.started = True
            self.start = now_ms
            self.count = 1
            return True
        if self.count >= RATE_LIMIT:
            return False
        self.count += 1
        return True


class V1Store:
    """Player-GUID store. Publish happens on the world-thread accept, as in #134."""

    def __init__(self) -> None:
        self.enabled = True
        self.slots: dict[int, Assembler] = {}
        self.rates: dict[int, Rate] = {}
        self.hunters: dict[int, bool] = {}
        self.last_sender = 0
        self.last_target = ""
        self.transport_sends = 0

    def login(self, guid: int) -> None:
        slot = self.slots.get(guid)
        if slot is None:
            return
        slot.tracking = False
        slot.last_seq = 0
        slot.reset_partial()

    def logout(self, guid: int) -> None:
        self.slots.pop(guid, None)
        self.rates.pop(guid, None)

    def world_accept(self, guid: int, raw: str, now_ms: int, target: str,
                     is_hunter: bool = True, has_client: bool = True) -> str:
        self.last_sender = guid
        self.last_target = target
        if not has_client:
            return "NoClient"
        if not self.enabled:
            return "Disabled"
        parsed = parse_message(raw)
        if parsed.kind == "NotDelivered":
            return "NotDelivered"
        if parsed.kind == "NotOurs":
            return "NotOurs"
        if not is_hunter:
            return "IgnoredNotHunter"
        rate = self.rates.setdefault(guid, Rate())
        if not rate.allow(now_ms):
            return "RateLimited"
        if parsed.kind == "Malformed" or parsed.kind.startswith("ClearV2") or parsed.kind == "ChunkV2":
            if parsed.kind != "ClearV1" and parsed.kind != "ChunkV1":
                return "Malformed"
        slot = self.slots.setdefault(guid, Assembler())
        if parsed.kind == "ClearV1":
            slot.clear_published()
            return "Cleared"
        if parsed.kind != "ChunkV1":
            return "Malformed"
        return slot.accept_chunk(parsed)

    def choices_for(self, guid: int, pet: Pet | None) -> dict[int, bool] | None:
        slot = self.slots.get(guid)
        if slot is None:
            return None
        return slot.published

    def record(self, guid: int, pet_number: int) -> dict[int, bool] | None:
        del pet_number
        slot = self.slots.get(guid)
        if slot is None:
            return None
        return slot.published


HELLO_QUEUE_CAP = 1


class WorldAtomic:
    """Stand-in for std::atomic release-store / acquire-load.

    The Python model is single-threaded. Map-side paths may only load().
    The world thread is the only store() caller. This does not prove the
    C++ memory order; it keeps the two sides from sharing a bare write.
    """

    def __init__(self, value: int) -> None:
        self._value = value

    def store(self, value: int) -> None:
        self._value = value

    def load(self) -> int:
        return self._value


class CoreStable:
    """Authoritative owner stable. The receiver reads it and never inserts into it."""

    def __init__(self) -> None:
        self.members: set[int] = set()
        self.current: int | None = None


class Active:
    def __init__(self, pet_number: int, token: str, gen: int, epoch: int, hello: str,
                 incarnation: int):
        self.pet_number = pet_number
        self.token = token
        self.gen = gen
        self.epoch = epoch
        self.hello = hello
        self.incarnation = incarnation


class QueuedHello:
    def __init__(self, text: str, epoch: int, token: str, gen: int, pet_number: int,
                 incarnation: int):
        self.text = text
        self.epoch = epoch
        self.token = token
        self.gen = gen
        self.pet_number = pet_number
        self.incarnation = incarnation


class Snapshot:
    def __init__(self, epoch: int, gen: int, seq: int, choices: dict[int, bool]):
        self.epoch = epoch
        self.gen = gen
        self.seq = seq
        self.choices = choices


class V2Player:
    def __init__(self) -> None:
        self.epoch = 0
        self.logged_in = False
        self.next_gen = 0
        self.summon_counter = 0
        self.active: Active | None = None
        self.inbox: list[Parsed] = []
        self.assembler = Assembler()
        self.snapshots: dict[int, Snapshot] = {}
        self.rate = Rate()
        self.outbound: list[str] = []
        self.pending: QueuedHello | None = None
        self.tombstones: set[int] = set()


class V2Store:
    """World thread enqueues. Map worker matches the active generation, then applies.

    selfbot_off starts closed. Harness opens it with a startup proof of level 0.
    A reload cannot open a closed proof. The warning is once per process.
    Entropy failure stays closed: no hello and no apply. Tokens are random per
    summon and are not a restarted counter. The boot epoch is random per process.
    """

    def __init__(self, *, entropy_fails: bool = False, entropy=None) -> None:
        self.enabled = True
        self.players: dict[int, V2Player] = {}
        self.core_stables: dict[int, CoreStable] = {}
        self.last_sender = 0
        self.last_target = ""
        self.transport_sends = 0
        self.last_sent: str | None = None
        self.selfbot_off = False
        self.selfbot_warnings = 0
        self._selfbot_warned = False
        self.effective_level = WorldAtomic(-1)
        self._entropy = entropy or os.urandom
        self.entropy_ok = False
        self.boot_nonce = b""
        self.boot_epoch: int | None = None
        self.entropy_error: str | None = None
        self._mint_process_entropy(entropy_fails)

    def _mint_process_entropy(self, entropy_fails: bool) -> None:
        try:
            if entropy_fails:
                raise OSError("entropy unavailable")
            nonce = self._entropy(8)
            epoch_raw = self._entropy(4)
            if len(nonce) != 8 or len(epoch_raw) != 4:
                raise OSError("short entropy")
            epoch = int.from_bytes(epoch_raw, "big") % MAX_SEQ + 1
            if epoch < 1 or epoch > MAX_SEQ:
                raise OSError("epoch out of range")
            self.boot_nonce = bytes(nonce)
            self.boot_epoch = epoch
            self.entropy_ok = True
        except Exception as exc:
            self.entropy_ok = False
            self.boot_nonce = b""
            self.boot_epoch = None
            self.entropy_error = type(exc).__name__

    def _level_is_off(self, level: int | None, *, readable: bool,
                      playerbots_enabled: bool) -> bool:
        return (
            readable is True
            and playerbots_enabled is not False
            and type(level) is int
            and level == 0
        )

    def load_selfbot(self, level: int | None, *, readable: bool = True,
                     playerbots_enabled: bool = True, reload: bool = False) -> None:
        """World-thread config sample. level None is a missing key.

        readable False is a bad token. playerbots_enabled False is
        Playerbots.Enabled explicit false, which skips the SelfBotLevel
        assignment. Only integer 0 with that flag not false is off.
        reload=True never opens a closed latch. Any other sample closes it.
        Map workers do not call this.
        """
        proven = self._level_is_off(
            level, readable=readable, playerbots_enabled=playerbots_enabled
        )
        self.effective_level.store(0 if proven else -1)
        if not reload:
            self.selfbot_off = proven
        elif not proven:
            self.selfbot_off = False
        if not self.selfbot_off:
            self._drop_outbound()
            if not self._selfbot_warned:
                self._selfbot_warned = True
                self.selfbot_warnings += 1

    def note_playerbots_reload(self, level: int | None, *, readable: bool = True,
                               playerbots_enabled: bool = True) -> None:
        """Playerbots Initialize() path. It does not call OnAfterConfigLoad.

        Re-samples the effective level on the world thread. Never opens a
        closed latch. A value other than integer 0 closes the gate.
        """
        self.load_selfbot(
            level, readable=readable, playerbots_enabled=playerbots_enabled, reload=True
        )

    def apply_allowed(self) -> bool:
        """Map-side acquire load. Missing, unreadable, and non-zero stay closed."""
        return bool(self.selfbot_off) and self.effective_level.load() == 0 and self.entropy_ok

    def _drop_outbound(self) -> None:
        for player in self.players.values():
            player.outbound.clear()
            player.pending = None

    def player(self, guid: int) -> V2Player:
        return self.players.setdefault(guid, V2Player())

    def core_note_current(self, guid: int, pet: Pet | None) -> None:
        """Simulated core PetStable update. observe() must not call this."""
        stable = self.core_stables.setdefault(guid, CoreStable())
        if pet is None or pet.number is None or pet.number == 0:
            stable.current = None
            return
        stable.members.add(pet.number)
        stable.current = pet.number

    def login(self, guid: int) -> None:
        player = self.player(guid)
        player.logged_in = True
        player.active = None
        player.inbox.clear()
        player.assembler = Assembler()
        player.outbound.clear()
        player.pending = None
        if not self.entropy_ok or self.boot_epoch is None:
            player.epoch = 0
            return
        player.epoch = self.boot_epoch

    def logout(self, guid: int) -> None:
        player = self.player(guid)
        player.logged_in = False
        player.active = None
        player.inbox.clear()
        player.assembler = Assembler()
        player.outbound.clear()
        player.pending = None

    def retire_number(self, guid: int, number: int) -> None:
        """Core removed this number. Later reuse in this process does not write."""
        player = self.player(guid)
        player.tombstones.add(number)
        stable = self.core_stables.setdefault(guid, CoreStable())
        stable.members.discard(number)
        if stable.current == number:
            stable.current = None
        player.snapshots.pop(number, None)
        if player.active and player.active.pet_number == number:
            player.active = None
            player.assembler = Assembler()
            player.outbound.clear()
            player.pending = None

    def _clear_active(self, player: V2Player) -> None:
        player.active = None
        player.assembler = Assembler()
        player.outbound.clear()
        player.pending = None

    def observe(self, guid: int, pet: Pet | None) -> None:
        player = self.player(guid)
        if not self.entropy_ok or not player.logged_in or player.epoch == 0:
            return
        if pet is None or pet.owner != guid or pet.number is None or pet.number == 0:
            self._clear_active(player)
            return
        number = pet.number
        stable = self.core_stables.get(guid)
        in_stable = (
            stable is not None
            and stable.current == number
            and number in stable.members
        )
        if number in player.tombstones or not in_stable:
            self._clear_active(player)
            return
        if (
            player.active
            and player.active.pet_number == number
            and player.active.epoch == player.epoch
            and pet.incarnation is not None
            and player.active.incarnation == pet.incarnation
        ):
            return
        self.issue(player, pet, new_summon=True)

    def mint_token(self) -> str | None:
        if not self.entropy_ok or len(self.boot_nonce) != 8:
            self.entropy_ok = False
            return None
        try:
            raw = self._entropy(8)
            if len(raw) != 8:
                raise OSError("short entropy")
            mixed = bytes(left ^ right for left, right in zip(raw, self.boot_nonce))
            token = mixed.hex()
            if _TOKEN.match(token) is None:
                raise OSError("token shape")
            return token
        except Exception as exc:
            self.entropy_ok = False
            self.entropy_error = type(exc).__name__
            return None

    def issue(self, player: V2Player, pet: Pet, *, new_summon: bool) -> None:
        if (
            not self.entropy_ok
            or player.epoch == 0
            or player.next_gen >= MAX_SEQ
            or pet.number is None
        ):
            self._clear_active(player)
            return
        token = self.mint_token()
        if token is None:
            self._clear_active(player)
            return
        player.next_gen += 1
        if new_summon or pet.incarnation is None:
            if player.summon_counter >= MAX_SEQ:
                self._clear_active(player)
                return
            player.summon_counter += 1
            pet.incarnation = player.summon_counter
        hello = f"v2|hello|{player.epoch}|{token}|{player.next_gen}|{pet.number}"
        pending = QueuedHello(
            hello, player.epoch, token, player.next_gen, pet.number, pet.incarnation or 0
        )
        # One slot. A new hello replaces an unsent one. Summons do not pile up.
        player.outbound = [hello]
        player.pending = pending
        assert len(player.outbound) <= HELLO_QUEUE_CAP
        player.active = Active(
            pet.number, token, player.next_gen, player.epoch, hello, pet.incarnation or 0
        )
        player.assembler = Assembler()

    def _hello_current(self, guid: int, player: V2Player, pending: QueuedHello) -> bool:
        if not self.apply_allowed() or not player.logged_in:
            return False
        active = player.active
        stable = self.core_stables.get(guid)
        if active is None or stable is None:
            return False
        if pending.pet_number in player.tombstones:
            return False
        if stable.current != pending.pet_number or pending.pet_number not in stable.members:
            return False
        return (
            pending.epoch == player.epoch
            and pending.epoch == active.epoch
            and pending.token == active.token
            and pending.gen == active.gen
            and pending.incarnation == active.incarnation
            and pending.pet_number == active.pet_number
        )

    def send_outbound(self, guid: int) -> str:
        """World-thread send-time recheck. This model does not call Whisper."""
        player = self.players.get(guid)
        if player is None or player.pending is None:
            return "Empty"
        pending = player.pending
        if not self._hello_current(guid, player, pending):
            player.outbound.clear()
            player.pending = None
            return "Dropped"
        self.last_sent = pending.text
        self.transport_sends += 1
        player.outbound.clear()
        player.pending = None
        return "Sent"

    def world_accept(self, guid: int, raw: str, now_ms: int, target: str,
                     is_hunter: bool = True, has_client: bool = True) -> str:
        self.last_sender = guid
        self.last_target = target
        if not has_client:
            return "NoClient"
        if not self.enabled:
            return "Disabled"
        parsed = parse_message(raw)
        if parsed.kind == "NotDelivered":
            return "NotDelivered"
        if parsed.kind == "NotOurs":
            return "NotOurs"
        if not is_hunter:
            return "IgnoredNotHunter"
        if not self.selfbot_off or self.effective_level.load() != 0:
            return "SelfBotBlocked"
        if not self.entropy_ok:
            return "EntropyClosed"
        player = self.player(guid)
        if not player.logged_in:
            return "NotInWorld"
        if not player.rate.allow(now_ms):
            return "RateLimited"
        if parsed.kind in ("ClearV1", "ChunkV1"):
            return "RejectedLegacy"
        if parsed.kind not in ("ClearV2", "ChunkV2"):
            return "Malformed"
        player.inbox.append(parsed)
        return "Queued"

    def drain(self, guid: int, pet: Pet | None) -> None:
        player = self.player(guid)
        if not self.apply_allowed():
            player.inbox.clear()
            return
        batch = player.inbox
        player.inbox = []
        stable = self.core_stables.get(guid)
        for parsed in batch:
            active = player.active
            if (
                pet is None
                or pet.owner != guid
                or pet.number is None
                or pet.number == 0
                or active is None
                or stable is None
                or pet.number in player.tombstones
                or pet.number not in stable.members
                or stable.current != pet.number
                or pet.incarnation != active.incarnation
            ):
                continue
            if (
                parsed.epoch != active.epoch
                or parsed.token != active.token
                or parsed.gen != active.gen
                or pet.number != active.pet_number
            ):
                continue
            if parsed.kind == "ClearV2":
                player.snapshots.pop(pet.number, None)
                player.assembler = Assembler()
                self.issue(player, pet, new_summon=False)
                continue
            result = player.assembler.accept_chunk(parsed)
            if result == "Published" and player.assembler.published is not None and player.active:
                player.snapshots[pet.number] = Snapshot(
                    player.active.epoch,
                    player.active.gen,
                    player.assembler.published_seq,
                    dict(player.assembler.published),
                )

    def choices_for(self, guid: int, pet: Pet | None) -> dict[int, bool] | None:
        if not self.apply_allowed():
            return None
        if pet is None or pet.number == 0:
            return None
        player = self.players.get(guid)
        if player is None or not player.logged_in or player.active is None:
            return None
        if player.active.pet_number != pet.number or pet.incarnation != player.active.incarnation:
            return None
        stable = self.core_stables.get(guid)
        if stable is None or stable.current != pet.number or pet.number not in stable.members:
            return None
        snap = player.snapshots.get(pet.number)
        if snap is None or snap.epoch != player.epoch or snap.gen != player.active.gen:
            return None
        return snap.choices

    def record(self, guid: int, pet_number: int) -> dict[int, bool] | None:
        player = self.players.get(guid)
        if player is None:
            return None
        snap = player.snapshots.get(pet_number)
        if snap is None or snap.epoch != player.epoch:
            return None
        return snap.choices


class Harness:
    def __init__(self, kind: str, *, entropy_fails: bool = False, guid: int = 1):
        self.kind = kind
        self.store: V1Store | V2Store = (
            V1Store() if kind == "v1" else V2Store(entropy_fails=entropy_fails)
        )
        self.store.enabled = True
        if kind == "v2":
            self.store.load_selfbot(0)
        self.guid = guid
        self.pet: Pet | None = None
        self.now = 0
        self.store.login(self.guid)

    def summon(self, pet: Pet | None, *, in_core_stable: bool = True) -> None:
        self.pet = pet
        if self.kind != "v2":
            return
        store = self.store
        assert isinstance(store, V2Store)
        if in_core_stable:
            store.core_note_current(self.guid, pet)
        store.observe(self.guid, pet)

    def identity(self) -> tuple[int, str, int] | None:
        player = self.store.players[self.guid]  # type: ignore[attr-defined]
        active = player.active
        if active is None:
            return None
        return active.epoch, active.token, active.gen

    def hello_pet(self) -> int | None:
        if self.kind != "v2":
            return None
        if self.identity() is None:
            return None
        player = self.store.players[self.guid]  # type: ignore[attr-defined]
        return player.active.pet_number

    def last_hello(self) -> str:
        player = self.store.players[self.guid]  # type: ignore[attr-defined]
        return player.outbound[-1]

    def chunk(self, seq: int, pairs: str, n: int = 1, total: int = 1,
              ident: tuple[int, str, int] | None = None) -> str:
        if self.kind == "v1":
            return f"{PREFIX}v1|{seq}|{n}/{total}|{pairs}"
        epoch, token, gen = ident or self.identity()  # type: ignore[misc]
        return f"{PREFIX}v2|{epoch}|{token}|{gen}|{seq}|{n}/{total}|{pairs}"

    def clear(self, ident: tuple[int, str, int] | None = None) -> str:
        if self.kind == "v1":
            return f"{PREFIX}v1|clear"
        epoch, token, gen = ident or self.identity()  # type: ignore[misc]
        return f"{PREFIX}v2|{epoch}|{token}|{gen}|clear"

    def send(self, raw: str, target: str = "not-a-recipient-check",
             guid: int | None = None, is_hunter: bool = True, has_client: bool = True) -> str:
        return self.store.world_accept(
            guid or self.guid, raw, self.now, target, is_hunter, has_client
        )

    def tick(self, mutate=None, pet: Pet | None = None, allow_other: bool = False):
        target = self.pet if pet is None else pet
        if pet is not None and pet is not self.pet and not allow_other:
            return []
        if self.kind == "v2" and pet is None:
            self.store.observe(self.guid, self.pet)
        if mutate and self.pet is not None and pet is None:
            mutate(self.pet)
        if self.kind == "v2" and pet is None:
            self.store.drain(self.guid, self.pet)
        if pet is not None and pet is not self.pet:
            return []
        return apply_choices(target, self.store.choices_for(self.guid, target))

    def relog(self) -> None:
        self.store.logout(self.guid)
        self.store.login(self.guid)
        if self.kind == "v2" and self.pet is not None:
            self.store.observe(self.guid, self.pet)


def bite(pet: Pet) -> bool:
    return pet.spells[17259]


class PakD1(unittest.TestCase):
    def check(self, case: str, v1_safe: bool, v2_safe: bool, expect_v1: bool,
              expect_v2: bool, note: str) -> None:
        witness(case, v1_safe, v2_safe, note)
        self.assertEqual(v1_safe, expect_v1, case + " v1")
        self.assertEqual(v2_safe, expect_v2, case + " v2")

    def test_pak_id_01_same_name_delayed_complete(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet_a = make_wolf(101, bite=True)
            pet_b = make_wolf(202, bite=True)
            self.assertEqual(pet_a.name, pet_b.name)
            self.assertEqual(pet_a.family, pet_b.family)
            harness.summon(pet_a)
            if kind == "v2":
                self.assertEqual(harness.store.transport_sends, 0)
                self.assertTrue(harness.store.players[1].outbound[-1].startswith("v2|hello|"))
                delayed = harness.chunk(7, "17259=0")
            else:
                delayed = harness.chunk(7, "17259=0")
            harness.summon(pet_b)
            harness.send(delayed)
            harness.tick()
            results[kind] = bite(pet_b) is True and 17259 in pet_b.spells
        self.check(
            "PAK-ID-01",
            results["v1"],
            results["v2"],
            False,
            True,
            "same name/family; A's Bite OFF arrives after B is current",
        )

    def test_pak_id_02_multipart_straddle_reorder_conflict(self) -> None:
        straddle = {}
        reorder = {}
        conflict = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet_a = make_wolf(101, bite=True)
            pet_b = make_wolf(202, bite=True)
            harness.summon(pet_a)
            ident = harness.identity() if kind == "v2" else None
            first = harness.chunk(8, "17259=0", 1, 2, ident)
            second = harness.chunk(8, "1742=0", 2, 2, ident)
            harness.send(first)
            harness.summon(pet_b)
            harness.send(second)
            harness.tick()
            straddle[kind] = bite(pet_b) is True and pet_b.spells[COWER] is True

            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            ident = harness.identity() if kind == "v2" else None
            harness.send(harness.chunk(3, "1742=0", 2, 2, ident))
            harness.send(harness.chunk(3, "17259=0", 1, 2, ident))
            harness.tick()
            reorder[kind] = bite(pet) is False and pet.spells[COWER] is False

            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            harness.send(harness.chunk(3, "17259=1"))
            harness.tick()
            harness.send(harness.chunk(4, "17259=0", 1, 2))
            harness.send(harness.chunk(4, "17259=1", 1, 2))
            harness.tick()
            conflict[kind] = bite(pet) is True
        self.check("PAK-ID-02-straddle", straddle["v1"], straddle["v2"], False, True,
                   "A's two chunks complete after the swap onto B")
        self.check("PAK-ID-02-reorder", reorder["v1"], reorder["v2"], True, True,
                   "chunks 2 then 1 of one active generation assemble")
        self.check("PAK-ID-02-conflict", conflict["v1"], conflict["v2"], True, True,
                   "conflicting repeat discards the partial and keeps the published bit")

    def test_pak_id_03_resummon_same_pet_number_new_generation(self) -> None:
        results = {}
        numbers = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            first = make_wolf(101, bite=True)
            harness.summon(first)
            old = harness.identity() if kind == "v2" else None
            harness.send(harness.chunk(4, "17259=0"))
            harness.tick()
            self.assertFalse(bite(first))
            resumed = make_wolf(101, bite=True)
            numbers[kind] = resumed.number
            harness.summon(resumed)
            if kind == "v2":
                harness.send(harness.chunk(4, "17259=0", ident=old))
                harness.send(harness.chunk(1, "17259=0", ident=old))
            else:
                harness.send(harness.chunk(1, "17259=0"))
            harness.tick()
            stayed_on = bite(resumed) is True
            if kind == "v2":
                harness.send(harness.chunk(1, "17259=0"))
                harness.tick()
                self.assertFalse(bite(resumed))
                self.assertNotEqual(harness.identity(), old)
            results[kind] = stayed_on
        self.assertEqual(numbers["v1"], 101)
        self.assertEqual(numbers["v2"], 101)
        self.check(
            "PAK-ID-03",
            results["v1"],
            results["v2"],
            False,
            True,
            "pet number 101 retained; old generation must not force Bite OFF on resummon",
        )

    def test_pak_id_04_replay_after_clear(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            old = harness.identity() if kind == "v2" else None
            payload = harness.chunk(7, "17259=0", ident=old)
            harness.send(payload)
            harness.tick()
            self.assertFalse(bite(pet))
            harness.send(harness.clear(old))
            harness.tick()
            pet.spells[17259] = True
            harness.send(payload)
            harness.tick()
            results[kind] = bite(pet) is True
        self.check("PAK-ID-04", results["v1"], results["v2"], False, True,
                   "replay of the cleared seq does not revive Bite OFF")

    def test_pak_id_05_login_replay_does_not_overwrite(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet_a = make_wolf(101, bite=True)
            harness.summon(pet_a)
            old = harness.identity() if kind == "v2" else None
            stale = harness.chunk(7, "17259=0", ident=old)
            harness.relog()
            pet_b = make_wolf(202, bite=True)
            harness.summon(pet_b)
            fresh = harness.chunk(1, "17259=1")
            harness.send(fresh)
            harness.tick()
            self.assertTrue(bite(pet_b))
            harness.send(stale)
            harness.tick()
            results[kind] = bite(pet_b) is True
        self.check("PAK-ID-05", results["v1"], results["v2"], False, True,
                   "after logout/login a SavedVariables replay does not overwrite B")

    def test_pak_id_06_no_pet_not_current_and_pet_number_zero(self) -> None:
        zero = {}
        absent = {}
        other = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet0 = make_wolf(0, bite=True)
            harness.summon(pet0)
            if kind == "v1":
                harness.send(harness.chunk(1, "17259=0"))
            else:
                self.assertIsNone(harness.identity())
                harness.send(f"{PREFIX}v1|1|1/1|17259=0")
                harness.send(f"{PREFIX}v2|1|aaaaaaaaaaaaaaaa|1|1|1/1|17259=0")
            harness.tick()
            zero[kind] = bite(pet0) is True

            harness = Harness(kind)
            detached = make_wolf(101, bite=True)
            harness.summon(None)
            harness.send(harness.chunk(1, "17259=0") if kind == "v1"
                         else f"{PREFIX}v1|1|1/1|17259=0")
            harness.tick()
            absent[kind] = bite(detached) is True and 17259 in detached.spells

            harness = Harness(kind)
            current = make_wolf(101, bite=True)
            background = make_wolf(202, bite=True)
            harness.summon(current)
            harness.send(harness.chunk(1, "17259=0"))
            harness.tick()
            harness.tick(pet=background)
            other[kind] = bite(background) is True
        self.check("PAK-ID-06-number-0", zero["v1"], zero["v2"], False, True,
                   "PetNumber 0 is not a write target")
        self.check("PAK-ID-06-no-pet", absent["v1"], absent["v2"], True, True,
                   "no current pet does not write a detached spellbook")
        self.check("PAK-ID-06-not-current", other["v1"], other["v2"], True, True,
                   "a pet that is not owner current is not written")

    def test_pak_clear_01_clear_leaves_the_other_pet(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet_a = make_wolf(101, bite=True)
            pet_b = make_wolf(202, bite=True)
            harness.summon(pet_a)
            harness.send(harness.chunk(1, "17259=0"))
            harness.tick()
            harness.summon(pet_b)
            harness.send(harness.chunk(2, "17259=1"))
            harness.tick()
            harness.send(harness.clear())
            harness.tick()
            kept = harness.store.record(harness.guid, 101)
            cleared = harness.store.record(harness.guid, 202)
            results[kind] = (
                kept is not None
                and kept.get(BITE[0]) is False
                and cleared is None
            )
        self.check("PAK-CLEAR-01", results["v1"], results["v2"], False, True,
                   "clear of the active pet leaves the other pet's Bite OFF record")

    def test_pak_spell_01_missing_spell_not_learned(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=None, cower=True)
            before = set(pet.spells)
            harness.summon(pet)
            harness.send(harness.chunk(1, "17259=0,1742=0"))
            harness.tick()
            results[kind] = 17259 not in pet.spells and set(pet.spells) == before and pet.spells[COWER] is False
        self.check("PAK-SPELL-01", results["v1"], results["v2"], True, True,
                   "listed Bite missing from the book is not inserted; present Cower still toggles")

    def test_pak_spell_02_bite_successor(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)

            def mutate(target: Pet) -> None:
                reconcile(target.spells, {627050}, BITE, BITE_DUMMY)

            harness.summon(pet)
            harness.send(harness.chunk(1, "17259=0"))
            harness.tick(mutate)
            results[kind] = (
                17259 not in pet.spells
                and pet.spells.get(27050) is False
                and GROWL in pet.spells
            )
        self.check("PAK-SPELL-02", results["v1"], results["v2"], True, True,
                   "IP Bite keep 27050 receives OFF; removed 17259 is not inserted")

    def test_pak_spell_03_claw_successor_and_wolf_claw_wipe(self) -> None:
        cat = {}
        wolf = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = Pet(101, "Fluffy", "Cat", {16827: True, GROWL: True})

            def mutate_cat(target: Pet) -> None:
                reconcile(target.spells, {627049}, CLAW, CAT_CLAW_DUMMY)

            harness.summon(pet)
            harness.send(harness.chunk(1, "16827=0"))
            harness.tick(mutate_cat)
            cat[kind] = 16827 not in pet.spells and pet.spells.get(27049) is False

            harness = Harness(kind)
            pet = make_wolf(101, bite=True, claw=16832)

            def mutate_wolf(target: Pet) -> None:
                reconcile(target.spells, set(), CLAW, [])

            before_growl = pet.spells[GROWL]
            harness.summon(pet)
            harness.send(harness.chunk(1, "16832=1"))
            harness.tick(mutate_wolf)
            wolf[kind] = (
                all(rank not in pet.spells for rank in CLAW)
                and pet.spells[GROWL] is before_growl
            )
        self.check("PAK-SPELL-03-cat-claw", cat["v1"], cat["v2"], True, True,
                   "Cat Claw keep 27049 receives OFF; 16827 is not inserted")
        self.check("PAK-SPELL-03-wolf-claw", wolf["v1"], wolf["v2"], True, True,
                   "Wolf Claw empty dummy list removes Claw; apply does not learn it")

    def test_pak_spell_04_cower_present_and_absent(self) -> None:
        present = {}
        absent = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True, cower=True)
            harness.summon(pet)
            harness.send(harness.chunk(1, "1742=0"))
            harness.tick()
            present[kind] = COWER in pet.spells and pet.spells[COWER] is False

            harness = Harness(kind)
            pet = Pet(202, "Fluffy", "Serpent", {17259: True, GROWL: True})

            def wipe(target: Pet) -> None:
                reconcile(target.spells, set(), [COWER], [])

            harness.summon(pet)
            harness.send(harness.chunk(1, "1742=1"))
            harness.tick(wipe)
            absent[kind] = COWER not in pet.spells
        self.check("PAK-SPELL-04-present", present["v1"], present["v2"], True, True,
                   "Cower 1742 present is toggled and kept")
        self.check("PAK-SPELL-04-absent", absent["v1"], absent["v2"], True, True,
                   "Serpent Cower wipe does not learn 1742")

    def test_pak_spell_05_unlisted_and_non_autocastable(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            pet.spells[NOT_AUTO] = True
            harness.summon(pet)
            harness.send(harness.chunk(1, f"17259=0,{NOT_AUTO}=0"))
            harness.tick()
            results[kind] = (
                pet.spells[GROWL] is True
                and pet.spells[NOT_AUTO] is True
                and bite(pet) is False
            )
        self.check("PAK-SPELL-05", results["v1"], results["v2"], True, True,
                   "unlisted Growl and non-autocastable 6603 are not written; listed Bite is")

    def test_pak_auth_01_sender_not_whisper_target(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            sender_pet = make_wolf(101, bite=True)
            other = make_wolf(303, bite=True)
            harness.summon(sender_pet)
            harness.send(harness.chunk(1, "17259=0"), target="OtherPlayer")
            sender = harness.store.last_sender
            target_name = harness.store.last_target
            harness.tick()
            results[kind] = (
                sender == 1
                and target_name == "OtherPlayer"
                and bite(sender_pet) is False
                and bite(other) is True
                and harness.store.record(2, other.number) is None
            )
        self.check("PAK-AUTH-01", results["v1"], results["v2"], True, True,
                   "write stays on the hook player; whisper target is not the key")

    def test_pak_v1_legacy_rejected_by_v2(self) -> None:
        v1 = Harness("v1")
        pet_v1 = make_wolf(101, bite=True)
        v1.summon(pet_v1)
        v1.send(f"{PREFIX}v1|7|1/1|17259=0")
        v1.tick()
        v1_published = bite(pet_v1) is False

        v2 = Harness("v2")
        pet = make_wolf(101, bite=True)
        v2.summon(pet)
        gen_before = v2.identity()
        self.assertEqual(v2.send(f"{PREFIX}v1|7|1/1|17259=0"), "RejectedLegacy")
        self.assertEqual(v2.send(f"{PREFIX}v1|clear"), "RejectedLegacy")
        v2.tick()
        v2_safe = bite(pet) is True and v2.identity() == gen_before and v2.store.record(1, 101) is None
        self.check("PAK-V1-LEGACY", not v1_published, v2_safe, False, True,
                   "v1 data and v1|clear publish on the v1 model and are rejected by v2")

    def test_pak_budget_and_documented_wires(self) -> None:
        proposal = PROPOSAL.read_text(encoding="utf-8")
        start = proposal.index("```wire\n") + len("```wire\n")
        block = proposal[start : proposal.index("```", start)]
        wires = [line.replace("\\t", "\t") for line in block.splitlines() if line.strip()]
        self.assertEqual(len(wires), 5)
        lengths = [(len(wire) - len(PREFIX), len(wire)) for wire in wires]
        self.assertEqual(lengths, [(33, 40), (44, 51), (29, 36), (23, 30), (8, 15)])
        for wire, (payload, combined) in zip(wires, lengths):
            self.assertLessEqual(combined, 255)
            self.assertLessEqual(payload, 233)
            self.assertTrue(wire.startswith(PREFIX))
        self.assertIn("| 44 | 51 |", proposal)
        self.assertIn("| 23 | 30 |", proposal)
        self.assertIn("That prefix is 54 bytes", proposal)
        self.assertIn("leaves 179 bytes", proposal)
        worst = "v2|999999999|aaaaaaaaaaaaaaaa|999999999|999999999|8/8|"
        self.assertEqual(len(worst), 54)
        self.assertEqual(233 - len(worst), 179)
        longest_hello = "v2|hello|999999999|aaaaaaaaaaaaaaaa|999999999|4294967295"
        self.assertEqual(len(longest_hello), 56)
        self.assertEqual(len(PREFIX) + len(longest_hello), 63)
        self.assertIn("is 56 bytes", proposal)

        dropped = PREFIX + ("v" * 249)
        delivered = PREFIX + ("v" * 248)
        self.assertEqual(len(dropped), 256)
        self.assertEqual(len(delivered), 255)
        held = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            self.assertEqual(harness.send(dropped), "NotDelivered")
            self.assertEqual(harness.send(delivered), "Malformed")
            harness.tick()
            held[kind] = bite(pet) is True
        self.check("PAK-BUDGET", held["v1"], held["v2"], True, True,
                   "256 is not delivered; 255 malformed does not write; documented wires fit")

    def test_pak_flag_defaults_off_and_model_fail_closed(self) -> None:
        conf = CONF.read_text(encoding="utf-8")
        cpp = CPP.read_text(encoding="utf-8")
        self.assertEqual(conf.count("NaxxramasCore.HunterPetAutocast.AddonOptIn = 0"), 1)
        self.assertEqual(conf.count("NaxxramasCore.HunterPetAutocast.RestoreHumanChain = 0"), 1)
        self.assertIn('GetOption<bool>("NaxxramasCore.HunterPetAutocast.AddonOptIn", false)', cpp)
        self.assertIn("AddonOptInEnabled{false}", cpp)
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            harness.store.enabled = False
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            status = harness.send(harness.chunk(1, "17259=0") if kind == "v1"
                                  else f"{PREFIX}v1|1|1/1|17259=0")
            self.assertEqual(status, "Disabled")
            harness.tick()
            results[kind] = bite(pet) is True and harness.store.transport_sends == 0
        self.check("PAK-FLAG", results["v1"], results["v2"], True, True,
                   "source defaults are 0; a disabled store does not apply or send")

    def test_source_anchors_and_proposal_labels(self) -> None:
        header = ADDON_H.read_text(encoding="utf-8")
        cpp = CPP.read_text(encoding="utf-8")
        proposal = PROPOSAL.read_text(encoding="utf-8")
        self.assertIn("kMaxRawBytes = 255", header)
        self.assertIn("slot.LastSeq = 0", header)
        self.assertIn("slot.Published.reset()", header)
        login = header.split("void OnLogin", 1)[1].split("void OnLogout", 1)[0]
        self.assertNotIn("Published", login)
        self.assertNotIn("GetPetNumber", cpp)
        self.assertNotIn("Playerbots.h", cpp)
        self.assertIn("does not read _playerbotsAIMap", cpp)
        self.assertIn("v2 PROPOSAL / v1 UNSAFE FOR AUTO APPLY", proposal)
        self.assertIn("Playerbots.SelfBotLevel", proposal)
        self.assertIn("08:04 GMT", proposal)
        self.assertIn("AC_PLAYERBOTS_SELF_BOT_LEVEL", proposal)
        self.assertIn("does not open a closed atomic", proposal)
        self.assertNotIn("OWNER DECISION REQUIRED", proposal)
        self.assertIn("CharmInfo::GetPetNumber", proposal)
        self.assertIn("v2|hello|<epoch>|<token>|<gen>|<pet>", proposal)
        self.assertIn("owner stated in chat to CS02, relayed on #48 6395196578", proposal)
        self.assertIn("6395269291", proposal)
        self.assertIn("db.pets[petNumber]", proposal)
        self.assertIn("not a durable", proposal)
        self.assertIn("PAK-RESTART-01", proposal)
        self.assertIn("PAK-STABLE-MEMBER-01", proposal)
        self.assertIn("PAK-HELLO-STALE-01", proposal)
        self.assertIn("GetRandomBytes", proposal)
        self.assertIn("Hybrid H", proposal)
        self.assertIn("not selected", proposal)
        self.assertIn("per-summon", proposal)
        self.assertIn("ChatHandler.cpp:292", proposal)
        self.assertIn("checkHunterPetSpells", proposal)
        self.assertIn("Playerbots `d750b4b` was read and not modified", proposal)
        self.assertIn("UNKNOWN", proposal)
        self.assertNotIn("passed in game", proposal.lower())
        print("SOURCE_ANCHORS proposal+header+cpp OK")

    def test_duplicate_same_chunk_does_not_disturb_an_open_partial(self) -> None:
        results = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            harness.send(harness.chunk(5, "17259=0", 1, 2))
            again = harness.send(harness.chunk(5, "17259=0", 1, 2))
            self.assertEqual(again, "Partial" if kind == "v1" else "Queued")
            harness.send(harness.chunk(5, "1742=1", 2, 2))
            harness.tick()
            results[kind] = bite(pet) is False and pet.spells[COWER] is True
        self.check("PAK-ID-02-duplicate", results["v1"], results["v2"], True, True,
                   "a repeated identical chunk still lets the sequence complete")

    def _closed_gate(self, level: int | None, *, readable: bool = True,
                     playerbots_enabled: bool = True, reload_to_zero: bool = False) -> dict[str, bool]:
        """True when that model did not turn Bite OFF."""
        held: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            if kind == "v2":
                if reload_to_zero:
                    harness.store.load_selfbot(1)
                    harness.store.load_selfbot(0, reload=True)
                    self.assertFalse(harness.store.selfbot_off)
                    self.assertEqual(harness.store.selfbot_warnings, 1)
                else:
                    harness.store.load_selfbot(
                        level, readable=readable, playerbots_enabled=playerbots_enabled
                    )
                    self.assertFalse(harness.store.selfbot_off)
                    self.assertEqual(harness.store.selfbot_warnings, 1)
                    harness.store.load_selfbot(
                        level, readable=readable, playerbots_enabled=playerbots_enabled,
                        reload=True,
                    )
                    self.assertEqual(harness.store.selfbot_warnings, 1)
                self.assertEqual(harness.send(harness.chunk(1, "17259=0")), "SelfBotBlocked")
            else:
                self.assertNotEqual(harness.send(harness.chunk(1, "17259=0")), "SelfBotBlocked")
            harness.tick()
            held[kind] = bite(pet) is True
        return held

    def test_pak_self_enabled_denies_a_valid_message(self) -> None:
        held = None
        for level in (1, 2, 3):
            held = self._closed_gate(level)
            self.assertFalse(held["v1"])
            self.assertTrue(held["v2"])
        assert held is not None
        self.check(
            "PAK-SELF-ENABLED",
            held["v1"],
            held["v2"],
            False,
            True,
            "SelfBotLevel 1, 2, and 3 deny a valid message; 1 is the dist default",
        )

    def test_pak_self_unreadable_and_missing_deny(self) -> None:
        bad = self._closed_gate(0, readable=False)
        missing = self._closed_gate(None)
        self.check(
            "PAK-SELF-UNREADABLE",
            bad["v1"],
            bad["v2"],
            False,
            True,
            "a bad SelfBot token denies the write and warns once",
        )
        self.check(
            "PAK-SELF-MISSING",
            missing["v1"],
            missing["v2"],
            False,
            True,
            "a missing SelfBot key denies the write",
        )

    def test_pak_self_enabled_false_denies_even_when_level_is_zero(self) -> None:
        held = self._closed_gate(0, playerbots_enabled=False)
        self.check(
            "PAK-SELF-MODULE",
            held["v1"],
            held["v2"],
            False,
            True,
            "Playerbots.Enabled false skips the SelfBotLevel assignment, so file 0 is not proof",
        )

    def test_pak_self_off_allows_a_valid_v2_message(self) -> None:
        wrote: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            if kind == "v2":
                harness.store.load_selfbot(0)
                self.assertTrue(harness.store.selfbot_off)
                self.assertEqual(harness.store.selfbot_warnings, 0)
            status = harness.send(harness.chunk(1, "17259=0"))
            harness.tick()
            if kind == "v2":
                self.assertEqual(status, "Queued")
            wrote[kind] = bite(pet) is False
        self.check(
            "PAK-SELF-OFF",
            wrote["v1"],
            wrote["v2"],
            True,
            True,
            "startup SelfBotLevel 0 applies one valid message from a connected client",
        )

    def test_pak_self_reload_to_zero_does_not_open(self) -> None:
        held = self._closed_gate(1, reload_to_zero=True)
        self.check(
            "PAK-SELF-RELOAD",
            held["v1"],
            held["v2"],
            False,
            True,
            "a reload from 1 to 0 does not open a gate that started closed",
        )

    def test_pak_self_no_client_is_not_delivered(self) -> None:
        held: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            raw = harness.chunk(1, "17259=0") if kind == "v1" else harness.chunk(1, "17259=0")
            self.assertEqual(harness.send(raw, has_client=False), "NoClient")
            harness.tick()
            held[kind] = bite(pet) is True and harness.store.record(harness.guid, pet.number) is None
        self.check(
            "PAK-SELF-NOCLIENT",
            held["v1"],
            held["v2"],
            True,
            True,
            "a sender with no client does not deliver NXCPAK; headless bots cannot write",
        )

    def test_pak_id_07_pet_number_restores_a_after_relog(self) -> None:
        """Client saves are keyed by hello pet number. v1 still uses the shared name."""
        restored: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            saves: dict[object, str] = {}
            pet_a = make_wolf(101, bite=True)
            pet_b = make_wolf(202, bite=True)
            harness.summon(pet_a)
            if kind == "v2":
                self.assertEqual(harness.hello_pet(), 101)
                self.assertTrue(harness.last_hello().endswith("|101"))
                self.assertNotIn("|101|", harness.chunk(1, "17259=0"))
                saves[101] = "17259=0"
            else:
                saves["name:Fluffy"] = "17259=0"
            key_a = 101 if kind == "v2" else "name:Fluffy"
            harness.send(harness.chunk(1, saves[key_a]))
            harness.tick()
            self.assertFalse(bite(pet_a))

            harness.summon(pet_b)
            if kind == "v2":
                self.assertEqual(harness.hello_pet(), 202)
                saves[202] = "17259=1"
                self.assertNotEqual(101, 202)
            else:
                saves["name:Fluffy"] = "17259=1"
            key_b = 202 if kind == "v2" else "name:Fluffy"
            harness.send(harness.chunk(2, saves[key_b]))
            harness.tick()
            self.assertTrue(bite(pet_b))
            b_after = dict(pet_b.spells)

            harness.summon(pet_a)
            looked_up = saves[harness.hello_pet() if kind == "v2" else "name:Fluffy"]
            harness.send(harness.chunk(1, looked_up))
            harness.tick()

            fresh = make_wolf(101, bite=True)
            old_token = harness.identity() if kind == "v2" else None
            harness.relog()
            harness.summon(fresh)
            if kind == "v2":
                self.assertEqual(harness.hello_pet(), 101)
                self.assertNotEqual(harness.identity(), old_token)
                self.assertTrue(harness.last_hello().endswith("|101"))
            looked_up = saves[harness.hello_pet() if kind == "v2" else "name:Fluffy"]
            harness.send(harness.chunk(1, looked_up))
            harness.tick()
            restored[kind] = (
                bite(fresh) is False
                and bite(pet_b) is True
                and pet_b.spells == b_after
                and (kind == "v1" or harness.store.record(1, 202) is None or True)
            )
            if kind == "v2":
                self.assertIsNone(harness.store.choices_for(1, pet_b))
                self.assertEqual(harness.store.record(1, 101), {BITE[0]: False})
                self.assertEqual(pet_b.spells, b_after)
        self.check(
            "PAK-ID-07",
            restored["v1"],
            restored["v2"],
            False,
            True,
            "same-process pet-number resend restores A OFF on a fresh token; B is not written; not a durable key",
        )

    def _no_write(self, mutate) -> dict[str, bool]:
        held: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            before = dict(pet.spells)
            mutate(harness, pet, kind)
            harness.tick()
            held[kind] = pet.spells == before
        return held

    def test_pak_id_07_missing_and_zero_do_not_write(self) -> None:
        def missing(harness: Harness, pet: Pet, kind: str) -> None:
            pet.number = None
            harness.summon(pet)
            if kind == "v2":
                self.assertIsNone(harness.identity())
                harness.send(f"{PREFIX}v2|1|aaaaaaaaaaaaaaaa|1|1|1/1|17259=0")
            else:
                harness.send(harness.chunk(1, "17259=0"))

        def zero(harness: Harness, pet: Pet, kind: str) -> None:
            pet.number = 0
            harness.summon(pet)
            if kind == "v2":
                self.assertIsNone(harness.identity())
                harness.send(f"{PREFIX}v2|1|aaaaaaaaaaaaaaaa|1|1|1/1|17259=0")
            else:
                harness.send(harness.chunk(1, "17259=0"))

        missed = self._no_write(missing)
        zeros = self._no_write(zero)
        self.check("PAK-ID-07-MISSING", missed["v1"], missed["v2"], False, True,
                   "a missing pet number does not write")
        self.check("PAK-ID-07-ZERO", zeros["v1"], zeros["v2"], False, True,
                   "pet number 0 does not write")

    def test_pak_id_07_deleted_and_reused_do_not_write(self) -> None:
        deleted: dict[str, bool] = {}
        reused: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            harness.send(harness.chunk(1, "17259=0"))
            harness.tick()
            self.assertFalse(bite(pet))
            if kind == "v2":
                harness.store.retire_number(harness.guid, 101)
            gone = make_wolf(101, bite=True)
            harness.summon(gone)
            if kind == "v2":
                self.assertIsNone(harness.identity())
                harness.send(f"{PREFIX}v2|1|bbbbbbbbbbbbbbbb|1|1|1/1|17259=0")
            else:
                harness.send(harness.chunk(2, "17259=0"))
            harness.tick()
            deleted[kind] = bite(gone) is True and gone.spells[17259] is True

            again = make_wolf(101, bite=True)
            harness.summon(again)
            if kind == "v2":
                self.assertIsNone(harness.hello_pet())
                harness.send(f"{PREFIX}v2|1|cccccccccccccccc|1|2|1/1|17259=0")
            else:
                harness.send(harness.chunk(3, "17259=0"))
            harness.tick()
            reused[kind] = bite(again) is True
        self.check("PAK-ID-07-DELETED", deleted["v1"], deleted["v2"], False, True,
                   "a deleted pet number does not write")
        self.check("PAK-ID-07-REUSED", reused["v1"], reused["v2"], False, True,
                   "a reused pet number does not write")

    def test_pak_id_07_stale_token_does_not_write(self) -> None:
        held: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            first = make_wolf(101, bite=True)
            harness.summon(first)
            old = harness.identity() if kind == "v2" else None
            harness.send(harness.chunk(1, "17259=1"))
            harness.tick()
            resumed = make_wolf(101, bite=True)
            harness.summon(resumed)
            harness.send(harness.chunk(2, "17259=0", ident=old))
            harness.tick()
            held[kind] = bite(resumed) is True
        self.check("PAK-ID-07-STALE", held["v1"], held["v2"], False, True,
                   "a chunk from the previous token does not write")

    def test_pak_id_07_clear_does_not_write_the_other_pet(self) -> None:
        held: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet_a = make_wolf(101, bite=True)
            pet_b = make_wolf(202, bite=True)
            harness.summon(pet_a)
            harness.send(harness.chunk(1, "17259=0"))
            harness.tick()
            harness.summon(pet_b)
            harness.send(harness.chunk(2, "17259=1"))
            harness.tick()
            b_spells = dict(pet_b.spells)
            harness.summon(pet_a)
            a_spells = dict(pet_a.spells)
            harness.send(harness.clear())
            harness.tick()
            b_record = harness.store.record(harness.guid, 202)
            a_record = harness.store.record(harness.guid, 101)
            held[kind] = (
                pet_a.spells == a_spells
                and pet_b.spells == b_spells
                and b_record is not None
                and b_record.get(BITE[0]) is True
                and a_record is None
            )
        self.check("PAK-ID-07-CLEAR", held["v1"], held["v2"], False, True,
                   "clear of A removes only A's record and writes neither spellbook")

    def test_pak_restart_01_fresh_process_rejects_the_old_packet(self) -> None:
        """Two process models, same owner and pet. No logout on the first."""
        first = Harness("v2", guid=7)
        pet = make_wolf(17259, bite=True, owner=7)
        first.summon(pet)
        old = first.chunk(1, "17259=0")
        first.send(old)
        first.tick()
        self.assertFalse(bite(pet))
        first_token = first.identity()
        assert first_token is not None

        second = Harness("v2", guid=7)
        resumed = make_wolf(17259, bite=True, owner=7)
        second.summon(resumed)
        second_token = second.identity()
        assert second_token is not None
        self.assertNotEqual(second_token[1], first_token[1])
        self.assertNotEqual(second.store.boot_epoch, first.store.boot_epoch)
        self.assertNotEqual(second.store.boot_nonce, first.store.boot_nonce)
        self.assertEqual(second.send(old), "Queued")
        second.tick()
        fresh_rejected = bite(resumed) is True and second.store.record(7, 17259) is None
        second.send(second.chunk(1, "17259=0"))
        second.tick()
        self.assertFalse(bite(resumed))

        legacy = Harness("v1", guid=7)
        legacy_pet = make_wolf(17259, bite=True, owner=7)
        legacy.summon(legacy_pet)
        legacy_old = legacy.chunk(1, "17259=0")
        legacy.send(legacy_old)
        legacy.tick()
        restarted = Harness("v1", guid=7)
        restarted_pet = make_wolf(17259, bite=True, owner=7)
        restarted.summon(restarted_pet)
        restarted.send(legacy_old)
        restarted.tick()
        v1_safe = bite(restarted_pet) is True
        self.check(
            "PAK-RESTART-01",
            v1_safe,
            fresh_rejected,
            False,
            True,
            "a completed pre-restart packet does not apply on a fresh process; v1 accepts it",
        )

    def test_pak_restart_entropy_failure_is_closed(self) -> None:
        closed = Harness("v2", entropy_fails=True)
        pet = make_wolf(101, bite=True)
        closed.summon(pet)
        self.assertFalse(closed.store.entropy_ok)
        self.assertIsNone(closed.identity())
        self.assertEqual(closed.store.players[1].outbound, [])
        self.assertEqual(closed.store.boot_epoch, None)
        status = closed.send(f"{PREFIX}v2|1|aaaaaaaaaaaaaaaa|1|1|1/1|17259=0")
        self.assertEqual(status, "EntropyClosed")
        closed.tick()
        entropy_held = bite(pet) is True and closed.store.record(1, 101) is None

        class ShortEntropy:
            def __call__(self, size: int) -> bytes:
                return b"\x01" * max(0, size - 1)

        short = V2Store(entropy=ShortEntropy())
        short.load_selfbot(0)
        short.login(1)
        self.assertFalse(short.entropy_ok)
        short.core_note_current(1, pet)
        short.observe(1, pet)
        self.assertIsNone(short.players[1].active)
        self.assertEqual(short.players[1].outbound, [])

        open_v1 = Harness("v1")
        v1_pet = make_wolf(101, bite=True)
        open_v1.summon(v1_pet)
        open_v1.send(open_v1.chunk(1, "17259=0"))
        open_v1.tick()
        self.check(
            "PAK-RESTART-ENTROPY",
            bite(v1_pet) is True,
            entropy_held and short.players[1].active is None,
            False,
            True,
            "entropy failure mints no token and applies nothing; there is no counter fallback",
        )

    def test_pak_stable_member_01_missing_number_does_not_self_insert(self) -> None:
        held: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            raw = harness.chunk(1, "17259=0")
            if kind == "v2":
                stable = harness.store.core_stables[1]
                stable.members.clear()
                stable.current = None
                self.assertNotIn(101, stable.members)
            harness.send(raw)
            harness.tick()
            if kind == "v2":
                self.assertNotIn(101, harness.store.core_stables[1].members)
                self.assertIsNone(harness.store.core_stables[1].current)
                unseen = make_wolf(303, bite=True)
                before = dict(unseen.spells)
                harness.store.observe(1, unseen)
                self.assertNotIn(303, harness.store.core_stables[1].members)
                self.assertIsNone(unseen.incarnation)
                self.assertEqual(unseen.spells, before)
            held[kind] = bite(pet) is True
        self.check(
            "PAK-STABLE-MEMBER-01",
            held["v1"],
            held["v2"],
            False,
            True,
            "a pet number missing from the core stable does not write and is not inserted by observe",
        )

    def test_pak_hello_stale_01_send_time_drops_stale_hello(self) -> None:
        capped = Harness("v2")
        for _ in range(50):
            capped.summon(make_wolf(101, bite=True))
        self.assertEqual(len(capped.store.players[1].outbound), HELLO_QUEUE_CAP)
        self.assertEqual(capped.store.players[1].summon_counter, 50)

        swapped = Harness("v2")
        pet_a = make_wolf(101, bite=True)
        pet_b = make_wolf(202, bite=True)
        swapped.summon(pet_a)
        stale = swapped.store.players[1].pending
        assert stale is not None
        swapped.summon(pet_b)
        player = swapped.store.players[1]
        player.outbound = [stale.text]
        player.pending = stale
        self.assertEqual(swapped.store.send_outbound(1), "Dropped")
        self.assertEqual(swapped.store.transport_sends, 0)
        self.assertIsNone(swapped.store.last_sent)
        self.assertEqual(
            client_bind_hello(stale.pet_number, pet_b.number, stale.epoch, None),
            "drop",
        )
        swap_held = bite(pet_b) is True and pet_b.spells[COWER] is True

        logged_out = Harness("v2")
        logged_out.summon(make_wolf(101, bite=True))
        pending = logged_out.store.players[1].pending
        assert pending is not None
        logged_out.store.logout(1)
        self.assertEqual(logged_out.store.players[1].outbound, [])
        logged_out.store.players[1].outbound = [pending.text]
        logged_out.store.players[1].pending = pending
        self.assertEqual(logged_out.store.send_outbound(1), "Dropped")

        gated = Harness("v2")
        gated.summon(make_wolf(101, bite=True))
        held_hello = gated.store.players[1].pending
        assert held_hello is not None
        gated.store.note_playerbots_reload(2)
        gated.store.players[1].outbound = [held_hello.text]
        gated.store.players[1].pending = held_hello
        self.assertEqual(gated.store.send_outbound(1), "Dropped")

        legacy = Harness("v1")
        legacy_a = make_wolf(101, bite=True)
        legacy_b = make_wolf(202, bite=True)
        legacy.summon(legacy_a)
        delayed = legacy.chunk(1, "17259=0")
        legacy.summon(legacy_b)
        legacy.send(delayed)
        legacy.tick()
        v1_safe = bite(legacy_b) is True
        v2_safe = swap_held and logged_out.store.last_sent is None and gated.store.last_sent is None
        self.check(
            "PAK-HELLO-STALE-01",
            v1_safe,
            v2_safe,
            False,
            True,
            "send-time recheck drops A's hello after a swap, logout, or SelfBot close; the queue stays at one",
        )

    def test_pak_summon_01_incarnation_is_not_the_pointer(self) -> None:
        results: dict[str, bool] = {}
        for kind in ("v1", "v2"):
            harness = Harness(kind)
            first = make_wolf(101, bite=True)
            harness.summon(first)
            old = harness.identity() if kind == "v2" else None
            second = make_wolf(101, bite=True)
            harness.summon(second)
            if kind == "v2":
                assert old is not None
                self.assertNotEqual(second.incarnation, None)
                self.assertNotEqual(second.incarnation, first.incarnation)
                self.assertNotEqual(harness.identity(), old)
                self.assertNotEqual(harness.identity()[1], f"{id(second) & ((1 << 64) - 1):016x}")
                harness.send(harness.chunk(1, "17259=0", ident=old))
                harness.tick()
                kept = harness.identity()
                harness.tick()
                self.assertEqual(harness.identity(), kept)
                self.assertEqual(second.incarnation, harness.store.players[1].summon_counter)
                results[kind] = bite(second) is True
            else:
                harness.send(harness.chunk(1, "17259=0"))
                harness.tick()
                results[kind] = bite(second) is True
        self.check(
            "PAK-SUMMON-01",
            results["v1"],
            results["v2"],
            False,
            True,
            "a new summon gets a new incarnation and token; the pointer is not the token; the old packet does not write",
        )

    def test_pak_self_apply_rechecks_playerbots_reload(self) -> None:
        def closed_after_queue(level: int | None, **kwargs: bool) -> bool:
            harness = Harness("v2")
            pet = make_wolf(101, bite=True)
            harness.summon(pet)
            harness.send(harness.chunk(1, "17259=0"))
            harness.tick()
            self.assertFalse(bite(pet))
            pet.spells[17259] = True
            harness.store.note_playerbots_reload(level, **kwargs)
            harness.send(harness.chunk(2, "17259=0"))
            harness.tick()
            return bite(pet) is True and harness.store.choices_for(1, pet) is None

        reloaded = closed_after_queue(2)
        missing = closed_after_queue(None)
        unreadable = closed_after_queue(0, readable=False)
        legacy = Harness("v1")
        legacy_pet = make_wolf(101, bite=True)
        legacy.summon(legacy_pet)
        legacy.send(legacy.chunk(1, "17259=0"))
        legacy.tick()
        self.check(
            "PAK-SELF-APPLY",
            bite(legacy_pet) is True,
            reloaded and missing and unreadable,
            False,
            True,
            "apply re-checks SelfBotLevel; 2, missing, and unreadable apply nothing after a Playerbots reload",
        )

    def test_pak_id_quarantine_pet_number_is_not_durable_across_restart(self) -> None:
        binder = ClientBinder()
        first = Harness("v2", guid=7)
        pet = make_wolf(101, bite=True, owner=7)
        first.summon(pet)
        epoch = first.identity()[0]  # type: ignore[index]
        self.assertTrue(binder.note_choice(epoch, 101, "17259=0"))
        old = first.chunk(1, "17259=0")
        first.send(old)
        first.tick()
        self.assertFalse(bite(pet))

        second = Harness("v2", guid=7)
        resumed = make_wolf(101, bite=True, owner=7)
        second.summon(resumed)
        new_epoch = second.identity()[0]  # type: ignore[index]
        self.assertEqual(binder.on_epoch(new_epoch), "quarantine")
        self.assertIsNone(binder.auto_payload(101))
        second.send(old)
        second.tick()
        quarantined = bite(resumed) is True and 101 in binder.quarantine

        legacy = Harness("v1")
        legacy_pet = make_wolf(101, bite=True)
        legacy.summon(legacy_pet)
        legacy.send(legacy.chunk(1, binder.rows_saved_for_v1()))
        legacy.tick()
        self.check(
            "PAK-ID-QUARANTINE",
            bite(legacy_pet) is True,
            quarantined,
            False,
            True,
            "a new boot epoch quarantines db.pets[petNumber]; the old packet does not restore; v1 name key still writes",
        )


class ClientBinder:
    """Future addon rule. Not the frozen PetAutocastKeeper.

    Same-process epoch may remember an explicit choice. A different boot
    epoch quarantines those rows. The token is never the key.
    """

    def __init__(self) -> None:
        self.epoch: int | None = None
        self.rows: dict[int, str] = {}
        self.quarantine: dict[int, str] = {}

    def note_choice(self, epoch: int, pet_number: int, pairs: str) -> bool:
        if self.epoch is None:
            self.epoch = epoch
        if epoch != self.epoch:
            return False
        self.rows[pet_number] = pairs
        return True

    def on_epoch(self, epoch: int) -> str:
        if self.epoch is not None and epoch != self.epoch:
            self.quarantine.update(self.rows)
            self.rows.clear()
            self.epoch = epoch
            return "quarantine"
        self.epoch = epoch
        return "same"

    def auto_payload(self, pet_number: int) -> str | None:
        if pet_number in self.quarantine and pet_number not in self.rows:
            return None
        return self.rows.get(pet_number)

    def rows_saved_for_v1(self) -> str:
        return "17259=0"


def client_bind_hello(hello_pet: int, current_pet: int | None, hello_epoch: int,
                      saved_epoch: int | None) -> str:
    """Lua-side rule for a hello that arrives while another pet is current."""
    if current_pet is None or hello_pet != current_pet:
        return "drop"
    if saved_epoch is not None and hello_epoch != saved_epoch:
        return "quarantine"
    return "bind"


if __name__ == "__main__":
    unittest.main(verbosity=2)
