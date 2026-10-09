# Progression-aware mount summoning — implementation and safety guide

**Status:** Source staged, **not compiled, deployed or tested**. The feature is **disabled by default**. This document describes a carefully scoped **optional AzerothCore core patch**, because the existing spell scripting hooks execute too late to set a per-character cast time before `SPELL_START`.

## Intended gameplay

| Individual Progression | Normal mount summon cast |
| --- | --- |
| Vanilla (stages 0–7) | **3.0 seconds** |
| TBC (stages 8–12) | **3.0 seconds** |
| Beginning of WotLK (stage 13 onwards) | **1.5 seconds** |

This **WotLK entry** unlock is a server design choice. Retail WoW's historical 1.5-second reduction was introduced later (patch 3.2). Only positive-cast, non-channeled mount spells that apply `SPELL_AURA_MOUNTED` are modified. Instant mounts, forms, other spells, and non-player casters are left alone.

## Files added / changed

- `src/Systems/EraMountCast.cpp` — module-owned, per-character logic; no-op unless the core patch marker is present.
- `src/NaxxramasCore_loader.cpp` — registers the optional system.
- `conf/mod_naxxramas_core.conf.dist` — all settings, default off.
- `patches/azerothcore-optional-after-calc-spell-cast-time.patch` — **optional** small core patch. It changes **four** AzerothCore source files only:
  - `src/server/game/Scripting/ScriptDefines/GlobalScript.h`
  - `src/server/game/Scripting/ScriptDefines/GlobalScript.cpp`
  - `src/server/game/Scripting/ScriptMgr.h`
  - `src/server/game/Spells/SpellInfo.cpp`

The patch adds a reusable `GlobalScript::OnAfterCalcSpellCastTime` hook after standard spell modifiers, before the cast timer and `SPELL_START` packet. It does **not** alter `Spell.dbc`, creature spells, other player spells, CharacterDatabase, WorldDatabase or Individual Progression source. Existing global hook indices are unchanged because the new hook is appended immediately before `GLOBALHOOK_END`.

## Configuration

In the **active installed** `mod_naxxramas_core.conf` (not merely `.dist`):

```ini
NaxxramasCore.EraMountCast.Enabled = 0
NaxxramasCore.EraMountCast.ClassicCastTimeMs = 3000
NaxxramasCore.EraMountCast.ModernCastTimeMs = 1500
NaxxramasCore.EraMountCast.UnlockStage = 13
NaxxramasCore.EraMountCast.ExemptPlayerbots = 1
```

- `Enabled = 0` is the **safe default**. Set it to `1` only after testing with the core patch installed.
- Times are milliseconds, clamped at 500–10000. Set the exact agreed values above.
- `UnlockStage` defaults to **13**; valid range **13–18**. Earlier values are rejected to prevent an accidental pre-WotLK unlock.
- `ExemptPlayerbots = 1` preserves normal AzerothCore mounts for bot accounts matching `IndividualProgression.BotAccountsRegex` (default `^RNDBOT.*`). An invalid regex cannot crash casting.
- If `IndividualProgression.Enable = 0`, this feature changes **nothing**.
- `IndividualProgression.ProgressionLimit`, when lower than the configured unlock, keeps affected characters in the Classic 3-second bucket.
- Modern Individual Progression rewarded hidden quest milestones `66013` through `66018` determine when 1.5 seconds unlocks; stages `66008` to `66012` remain at 3 seconds.
- Older Individual Progression variants using the **legacy player-settings progression storage** are **not supported** until their exact revision is reviewed.

## Essential compatibility points

