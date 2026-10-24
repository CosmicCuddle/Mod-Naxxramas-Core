# P0 × B10 combined integration — REVIEW ONLY

**Status:** isolated combined source candidate, **not a merge request**. This integration does not change production `main` or either source draft. No SQL/DBC, owner server, installed Playerbots, config, character, inventory or in-game change.

## Exact pinned origins

- P0 four-fix [draft PR #105](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/105): `b5311a70f609767011f9ecc0a72e506f031c9957`.
- B10 combined thread safety [draft PR #118](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/118): `653da3ad5c620040c219c15c0890b9b30bab5a0c`.
- This review-only candidate starts from the full exact #118 tree, ports #105's **17 nonoverlapping files unchanged**, and manually reconciles its **three shared files**:
  - `src/Systems/BotRaidConsumables.cpp`: keeps #118 Player::CustomData, queue, order of `ConsumeIfDue`/cross-map guard; changes GFPP one-shot 90s → **120s exactly once** with no retry.
  - `conf/mod_naxxramas_core.conf.dist`: keeps CrossMapAuraSafety OFF and GFPP OFF, updates GFPP timer description to 120s, retains #105 named-single-bot Golemagg guard OFF.
  - `tests/test_mc_gfpp_one_shot.py`: combines #105's 120s native/timer regression with #118's `EraseRaidConsumableTracker` cleanup assertion.
- Adds `test_combined_p0_b10_source.py` source contract checking conflicts; standalone exact-head synthetic CI. Any prior #105 or #118 CI pass **does not** transfer to this new tree.

## Mandatory review gates

1. Full exact-head source and native regressions, including P0 Warlock Meeting Stone, Shaman totem preservation, Golemagg named-bot constraints, 120s one-shot/no-retry, #114 queue ABA/bounded retention, pet identity, timer-before-offmap-guard, and OFF parity.
2. Exact-head **full linked Worldserver**, with unchanged pinned Grimfeather `8daffdabe`, public Playerbots `d750b4b3`, public IP `dd96f2b`; linked loader/world-thread symbols verified, **zero artifact uploads**.
3. Independent **CS02/Grok** and **CS03/Claude** reciprocal source/delta review of this exact new commit and possible hidden semantic conflicts.
4. Later owner-approved backup/repro/build with **owner's Playerbots `e88cc409` + two local compatibility edits**, followed by owner-controlled `MapUpdate.Threads = 8` game tests, one named Golemagg Altbot, GFPP, pet swap and human loot negative cases. **Not authorised/performed in this draft.**

All new features remain OFF by default. No merge, install, enable, deploy or live server edit.
