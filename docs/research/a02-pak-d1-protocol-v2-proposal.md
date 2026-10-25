# A02 PAK-D1 — v2 PROPOSAL / v1 UNSAFE FOR AUTO APPLY

**Status:** candidate only. Not approved, not canonical, not a replacement for `docs/A02-ADDON-PROTOCOL.md`. Both config keys stay 0. This file is not permission to enable them, send a packet, merge, release, tag, or run a gameplay trial. In-game behaviour is **NOT TESTED**. No worldserver was started. No database was opened. The live `playerbots.conf` was not opened. Playerbots `d750b4b` was read and not modified.

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
| `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` | Read-only checkout. Not modified. No `_playerbotsAIMap` read |
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

## SelfBot gate

**OWNER DECISION.** The owner stated in chat to CS02, relayed on #48 6395196578. Option B: real human-controlled Hunters only. SelfBots stay excluded. The 08:04 GMT clarification (SelfBot is disabled on the live server, and an `NXCPAK` message from a connected client is the human signal provided a startup SelfBot-off check passes, fail-closed) was relayed on #48 6395196578 / 6395269291. Playerbots and Altbots have no client and cannot send the message. The frozen addon's manual fallback button stays. This branch does not edit the addon.

CS01 still has to agree the v2 wire before the addon or the module adopts it. Both module flags stay 0. This file does not turn them on, and it does not add the config read to the C++.

### What "off" is

One key. `conf/playerbots.conf.dist` has no second SelfBot switch.

| Fact | Where | Verdict |
| --- | --- | --- |
| Key `Playerbots.SelfBotLevel` | `conf/playerbots.conf.dist:195-197` | **VERIFIED** |
| Comment: `0 = disabled, 1 = GM only (default), 2 = all players, 3 = activate on login` | same lines | **VERIFIED** |
| Distributed value is `1` | `:197` | **VERIFIED**. The distributed default is not off |
| `SelfBotLevel = sConfigMgr->GetOption<int32>("Playerbots.SelfBotLevel", 1)` | `PlayerbotAIConfig.cpp:759` | **VERIFIED** |
| `0` answers the command with "SelfBot is disabled server-wide." | `PlayerbotMgr.cpp:1110-1111` | **VERIFIED**. This is the only off value |
| `1` and a non-GM answers "SelfBot is restricted for this account." | `:1112-1113` | **VERIFIED**. A GM can still activate. Not off |
| Every other value, including `2` and `3`, activates | `:1114-1118` | **VERIFIED**. Not off |
| `SelfBotLevel > 2` calls `HandlePlayerbotCommand("self")` on login | `PlayerbotMgr.cpp:1733-1734` | **VERIFIED**. Not off |

Off means the effective integer is `0`. The live file was not read. Michael's statement is the owner report. The bytes on disk stay **UNKNOWN** until the read below is implemented.

### Reading it without editing Playerbots

**VERIFIED** for `sConfigMgr`, on the config-load thread only. **REJECTED** for `sPlayerbotAIConfig.SelfBotLevel`. **REJECTED** for a per-tick `GetOption`.

`Main.cpp:270` loads module configs before scripts, so `playerbots.conf` is already in `sConfigMgr` when `World::LoadConfigSettings` runs (`World.cpp:323`). `OnAfterConfigLoad` is the end of that function (`World.cpp:302`). That first call is before `MapMgr::Initialize` (`World.cpp:941`), so no map worker exists. `.reload config` is `cs_reload.cpp:351-354`, on the world thread inside session update (`World.cpp:1227`), which returns before `sMapMgr->Update` (`:1254`).

`GetValueDefault` finds `_configOptions` without `_configLock` (`Config.cpp:533-538`). A missing key returns the caller-supplied default (`:553-577`). A bad token returns that same default (`:584-594`). `GetEnvFromCache` inserts into `_envVarCache` with no lock (`Config.cpp:489-501`). Map workers calling `GetOption` race that cache. The candidate calls it once per config load, on the world thread, and stores an atomic. Map workers read the atomic.

