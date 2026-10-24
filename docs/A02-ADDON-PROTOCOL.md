# A02 S2c — PetAutocastKeeper addon protocol

**Status:** isolated draft. Both config keys stay 0. This file is not permission to enable them, not a merge, and not an in-game result. In-game behaviour is **NOT TESTED**.

**Author:** CosmicScript02. Independent exact-head review requested from CosmicScript01.

The module does not edit core, Playerbots, or Individual Progression. It does not send SQL. The Playerbots `IsRealPlayerSynchronized` proposal is not implemented.

Pins read, not modified:

| Tree | Commit |
| --- | --- |
| Grimfeather `azerothcore-wotlk` | `8daffdabe9202c228e45d833c9a1d399597a15cd` |
| `mod-playerbots` | `d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` |
| Grimfeather `mod-individual-progression` | `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61` |

## Hook and thread

**VERIFIED** at the core pin. There is no separate addon-message script hook.

`CMSG_MESSAGECHAT` is `PROCESS_THREADUNSAFE` (`src/server/game/Server/Protocol/Opcodes.cpp:280`). `WorldSessionFilter::Process` returns true for `PROCESS_THREADUNSAFE` (`src/server/game/Server/WorldSession.cpp:96-98`), so `World::Update` runs it from `sWorldSessionMgr->UpdateSessions` (`src/server/game/World/World.cpp:1227`). That call is before `sMapMgr->Update` (`World.cpp:1254`). `MapSessionFilter::Process` returns false for the same opcode (`WorldSession.cpp:74-76`), and `Map::Update` uses that filter (`src/server/game/Maps/Map.cpp:449-450`). The handler therefore runs on the world thread, not on a map worker.

`WorldSession::HandleMessagechatOpcode` (`src/server/game/Handlers/ChatHandler.cpp:61`) calls `sScriptMgr->OnPlayerBeforeSendChatMessage` at `ChatHandler.cpp:364`. The dispatcher is `ScriptMgr::OnPlayerBeforeSendChatMessage` (`src/server/game/Scripting/ScriptDefines/PlayerScript.cpp:190-192`), hook id `PLAYERHOOK_ON_BEFORE_SEND_CHAT_MESSAGE` (`PlayerScript.h:73`), virtual `PlayerScript::OnPlayerBeforeSendChatMessage` (`PlayerScript.h:341`). The call at line 364 is before the whisper `switch` at line 390. `OnPlayerCanUseChat` for a whisper runs later, inside `Player::Whisper` (`src/server/game/Entities/Player/Player.cpp:9694`).

`LANG_ADDON` is `0xFFFFFFFF` (`src/server/shared/SharedDefines.h:741`) and is a real language row (`src/server/game/Globals/ObjectMgr.cpp:233`), so the unknown-language return at `ChatHandler.cpp:87-92` does not drop it. `CHAT_MSG_WHISPER` is an allowed addon type when `AddonChannel` is true (`ChatHandler.cpp:186-201`). The default of `AddonChannel` is true (`src/server/game/World/WorldConfig.cpp:154`). **UNKNOWN:** the owner's live `worldserver.conf` may set `AddonChannel` to 0. This module does not change that key. If it is 0, the handler returns at `ChatHandler.cpp:197-200` and the hook does not run.

`AddonChannelCommandHandler::ParseCommands` returns false unless the text starts with `AzerothCore\t` (`src/server/game/Chat/Chat.cpp:991-994`). `NXCPAK` is not consumed there, so control reaches line 364.

The hook's `msg` is the raw chat string. The core does not split on tab. A 3.3.5 `SendAddonMessage` puts `prefix`, a TAB, and the payload into that string.

Logout is also the world thread. `OnPlayerLogout` is `WorldSession.cpp:837`, reached from `LogoutPlayer` (`WorldSession.cpp:686`) on the `ProcessUnsafe` path (`WorldSession.cpp:595-607`). Login is `CharacterHandler.cpp:1126`, and `CMSG_PLAYER_LOGIN` is `PROCESS_THREADUNSAFE`. The restore hook stays `OnWorldObjectUpdate` on the map thread. The store mutex publishes an immutable `shared_ptr` from the world thread. The map thread copies that pointer under the mutex and reads it after the unlock.

The live `MapUpdate.Threads` value was not read. The owner states 8. That value is **UNKNOWN**.

## Decisions on the addon inputs

