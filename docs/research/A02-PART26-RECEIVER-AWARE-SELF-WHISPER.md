# A02 P26 — receiver-aware self-whisper ingress fix

**DRAFT only. Not approved for merge, release, server enablement or gameplay trial.**

## What is actually improved

This child of [#163](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/163) replaces only A02's legacy `OnPlayerBeforeSendChatMessage` input hook with the pinned-core `OnPlayerCanUseChat(Player*, uint32, uint32, std::string&, Player* receiver)` overload. No pet-writing or preference-store code is modified. The hook is enabled through `PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT` and rejects messages unless `receiver == player`, `CHAT_MSG_WHISPER`, `LANG_ADDON`, and the existing A02 opt-in flag is on. Every path returns true so it does not veto normal whisper delivery or override another module's chat policy.

**Direct native source witnesses** (exact pins; public sources only):
- Core `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` `ChatHandler.cpp:364`: the old before-send hook fires *before* the whisper receiver has been resolved. The handler obtains the receiver around `ChatHandler.cpp:396`, invokes `GetPlayer()->Whisper(msg, Language(lang), receiver)` at line 448.
- `Player.cpp:9683–9707`: `Player::Whisper` calls `sScriptMgr->OnPlayerCanUseChat(this, CHAT_MSG_WHISPER, language, _text, target)` after it has the actual `Player* target`, before constructing the packet.
- `PlayerScript.h:688,701` and `PlayerScript.cpp:845–848`: exact receiver-aware overload + `PLAYERHOOK_CAN_PLAYER_USE_PRIVATE_CHAT` dispatch.
- Playerbots `mod-playerbots/mod-playerbots@d750b4b3a50effdf22bedc8032f0e8e5f7cb8091` already registers this hook, providing pinned compatibility evidence. In-game event order is not tested.

## Exact safety limit

This proves **resolved same-recipient routing only**, not proof that a click came from a human, that a specific persistent pet was selected, or that a newer manual OFF wasn't lost before the client sent its packet. `LANG_ADDON` and a sender session are not physical-human attestation. The underlying **v1** store is still per-player; no v2 identity/ack/hello, latest manual sequence, positive current-human/SelfBot mode, IP-end signal or durable pet ID has been implemented. **Enabling A02 flags is still UNSAFE.** The sibling #163 header remains unwired. The new test checks source structure; it is not a network, process or timing test.

## CI / acceptance

A dedicated source gate checks the resolved-recipient condition, continued return-true behaviour and default-off flags. The inherited source/native/pinned full Worldserver workflow is updated to demand the **new exact symbol**, with pinned public core, Playerbots and Individual Progression. Do not report build or link PASS until the exact-head hosted job completes successfully. Passing full link is not game testing.

**No changes** to core, IP, Playerbots, N-Core, SQL/DBC, live config or any owner host. Existing #135/#163/#160 are untouched. Preserve `MapUpdate.Threads=8`, owner-customised Playerbots files and newest manual ON/OFF policy A. Still requires independent review and separately approved staging and gameplay tests.