The call is `sConfigMgr->GetOption<int32>("Playerbots.SelfBotLevel", -1)`. The sentinel is `-1`, not `0`, and not Playerbots' own default `1`. Missing and a bad token both come back as `-1`. Only an effective value equal to `0` is off. A configured `-1` is not off either, so it stays closed. `GetEnvVarName` (`Config.cpp:435-437`, converter `:370-433`) names the override `AC_PLAYERBOTS_SELF_BOT_LEVEL`. `GetValueDefault` prefers that variable when it is set (`:541-551`). The gate sees the effective value. An override other than `0` stays closed.

`Playerbots.Enabled` false returns from `Initialize` before `SelfBotLevel` is assigned (`PlayerbotAIConfig.cpp:83-87`). The chat command returns as well (`PlayerbotMgr.cpp:913-916`). The field has no initializer (`PlayerbotAIConfig.h:414`, constructor `:523`). Login still reaches `SelfBotLevel > 2` through `AddPlayerbotData` (`Playerbots.cpp:148-150`, `PlayerbotMgr.cpp:1824`, `:1733`). A file value of `0` is not a runtime proof while that assignment is skipped. The candidate also reads `sConfigMgr->GetOption<bool>("Playerbots.Enabled", true)`. Explicit false keeps the gate closed. A missing `Enabled` is Playerbots' own default true, and `SelfBotLevel` still has to be `0`.

`sPlayerbotAIConfig.SelfBotLevel` is the wrong accessor. It is a plain `uint32`. `LogMutex` (`PlayerbotAIConfig.h:331`) covers logs, not this field. `Initialize()` writes it from `OnBeforeWorldInitialized` (`Playerbots.cpp:509-531`, `World.cpp:1033`), from the GM `reload` command (`PlayerbotMgr.cpp:1075-1079`), and from `rndbot reload` (`RandomPlayerbotMgr.cpp:2532-2534`). `.reload config` does not call `Initialize`, so the field can lag the file. The `GetOption` inside `Initialize` substitutes `1` when the key is missing, so the field cannot record "missing". This module does not include the header.

### Cache rule

Startup (`OnAfterConfigLoad(false)`): the atomic opens only when `Playerbots.Enabled` is not explicit false and the effective `Playerbots.SelfBotLevel` is integer `0`. Otherwise it stays closed, and the module logs one warning.

A later config load (`OnAfterConfigLoad(true)`): a value that is not that proof closes the atomic. A value that is the proof does not open a closed atomic. Opening happens at process start. A `.reload config` that moves the file from non-zero to `0` updates `sConfigMgr` and leaves `sPlayerbotAIConfig.SelfBotLevel` unchanged until `reload` or `rndbot reload`. Opening on that reload would accept addon messages while the command could still activate SelfBot. Staying closed is the fail-closed side. Setting `0` and restarting is the path that opens. A second close in the same process does not log again.

### Gate

A write needs both of these. Otherwise nothing is written.

1. `NaxxramasCore.HunterPetAutocast.AddonOptIn` is on. It stays default `0` (`conf/mod_naxxramas_core.conf.dist:419`). While it is off the chat hook returns before `Accept`, as it does now.
2. The cached proof above is open.

The addon message does not create the proof. It is the human signal only while the proof is already open. `RestoreHumanChain` stays default `0` (`conf/mod_naxxramas_core.conf.dist:411`). Both flags off means no restore.

Playerbots and Altbots stay unaffected. `AddPlayerBot` constructs the session with a null socket (`PlayerbotMgr.cpp:158-160`). `WorldSession::Update` pops client packets only while `m_Socket` is set (`WorldSession.cpp:414`). The hook runs from `CMSG_MESSAGECHAT` (`Opcodes.cpp:280`, `ChatHandler.cpp:364`). A search of the pinned Playerbots tree finds no call to that handler. A headless session does not deliver `NXCPAK`. A forced headless accept returns without a write.

An active SelfBot stays unaffected because the proof is closed whenever the startup value is not `0`. No per-player AI read is added. `_playerbotsAIMap` stays unread.

The #130 note already rejected a per-player distinction: the unlocked AI map, `!IsHeadless`, account lists, `playerBots`, and a login latch. This decision does not reopen them. No Playerbots, core, or Individual Progression file was edited.

## Candidate wire

