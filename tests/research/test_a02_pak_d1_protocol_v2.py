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
    if len(parts) == 5 and parts[1] == "hello":
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
    def __init__(self, number: int, name: str, family: str, spells: dict[int, bool]):
        self.number = number
        self.name = name
        self.family = family
        self.spells = dict(spells)


def make_wolf(number: int, bite: bool = True, cower: bool | None = True,
              claw: int | None = None) -> Pet:
    spells = {GROWL: True}
    if bite is not None:
        spells[17259] = bite
    if cower is not None:
        spells[COWER] = cower
    if claw is not None:
        spells[claw] = True
    return Pet(number, "Fluffy", "Wolf", spells)


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
                     is_hunter: bool = True) -> str:
        self.last_sender = guid
        self.last_target = target
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


class Active:
    def __init__(self, pet_number: int, token: str, gen: int, epoch: int, hello: str,
                 instance_id: int):
        self.pet_number = pet_number
        self.token = token
        self.gen = gen
        self.epoch = epoch
        self.hello = hello
        self.instance_id = instance_id


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
        self.token_n = 0
        self.active: Active | None = None
        self.inbox: list[Parsed] = []
        self.assembler = Assembler()
        self.snapshots: dict[int, Snapshot] = {}
        self.rate = Rate()
        self.outbound: list[str] = []


class V2Store:
    """World thread enqueues. Map worker matches the active generation, then applies."""

    def __init__(self) -> None:
        self.enabled = True
        self.players: dict[int, V2Player] = {}
        self.last_sender = 0
        self.last_target = ""
        self.transport_sends = 0

    def player(self, guid: int) -> V2Player:
        return self.players.setdefault(guid, V2Player())

    def login(self, guid: int) -> None:
        player = self.player(guid)
        if player.epoch >= MAX_SEQ:
            player.logged_in = True
            player.active = None
            player.inbox.clear()
            player.assembler = Assembler()
            player.epoch = MAX_SEQ
            return
        player.epoch += 1
        player.logged_in = True
        player.active = None
        player.inbox.clear()
        player.assembler = Assembler()

    def logout(self, guid: int) -> None:
        player = self.player(guid)
        player.logged_in = False
        player.active = None
        player.inbox.clear()
        player.assembler = Assembler()

    def observe(self, guid: int, pet: Pet | None) -> None:
        player = self.player(guid)
        if not player.logged_in or player.epoch == 0 or player.epoch >= MAX_SEQ and player.next_gen >= MAX_SEQ:
            return
        number = 0 if pet is None else pet.number
        if number == 0:
            player.active = None
            player.assembler = Assembler()
            return
        instance_id = id(pet)
        if (
            player.active
            and player.active.pet_number == number
            and player.active.epoch == player.epoch
            and player.active.instance_id == instance_id
        ):
            return
        self.issue(player, number, instance_id)

    def issue(self, player: V2Player, pet_number: int, instance_id: int) -> None:
        if player.next_gen >= MAX_SEQ:
            player.active = None
            player.assembler = Assembler()
            return
        player.next_gen += 1
        player.token_n += 1
        token = f"{player.token_n:016x}"
        hello = f"v2|hello|{player.epoch}|{token}|{player.next_gen}"
        player.outbound.append(hello)
        player.active = Active(
            pet_number, token, player.next_gen, player.epoch, hello, instance_id
        )
        player.assembler = Assembler()

    def world_accept(self, guid: int, raw: str, now_ms: int, target: str,
                     is_hunter: bool = True) -> str:
        self.last_sender = guid
        self.last_target = target
        if not self.enabled:
            return "Disabled"
        parsed = parse_message(raw)
        if parsed.kind == "NotDelivered":
            return "NotDelivered"
        if parsed.kind == "NotOurs":
            return "NotOurs"
        if not is_hunter:
            return "IgnoredNotHunter"
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
        batch = player.inbox
        player.inbox = []
        for parsed in batch:
            active = player.active
            if pet is None or pet.number == 0 or active is None:
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
                self.issue(player, pet.number, id(pet))
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
        if pet is None or pet.number == 0:
            return None
        player = self.players.get(guid)
        if player is None or not player.logged_in or player.active is None:
            return None
        if player.active.pet_number != pet.number:
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
    def __init__(self, kind: str):
        self.kind = kind
        self.store: V1Store | V2Store = V1Store() if kind == "v1" else V2Store()
        self.store.enabled = True
        self.guid = 1
        self.pet: Pet | None = None
        self.now = 0
        self.store.login(self.guid)

    def summon(self, pet: Pet | None) -> None:
        self.pet = pet
        if self.kind == "v2":
            self.store.observe(self.guid, pet)

    def identity(self) -> tuple[int, str, int] | None:
        player = self.store.players[self.guid]  # type: ignore[attr-defined]
        active = player.active
        if active is None:
            return None
        return active.epoch, active.token, active.gen

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
             guid: int | None = None, is_hunter: bool = True) -> str:
        return self.store.world_accept(guid or self.guid, raw, self.now, target, is_hunter)

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
        self.assertEqual(lengths, [(29, 36), (44, 51), (29, 36), (23, 30), (8, 15)])
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
        self.assertIn("OWNER DECISION REQUIRED", proposal)
        self.assertIn("CharmInfo::GetPetNumber", proposal)
        self.assertIn("ChatHandler.cpp:292", proposal)
        self.assertIn("checkHunterPetSpells", proposal)
        self.assertIn("Playerbots sources were not opened", proposal)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
