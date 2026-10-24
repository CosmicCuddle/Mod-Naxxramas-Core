# A02 PAK-D1 — v2 PROPOSAL / v1 UNSAFE FOR AUTO APPLY

**Status:** candidate only. Not approved, not canonical, not a replacement for `docs/A02-ADDON-PROTOCOL.md`. Both config keys stay 0. This file is not permission to enable them, send a packet, merge, release, tag, or run a gameplay trial. In-game behaviour is **NOT TESTED**. No worldserver was started. No database was opened. Playerbots sources were not opened.

**Author:** CosmicScript02. Peer review requested from CosmicScript01 and from the Module Editor who owns draft PR #134.

**Parent commit:** `2ab30306c884d3af1c92bb5ad7042648b90fd162` (draft #134 head reviewed by CS01 in comment 6390392020). This branch does not push to `cursor/a02-s2c-addon-optin-193f`.

`docs/A02-ADDON-PROTOCOL.md` on that head remains the only wire text inside #134. It is a draft. It is not signed off. The text below is the one revised candidate CS01 assigned as PAK-D1. Module Editor copies an accepted wire into `docs/A02-ADDON-PROTOCOL.md` once, after CS01 and CS02 both sign that exact text. Until that happens, v1 stays the #134 draft and v2 stays a proposal.

## Label

v1 cannot guarantee that a fragment built for pet A is applied only to pet A after a stable swap, a `v1|clear`, or a login. The label is **v2 PROPOSAL / v1 UNSAFE FOR AUTO APPLY**.

## Pins and frozen addon

| Tree | Commit or hash | How it was read |
| --- | --- | --- |
| This module, #134 head | `2ab30306c884d3af1c92bb5ad7042648b90fd162` | Working tree parent. Receiver and protocol text read in full |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` | Sparse checkout under `/tmp/pak/core`. Not modified |
| Grimfeather `mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` | Checkout under `/tmp/pak/ip`. Not modified |
| `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` named by the v1 protocol | **Not opened.** No `_playerbotsAIMap` read |
| Addon zip supplied for this task | sha256 `4d4e04843e6274b4ede20a03429c3c6f05f2b579f8536d48d59710ec9dc7e007` | Read-only unpack. Addon files were not modified and are not in this branch |

Addon file hashes inside that zip (sha256):

| File | sha256 |
| --- | --- |
| `Logic.lua` | `f9f298d7b6aeedadf8f97650efe868bce031c9442ac9be793532fa526ebe1197` |
| `Core.lua` | `9cff769e2259df711f43c3bc7878070e5289267a6585c87c0c4b44b87c0e234d` |
| `HANDOVER.md` | `3b9327986eeeb3134d7a68cc68cabf7d8bbab8717f417011d9c05e41d2de3253` |
| `README.md` | `7cd46eec44b9fef75bc652dc580cacef6913865f177a3246c9f65cf3b0c4c861` |

The Lua contract test refuses to run if `Logic.lua` or `Core.lua` hash differs.

## Why v1 is unsafe for auto-apply

Modelled from `src/Systems/HunterPetAutocastAddon.h` and `src/Systems/HunterPetAutocast.cpp` at the parent commit. This is source behaviour, not a gameplay result.

1. **One published set per player.** `OptInStore` is keyed by player GUID. `PreferenceSnapshot` has `Seq`, `OptedIn`, and `Choices` only. It has no pet number, token, or epoch. `OnWorldObjectUpdate` reads that snapshot for the owner's current hunter pet (`HunterPetAutocast.cpp` `AddonStore().Read(owner->GetGUID().GetCounter(), ...)`). `owner->GetPet() != pet` skips a pet that is not current. It does not stop the current pet from receiving the previous pet's choices.
2. **Same name and family are invisible on the wire.** Frozen `Logic.lua` `PetKey` returns `name:` plus the name when the name is non-empty. Two wolves both named Fluffy share one client save and one v1 sequence. The server cannot tell them apart because the payload has no pet field (`docs/A02-ADDON-PROTOCOL.md` final block: "There is no pet identifier.").
3. **A delayed complete sequence publishes onto whoever is current.** `Accept` runs on the world thread from `OnPlayerBeforeSendChatMessage` and publishes as soon as indexes `1..total` are present. The map thread later applies that publish. A sequence that finishes after A is stabled and B is summoned is applied to B.
4. **`v1|clear` reopens the sequence space.** `ClearSlot` sets `Tracking = false`, `LastSeq = 0`, clears the partial, increments `Generation`, and `Published.reset()`. The next complete sequence is accepted even when it reuses the seq that was just cleared. A delayed fragment from before the clear revives the cleared set onto the pet that is current at the next apply.
5. **Login resets the sequence and keeps a published set.** `OnLogin` sets `Tracking = false` and `LastSeq = 0` and does not clear `Published`. A later lower seq replaces the set. `OnLogout` erases the slot, so a normal logout-then-login also accepts an old payload as a brand new set. SavedVariables can resend that payload.
6. **Client clear is per name key, and the wire clear is global.** `Core.lua` `/pak reset` deletes `db.pets[k]` for the current `PetKey` and, when relay is on, sends `v1|clear`. That wire clear deletes the only server slot. It cannot clear pet A and leave pet B's server record, because v1 has one record.

The native plan already toggles spell 1742 when the pet has it and skips it when the pet does not. That part is not the isolation defect. The frozen addon README and HANDOVER still say the server never toggles 1742 and still name head `7b21bc0`. That doc mismatch is **VERIFIED** by reading those files against parent `2ab3030`. It is an addon-owner doc fix, not a wire fix. In-game bar behaviour is **NOT TESTED**.

## Authenticated sender and whisper target

**VERIFIED** at core `8daffda`:

- `CMSG_MESSAGECHAT` is `PROCESS_THREADUNSAFE` (`Opcodes.cpp:280`). `WorldSessionFilter::Process` returns true for that class (`WorldSession.cpp:96-98`), so the handler runs from `sWorldSessionMgr->UpdateSessions` (`World.cpp:1227`), which returns before `sMapMgr->Update` (`World.cpp:1254`). `MapSessionFilter::Process` returns false for the same class (`WorldSession.cpp:74-76`). The chat handler is not a map worker.
- `WorldSession::HandleMessagechatOpcode` calls `sScriptMgr->OnPlayerBeforeSendChatMessage(_player, type, lang, msg)` at `ChatHandler.cpp:364`. The whisper `switch` starts at line 390. `normalizePlayerName(to)` is at line 392. The hook argument list in `PlayerScript.h:341` has no receiver.
- The module passes `player->GetGUID().GetCounter()` into `Accept` (`HunterPetAutocast.cpp`). The string `to` is not a parameter of that hook.

**Candidate rule:** the authenticated sender is the hook's `_player`. The store key is that player's GUID. A `LANG_ADDON` whisper whose target name is someone else still mutates only that sender's records. v2 does not claim the whisper was self-addressed.

**Not selected:** `OnPlayerCanUseChat(Player*, type, language, msg, Player* receiver)` (`PlayerScript.h:701`), called from `Player::Whisper` at `Player.cpp:9694`. That hook can see `target`, and returning false cancels the whisper. v2 does not move the receiver onto it. Self-target remains **UNKNOWN** / **NOT TESTED**. Own-pet scope is the mitigation, not a proof of self-delivery.

`LANG_ADDON` whispers are allowed only when `AddonChannel` is true (`ChatHandler.cpp:186-201`). The pinned default is true (`WorldConfig.cpp:154`). The owner's live `worldserver.conf` was not read. Live `AddonChannel` is **UNKNOWN**.

## Server-derived pet identity

**VERIFIED** at core `8daffda`, matching CS01 comment 6390610586:

- `CharmInfo::GetPetNumber()` returns `_petnumber` (`CharmInfo.h:132`). `SetPetNumber(uint32, bool)` is declared at `CharmInfo.h:133`.
- `PetStable::PetInfo::PetNumber` defaults to 0 (`PetDefines.h:220`).
- `Pet::GetLoadPetInfo` (`Pet.cpp:171`) matches a non-zero `petnumber` against `CurrentPet` (line 176), each `StabledPets` slot (line 180), and each `UnslottedPets` entry (line 184).
- `Pet::LoadPetFromDB` (`Pet.cpp:216`) loads that `PetInfo` and `GetCharmInfo()->SetPetNumber(petInfo->PetNumber, ...)` at line 295 for a hunter pet.
- `Pet::FillPetInfo` writes `m_charmInfo->GetPetNumber()` back (`Pet.cpp:2466-2468`).
- `Pet::CreateBaseAtTamed` assigns `sObjectMgr->GeneratePetNumber()` (`Pet.cpp:1018`). The generator body was not re-audited in this pass. Uniqueness of the counter is **NOT TESTED** here. The stable lookup by the stored number is **VERIFIED** at the lines above.
- `Player::GetPetStable()` is public (`Player.h:1226`). `Player::GetPet()` is public (`Player.h:1230`).

Name and family are not this key. Runtime creature GUID changes across resummon. The saved pet number is the identity the proposal binds.

**VERIFIED limitation of a receive-time stamp:** if the world thread, or the map thread at the moment a fragment is parsed, writes "whatever `GetPetNumber()` is right now" onto a fragment that was built for A, a fragment that arrives after the swap is stamped with B. v2 does not do that. The fragment must carry the token that was issued for A, and the map thread must reject it when A's generation is no longer active.

`PetNumber == 0` is never a writable identity. No pet, or a pet that is not `owner->GetPet()`, is never a write target.

## Server to addon transport

Pinned server source can build the packet. Delivery into addon Lua is **UNKNOWN**.

**VERIFIED** at `Player.cpp:9683-9707`: `Player::Whisper(text, language, target)` treats `language == LANG_ADDON` as an addon message, calls `OnPlayerCanUseChat` with the target, `ChatHandler::BuildChatPacket(..., CHAT_MSG_WHISPER, language, ...)`, `target->SendDirectMessage`, and returns before the inform path. That is a server send path. It is not a 3.3.5a client trace.

**UNKNOWN / NOT TESTED:**

- Whether the 3.3.5a client surfaces that packet to Lua as `CHAT_MSG_ADDON`.
- Whether a self-targeted addon whisper is delivered to the sender's own addon.
- The client's addon prefix filter and the payload size the client accepts.
- `SendDirectMessage` thread rules if it were called from a map worker. This proposal does not call it from the map worker. It also does not call it at all in this branch.

Frozen `Core.lua` registers `ADDON_LOADED`, `PLAYER_ENTERING_WORLD`, `UNIT_PET`, `PET_BAR_UPDATE`, `PET_STABLE_CLOSED`, and `PLAYER_REGEN_ENABLED`. It does not register `CHAT_MSG_ADDON`. The v1 protocol says the server sends no reply. There is no client receiver to echo a token.

**Consequence:** a handshake that needs the addon to echo a server token cannot be auto-applied. v2 specifies the handshake so it can be reviewed, and the receiver fail-closes with no writes until that transport is shown. This branch composes no outbound packet and does not add a `Whisper` call.

No client API for the stable pet number was found in the frozen addon, and none is assumed. Whether 3.3.5a Lua can read the database pet number is **UNKNOWN**. The client echoes an opaque token, not a pet number it discovered locally.

## Byte budget

**VERIFIED** at `ChatHandler.cpp:292`: `msg.length() > 255` returns before the hook. A string of length 255 still reaches the hook. The module constant `kMaxRawBytes = 255` matches that.

`NXCPAK` is 6 bytes. The TAB is 1 byte (`0x09`). The largest payload that can reach the hook is 248 bytes (`255 - 7`). A combined string of 256 bytes is not delivered.

The frozen addon uses a payload budget of 233 (`Logic.lua` `P.MAX_PAYLOAD`). `6 + 1 + 233 = 240`, which is under 255. v2 keeps that client budget so a chunk that obeyed v1's length rule still reaches the hook. The server candidate accepts any delivered `NXCPAK` string of 1 to 255 bytes and does not add a second cutoff. Payloads over 233 are a client concern; the server still parses them when the combined length is at most 255.

Party, raid, guild, and battleground addon messages stay ignored, as in v1.

## Map threads, stable opcodes, and Individual Progression

The owner states `MapUpdate.Threads = 8`. **VERIFIED** pinned default is 1 at `WorldConfig.cpp:575` (`"MapUpdate.Threads", 1`). The live conf was not read, so the deployed value is **UNKNOWN**. The design is for more than one map worker because `MapMgr::Update` schedules maps and then `m_updater.wait()` (`MapMgr.cpp:273-280`) when the updater is active (`MapMgr.cpp:61-62`, `num_threads > 0`). Workers run in parallel with each other. The world thread is inside `wait()` during that span, then continues. `World::Update` does not start the next `UpdateSessions` until `MapMgr::Update` returns.

`CMSG_STABLE_PET`, `CMSG_UNSTABLE_PET`, `CMSG_STABLE_SWAP_PET`, and `CMSG_STABLE_REVIVE_PET` are `PROCESS_THREADUNSAFE` (`Opcodes.cpp:755-760`). They run on the world thread in session update, before that tick's map update. v2 does not hook those opcodes and does not read `Pet*` or `PetStable` on the world thread.

On the map worker, inside one `Unit::Update` for the pet (`Unit.cpp:510-517`):

1. `OnUnitUpdate` runs first (the existing module snapshots the book here).
2. `WorldObject::Update` runs `m_Events.Update` (`Object.cpp:1074-1076`), then `OnWorldObjectUpdate` (`Object.cpp:1085`).

Individual Progression schedules `DelayedPetSpellCheck` at 200 ms on `pet->m_Events` from `OnPetAddToWorld` and `OnInitStatsForLevel` (`IndividualProgressionSpells.cpp:1304-1306` and `:1312-1329`). When that event fires it calls `checkHunterPetSpells` (`:1361-1362`) on the same map worker, inside step 2, before `OnWorldObjectUpdate`. **VERIFIED** as source order. Whether a given world tick actually fires the 200 ms event is **NOT TESTED**.

`checkHunterPetSpells` (`IndividualProgressionSpells.cpp:56`) returns immediately unless the player is in world, `VanillaHunterPets` is on, the player is not classified by IP as a bot account, the class is hunter, and progression has not passed TBC tier 5. The bot-account predicate was not followed into other IP files beyond this function. Its gameplay result is **NOT TESTED**.

Rank lists read from that function (ids are the source lists; DBC spell-chain linkage is **NOT TESTED** and is only assumed by `SpellMgr::GetFirstSpellInChain` in the current receiver):

| Family call | Lines | What the lambda does |
| --- | --- | --- |
| Wolf Bite | `:117` | Non-empty dummy list. Highest dummy spell the player has, minus 600000, is kept. Other listed ranks are unlearned. Missing keep id is learned |
| Wolf Claw | `:120` | Dummy list is empty. Every listed Claw rank the pet has is unlearned. Nothing is learned |
| Cat Claw | `:137` | Non-empty dummy list, same keep rule as Wolf Bite |
| Wolf Cower | `:129` | The reconcile call is commented out. This function does not remove 1742 for Wolf |
| Serpent, Moth, Chimaera, Silithid Cower | `:445`, `:453`, `:460`, `:467` | `reconcile({ 1742 }, {})` unlearns 1742 and learns nothing |

v2 apply stays in `OnWorldObjectUpdate`, after that event, on the post-event book, and only for the pet number whose current generation published the set. It does not learn a missing id. A later tick whose book changed applies that same pet's current snapshot again, which is how a Bite/Claw successor rank receives the stored on/off bit. Another pet's snapshot is not consulted.

Publication across the world thread and the map worker uses the existing mutex and an immutable snapshot `shared_ptr`. The world thread only enqueues a parsed fragment. The map worker matches the token, publishes, and toggles. `MapUpdate.Threads` being 8 does not allow one worker to apply another map's pet; the pet check remains `owner->GetPet() == pet` plus the pet number.

## SelfBot and human control

**OWNER DECISION REQUIRED.** It is not approved.

The v1 protocol label says a SelfBot client sending the addon message is a potential issue "accepted by the owner's direction". CS01's review 6390392020 says that acceptance was not owner-authorized. This proposal agrees. Client-connected SelfBot inclusion is not treated as approved.

Rules for the candidate:

- `NaxxramasCore.HunterPetAutocast.RestoreHumanChain` and `NaxxramasCore.HunterPetAutocast.AddonOptIn` stay default 0 (`conf/mod_naxxramas_core.conf.dist:411` and `:419`; `HunterPetAutocast.cpp` stores both atomics as false). With `AddonOptIn` false the chat hook returns before `Accept`. Fail closed.
- An addon message, a non-headless socket, or `!IsHeadless` is not proof that SelfBot AI is absent.
- v2 does not read `_playerbotsAIMap`, does not include Playerbots headers, and does not call `IsRealPlayer`. This pass did not open `mod-playerbots`.
- No opt-in exception is added for a client-connected bot.

Michael's open choice, unchanged by this file:

- (a) a client-connected character is eligible, SelfBot included, or
- (b) SelfBot is excluded, using a synchronized public API or another design that CS01 and the owner both accept.

Until one of those is written down by the owner, the flags stay 0 and this candidate does not enable a path for either outcome.

## Candidate wire

Prefix `NXCPAK`, one TAB, then the payload. The payload has no TAB and no spaces. Decimal fields have no leading zero. The token is exactly 16 lowercase hex digits (`[0-9a-f]{16}`), minted by the module, opaque to the pet number. Epoch, generation, and seq are decimal integers from 1 to 999999999.

Outbound hello, composed on the map worker into a queue, sent only by a future world-thread step that this branch does not implement:

```text
v2|hello|<epoch>|<token>|<gen>
```

Client data, echoed after a hello the client has actually observed (transport **UNKNOWN**, so no current addon can form this):

```text
v2|<epoch>|<token>|<gen>|<seq>|<n>/<total>|<pairs>
```

Client clear, scoped to that same generation:

```text
v2|<epoch>|<token>|<gen>|clear
```

`<seq>` is 1..999999999. `<n>` and `<total>` are 1..8, and `<n> <= <total>`. `<pairs>` is empty or a comma-separated list of `<spellId>=<0|1>` with no trailing comma. `<spellId>` is 1..4294967295 with no leading zero. At most 64 pairs in one chunk and 64 pairs in one completed sequence. A duplicate spell id in a chunk, or the same spell id in two chunks of one sequence, is malformed. Version `v2` only. Any other version, including `v1`, is not applied.

Epoch does not wrap. Generation does not wrap. If either counter would pass 999999999, further fragments for that player are rejected and nothing is published. Seq may start again at 1 on a new generation. The old generation's seq 1 stays rejected because the generation does not match. Within one active generation, a lower seq is ignored, a seq that was already published is ignored, a repeated index with the same pairs is ignored, and a repeated index with different pairs discards that partial and does not change the published record.

### Exact bytes

The hook sees `NXCPAK`, one TAB byte, then the payload. Lengths below include that TAB. All of them are under 255. All payloads are under the 233-byte client budget.

```wire
NXCPAK\tv2|hello|3|a1b2c3d4e5f60718|1
NXCPAK\tv2|3|a1b2c3d4e5f60718|1|7|1/1|1742=0,17259=1
NXCPAK\tv2|3|a1b2c3d4e5f60718|1|clear
NXCPAK\tv1|7|1/1|1742=0,17259=1
NXCPAK\tv1|clear
```

| Wire | Payload bytes | Combined bytes | Candidate result |
| --- | --- | --- | --- |
| hello `epoch=3`, token `a1b2c3d4e5f60718`, `gen=1` | 29 | 36 | Outbound composition only. Not sent here |
| data seq 7, one chunk, `1742=0,17259=1` | 44 | 51 | Applied only if that token is the active generation for the pet being updated |
| clear for that same generation | 29 | 36 | Deletes that pet's current-epoch record and retires the generation |
| v1 data example from the #134 protocol | 23 | 30 | `RejectedLegacy`. No publish, no clear, no apply |
| v1 `clear` | 8 | 15 | `RejectedLegacy`. Does not clear a v2 record and does not reset epoch or generation |

A combined length of 256 is not delivered (`ChatHandler.cpp:292`). A combined length of 255 is delivered and then parsed.

Header size used when the client splits pairs, for an 8-chunk sequence at the maximum field widths (9-digit epoch, 16-hex token, 9-digit gen, 9-digit seq, `8/8`):

```text
v2|999999999|aaaaaaaaaaaaaaaa|999999999|999999999|8/8|
```

That prefix is 54 bytes. The 233-byte client budget leaves 179 bytes for the pair text of a worst-case chunk. The frozen v1 header `v1|<seq>|8/8|` is shorter. An addon that reuses the v1 room calculation can build a v2 chunk whose combined length exceeds 255. The addon must measure `6 + 1 + payload` and must not send when that exceeds 255, and should keep the payload at or below 233. Spell ids in the example (`1742`, `17259`) are the ids already used by the v1 protocol text. They are illustrative in this document. DBC autocast flags are **NOT TESTED**.

Rate limit, same as v1: 8 `NXCPAK` messages per player per 10000 ms. A further message in the window is ignored. Malformed messages and rejected v1 messages count. Messages that are not `NXCPAK`, and messages from a player who is not a hunter, do not count and do not write. The frozen addon limiter is 8 sends per 11.0 s (`Logic.lua` `P.RATE_WINDOW`). The 1 second margin is a client choice. The live server window is the 10000 ms constant, not the addon constant. Live config is **UNKNOWN** because this limit is compiled in, not a conf key.

## State machine

Per player GUID, all under the existing store mutex except the pet read and the autocast toggles, which stay on the map worker after the snapshot pointer is copied.

- **Login (`OnPlayerLogin`).** Epoch increments by one. Active token is cleared. Inbox and partial are dropped. Tracking for the new epoch starts empty. Snapshots from the previous epoch are not applied. Seq tracking from the previous epoch is not reused.
- **Logout (`OnPlayerLogout`).** Active token, inbox, and partial are dropped. The player is logged out, so a late call does not publish. Previous-epoch snapshots stay inert.
- **Map worker observes the current pet.** This runs at the start of the pet's `OnWorldObjectUpdate`, before the inbox is drained. Read `CharmInfo::GetPetNumber()` only here, and only for the pet currently being updated, and only when `owner->GetPet() == pet`, the owner is an in-world hunter, and the pet is a hunter pet that is not loading. If there is no such pet, or the number is 0, retire any active generation and publish nothing. Mint a new token and generation when this pet object is not the object that holds the active generation, including a resummon that keeps the same pet number, and when the pet number itself changes. The same pet object, updated again on a later tick, keeps its generation. Retire drops that generation's partial and leaves its snapshot stored but ineligible for apply. Compose `v2|hello|...` into the outbound queue. Do not call `Whisper` here.
- **World thread accepts a chat string.** If `AddonOptIn` is false, return before any parse. If the sender is missing, the type is not `CHAT_MSG_WHISPER`, or the language is not `LANG_ADDON`, return. If `msg.length()` is above 255, the core already returned. Parse. Non-`NXCPAK` returns without a rate count. Non-hunter returns without a rate count and without a write. Otherwise count the rate limit, then enqueue a v2 fragment, or mark `v1` as `RejectedLegacy` with no enqueue. Do not call `GetPet`, `GetPetStable`, or `GetPetNumber` on this thread.
- **Map worker drains the inbox** after Individual Progression's event slot (step 2 above), still inside `OnWorldObjectUpdate`. A fragment applies only when its epoch, token, and generation equal the active generation, and the pet being updated has that generation's pet number. Otherwise it is rejected, including when the seq number was used before or is reused.
- **Complete sequence.** Publish one immutable record keyed by `(player GUID, pet number)` for this epoch and generation: the merged pairs, normalized by the same `GetFirstSpellInChain` rule as v1 (first id of a chain, later rank matches). A spell that is not autocastable, or whose chain id is 0, is dropped from the record and does not fail the rest. Two pairs that normalize to one chain: the later pair in chunk order wins. Publishing replaces that pet's record only. Other pet numbers are left as they are.
- **Clear.** In the same critical section: if the echoed generation is the active one and the pet number matches, delete that pet's record, drop partials for that generation, retire the generation, and mint the next generation (new token, new hello queued) for the same pet number. A second pet's record is not deleted. A replay of the retired generation does not publish, even if it repeats the old seq or repeats `clear`. A `v1|clear` does not enter this path.
- **Apply.** Copy the immutable record under the mutex. Toggle only spells that are already on the post-event book, present, autocastable, and listed under that chain. Do not insert a spell. Do not call `learnSpell`. Unlisted spells stay as they are. Empty pair list publishes a record with no choices, so this pet stops receiving restores and other pets are untouched. A same-id book at the same generation still skips `DecideChains`, as the current receiver does, once this candidate is implemented. This proposal does not change that fast path's source.

Resummon of A keeps A's pet number (`LoadPetFromDB` / `SetPetNumber`) and receives a new generation. Fragments from the previous generation are rejected. A's old record is not applied until a new complete sequence in the new generation publishes one. That is fail-closed across the **UNKNOWN** hello round-trip: silence does not restore, and it also does not leak A onto B.

## Migration for the staged addon v1

The staged addon at zip `4d4e0484…` speaks only `v1|<seq>|<n>/<total>|<pairs>` and `v1|clear`. It stores choices under `PetKey`. It does not listen for a hello. This branch does not patch it.

| Stage | Server | Addon | Writes |
| --- | --- | --- | --- |
| Now | #134 v1 draft, both flags 0 | Frozen v1, relay is the addon's own saved variable | None while the flags are 0 |
| This candidate, if Module Editor implements it later | Parse v2. `v1` is `RejectedLegacy` | Unchanged v1 | None. v1 cannot satisfy a token check. Flags still default 0 |
| Transport check | Still default 0 until the owner allows one character to receive a hello | Addon Creator, not this branch | Still none until Lua observation is recorded |
| Addon v2 | One accepted text copied into `docs/A02-ADDON-PROTOCOL.md` | Echo hello fields; save choices per token, not per `PetKey`; measure the longer header | Only after the flags are turned on by an explicit later decision |

v1 and v2 are not mixed on one publish. A v1 payload must not complete a v2 partial, must not clear a v2 record, and must not reset epoch or generation. The addon's seq wrap (`NextSeq` returns 1 and `RelayDecide` prefixes `v1|clear`) is a v1 behaviour. Against a v2 receiver that wrap is two rejected legacy messages.

Same-name collision is also a client save bug. Server isolation does not split `db.pets["name:Fluffy"]`. Addon v2 has to store by the token (or by a pet number the server put in a hello the client verifiably received). That work belongs to the Addon Creator after the wire is accepted.

Cower documentation on the addon (`README.md`: "The server never toggles Cower (1742)") disagrees with parent `2ab3030`, which toggles 1742 when the pet has it. v2 keeps that rule: present means the explicit bit is applied; absent means no toggle and no learn. The README/HANDOVER update waits on the addon owner and on a pinned wire.

The 4 second fallback button, click capture, combat lockdown, and three-macro truncation are addon behaviour. They are outside this candidate. They stay **NOT TESTED** in game. PAK-T2/T4/T5 from comment 6390397721 are not implemented here; this deliverable is PAK-D1 items 1 and 2 from comment 6390535080.

## Witnesses

Runnable models, not a worldserver:

- `python3 tests/research/test_a02_pak_d1_protocol_v2.py`
- `lua5.1 tests/research/test_a02_pak_d1_addon_contract.lua <PetAutocastKeeper directory>`

The Python file models v1 from the parent receiver and models this candidate. The Lua file loads the frozen addon at the hashes above and does not write into it.

| Id | Safety property | v1 model | v2 candidate |
| --- | --- | --- | --- |
| PAK-ID-01 | Delayed A Bite OFF does not turn same-name same-family B Bite ON into OFF | Fails the property | Holds |
| PAK-ID-02 | Two chunks of A that straddle a swap do not publish onto B; reordered chunks of one active generation still assemble; a conflicting repeat does not replace a published record | Straddle fails the property. Reorder and conflict hold | Holds |
| PAK-ID-03 | Resummon keeps A's pet number, new generation rejects A's old fragment, old record is not applied | Fails the property | Holds |
| PAK-ID-04 | After clear, a replay of the old seq does not revive the cleared bit | Fails the property | Holds |
| PAK-ID-05 | After login, a SavedVariables replay does not overwrite the new pet's set | Fails the property | Holds |
| PAK-ID-06 | No pet, a non-current pet, and `PetNumber == 0` do not gain a write. v1 already skips no-pet and non-current; it still writes pet number 0 | Pet number 0 fails. The other two hold | Holds |
| PAK-CLEAR-01 | Clear of A leaves B's Bite ON record | Fails the property (one slot) | Holds |
| PAK-SPELL-01 | A listed spell missing from the book is not inserted | Holds | Holds |
| PAK-SPELL-02 | Bite successor id is the one toggled; the removed rank is not inserted | Holds | Holds |
| PAK-SPELL-03 | Cat Claw successor id is toggled; Wolf Claw's empty dummy list removes Claw and the apply does not learn it | Holds | Holds |
| PAK-SPELL-04 | Cower 1742 present is toggled; absent (Serpent wipe) is not learned | Holds | Holds |
| PAK-SPELL-05 | Unlisted Growl and a non-autocastable id are not written | Holds | Holds |
| PAK-AUTH-01 | The whisper target name is not the store key; another player's pet is not written | Holds | Holds |
| PAK-V1-LEGACY | A v1 data or `v1|clear` does not publish, clear, or reset a v2 generation | v1 implements those strings | v2 rejects them |
| PAK-BUDGET | 256-byte `NXCPAK` string is not delivered; 255 is delivered; the wire block above fits | Holds | Holds |
| PAK-FLAG | Source defaults are 0; a disabled v2 store does not apply | Source default off | Holds |

Lua, against the frozen addon, covers `PetKey` same-name collision, `v1|clear` with no pet field, seq wrap prefixing `v1|clear`, empty and missing spellbook entries omitted, Cower omitted when the bar does not have it, and the absence of `CHAT_MSG_ADDON`. Those are client-source facts. They are not in-game results.

## Labels

| Finding | Label |
| --- | --- |
| v1 player-scoped snapshot can apply A's choices to B | **VERIFIED** as source structure. Isolation failure is **VERIFIED** in the Python model of that source. In-game **NOT TESTED** |
| `CharmInfo::GetPetNumber` persists across load/save in pinned core | **VERIFIED** at the cited lines. In-game **NOT TESTED** |
| Receive-time pet number stamp mis-attributes a delayed fragment | **VERIFIED** as a logic consequence of the cited control flow. In-game **NOT TESTED** |
| 3.3.5a server packet build for `LANG_ADDON` whisper | **VERIFIED** at `Player.cpp:9683-9707` |
| 3.3.5a addon Lua actually receiving that packet | **UNKNOWN** |
| `msg.length() > 255` dropped before the hook | **VERIFIED** at `ChatHandler.cpp:292`. In-game **NOT TESTED** |
| Pinned `MapUpdate.Threads` default 1; owner states 8; live conf not read | Default **VERIFIED**. Deployed value **UNKNOWN** |
| World session update before map update, and IP event before `OnWorldObjectUpdate` | **VERIFIED** source order. Same-tick gameplay **NOT TESTED** |
| `GetFirstSpellInChain` matches the IP Bite/Claw rank lists in DBC | **NOT TESTED**. The model uses the IP lists as the chain |
| `SpellInfo::IsAutocastable` for the sample ids | **NOT TESTED**. The model marks Bite, Claw, Cower, and illustrative Growl 2649 autocastable, and illustrative 6603 not |
| Active bit left by `learnSpell` | **NOT TESTED**. The successor witness sets the keep id present and on, then expects the stored bit |
| SelfBot client-connected inclusion | **OWNER DECISION REQUIRED**. Not approved. Flags default off |
| Live `AddonChannel` | **UNKNOWN** |
| In-game summon, stable, relog, bar, fallback button | **NOT TESTED** |
| Playerbots internals | **NOT TESTED** / not read |

## Open decisions for Michael

1. SelfBot: (a) client-connected characters are eligible, SelfBot included, or (b) SelfBot is excluded. This candidate does not choose.
2. Whether any later build may send one `LANG_ADDON` whisper to the authenticated client so an addon can echo a token. Lua delivery is **UNKNOWN** until that trial exists. This branch does not send it.
3. Live `AddonChannel` and live `MapUpdate.Threads`, when an operator is ready to read them. Not read here.
4. Whether the Addon Creator should key saves by a server token after the wire is accepted. The frozen addon is unchanged.
5. When, if ever, Module Editor replaces the #134 protocol text with an accepted v2. Not in this branch.

## Recorded run

Offline only. Not an in-game result. Parent `2ab30306c884d3af1c92bb5ad7042648b90fd162`. The commit SHA is the `#48` checkpoint after this tree is committed. Workflow files were not edited. The new paths are `docs/research/a02-pak-d1-protocol-v2-proposal.md` and `tests/research/`. Those paths sit outside the path filters of the worldserver workflows in `.github/workflows/`, including `hunter-pet-autocast-pinned-worldserver.yml`. This proposal does not add a workflow trigger.

```text
python3 tests/research/test_a02_pak_d1_protocol_v2.py
```

Result: 18 unittest methods, OK, exit 0. Printed witnesses: 23. v1 safety FAIL 8, v1 safety PASS 15, v2 safety FAIL 0, v2 safety PASS 23. The eight v1 failures are PAK-ID-01, PAK-ID-02-straddle, PAK-ID-03, PAK-ID-04, PAK-ID-05, PAK-ID-06-number-0, PAK-CLEAR-01, and PAK-V1-LEGACY. `SOURCE_ANCHORS proposal+header+cpp OK` is an extra unittest check, not one of the 23.

```text
lua5.1 tests/research/test_a02_pak_d1_addon_contract.lua <PetAutocastKeeper directory at zip sha256 4d4e04843e6274b4ede20a03429c3c6f05f2b579f8536d48d59710ec9dc7e007>
```

Result against that directory: passed 35, failed 0, exit 0. Lua 5.1.5. The addon directory is not in this repository.

Still **NOT TESTED**: in-game summon, stable, relog, bar, fallback button, 3.3.5a Lua delivery of a server addon whisper, live `AddonChannel`, live `MapUpdate.Threads`, DBC autocast and spell-chain rows, `learnSpell`'s autocast bit, and Playerbots internals.