Prefix `NXCPAK`, one TAB, then the payload. The payload has no TAB and no spaces. Decimal fields have no leading zero. The token is exactly 16 lowercase hex digits (`[0-9a-f]{16}`), minted by the module, opaque, and new on each summon and each login. It is not the persistence key. Epoch, generation, and seq are decimal integers from 1 to 999999999. `<pet>` is the server-derived stable pet number, decimal, from 1 to 4294967295, with no leading zero. It appears only on the hello.

Outbound hello, composed on the map worker into a queue, sent only by a future world-thread step that this branch does not implement:

```text
v2|hello|<epoch>|<token>|<gen>|<pet>
```

`<pet>` is `CharmInfo::GetPetNumber()` (`CharmInfo.h:132`) for the pet being updated, which `Pet::LoadPetFromDB` copies from `PetStable::PetInfo::PetNumber` (`PetDefines.h:220`, `Pet.cpp:295`). `Pet::FillPetInfo` writes that same field back (`Pet.cpp:2468`). `Pet::GetLoadPetInfo` finds the owner's stable row by that number (`Pet.cpp:171-184`). The client does not send `<pet>`. An inbound `v2|hello|...` is malformed. Data and clear stay on the epoch, token, and generation only:

```text
v2|<epoch>|<token>|<gen>|<seq>|<n>/<total>|<pairs>
```

Client clear, scoped to that same generation:

```text
v2|<epoch>|<token>|<gen>|clear
```

The map worker applies a fragment only when those three fence fields match the active generation and the pet now being updated is `owner->GetPet()`, its `GetPetNumber()` equals the number stored on that generation, and that number is still in this owner's stable. A client-supplied number is not a field and is not read. `0` is not written into a hello. A number removed from this owner's stable is not a write target afterwards, including if a later pet object carries that number again. `GeneratePetNumber` is `++_hiPetNumber` under `_hiPetNumberMutex` (`ObjectMgr.cpp:8163-8166`). `LoadPetNumber` sets the counter from `MAX(id)+1` (`ObjectMgr.cpp:8117-8125`). The generator does not recycle. Reuse would be an out-of-band database edit. The candidate still refuses a tombstoned number. `MSG_LIST_STABLED_PETS` already sends `PetNumber` to the owning client (`NPCHandler.cpp:380`, `:391`, `:405`). This branch does not send the hello, so it does not widen that audience.

`<seq>` is 1..999999999. `<n>` and `<total>` are 1..8, and `<n> <= <total>`. `<pairs>` is empty or a comma-separated list of `<spellId>=<0|1>` with no trailing comma. `<spellId>` is 1..4294967295 with no leading zero. At most 64 pairs in one chunk and 64 pairs in one completed sequence. A duplicate spell id in a chunk, or the same spell id in two chunks of one sequence, is malformed. Version `v2` only. Any other version, including `v1`, is not applied.

Epoch does not wrap. Generation does not wrap. If either counter would pass 999999999, further fragments for that player are rejected and nothing is published. Seq may start again at 1 on a new generation. The old generation's seq 1 stays rejected because the generation does not match. Within one active generation, a lower seq is ignored, a seq that was already published is ignored, a repeated index with the same pairs is ignored, and a repeated index with different pairs discards that partial and does not change the published record.

### Exact bytes

The hook sees `NXCPAK`, one TAB byte, then the payload. Lengths below include that TAB. All of them are under 255. All payloads are under the 233-byte client budget.

```wire
NXCPAK\tv2|hello|3|a1b2c3d4e5f60718|1|101
NXCPAK\tv2|3|a1b2c3d4e5f60718|1|7|1/1|1742=0,17259=1
NXCPAK\tv2|3|a1b2c3d4e5f60718|1|clear
NXCPAK\tv1|7|1/1|1742=0,17259=1
NXCPAK\tv1|clear
```

| Wire | Payload bytes | Combined bytes | Candidate result |
| --- | --- | --- | --- |
| hello `epoch=3`, token `a1b2c3d4e5f60718`, `gen=1`, pet `101` | 33 | 40 | Outbound composition only. Not sent here |
| data seq 7, one chunk, `1742=0,17259=1` | 44 | 51 | Applied only if that token is the active generation for the pet being updated |
| clear for that same generation | 29 | 36 | Deletes that pet's current-epoch record and retires the generation |
| v1 data example from the #134 protocol | 23 | 30 | `RejectedLegacy`. No publish, no clear, no apply |
| v1 `clear` | 8 | 15 | `RejectedLegacy`. Does not clear a v2 record and does not reset epoch or generation |

