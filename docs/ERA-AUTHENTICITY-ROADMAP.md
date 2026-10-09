# Era-authenticity roadmap — decisions 2026-10-09

## Decisions

### Approved

- **Mount summoning cast time:** implement individual progression-dependent
  historical cast times, with safe configuration and full rollback. Vanilla and
  TBC mount summoning should take 3 seconds, and late WotLK should take
  1.5 seconds. The historic unlock is WoW patch 3.2.0, corresponding
  approximately to modern IP Trial of the Crusader stage **15**. Allow
  `UnlockStage = 13` to switch at WotLK entry if desired.
- **Vanilla Arena interface:** hide Arena points and Arena team frames before
  modern IP's TBC entry **stage 8**. Already committed to the
  `NaxxramasClassicBattlegrounds` UI addon, awaits client test.
- **Wintergrasp interface:** hide until modern IP WotLK entry **stage 13**.
  Already committed to the same addon, awaits client test.
- **Battleground remote tab and server-only Battlemaster queues:** existing
  implementation; client tab hide confirmed in-game, server not yet compiled.

### Explicitly rejected / do not develop

- Hearthstone cooldown changes.
- Same-account mail changes.
- Achievement window hiding, achievement notifications, game calendar,
  Equipment Manager UI, dungeon maps, quest objective map overlays,
  automatic quest tracking, Quest Log Show Map, original quest text
  scrolling, talent preview interface changes.

Do not resurrect these suggestions without a new explicit request.

## Mount-cast technical design / blocker

The user requested implementation but does **not** want the server recompiled
until the current brainstorming session is complete.

Modern AzerothCore's `Spell::prepare` calculates `m_casttime` through
`SpellInfo::CalcCastTime` and sends spell start/cast packets **before** its
ordinary `AllSpellScript::OnSpellPrepare` hook. The existing
`PlayerScript::OnPlayerSpellCast` is also too late. At time of inspection there
is no exposed public `OnCalcCastTime` module hook.

**Do not** attempt to change cast time in OnPlayerSpellCast/OnSpellPrepare:
that will not produce a correct authoritative per-caster summon time.
**Do not** change every mount's Spell.dbc cast time globally: mixed Vanilla,
TBC and WotLK players must experience different times simultaneously.
**Do not** apply general spell-haste auras to simulate mount casting: they
would affect unrelated spells and Playerbots.

Safe next step: investigate whether user's exact pinned AzerothCore branch has
a suitable early cast-time hook. If absent, evaluate a **tiny optional upstream
hook** at the actual cast-time calculation (with user approval, a clean
patch, and a reversible core diff). Or a strictly proven mount-specific spell
modifier that works per player. Preserve original `Spell.dbc` backups.
Then implement in `mod-naxxramas-core` with:

```ini
NaxxramasCore.EraMountCast.Enabled = 0
NaxxramasCore.EraMountCast.ClassicCastTimeMs = 3000
NaxxramasCore.EraMountCast.ModernCastTimeMs = 1500
NaxxramasCore.EraMountCast.UnlockStage = 15
NaxxramasCore.EraMountCast.ExemptPlayerbots = 1
```

These are **PROPOSED** config keys, not implemented. Test ground/flying
mounts, shapeshift/instant mounts, cast interruptions, talent/spell-haste,
and Playerbots. Keep old build/config for rollback.

## BRD-to-Molten Core raid entry — design investigation

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

**No BRD/MC gameplay change has been coded, deployed or approved yet.**
Next question: is the 40-person *shared journey physically inside BRD* an
absolute requirement, or is every raid member *entering MC through a
BRD-related first-entry passage* sufficient?

## Project rules

- No server build/restart until brainstorming ends.
- Back up source, active config, DBCs and databases before destructive steps.
- Each module feature is off by default until compiled and tested.
- No duplicate features that Individual Progression already implements.
- Avoid upstream source changes when possible and preserve Playerbots.
- No casual alteration of rewards, loot tables, achievements or IP progress.