1. **Individual Progression:** Uses the existing hidden reward quests and respects its enable switch and progression cap. Does not grant, consume or delete a quest.
2. **Playerbots:** Exempt by default using the same bot-account regex as the other Naxxramas Core progression restrictions. No Playerbots source or AI routines are modified.
3. **Battlemaster queues / Meeting Stones:** Their independent script hooks and config keys are unchanged.
4. **Class talents and custom spells:** `HasAura(SPELL_AURA_MOUNTED)` filters out normal class spells; `CastTimeEntry` and existing `castTime > 0` protect genuine instant or triggered mount effects. A client-specific unusual spell that indirectly triggers mount effects should be checked in game.
5. **DBC and client:** Does not modify `Spell.dbc` or ship a client patch. Server `SPELL_START` carries the new timer. Client visual/timing should still be confirmed in-game for ground and flying mounts.
6. **Server updates:** The optional core patch touches four upstream files; a future AzerothCore update may require rebasing/re-applying it. Never force-apply a conflicting patch.
7. **Other AzerothCore modules:** The hook is generic and does not mutate shared `SpellInfo`; only this script currently opts in. Review other modules implementing custom spell cast-time modifiers before enabling it. Cast time is replaced with the configured mount value *after* normal modifiers, which may override rare mount-specific haste/instant reductions; spells already calculated as instant remain instant.

## Before compilation: backup and optional patch review

**Do not apply the patch to your live server without a source and database backup.** First capture the exact AzerothCore revision because the patch was prepared against the publicly available upstream snapshot on 9 October 2026.

From your **AzerothCore source root** in MobaXterm, after making a full server backup:

```bash
git rev-parse HEAD
git status --short
```

**Stop if you have uncommitted modifications you have not backed up.**

Once the Naxxramas Core module is pulled under your `modules/` directory and you have confirmed your local path, test the patch without changing any files. Example (change the module folder name if yours is different):

```bash
git apply --check modules/Mod-Naxxramas-Core/patches/azerothcore-optional-after-calc-spell-cast-time.patch
```

- If the command completes silently, Git considers the patch applicable.
- If it reports a failure, **stop**, do not use `git apply --reject` or force the patch. Supply the exact AzerothCore commit, failure output and current module path so we can adapt it.
- Passing `git apply --check` does **not** prove compilation, in-game behaviour, or compatibility with every installed module.

When the check passes, you explicitly approve the core modification, and the backup is verified, apply the patch:

```bash
git apply modules/Mod-Naxxramas-Core/patches/azerothcore-optional-after-calc-spell-cast-time.patch
```

Confirm `git diff --stat` shows **only the intended four core source files**. Keep the feature **Enabled = 0** for your first rebuild and restart. After a clean build, enable and test on a staging server or at a quiet time.

## Test matrix — before enabling for players

1. Config 0: mount casts on Vanilla/TBC/WotLK characters remain **unchanged**.
2. Config 1, Vanilla character: normal casted ground mount takes **3.0 seconds**.
3. Config 1, TBC stages 8–12: normal casted ground/flying mounts take **3.0 seconds**.
4. Config 1, WotLK stage 13+: the same normal casted mounts take **1.5 seconds**.
5. Test a character with later hidden quest progress and an IP progression cap below 13: **3.0 seconds**.
6. Turn Individual Progression off in test config: the system makes **no override**.
7. Keep `ExemptPlayerbots = 1`: bot summon behaviour remains stock. Also test a party containing bots.
8. Test instant mounts, shapeshift/travel forms and mount-related scripted effects: **unchanged**.
9. Verify several non-mount spells (cast times, talents, haste) stay **unchanged**.
10. Test movement interruption, failed mount attempts, relogging, multiple character stages online and PvP queue/Meeting Stone features to detect regressions.
11. Confirm the client's cast bar and the server's actual completion time agree. Retest if a third-party cast-bar addon is used.

**Test results are pending. No compilation or live client tests have been performed by this change.**

## Rollback and uninstall

**Immediate configuration rollback:** set `NaxxramasCore.EraMountCast.Enabled = 0` in the **active installed config** and restart worldserver. This retains all source changes but restores native cast behaviour.

**Remove the optional core patch:** first disable it and back up modified sources. From the same source root, and only if `git apply --reverse --check` succeeds:

```bash
git apply --reverse --check modules/Mod-Naxxramas-Core/patches/azerothcore-optional-after-calc-spell-cast-time.patch
git apply --reverse modules/Mod-Naxxramas-Core/patches/azerothcore-optional-after-calc-spell-cast-time.patch
```

Then rebuild and restart using the unpatched source. **Do not** use `git reset --hard`; other unrelated edits may be present. Reversing a patch from a newer changed source could fail, in which case stop and review the diff manually.

No new database tables or item/spell DBC changes are made by this implementation. The feature can be fully disabled without undoing any character inventory, progression or spell records.