A combined length of 256 is not delivered (`ChatHandler.cpp:292`). A combined length of 255 is delivered and then parsed.

Header size used when the client splits pairs, for an 8-chunk sequence at the maximum field widths (9-digit epoch, 16-hex token, 9-digit gen, 9-digit seq, `8/8`):

```text
v2|999999999|aaaaaaaaaaaaaaaa|999999999|999999999|8/8|
```

That prefix is 54 bytes. The 233-byte client budget leaves 179 bytes for the pair text of a worst-case chunk. The longest hello, `v2|hello|999999999|aaaaaaaaaaaaaaaa|999999999|4294967295`, is 56 bytes. With the prefix and TAB it is 63, still under 255. The pet number is not added to the data header, so the 54-byte chunk prefix is unchanged. The frozen v1 header `v1|<seq>|8/8|` is shorter. An addon that reuses the v1 room calculation can build a v2 chunk whose combined length exceeds 255. The addon must measure `6 + 1 + payload` and must not send when that exceeds 255, and should keep the payload at or below 233. Spell ids in the example (`1742`, `17259`) are the ids already used by the v1 protocol text. They are illustrative in this document. DBC autocast flags are **NOT TESTED**.

Rate limit, same as v1: 8 `NXCPAK` messages per player per 10000 ms. A further message in the window is ignored. Malformed messages and rejected v1 messages count. Messages that are not `NXCPAK`, and messages from a player who is not a hunter, do not count and do not write. The frozen addon limiter is 8 sends per 11.0 s (`Logic.lua` `P.RATE_WINDOW`). The 1 second margin is a client choice. The live server window is the 10000 ms constant, not the addon constant. Live config is **UNKNOWN** because this limit is compiled in, not a conf key.

## State machine

Per player GUID, all under the existing store mutex except the pet read and the autocast toggles, which stay on the map worker after the snapshot pointer is copied.

- **Login (`OnPlayerLogin`).** Epoch increments by one. Active token is cleared. Inbox and partial are dropped. Tracking for the new epoch starts empty. Snapshots from the previous epoch are not applied. Seq tracking from the previous epoch is not reused.
- **Logout (`OnPlayerLogout`).** Active token, inbox, and partial are dropped. The player is logged out, so a late call does not publish. Previous-epoch snapshots stay inert.
- **Map worker observes the current pet.** This runs at the start of the pet's `OnWorldObjectUpdate`, before the inbox is drained. Read `CharmInfo::GetPetNumber()` only here, and only for the pet currently being updated, and only when `owner->GetPet() == pet`, the owner is an in-world hunter, and the pet is a hunter pet that is not loading. If there is no such pet, the number is missing or `0`, or that number was removed from this owner's stable, retire any active generation and publish nothing. Do not compose a hello. Mint a new token and generation when this pet object is not the object that holds the active generation, including a resummon that keeps the same pet number, and when the pet number itself changes. The same pet object, updated again on a later tick, keeps its generation. Retire drops that generation's partial and leaves its snapshot stored but ineligible for apply. Compose `v2|hello|<epoch>|<token>|<gen>|<pet>` into the outbound queue. The pet field is the number just read. Do not call `Whisper` here.
- **World thread accepts a chat string.** If the session has no client socket, return. The core does not deliver that packet. If `AddonOptIn` is false, return before any parse. If the cached SelfBot proof is closed, return with no enqueue and no write. The one warning was logged at the config load that closed the proof, not on this message. If the sender is missing, the type is not `CHAT_MSG_WHISPER`, or the language is not `LANG_ADDON`, return. If `msg.length()` is above 255, the core already returned. Parse. Non-`NXCPAK` returns without a rate count. Non-hunter returns without a rate count and without a write. An inbound hello is malformed and is not a pet-number claim. Otherwise count the rate limit, then enqueue a v2 fragment, or mark `v1` as `RejectedLegacy` with no enqueue. Do not call `GetPet`, `GetPetStable`, or `GetPetNumber` on the world thread. Do not call `GetOption` on a map worker. The SelfBot proof was copied at config load.
- **Map worker drains the inbox** after Individual Progression's event slot (step 2 above), still inside `OnWorldObjectUpdate`. A fragment carries no pet number. It is eligible only when its epoch, token, and generation equal the active generation, the pet being updated is owned by the sender and is `owner->GetPet()`, and `GetPetNumber()` equals the number stored on that generation and still present in that owner's stable. Otherwise it is rejected and nothing is written, including when the seq was used before, the token is stale, the number is missing, `0`, deleted, or reused, or the pet belongs to someone else.
- **Complete sequence.** Publish one immutable record keyed by `(player GUID, pet number)` for this epoch and generation: the merged pairs, normalized by the same `GetFirstSpellInChain` rule as v1 (first id of a chain, later rank matches). A spell that is not autocastable, or whose chain id is 0, is dropped from the record and does not fail the rest. Two pairs that normalize to one chain: the later pair in chunk order wins. Publishing replaces that pet's record only. Other pet numbers are left as they are.
- **Clear.** In the same critical section: if the echoed generation is the active one and the pet number matches, delete that pet's record, drop partials for that generation, retire the generation, and mint the next generation (new token, new hello queued) for the same pet number. A second pet's record is not deleted. A replay of the retired generation does not publish, even if it repeats the old seq or repeats `clear`. A `v1|clear` does not enter this path.
- **Apply.** Copy the immutable record under the mutex. Toggle only spells that are already on the post-event book, present, autocastable, and listed under that chain. Do not insert a spell. Do not call `learnSpell`. Unlisted spells stay as they are. Empty pair list publishes a record with no choices, so this pet stops receiving restores and other pets are untouched. A same-id book at the same generation still skips `DecideChains`, as the current receiver does, once this candidate is implemented. This proposal does not change that fast path's source.

