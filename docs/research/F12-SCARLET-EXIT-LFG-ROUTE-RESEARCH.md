# F12 — Scarlet Monastery Armory/Cathedral exit route proof

**Stage:** S1 pinned-source investigation and synthetic decision regression. **REVIEW ONLY.** No runtime C++ fix, SQL, DBC, teleport coordinates, packaged artifact or server change. Desired gameplay outcome remains **behind each wing's corresponding entrance door**, not a guessed position.

## Exact public pinned source

Grimfeather AzerothCore commit: `8daffdabe9202c228e45d833c9a1d399597a15cd`.

| Wing | Inside exit trigger | Source map | SQL destination map | Public baseline destination (XYZ/O) | Outside entrance trigger |
| --- | ---: | ---: | ---: | --- | ---: |
| Cathedral | 604 | 189 | 0 | (2906.14, -813.772, 160.333, 1.95739) | 610 |
| Armory | 606 | 189 | 0 | (2884.45, -822.01, 160.333, 1.95268) | 612 |

These are **public baseline** rows at [`areatrigger_teleport.sql` lines 72–76](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/data/sql/base/db_world/areatrigger_teleport.sql) and source geometry IDs from [`areatrigger.sql` lines 127–131](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/data/sql/base/db_world/areatrigger.sql). They are *not* proposed corrected behind-door coordinates and not proof of the owner's loaded `acore_world`.

## Why a normal exit can differ from a Dungeon Finder exit

Pinned [`MiscHandler.cpp::HandleAreaTriggerOpcode` lines 691–806](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/MiscHandler.cpp) checks source DBC/radius, a script interception, earlier handlers, `GetAreaTriggerTeleport`, and map entry permission. On a **cross-map** exit, if group is `isLFGGroup()` and the *current* map `IsDungeon()`, it attempts `TeleportToEntryPoint()`. If that call **returns true**, the SQL destination is bypassed. If the call returns **false**, execution falls through to the normal SQL destination. Other groups use the SQL destination directly.

Pinned [`Player.cpp::TeleportToEntryPoint` lines 1648–1663](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Player/Player.cpp) uses `m_entryPointData.joinPos` or, when invalid, attempts the homebind. It clears the stored join-map ID and schedules delayed operations before attempting the teleport. **A failed return is not a guarantee that no preliminary side effects happened.** Do not replace the normal SQL target without investigating which path produced the reported symptom.

## Synthetic regression contract

Run `python3 -m unittest discover -s tests -p 'test_f12_scarlet_exit_path_model.py' -v`.

The 16 standalone tests distinguish Cathedral/Armory IDs, normal-group SQL, LFG saved position, homebind, failed entry-point fallback, non-dungeon LFG, same-map case, denied map entry, script interception, invalid DBC/out-of-radius, early handlers, missing SQL rows and non-F12 triggers. **Tests predict conditional branches; they do not call AzerothCore, launch a server, validate door collision, or test the owner's live database.** CI is synthetic-only, checkout pinned to PR head, with no binary or artifact upload.

## Outstanding proof gates

1. Establish whether the owner's original problem was in a Dungeon Finder group or normal party/solo; record where the exit actually placed the character, but no in-game retest is requested now.
2. When separately authorised, compare **read-only** active teleport rows 604, 606, 610, 612 and associated `areatrigger` source geometry / `radius` to the pinned baseline. Do not execute schema updates, `RELOAD`, teleport commands or DBC edits.
3. Verify script interception / effective config / IP / Playerbots behaviour, and **actual behind-door world geometry** (do not invent XYZ or interchange the wings).
4. Only after design review and owner approval, stage backed-up 8-thread normal-party and LFG acceptance tests, both wings, failed-return safety, portal re-entry and facing.

See permanent master issue #28 and coordination issue #48. This candidate is *not* feature S2, full-linked S4, deployable S5, or gameplay S6.
