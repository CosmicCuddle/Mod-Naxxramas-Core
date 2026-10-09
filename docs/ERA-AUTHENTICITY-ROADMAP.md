# Era-authenticity roadmap — decisions 2026-10-09

## Decisions

### Approved

- **Mount summoning cast time (approved, WotLK entry):** Vanilla and TBC
  progression (stages **0–12**) retain a **3-second** cast. Starting at the
  very beginning of WotLK progression (**stage 13**), mount summoning takes
  **1.5 seconds**. This is an intentional server preference, even though
  the historical retail reduction happened later in WotLK (patch 3.2.0).
  The change must be per character, configurable and completely reversible.
  Do not implement via a global DBC change or an unrelated spell haste buff.
- **Vanilla Arena interface:** hide Arena points and Arena team frames before
  modern IP's TBC entry **stage 8**. Already committed to the
  `NaxxramasClassicBattlegrounds` UI addon, awaits client test.
- **Wintergrasp interface:** hide until modern IP WotLK entry **stage 13**.
  Already committed to the same addon, awaits client test.
- **Battleground remote tab and server-only Battlemaster queues:** existing
  implementation; client tab hide confirmed in-game, server not yet compiled.

### Not selected — leave existing systems untouched

The user does **not** want us to make any changes to these systems as part of
the current era-authenticity development. This is **not** a request to remove,
disable, roll back or uninstall any of their existing functionality.

- Hearthstone cooldowns.
- Same-account mail.
- Achievements window and achievement notifications.
- In-game Calendar.
- Equipment Manager.
- Dungeon maps.
- Quest objective map overlays, automatic quest tracking and Quest Log
  "Show Map" functionality.
- Original quest text scrolling.
- Talent preview conveniences.

Do not propose or implement changes to the above during this phase unless
the user explicitly revisits them.

## Mount-cast implementation — alternative research, feature not active

**Decision 9 October 2026:** Do **not** modify AzerothCore core files for this feature, even with the previously prepared optional hook. That patch is an unapproved archived experiment. Research a module-only solution using existing spell-modifier mechanisms; see [module-only assessment](ERA-MOUNT-CAST-MODULE-ONLY-RESEARCH.md). No safe module-only implementation has yet been validated. The currently staged script stays **disabled and inert** without the archived patch.

### Historical optional-hook implementation (NOT APPROVED)


**Implementation staged on 9 October 2026:** `src/Systems/EraMountCast.cpp`,
loader registration and five configuration entries are committed.
Vanilla/TBC = **3000 ms**, WotLK from IP stage **13** = **1500 ms**.
The feature is **disabled by default** and, on an unpatched AzerothCore build,
is a **no-op**. The modern-IP hidden quest thresholds and configurable bot
exemption were reviewed.

The existing AzerothCore spell callbacks are too late for an authoritative
pre-packet cast-time change. To avoid global Spell.dbc edits or affecting other
spells, a narrowly scoped, **optional** four-file upstream hook patch is
included at `patches/azerothcore-optional-after-calc-spell-cast-time.patch`.
Do not apply it blindly: first compare the actual server's pinned AzerothCore
revision and run `git apply --check` on a backed-up source tree.

**No server recompilation, actual AzerothCore patch application or in-game
regression test has occurred.** Do not claim this feature is active until the
patch is reviewed, applied, rebuilt, enabled and tested. The module is safe
to compile without the optional hook, but it will not change mount timers.

Complete compatibility review, commands, tests and rollback:
[Era Mount Cast guide](ERA-MOUNT-CAST.md).

## BRD-to-Molten Core raid entry — PAUSED / PARKED

The user wants to assemble **40 raid members** and enter the original Molten
Core portal **through Blackrock Depths**, while preventing a larger BRD group
from exploiting mob/quest/XP/loot farming. User is open to possibly **10–15**
players if full 40 isn't feasible.

Confirmed AzerothCore internals:
- BRD is an ordinary non-raid dungeon, map ID **230** (verify map settings
  on the user's installed build).
- `InstanceMap::GetMaxPlayers` returns the map/difficulty maximum from
  `MapDifficulty` or `MapEntry`.
- `InstanceMap::CannotEnter` checks the current player count against that
  maximum; a PlayerScript `OnPlayerCanEnterMap` hook **cannot increase the cap**
  because the capacity check runs subsequently.
- Therefore, lifting BRD's cap requires a new **capacity override at the
  instance map level** (or a separate purpose-built instance), not merely
  allowing entry via a PlayerScript.

Implementation approaches to discuss:

**A. Special raid-transit BRD instance (up to 40):**
  Separate, explicitly selected raid transit mode restricted to qualifying
  MC-bound 40-man groups. Permit players only through to the original MC
  entrance, prevent combat farming and all XP, loot, quests, gold and rewards,
  avoid regular instance save/lockout abuse, enforce MC/IP level/attunement
  checks, and auto-expire the mode after transit. Needs careful map cap and
  instance routing design and likely a **small core change**. Not safe to
  implement blindly.

**B. Conditional 10–15-cap raid-transit BRD:**
  Same anti-exploit requirements; lower stress but still cannot admit all
  40 simultaneously. A plain higher cap is **not safe**.

**C. Five-player advance party:**
  A normal 5-player team enters/clears BRD and unlocks a temporary, group-
  restricted passage for remaining MC raid members, still requiring their
  physical presence inside Blackrock Mountain. Less risky but not equivalent
  to all 40 traversing BRD; compatibility with server's custom first-entrance
  rule and attunement must be verified.

**Status: on hold at the user's request.** No BRD/MC gameplay change has
been coded or approved, and there should be **no further investigation,
implementation or follow-up questions** about BRD raid-group size until the
user asks to resume it. Keep the current original Molten Core first-entry
via BRD requirements unchanged.

## Project rules

- No server build/restart until brainstorming ends.
- Back up source, active config, DBCs and databases before destructive steps.
- Each module feature is off by default until compiled and tested.
- No duplicate features that Individual Progression already implements.
- Avoid upstream source changes when possible and preserve Playerbots.
- No casual alteration of rewards, loot tables, achievements or IP progress.