Resummon of A keeps A's pet number (`LoadPetFromDB` / `SetPetNumber`) and receives a new generation and a new token. The hello repeats that same pet number. Fragments from the previous token are rejected and do not write. The addon, once it can hear the hello, loads `db.pets` by that number and may send a new sequence on the new token. The server applies that new sequence only to the owned current pet with that number. Silence does not restore. A name or family key is not used. A's choices do not publish onto B.

## Migration for the staged addon v1

The staged addon at zip `4d4e0484…` speaks only `v1|<seq>|<n>/<total>|<pairs>` and `v1|clear`. It stores choices under `PetKey`. It does not listen for a hello. This branch does not patch it.

| Stage | Server | Addon | Writes |
| --- | --- | --- | --- |
| Now | #134 v1 draft, both flags 0 | Frozen v1, relay is the addon's own saved variable | None while the flags are 0 |
| This candidate, if Module Editor implements it later | Parse v2. `v1` is `RejectedLegacy` | Unchanged v1 | None. v1 cannot satisfy a token check. Flags still default 0 |
| Transport check | Still default 0 until the owner allows one character to receive a hello | Addon Creator, not this branch | Still none until Lua observation is recorded |
| Addon v2 | One accepted text copied into `docs/A02-ADDON-PROTOCOL.md` | Key `db.pets` by the hello's stable pet number; echo epoch, token, and generation only; measure the longer hello | Only after the flags are turned on by an explicit later decision |

v1 and v2 are not mixed on one publish. A v1 payload must not complete a v2 partial, must not clear a v2 record, and must not reset epoch or generation. The addon's seq wrap (`NextSeq` returns 1 and `RelayDecide` prefixes `v1|clear`) is a v1 behaviour. Against a v2 receiver that wrap is two rejected legacy messages.