1. **Length. VERIFIED** in source, **NOT TESTED** in game. `ChatHandler.cpp:292` returns when `msg.length() > 255`, before the hook. A string of length 255 still reaches the hook. The server accepts `NXCPAK` + TAB + payload when the combined string is 1 to 255 bytes, and it splits on the first tab. PetAutocastKeeper's 233-byte payload budget is the addon's send limit, not a second server cutoff: 6 + 1 + 233 = 240, which is under 255. A combined string of 256 bytes is ignored. A payload longer than 233 is still parsed when the combined string is at most 255.

2. **Whisper to self. VERIFIED** in source that the hook sees a `LANG_ADDON` whisper before whisper delivery, including a whisper whose target is the sender. The level check skips `receiver == sender` (`ChatHandler.cpp:402-405`). The ignore-whisper filter is skipped for `LANG_ADDON` (`ChatHandler.cpp:408`). The trial check skips `receiver == sender` (`ChatHandler.cpp:415-416`). `Player::Whisper` sends an addon whisper to that target and returns before the inform path (`Player.cpp:9687-9707`). No alternate channel is proposed. Party, raid, guild, and battleground addon messages are ignored by this module even though the core would deliver them to the same hook. **NOT TESTED** in game.

3. **Sequence.** Chunks for one seq are buffered until every index `1..total` has arrived. Arrival order does not matter. A higher seq discards an older partial assembly. A repeated index with the same pairs is ignored. A repeated index with different pairs discards that partial assembly and does not change the published set. A seq that was already published is ignored, so a retry must use a higher seq if it should replace the set. `OnPlayerLogin` resets seq tracking and keeps a published set if logout did not erase it. The next complete seq is then accepted even when it is lower. `OnPlayerLogout` erases the set and the tracker. A lower seq while the tracker is still live does not replace a published set. SavedVariables lost without a logout stay ignored until relog or `v1|clear`.

4. **Set meaning.** A pair is an explicit autocast choice for that spell id. The server stores it under `SpellMgr::GetFirstSpellInChain`, so a later rank of the same chain matches. The addon may send the highest rank it knows, in ascending id order. The server does not require that order and does not check spell names. Two pairs that normalize to one chain: the later pair in chunk order wins. Spells absent from the set are left alone. A listed spell the pet does not currently have is skipped and is not learned. Cower 1742 is that case when Individual Progression has removed it, as it does for Serpent, Moth, Chimaera, and Silithid. When the current pet has 1742, the explicit on/off is applied like any other listed spell. The module does not call `learnSpell`. A non-autocastable spell id is dropped from the set and does not fail the rest of the message. The illustrative payload `v1|7|1/1|1742=0,17259=1` is accepted as written.

5. **Timing. VERIFIED** as source order, **NOT TESTED** in game. The chat hook runs in session update before that tick's map update, so a set that arrives in the same world tick as `checkHunterPetSpells` is stored before the pet update. The map thread applies a new generation to the spells the current pet has, including the post-reset book on that tick. The same published set is applied again when a later rank replacement changes the book. A same-id autocast click is not overwritten. The next rank reset of a listed chain applies the stored choice again, which can put back the saved bit after that reset.

6. **No acknowledgement.** The server sends no whisper, no addon message, and no other reply. The addon's 4 second bar check and fallback button are the only completion signal.

7. **No pet identifier in v1.** The payload does not name a pet, and v1 does not add an optional pet field. The server applies the set only to the owner's current hunter pet (`owner->GetPet()`). Stabled pets are not updated. **POTENTIAL ISSUE:** if the summoned pet changes and the addon does not send a new seq, the previous pet's set can be applied to the new pet on the next reset. The addon should send a new seq when the summoned pet's bar changes. A v2 would be required to add a pet field. None is defined here.

## Labels

