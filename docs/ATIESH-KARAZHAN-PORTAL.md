# Atiesh: Portal to Karazhan, Vanilla arrival (F13)

**Status:** review-only prototype. Default **OFF**. Not installed, not
tested in game. The design was reviewed as S1 in PR #123
(`docs/research/F13-ATIESH-OPTION-G-S1.md` on that branch).

## What it changes

With `NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled = 1`, a character
in the **Vanilla stage** of Individual Progression who uses the Atiesh
"Portal to Karazhan" (GO 181146) arrives just outside Karazhan's main gate
instead of inside the raid. The destination is the live
`areatrigger_teleport` row **4436** ("Karazhan, Main (Exit)"), read at
runtime; no coordinates are built in.

Stock behaviour is kept for: the switch off, GMs, IP disabled, any
character past the Vanilla stage, every other game object, and a 181146
template whose spell is not 28147.

## How

- `src/Systems/AtieshKarazhanPortal.cpp` — an `AllGameObjectScript`
  `CanGameObjectGossipHello` hook (global, no `ScriptName` or SQL binding;
  same pattern as `MeetingStoneProgression.cpp`). It runs at the start of
  `GameObject::Use`, before the native cast of 28147.
- `src/Systems/AtieshPortalPolicy.h` — dependency-free decision, unit-tested
  natively.
- `src/Systems/IndividualProgressionEra.h` — the era rule, identical to
  Meeting Stones' `IsVanillaProgression` (a test keeps them identical).
  Meeting Stones themselves are not changed.

Rules:

- **Party rule (native parity):** if the portal has an owner, a non-owner
  must be in a group that contains the owner's GUID (the owner may be
  offline). Otherwise the hook returns false and the core refuses the click
  exactly as today. An ownerless portal is allowed, as stock allows it.
- **Fail closed:** if row 4436 is missing, not on map 0 or invalid, or the
  teleport is refused, the player gets a message and stays put. The inside
  cast never runs as a fallback.
- **Parity:** no new cooldown (type 22 has none), mount aura removed only if
  the template does not allow mounted use, `AddUse()` only after an
  accepted teleport. A pending teleport makes a second click do nothing.
- **Mount on a refused click:** the dismount happens only on the teleport
  path. A fail-closed or ignored click returns before native `Use` reaches
  its dismount (`GameObject.cpp` L1525), so the rider keeps the mount and
  nothing else happens either. This is deliberate. Stock 181146 has
  `allowMounted = 1` (Data3), where native would not dismount anyway. It
  only differs if the owner's template sets `allowMounted = 0` (**UNKNOWN**),
  and then a click that does nothing should not cost the mount.
- **Era is per character** (strictly personal, as IP gates everything else).
  Random bots take the group leader's stage when they join; Altbots keep
  their own, so a mixed-era group can split.

## Known limits

- **Playerbots `teleport` command:** it casts 28147 directly
  (`TeleportAction.cpp`), never `GameObject::Use`, so it bypasses this hook
  and gets stock admission. Playerbots' "use" action (`UseItemAction`,
  registered as `"use"`) does go through the hook: it sends
  `CMSG_GAMEOBJ_USE` to `HandleGameObjectUseOpcode`
  (`UseItemAction.cpp` L131–L133 at `d750b4b`), which reaches
  `GameObject::Use`.
- **Premises for activation (not checked here):** that the owner's 3.3.5a
  spell 28148 still summons 181146 with the caster as owner (Vanilla data
  says so); the owner's loaded rows 181146 and 4436; landing height and
  facing in game; the owner's IP and `Instance.Ignore*` settings.
- `TeleportTo` returning true means the teleport was accepted, not that the
  player arrived.

## Tests

- `tests/atiesh_portal_policy.cpp` — native C++17/C++20 `-Werror`: every
  decision case (OFF, GM, era, other objects, edited template, party rule
  with owner/member/offline owner/stranger/ownerless, pending teleport,
  missing/wrong-map/invalid row, mixed-era bots).
- `tests/test_atiesh_karazhan_portal.py` — source contract: default OFF,
  loader, entry filter first, only Stock returns false, `AddUse` after
  accepted teleport, mount parity, live-row teleport only, era helper
  identical to Meeting Stones, no DB or spell paths.
- `.github/workflows/atiesh-karazhan-portal.yml` — the above plus a pinned
  full Worldserver link and symbol check.

## Rollback

Leave `NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled = 0` (the
default) and restart.