Same-name collision is the frozen addon's `PetKey`. This branch does not edit that addon. The addon contract for a later v2, documented here and not implemented in the zip, is `db.pets[petNumber]` where `petNumber` is the decimal field from a hello the client verifiably received. The ephemeral token is not that key. A name or family fallback is not that key. Two wolves named Fluffy with pet numbers 101 and 202 are two save rows. The server still ignores any number the client might try to add to a data or clear payload.

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
| PAK-ID-07 | After A→B→A, relog, and resummon A on a fresh token, A restores Bite OFF from the pet-number save and B stays ON and unwritten | Fails. One name key | Holds |
| PAK-ID-07-MISSING | A missing pet number does not write | v1 writes | Holds. No write |
| PAK-ID-07-ZERO | Pet number 0 does not write | v1 writes | Holds. No write |
| PAK-ID-07-DELETED | A deleted pet number does not write | v1 writes | Holds. No write |
| PAK-ID-07-REUSED | A reused pet number does not write | v1 writes | Holds. No write |
| PAK-ID-07-STALE | A chunk from the previous token does not write | v1 writes the new seq | Holds. No write |
| PAK-ID-07-CLEAR | Clear of A leaves B's record and does not write either spellbook | Fails the record split | Holds. No spell write |
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
| PAK-SELF-ENABLED | `SelfBotLevel` 1, 2, or 3 plus a valid message does not write. 1 is the distributed default | v1 writes | Holds |
| PAK-SELF-UNREADABLE | A bad SelfBot token does not write, and the warning is once | v1 writes | Holds |
| PAK-SELF-MISSING | A missing SelfBot key does not write | v1 writes | Holds |
| PAK-SELF-MODULE | `Playerbots.Enabled` false with file level 0 does not write | v1 writes | Holds |
| PAK-SELF-OFF | Startup level 0 with Enabled not false applies one valid v2 message | Holds | Holds |
| PAK-SELF-RELOAD | A reload from non-zero to 0 does not open a closed gate | v1 writes | Holds |
| PAK-SELF-NOCLIENT | A sender with no client does not deliver a message | Holds. The hook is not entered | Holds |

Lua, against the frozen addon, covers `PetKey` same-name collision, `v1|clear` with no pet field, seq wrap prefixing `v1|clear`, empty and missing spellbook entries omitted, Cower omitted when the bar does not have it, and the absence of `CHAT_MSG_ADDON`. Those are client-source facts. They are not in-game results.

## Labels

| Finding | Label |
| --- | --- |
| v1 player-scoped snapshot can apply A's choices to B | **VERIFIED** as source structure. Isolation failure is **VERIFIED** in the Python model of that source. In-game **NOT TESTED** |
| `CharmInfo::GetPetNumber` persists across load/save in pinned core | **VERIFIED** at `CharmInfo.h:132`, `PetDefines.h:220`, `Pet.cpp:176-184`, `:295`, `:2468`. In-game **NOT TESTED** |
| Hello carries that number; data and clear do not; client number is not trusted | Candidate wire. Modelled. Not sent |
| Receive-time pet number stamp mis-attributes a delayed fragment | **VERIFIED** as a logic consequence of the cited control flow. In-game **NOT TESTED** |
| 3.3.5a server packet build for `LANG_ADDON` whisper | **VERIFIED** at `Player.cpp:9683-9707` |
| 3.3.5a addon Lua actually receiving that packet | **UNKNOWN** |
| `msg.length() > 255` dropped before the hook | **VERIFIED** at `ChatHandler.cpp:292`. In-game **NOT TESTED** |
| Pinned `MapUpdate.Threads` default 1; owner states 8; live conf not read | Default **VERIFIED**. Deployed value **UNKNOWN** |
| World session update before map update, and IP event before `OnWorldObjectUpdate` | **VERIFIED** source order. Same-tick gameplay **NOT TESTED** |
| `GetFirstSpellInChain` matches the IP Bite/Claw rank lists in DBC | **NOT TESTED**. The model uses the IP lists as the chain |
| `SpellInfo::IsAutocastable` for the sample ids | **NOT TESTED**. The model marks Bite, Claw, Cower, and illustrative Growl 2649 autocastable, and illustrative 6603 not |
| Active bit left by `learnSpell` | **NOT TESTED**. The successor witness sets the keep id present and on, then expects the stored bit |
| `Playerbots.SelfBotLevel` `0` is the only off value; dist default `1` is GM-only | **VERIFIED** at `playerbots.conf.dist:195-197` and `PlayerbotMgr.cpp:1110-1118` |
| `sConfigMgr` read of that key on `OnAfterConfigLoad`, sentinel `-1`, cached in an atomic | **VERIFIED** available without editing Playerbots. Not implemented in this branch |
| Per-tick `GetOption`, and `sPlayerbotAIConfig.SelfBotLevel` as the accessor | **REJECTED**. Unlocked `GetOption` cache; plain `uint32` lags `.reload config` and cannot record a missing key |
| Startup proof opens the gate; a later reload does not open a closed gate | Candidate rule. Modelled. Not implemented |
| Live `playerbots.conf` bytes | **UNKNOWN**. Michael states SelfBot is disabled. The file was not read |
| Addon message alone, with the proof closed | Not a human signal. No write |
| Headless Playerbot or Altbot `NXCPAK` | **VERIFIED** not delivered (`WorldSession.cpp:414`, `PlayerbotMgr.cpp:158-160`). In-game **NOT TESTED** |
| Live `AddonChannel` | **UNKNOWN** |
| In-game summon, stable, relog, bar, fallback button | **NOT TESTED** |
| Per-player AI map as a human proof | Not reopened. Still the #130 rejection |

