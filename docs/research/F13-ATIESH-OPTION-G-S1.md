# F13 — Atiesh portal: Vanilla arrival outside Karazhan (option G, S1 design)

**Stage:** S1 research and design only. **No code, config key, SQL, DBC or
server change.** S2 implementation needs CS01's separate go-ahead after peer
review of this document.

**Pins:** Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`,
Individual Progression `dd96f2b77e3ebfa2a4726bf785525ba133f1ab61`, Playerbots
`e88cc409` / `d750b4b`, this module `main` `80e9de1`. External read-only
spell data: VMaNGOS `brotalnia/database` `fc4af4870578efa63b36824bfd48fca7933f7362`. Line numbers refer to
those trees. Nothing here describes the owner's loaded database.

**Goal (#28 F13):** keep the Atiesh portal working, but during the Vanilla
stage send the user to the outside of Karazhan's main gate instead of into
the raid map. Later eras keep the stock behaviour.

## 1. Facts the design depends on

| # | Fact | Source | Status |
|---|---|---|---|
| F1 | GO 181146 "Portal to Karazhan" is type 22 SPELLCASTER: Data0 spell 28147, Data1 charges 0, Data2 partyOnly 1, Data3 allowMounted 1; no `ScriptName`/`AIName` | `gameobject_template.sql` L10542; field meaning `GameObjectData.h` L250–257 | Verified (baseline) |
| F2 | Spell 28147 targets map 532 `(-11100, -2001.64, 49.8927, 0.7995)` | `spell_target_position.sql` L348 | Verified (baseline) |
| F3 | Items 22589/22630/22631/22632 carry on-use spell 28148; IP keeps it and only removes 31796 | `item_template.sql`; IP `vanilla_item_changes.sql` L18905–18914 | Verified |
| F4 | 28148 summons GO 181146: effect1 **50** (`SPELL_EFFECT_TRANS_DOOR`), misc value **181146**, target A **47** (`TARGET_DEST_CASTER_FRONT`), cast-time index 7 | VMaNGOS `brotalnia/database` `fc4af48`, `world_full_14_june_2021.sql` `spell_template` line 882436 (client build 5464). Enum values: `SharedDefines.h` L816, L1455 | Verified for **Vanilla client data**; the 3.3.5a `Spell.dbc` the owner's core loads is not read (very likely identical, still a premise) |
| F5 | Summon type decides the GO owner: `EffectSummonObjectWild` sets **no owner** (`SpellEffects.cpp` L4008); `EffectTransmitted` (effect 50, L122) sets the caster as owner (L5765) | pinned core | Verified. With F4, a real Atiesh portal **has an owner**; an ownerless 181146 only comes from a manual spawn (e.g. GM `.gobject add`) |
| F4b | 28147: effect1 5 `TELEPORT_UNITS` (A 25 `TARGET_UNIT_TARGET_ANY`, B 17 `TARGET_DEST_DB`), effect2 77 `SCRIPT_EFFECT` | same VMaNGOS row 882435; `SharedDefines.h` L771, L843, L1426, L1433 | Verified (Vanilla data). No `spell_script_names` or `spell_scripts` row for 28147 in pinned core, so effect 2 has nothing to run there |
| F6 | Native `partyOnly` check applies **only when the GO has an owner GUID**: a non-owner must be in a group that contains that GUID (`Group::IsMember`, no online check) | `GameObject.cpp` L1920–1934; `Group.cpp` L2556–2559 | Verified |
| F7 | Global hook `AllGameObjectScript::CanGameObjectGossipHello(Player*, GameObject*)`, registered by constructor with no DB binding; first `true` wins | `AllGameObjectScript.h` L56; `AllGameObjectScript.cpp` L52–56; `GameObjectScript.cpp` L24–42; `ScriptMgrMacros.h` L24–36 | Verified; already used by `MeetingStoneProgression.cpp` L108 (`main`) |
| F8 | In `GameObject::Use`, the order is: `GO_FLAG_NOT_SELECTABLE` reject (L1499) → **hook** (L1509) → GO AI → cooldown (L1516) → dismount unless usable mounted (L1524–1526) → type switch → cast and `AddUse` (L2114–2117) | `GameObject.cpp` | Verified |
| F9 | `GetCooldown()` is 0 for type 22; `IsUsableMounted()` returns `spellcaster.allowMounted` | `GameObjectData.h` L411–423, L581–590 | Verified. GO 181146 never dismounts at baseline |
| F10 | `CMSG_GAMEOBJ_USE` is `PROCESS_INPLACE`; the handler checks spawned, distance and mover before `Use()` | `Opcodes.cpp` L308; `SpellHandler.cpp` L329–350 | Verified. The hook runs where the native cast runs today |
| F11 | IP has no rule for map 532; its parent map is 0 | `IndividualProgressionPlayer.cpp` L169–405; `instance_template.sql` L70 | Verified |
| F12 | Core admission for 532: raid group (unless `Instance.IgnoreRaid`) and level 68 (unless `Instance.IgnoreLevel`); GMs bypass | `MapMgr.cpp` L160–248; `dungeon_access_template.sql` L71; `PlayerStorage.cpp` L6894–6916 | Verified. Owner's config **UNKNOWN** |
| F13 | Outside target: `areatrigger_teleport` 4436 "Karazhan, Main (Exit)" → map 0 `(-11112.9, -2005.89, 49.3307, 4.02516)`; trigger 4436 is the gate's exit box on map 532 | `areatrigger_teleport.sql` L188; `areatrigger.sql` L584 | Verified (baseline). Owner's row **UNKNOWN** |
| F14 | That point is ~3.4 yd outside the outdoor entrance box 4131 (local x −13.42 vs half-length 10.04, using `Position::IsWithinBox`) | `areatrigger.sql` L453; `Position.cpp` L118–140 | Verified by calculation, not in game |
| F15 | `TELE_TO_SPELL` only stops a teleport from interrupting the caster's own spell | `Player.cpp` L1597; `SpellEffects.cpp` L1299 | Verified |
| F16 | Map 0 is never refused by `PlayerCannotEnter` (non-dungeon) or by IP's teleport hook | `MapMgr.cpp` L142–143; F11 | Verified |

**Predicted stock behaviour today (not tested):** a level-60 Vanilla character
casts 28147, then `TeleportTo` refuses map 532 (level 68 / raid group) and the
character stays where it is. With `Instance.IgnoreLevel = 1`, a GM, or a level
70 character in a raid, the character arrives inside. The owner's actual
experience is still needed for acceptance.

## 2. Proposed handler (S2, not written)

One `AllGameObjectScript` in a new file, registered from the loader. Proposed
key `NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled = 0`. The name is a
proposal; no config file is changed here.

`CanGameObjectGossipHello(player, go)`:

1. `!player || !go` → **false**.
2. Entry is not 181146, type is not SPELLCASTER, or `spellcaster.spellId` is
   not 28147 → **false**. The spell check stops the handler from acting on an
   edited template.
3. Flag off → **false**.
4. Not Vanilla by the shared era helper (§4) → **false**. Later eras use stock.
5. GM → **false** (proposed, decision D1).
6. **`partyOnly` mirror (F6):** if `partyOnly` and the owner GUID is set and
   the user is not the owner and (no group or `!group->IsMember(owner)`) →
   **false**. The native path then rejects exactly as today. With no owner
   GUID, allow, as stock does (D2).
7. Already teleporting (`IsBeingTeleported()`) → **true**, nothing else.
8. Read row 4436 with `sObjectMgr->GetAreaTriggerTeleport(4436)`. Missing,
   `target_mapId != 0`, or `!MapMgr::IsValidMapCoord(...)` → **true** plus a
   system message, and **no teleport** (fail closed, D3).
9. Mount parity: if `!go->GetGOInfo()->IsUsableMounted()`, remove mounted
   auras first. At baseline this does nothing (F9).
10. `TeleportTo(0, x, y, z, o, 0)` (no `TELE_TO_SPELL`, F15). Whether it
    returns true or false → **true** (fail closed). Only on true, call
    `go->AddUse()` for charge parity (D4).

**Return contract:** false means "stock path, unchanged". True means "handled;
no 28147 cast". The handler never returns true for another GO, so it cannot
hide other modules' hooks (F7).

## 3. Negative-case and acceptance matrix

"Stock" is the native path. "G" is the proposed handler with the flag on. All
rows are source predictions, **not test results**.

| ID | Case | Stock | G | Basis |
|---|---|---|---|---|
| N01 | Flag off, any era | 28147 cast | Identical (false at step 3) | OFF parity |
| N02 | Other GO entry or type (meeting stone, other portal) | Unchanged | Unchanged (false at step 2) | F7 |
| N03 | Entry 181146 but template spell ≠ 28147 | Casts that spell | Unchanged (false at step 2) | Guard |
| N04 | IP disabled (`IndividualProgression.Enable = 0`) | 28147 | Unchanged (helper false) | §4 |
| N05 | Post-TBC character | 28147 → inside if admitted | Unchanged | Requirement |
| N06 | Vanilla, portal owner | Refused at map 532 (predicted) | Teleport to 4436 outside | Requirement |
| N07 | Vanilla, member of the owner's group | As N06 | Outside | F6 |
| N08 | Vanilla, offline owner still in user's group | Native allows (GUID check only) | Outside (same rule) | F6 |
| N09 | Vanilla stranger, GO has an owner | Silently rejected | Rejected the same way (false → native) | F6 |
| N10 | Vanilla stranger, **ownerless** GO (manual spawn only, F5) | Native allows | Outside, mirroring stock (D2) | F5, F6 |
| N11 | Vanilla, mounted | No dismount (allowMounted 1) | No dismount | F9 |
| N12 | Row 4436 missing or wrong map | — | No teleport, message, no inside fallback | D3 |
| N13 | `TeleportTo` refuses (e.g. another module's `OnPlayerBeforeTeleport`) | — | No teleport, no inside fallback | D3 |
| N14 | Double click / already teleporting | Second cast | Ignored (step 7) | Guard |
| N15 | GM | GM bypasses admission → inside | Stock (D1) | F12 |
| N16 | `GO_FLAG_NOT_SELECTABLE` set | Rejected before hook | Same (hook never runs) | F8 |
| N17 | Bot clicks the portal via `CMSG_GAMEOBJ_USE` | Same path as a player | Same per-character era rule (D5) | F10, §5b |
| N17b | Bot told `teleport` near the portal (Playerbots `TeleportAction`) | Bot casts 28147 **directly** (no GO use, no `partyOnly`) | **Not covered: stock** (known limit) | §5b |
| N17c | Random bot in a Vanilla leader's group | IP forces the leader's stage onto the bot | Treated as Vanilla, outside with the leader | §5b |
| N17d | Altbot whose own stage differs from the master's (only if `EnforceGroupRules = 0`) | Per character | Each character follows its own era | §5b |
| N18 | Charges | 0 = unlimited | `AddUse` only on success; no new limit | D4 |
| N19 | Cooldown | None for type 22 | No new cooldown | F9 |
| N20 | Portal summoned outside Deadwind (another map) | Far teleport attempt | Far teleport to map 0 | F16 |
| N21 | Owner's live rows differ from baseline | Unknown | Read at runtime; N12 if invalid | F13 |

**Acceptance (future, owner-approved only):** separate "portal appeared"
from "arrived outside"; test a Vanilla non-GM character as owner, as group
member and as stranger; one post-TBC character to show the stock path;
flag off once. Record position and facing on arrival.

## 4. Era rule and the shared helper

- `IsVanillaProgression(Player*)` in `MeetingStoneProgression.cpp` (`main`
  L52; #105/#120 L65) already handles: IP disabled → not Vanilla; the
  current (8) vs legacy (7) TBC boundary through the IP header; and, without
  the header, `IndividualProgression.Enable` / `ProgressionLimit` plus quests
  66008–66018.
- It sits in an anonymous namespace, so it cannot be reused as is. Moving it
  would change a file that #105 and #120 also change.
- **Proposal:** S2 adds a new header (for example
  `src/Systems/IndividualProgressionEra.h`) with the same logic, used only by
  the F13 handler. A source test asserts the two bodies stay equivalent.
  Moving Meeting Stones onto the header is a later, separate change after
  #105/#120 settle. No other developer's branch is touched.
- The helper does not exempt GMs or bot accounts. IP's own teleport gate
  exempts both (`IndividualProgressionPlayer.cpp` L178). See D1 and D5.

## 5. Decisions (CS03 recommendation, for CS01 sign-off)

| ID | Recommendation | Why (source) | Stricter or looser than stock? |
|---|---|---|---|
| D1 GM | **Stock path for GMs** (return false at step 5) | Both era gates already exempt GMs: IP's teleport hook (`IndividualProgressionPlayer.cpp` L178) and core admission (`MapMgr.cpp` L160). A GM using the portal today goes inside; keeping that keeps GM debugging honest. Acceptance must therefore use a non-GM character (N15). | Same as stock |
| D2 Ownerless | **Mirror stock: allow** | F4/F5: a spell-made Atiesh portal always has an owner, so the native `partyOnly` rule applies to every real portal. Ownerless 181146 exists only after a manual spawn, which is already a GM/debug situation. Requiring an owner would add a rule stock does not have, for a case players cannot create. | Same as stock |
| D3 Fail closed | **Block the inside cast** when row 4436 is missing/invalid or `TeleportTo` refuses | For a Vanilla character, the only alternatives are the native inside cast (refused by admission at level 60, or *inside* if admission passes, which is the bug F13 exists to stop). Blocking plus a system message never sends anyone inside early and never claims a landing. | Stricter, only for eligible Vanilla users with the flag on |
| D4 Charges | **`AddUse()` only after `TeleportTo` returns true** | Native calls `AddUse()` after `CastSpell == SPELL_CAST_OK` (`GameObject.cpp` L2114–2117). At baseline `charges = 0`, so this is a no-op; it only matters if the owner's live row has charges, where it keeps the same count. Never on a refused request. | Same as stock in effect |
| D5 Bots | **Per-character era, same helper as players** (no bot exemption) | §5b: random-bot accounts get the group leader's progression written onto them when they join (`OnPlayerCanGroupAccept`, `IndividualProgressionPlayer.cpp` L595–655; `SyncBotsProgressionToLeader`, `IndividualProgression.cpp` L431–456 via `OnAddMember` L980–989), so they follow the leader. Altbots are normal accounts and keep their own stage, exactly as IP gates them everywhere else. No leader lookup or Playerbots dependency is needed. The `teleport` chat command path cannot be covered by this hook (N17b). | Same as IP's per-character model |

## 5b. Bot paths (Playerbots `e88cc409`, IP `dd96f2b`)

- **Who is a "bot account" to IP:** account names matching
  `IndividualProgression.BotAccountsRegex` (default `^RNDBOT.*`,
  `IndividualProgression.cpp` L363–381). Altbots on the owner's own account
  are normal accounts.
- **Random bots follow the leader:** on joining a group IP rewrites their
  hidden progression quests to the leader's stage (L595–655 and L431–456).
  With `EnforceGroupRules = 1` it also refuses a bot whose level does not
  match the leader's era. Default is 0 (`individualProgression.conf.dist`
  L23–30).
- **Altbots keep their own stage.** With `EnforceGroupRules = 0` a group can
  mix eras (N17d); with 1, IP refuses mismatched normal-account members
  (L651–653).
- **How bots use portals:** Playerbots' `teleport` chat command
  (`src/Ai/Base/Actions/TeleportAction.cpp` L68–95) finds a nearby type-22
  or goober GO whose spell teleports and **casts that spell itself**
  (`new Spell(bot, ...)`, `prepare`, then `cast(true)`). It never calls
  `GameObject::Use`, so no GO hook sees it, and `partyOnly` does not apply.
  An older version that sent `CMSG_GAMEOBJ_USE` (and listed 181146) is
  commented out (L17–65).
- **Why not move to a spell hook:** `AllSpellScript::CanPrepare` can cancel
  28147 in `Spell::prepare` (`Spell.cpp` L3571–3575), but `TeleportAction`
  calls `cast(true)` without checking the result, and `Spell::_cast`
  (L3916+) has no finished-state guard. The cancelled spell could still run,
  so a spell-level seam would not reliably stop the bot path and adds
  lifetime risk. Option G stays on the GO hook.
- **Effect of the known limit (N17b):** the bot's own 28147 cast goes to
  stock admission for map 532 (level 68 + raid group). A level-60 bot is
  refused and stays put; only a level-68+ bot in a raid group could enter.
  Normal follow-the-master movement is unaffected by this design.

## 6. Acceptance premises

| Premise | Status | Evidence | Blocks S2 code? |
|---|---|---|---|
| Global hook exists and is DB-free | Verified | F7; linked precedent `MeetingStoneProgression.cpp` | No |
| 181146 is type 22 → 28147, partyOnly 1, allowMounted 1, charges 0 | Verified (baseline) | F1 | No; handler reads live template |
| 28148 summons 181146 with an owner | Verified (Vanilla data) | F4, F5 | No (handler keys on the GO, not the spell) |
| 28147 targets inside map 532 | Verified (baseline) | F2 | No |
| Row 4436 is the outside main-gate exit | Verified (baseline) | F13, F14 | No; runtime lookup, fail closed |
| Era helper semantics | Verified | §4 | No; shared header plan |
| Owner's live rows and `Instance.Ignore*` | UNKNOWN | — | No (runtime validation); needed for acceptance |
| In-game landing height/facing at 4436 | UNKNOWN | — | No; owner acceptance test |
| 3.3.5a `Spell.dbc` for 28148 | Premise | F4 | No |

## 7. Not verified

- The owner's loaded rows (181146, 28147, 4436, access template 29) and
  `Instance.IgnoreLevel` / `IgnoreRaid`.
- The 3.3.5a `Spell.dbc` entry for 28148 (Vanilla data read instead).
- Ground height, facing and line of sight at the 4436 point in game.
- Today's in-game behaviour for the owner's characters.

Rollback for any later S2: flag off (default) and restart.