| Finding | Label |
| --- | --- |
| `OnPlayerBeforeSendChatMessage` on the world thread, before whisper handling | **VERIFIED** at the pin. In-game delivery is **NOT TESTED** |
| `msg.length() > 255` dropped before the hook; 255 still delivered | **VERIFIED** source. **NOT TESTED** in game |
| `AddonChannel` default true | **VERIFIED** source. The owner's live value is **UNKNOWN** |
| Whisper-to-self checks do not drop `LANG_ADDON` before the hook | **VERIFIED** source. **NOT TESTED** in game |
| SelfBot client can send the addon message | **POTENTIAL ISSUE** accepted by the owner's direction. This module does not read Playerbots |
| No pet field; a pet swap without a new seq can apply the old set | **POTENTIAL ISSUE** |
| Cower 1742 toggled when the pet has it, skipped and not learned when the pet lacks it | **VERIFIED** by the native plan test. In-game bar is **NOT TESTED** |
| Unchanged book at the same generation skips `DecideChains` | **VERIFIED** by the native test |
| No write without a published opt-in | **VERIFIED** by the native plan test |
| Login resets seq tracking; logout erases the set | **VERIFIED** by the native store test. The logout hook's live timing is **NOT TESTED** |
| Hosted pinned worldserver link of this SHA | **NOT TESTED** until that workflow finishes |
| In-game autocast, relog, resummon, stable, client bar | **NOT TESTED** |

## Final protocol text

The following block is the protocol. PetAutocastKeeper should match it.

```text
PetAutocastKeeper sends one addon whisper to the player:

    SendAddonMessage("NXCPAK", payload, "WHISPER", UnitName("player"))

The client puts the six-character prefix, one TAB (0x09), and the payload into one chat string. The server splits on the first TAB. The payload itself contains no TAB and no spaces.

The combined string is accepted only when its length is from 1 to 255 bytes inclusive. A longer string is ignored. The addon keeps the payload at or below 233 bytes. The prefix, the TAB, and a 233-byte payload are 240 bytes.

Only a LANG_ADDON whisper is accepted. Party, raid, guild, and battleground messages are ignored. The server sends no reply.

The payload is one of these two forms:

    v1|<seq>|<n>/<total>|<pairs>
    v1|clear

<seq> is a decimal integer from 1 to 999999999 with no leading zero.
<n> and <total> are decimal integers from 1 to 8 with no leading zero, and <n> is less than or equal to <total>.
<pairs> is empty, or a comma-separated list of <spellId>=<0|1> with no trailing comma.
<spellId> is a decimal integer from 1 to 4294967295 with no leading zero.
A single chunk contains at most 64 pairs. A completed sequence contains at most 64 pairs. A duplicate spell id in one chunk, or the same spell id repeated in two chunks of one sequence, is malformed.
The version is the two characters v1. Any other version is malformed.

Chunks of one seq are stored until indexes 1 through <total> have all arrived. They are merged in index order, not arrival order. The published set is replaced only when the sequence is complete. A higher seq discards an older unfinished sequence. A repeated index with the same pairs is ignored. A repeated index with different pairs discards that unfinished sequence and does not change the published set. A seq that was already published is ignored. A lower seq is ignored while seq tracking is live.

v1|clear deletes the published set and the unfinished sequence and resets seq tracking. It has no sequence number.

OnPlayerLogin resets seq tracking. The next complete sequence is accepted even if its seq is lower than a seq from earlier in the process. OnPlayerLogin does not by itself delete a published set. OnPlayerLogout deletes the published set, the unfinished sequence, and the rate window.

A published set is explicit on/off choices for the listed spells. The server normalizes each spell id with GetFirstSpellInChain and matches a later rank of that chain. Unlisted spells are left alone. A listed spell the current pet does not have is skipped and is not learned. Spell 1742 is never learned. When the current pet has spell 1742, its explicit on/off is applied like any other listed spell. A spell id that is not an autocastable pet spell is dropped and the rest of the message is kept. If two accepted pairs share a chain, the later pair in chunk order wins. The addon may send the highest rank it knows for each spell name, in ascending id order. The server does not require that order.

Example, with illustrative ids:

    v1|7|1/1|1742=0,17259=1

There is no pet identifier. The set applies to the owner's current hunter pet only. The addon sends a new, higher seq when that pet's saved bar changes. v1 defines no optional pet field.

The set is stored when the sequence completes. A new generation is applied on the next pet update to listed spells the pet has. The same set is applied again after a later rank reset of a listed chain. A same-id autocast click is not overwritten.

Each player may deliver 8 NXCPAK messages per 10000 milliseconds. A further message in that window is ignored and does not change the stored set. Malformed messages count toward the limit. Messages that are not NXCPAK, and messages from a player who is not a Hunter, do not.

Both of these config keys default to 0 and this draft does not turn them on:

    NaxxramasCore.HunterPetAutocast.RestoreHumanChain = 0
    NaxxramasCore.HunterPetAutocast.AddonOptIn = 0

A write requires both keys on and a published set. With either key off, or with no published set, the module does not toggle pet autocast.
```