## Open decisions for Michael

The SelfBot choice is recorded above. These remain:

1. Whether any later build may send one `LANG_ADDON` whisper to the authenticated client so an addon can echo a token. Lua delivery is **UNKNOWN** until that trial exists. This branch does not send it.
2. Live `AddonChannel` and live `MapUpdate.Threads`, when an operator is ready to read them. Not read here. Live `Playerbots.SelfBotLevel` was not read here either. The startup read is the proof, once it is implemented.
3. Whether a process restart is the required way to open the gate after `Playerbots.SelfBotLevel` changes. This candidate says yes, because a `.reload config` to `0` does not by itself update `sPlayerbotAIConfig.SelfBotLevel`.
4. Whether the Addon Creator should key saves by a server token after the wire is accepted. The frozen addon is unchanged.
5. When, if ever, Module Editor replaces the #134 protocol text with an accepted v2. CS01 still has to agree that text. Not in this branch.

## Recorded run

Offline only. Not an in-game result. Parent `2ab30306c884d3af1c92bb5ad7042648b90fd162`. The commit SHA is the `#48` checkpoint after this tree is committed. Workflow files were not edited. The new paths are `docs/research/a02-pak-d1-protocol-v2-proposal.md` and `tests/research/`. Those paths sit outside the path filters of the worldserver workflows in `.github/workflows/`, including `hunter-pet-autocast-pinned-worldserver.yml`. This proposal does not add a workflow trigger.

```text
python3 tests/research/test_a02_pak_d1_protocol_v2.py
```

Result on this revision: 29 unittest methods, OK, exit 0. Printed witnesses: 37. v1 safety FAIL 20, v1 safety PASS 17, v2 safety FAIL 0, v2 safety PASS 37. `SOURCE_ANCHORS proposal+header+cpp OK` is an extra unittest check, not one of the 37. Isolation witnesses still assume a startup proof that `Playerbots.SelfBotLevel` is 0. The new v2 passes are PAK-ID-07 (A OFF restored from the pet-number save, B unwritten), PAK-ID-07-MISSING, PAK-ID-07-ZERO, PAK-ID-07-DELETED, PAK-ID-07-REUSED, PAK-ID-07-STALE, PAK-ID-07-CLEAR (no spell write), and the SelfBot gate witnesses PAK-SELF-ENABLED, PAK-SELF-UNREADABLE, PAK-SELF-MISSING, PAK-SELF-MODULE, PAK-SELF-OFF, PAK-SELF-RELOAD, and PAK-SELF-NOCLIENT.

```text
lua5.1 tests/research/test_a02_pak_d1_addon_contract.lua <PetAutocastKeeper directory at zip sha256 4d4e04843e6274b4ede20a03429c3c6f05f2b579f8536d48d59710ec9dc7e007>
```

**NOT RUN** on this revision. The zip is not in this repository, and `lua5.1` is not installed here. The Lua file was not changed. It still checks the frozen addon, which keys by `PetKey` and does not know a pet number. The `db.pets[petNumber]` contract is documentation for a later addon. It is not a patch to that zip.

Still **NOT TESTED**: in-game summon, stable, relog, bar, fallback button, 3.3.5a Lua delivery of a server addon whisper, live `AddonChannel`, live `MapUpdate.Threads`, live `playerbots.conf`, DBC autocast and spell-chain rows, `learnSpell`'s autocast bit, and any C++ implementation of this candidate. Both module flags stay 0.
