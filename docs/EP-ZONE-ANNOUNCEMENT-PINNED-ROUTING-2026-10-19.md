# EP towers — pinned native zone announcement path

**19 October 2026 · independent read-only DRAFT, stacked on EP announcement PR #24.**

We want one additional, native-zone message when the **full** Eastwall, Northpass, Plaguewood or Crown Guard Tower capture reaches 100% and starts the 90-minute lock. The base OutdoorPvP script already has earlier ownership text; that stock text remains unchanged.

This isolated test checks assumptions that the draft announcement source relies on, without changing **any** runtime C++, stock AzerothCore, Individual Progression, Playerbots, game tables or actual Worldserver configuration.

## Pinned source evidence and contracts

**Exactly pinned core:** `Grimfeather/azerothcore-wotlk@a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7`.

- `OutdoorPvPEP.h`: the `EP_Towers` enum starts at `EP_EWT=0` and orders **EWT, NPT, PWT, CGT**. That is exactly the name-array order in our module: **Eastwall, Northpass, Plaguewood, Crown Guard**. Wrong names or reordered indexes must fail.
- `OutdoorPvPEP.h`: `EP_GraveyardZone` resolves to `AREA_EASTERN_PLAGUELANDS`, so the target of the custom notice stays inside Eastern Plaguelands.
- `Map.h` and `Map.cpp`: `SendZoneText(zoneId, text)` defaults to **TEAM_NEUTRAL**. Its `SendZoneMessage` path includes all in-world players in that zone across both factions unless an explicit team filter is supplied; the module provides none. This is a *source-level* expectation, not confirmation two clients actually received the message.
- `EasternPlaguelandsTowerLock.cpp`: the only custom `SendZoneText` sits in the full-cap signed-endpoint path, after the `PackLock` check and **after calling** `sWorldState->setWorldState` for this tower. Locked ticks use `Update(0)` and restored/neutral-reset paths do not announce. This is an ordering check against the persistence **API call**, **not proof** that a database transaction is flushed/durable or that a player saw the text.

## Run and safety

The sparse checkout GitHub Action validates exact SHA pins, runs **eight disposable synthetic positive/negative tests**, then tests the real pinned EP header, native map header/dispatcher and current module draft source. It does not build/start Worldserver, send chat, perform manual SQL binding, read/alter the owner's DB, or activate anything.

Actual S5/S6 testing still requires separate owner authorization, exact installed versions, restorable binary/config/characters/affected worldstate backups and manually approved EP handler selection. Test the four towers in both factions, an observer elsewhere in Eastern Plaguelands, repeat locked ticks, restart, neutral expiry, and unaffected core objectives. An in-zone notice screenshot is separate from the synthetic check.

See [module EP announcement draft #24](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/24) and [authoritative tracker #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28).
