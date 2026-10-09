# mod-naxxramas-core

Custom gameplay module for **AzerothCore WotLK 3.3.5a**, built for the Naxxramas Core project.

The module keeps server-specific gameplay changes in one place, including class changes, racial changes, event overrides, item fixes, PvP systems, mail behaviour, and Playerbot raid preparation.

Some features require matching **DBC edits** on both the server and client. Those changes are documented in [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md).

> **Back up your module directory, databases, configuration, and known-working DBC files before updating the module.** Git history makes module-code changes reversible, but database and DBC changes should still be backed up separately.

## Current patch line

**Naxxramas Core 1.0.6.8.4**

## Current features

### Warrior

#### Rend Flurry (`90054`)

- 1-point Arms talent, Talent ID `3000`.
- 15-second active buff.
- 60-second cooldown.
- Rend affects the primary target and up to **2 additional hostile targets** within **8 yards** of the primary target.
- Additional targets receive the same Rend rank as the original cast.
- Bleed-immune targets receive **Rend Flurry Strike** (`90055`) for **150% weapon damage** instead.
- The replacement strike uses one shared **2-second internal cooldown** via spell `90056`.
- Triggered extra Rends are free and do not recursively spread.

#### Improved Rend Rank 3 (`90057`)

- Extends the original Improved Rend talent to 3 ranks.
- Rank 3 increases Rend bleed damage by **22%**.
- Each valid Rend periodic damage tick has a **3% chance** to generate **25 Rage**.
- Spread Rends created by Rend Flurry can proc independently.

#### Improved Heroic Strike (`12282`)

- Reworked from a 3-point talent to **1 point**.
- Reduces Heroic Strike cost by **5 Rage**.

### Mage

#### Arcane Momentum (optional directional Blink)

- Mage trainers offer a free, reversible **Arcane Momentum** technique.
- The default Blink (spell `1953`) still teleports in the direction the Mage is facing.
- With Arcane Momentum enabled, Blink follows forward/backward/strafing movement instead; combined inputs support diagonals.
- Standing still uses normal facing-based Blink.
- The preference is stored per character in the characters database and survives logout/restart.
- Original Blink cooldown, root/stun effects and DBC values are unchanged.
- The new destination is checked using AzerothCore's map collision helper; test walls, ramps, stairs, water and elevation changes before enabling on a public server.
- Requires both SQL files `data/sql/db-characters/2026_10_08_00_arcane_momentum.sql` and `data/sql/db-world/2026_10_08_00_arcane_momentum.sql` as well as a rebuild/restart.
- No new DBC entry or client patch is required for this feature.

### Classic Battlemaster Battleground queues (optional, WotLK unlock)

**Standalone addon name:** `NClassicBattlegrounds` (`N Classic Battlegrounds` in game). Its GitHub repository is still under the original URL until renamed by the owner; `addons/NaxxramasClassicBattlegrounds/` is a historical backup only.


- Modern Individual Progression **stage 13** unlocks remote Battleground queueing.
- Vanilla and TBC characters must use an actual, nearby Battlemaster NPC (including remote queue macros).
- Preserves the PvP window, Honor and kills; no Arena queue or Honor system changes.
- The C++ `OnPlayerCanJoinInBattlegroundQueue` hook validates the Battlemaster's NPC flag, distance, faction interaction and matching BG type, and checks mixed-progression group members.
- Optional **3.3.5a standalone addon**, now maintained at [NClassicBattlegrounds](https://github.com/CosmicCuddle/NaxxramasClassicBattlegrounds), hides the **Battlegrounds tab next to PvP** in the normal interface. It requests modern-IP hidden completed quests `66013..66018` to restore the tab in WotLK; the Battlemaster's NPC queue window stays usable. No bottom-screen overlay text or Join Button modifications.
- Configured through `NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled = 0` (**disabled by default for testing**) and `...UnlockStage = 13`, with GM/Playerbot exemptions.
- **Compatibility:** modern hidden-quest Individual Progression builds only; other older IP data schemas need extra integration. No DBC/SQL/client MPQ modifications.
- Complete setup, tests and rollback: [Classic Battlemaster Queue Guide](docs/CLASSIC-BATTLEMASTER-QUEUES.md).
- **Source added; AzerothCore compilation, Playerbot regression tests and client in-game tests still pending.**

### Meeting stones — Classic progression

- Config: `NaxxramasCore.MeetingStones.ClassicMode.Enabled = 1` (**enabled by default**; set `0` for unmodified WotLK behaviour).
- When Individual Progression says the **interacting character is still in Vanilla**, a meeting stone (gameobject type 23) remains visible but cannot begin its native summoning interaction.
- Clicking an unavailable stone tells the player: **"Summoning stones are currently unavailable. They unlock when you reach The Burning Crusade in Individual Progression."** The native hover cursor/tooltip remains client-controlled.
- Once that same character reaches **TBC** or **WotLK** progression, the native AzerothCore meeting-stone rules, level checks and summoning mechanism run unchanged. A character's **level or current zone alone is not an expansion check**.
- The new hook runs before GameObject::Use's meeting-stone branch. No global GO flags, GameObject template edits or client patches are required.
- Uses Individual Progression's public API when its header is available. Supports both modern hidden-quest progression and older player-settings-based IP APIs. If the header is unavailable, it falls back to modern IP rewarded milestone quests **66008–66018** (PRE_TBC and later), while also honouring `IndividualProgression.Enable` and `IndividualProgression.ProgressionLimit` from config. **Old IP branches that do not export their header require extra integration; test before enabling.**
- Does not disable Warlock Ritual of Summoning or other non-meeting-stone objects. No database migration is needed.
- Build status: committed source; a new build and live testing are required before declaring it deployed.

**Testing:** Back up the active config/module; start with a Vanilla-tier character and click an existing meeting stone. It must remain in place but not start a summon. Repeat with a TBC-tier and WotLK-tier character at the same stone; normal AzerothCore meeting-stone behaviour must work (group, target and level requirements still apply). Toggle the config to `0`, reload or restart, and confirm the Vanilla character can again use it. Test characters whose *levels* differ from their IP tiers to ensure the stage check—not their level—controls it.

### Racials

#### Orc — Blood Fury

- Keeps the WotLK offensive Blood Fury bonuses.
- Restores the older **50% healing-received penalty** for **25 seconds**.
- Covers spell IDs `20572`, `33697`, and `33702`.

#### Troll — Berserking (`26297`)

- Keeps the WotLK **20% haste** baseline.
- Restores health-based scaling up to **30% haste** at 10% health or lower.
- The haste amount is snapshotted when Berserking is activated.

#### Blood Elf — Mana Tap / Arcane Torrent

- **Mana Tap** (`28734`) restored as a starting Blood Elf racial.
- **Arcane Torrent** keeps the WotLK 2-second silence while restoring the Mana Tap charge/resource interaction.
- Supports the Mana (`28730`) and Energy (`25046`) Arcane Torrent variants.

#### Forsaken — Touch of the Grave

- **Touch of the Grave** passive: `90052`.
- Health-leech proc: `90053`.
- Uses custom level scaling:
  - Level 1: 5
  - Level 20: 35
  - Level 40: 70
  - Level 60: 150
  - Level 70: 300
  - Level 80: 600
- Includes damage and healing compensation for the server's **Individual Progression** power adjustments.
- World SQL registers the custom spell script/proc behaviour.

#### Forsaken — DBC-based racial work

The project also contains Forsaken changes that depend on matching DBC data:

- **Will of the Forsaken** (`7744`) — custom 5-second Charm/Fear/Sleep immunity implementation with a 120-second cooldown in the current DBC work.
- **Shadow Resistance** (`20579`) — custom **+10 Shadow Resistance** passive.
- **Forsaken Swordsmanship** (`90051`) — +5 Swords and Two-Handed Swords skill.
- Touch of the Grave also requires its matching custom spell rows.

See [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md) before distributing a client patch.

### Events

#### Brewfest — Dark Iron Attack

- Replaces AzerothCore's Dark Iron attack generator with the Naxxramas Core version.
- Dark Iron mole-machine spawning is slowed from AzerothCore's **3-second** repeat to **12 seconds**.
- Other Dark Iron attack-generator behaviour is preserved.

#### Brewfest — sober accessibility option

- Adds a gossip option to **Goldark Snipehunter** and **Glodrak Huntsniper**.
- Allows the player to immediately remove Brewfest drunkenness/fake-inebriation effects.
- The normal Brewfest gossip options remain available.

#### Hallow's End — Shade of the Horseman

- Replaces the event NPC script with the Naxxramas Core version.
- Fire cycle changed from **15 seconds** to **30 seconds**.
- Completion/failure counter threshold changed from **greater than 21** to **greater than 14**.
- Other Shade of the Horseman behaviour is preserved.

### Items

#### Green Whelp Armor

- Restores the server's custom Sleep proc restriction.
- The Sleep proc is allowed when the triggering actor is **level 63 or below**.

### Server systems

#### Honor Overflow

When a player earns Honor after reaching AzerothCore's configured Honor cap:

- Excess Honor can be converted into gold.
- The conversion rate is configurable in `mod_naxxramas_core.conf`.
- Battleground conversion rewards are awarded immediately.
- Battleground spam is suppressed and replaced with one summary when the Battleground ends or the player leaves.
- Playerbot participation can be enabled or disabled separately.
- Gold-cap handling prevents invalid over-cap rewards.

Main settings:

```ini
NaxxramasCore.HonorOverflow.Enabled
NaxxramasCore.HonorOverflow.CopperPerHonor
NaxxramasCore.HonorOverflow.Notify
NaxxramasCore.HonorOverflow.IncludeBots
```

#### Fortnightly Honor Reset

- Automatically resets spendable Honor on a configurable schedule.
- Resets both **online and offline** characters.
- Stores the last completed reset in the characters database.
- Survives server restarts and catches up a missed scheduled reset.
- Reset interval, weekday, time, anchor date, and player notification are configurable.

Main settings:

```ini
NaxxramasCore.HonorReset.Enabled
NaxxramasCore.HonorReset.IntervalWeeks
NaxxramasCore.HonorReset.DayOfWeek
NaxxramasCore.HonorReset.Hour
NaxxramasCore.HonorReset.Minute
NaxxramasCore.HonorReset.AnchorDate
NaxxramasCore.HonorReset.Notify
```

The module includes the required characters-database SQL table under `data/sql/db-characters/`.

#### Forced PvP zones

- Forces normal faction PvP throughout:
  - **Silithus**
  - **Eastern Plaguelands**
- Remembers whether the player had manually enabled PvP before entering.
- Restores the player's original PvP preference after leaving.
- Prevents players from disabling PvP while still inside a forced zone.
- GMs are not forced into PvP.
- Playerbot inclusion and entry notifications are configurable.

Main settings:

```ini
NaxxramasCore.ForcedPvP.Enabled
NaxxramasCore.ForcedPvP.Silithus
NaxxramasCore.ForcedPvP.EasternPlaguelands
NaxxramasCore.ForcedPvP.IncludeBots
NaxxramasCore.ForcedPvP.Notify
```

#### Same-account alt mail delay

- Restores AzerothCore's configured `MailDeliveryDelay` for player mail sent between characters on the **same account**.
- Normal player-to-player mail rules remain unchanged.
- GM/customer-support mail, returned mail, COD payments, invalid mail, and self-mail are excluded.

### Playerbot manual talent expansion limits

`src/Systems/BotTalentExpansionLimits.cpp` makes manual Playerbot talent assignment obey the same **level-based talent row limits** as `AiPlayerbot.LimitTalentsExpansion = 1`, without changing Playerbots source files.

- **Level 1–60 (Vanilla):** first six rows, plus only the middle talent on row seven.
- **Level 61–70 (TBC):** first eight rows, plus only the middle talent on row nine.
- **Level 71–80 (WotLK):** unrestricted talent rows.
- Applies when a Playerbot learns talents through the built-in `talents spec <name>` and `talents apply <link>` commands, as well as other calls to `Player::LearnTalent`.
- Does not impose a per-tree **point total**: a level-60 Mage can still put 37 or more points into Frost if all selected talents are within the allowed rows.
- Only affects recognised Playerbots; normal players are unchanged.
- Uses Playerbots' **existing** `AiPlayerbot.LimitTalentsExpansion` configuration. If that setting is disabled, this module hook allows all talent rows.
- Keeps the original Playerbots selection order. Since a manual WotLK template may contain talents that are now rejected, **some points can remain unspent**; this safeguard does not invent a replacement build or redistribute points.

**Scope:** This initial compatibility fix deliberately mirrors Playerbots' current level-based setting. It does **not** yet substitute Individual Progression stages for levels; doing that correctly for both automatic and manual builds requires an additional integration. No SQL or DBC change is required. Rebuild and restart the server after updating the module.

#### Optional Playerbot talent completion

The existing talent-row guard prevents Playerbots from learning expansion-inappropriate talents, but a manually applied WotLK preset may finish with unused points. The optional `src/Systems/BotTalentCompletion.cpp` script addresses that specific issue **without resetting the bot again** or editing mod-playerbots.

- Enabled by `NaxxramasCore.BotTalentCompletion.Enabled = 1` in the **active server config**; default 0 as a safe opt-out.
- Requires `AiPlayerbot.LimitTalentsExpansion = 1`. Uses the original level-based expansion limits, not IP tier-based expansion detection.
- Runs only after a recognised Playerbot's **no-cost talent reset** and subsequent successful talent assignment. Waits 1.2 seconds after the last learned talent, and waits for combat to finish. Ordinary player characters and normal paid talent resets are not affected.
- Without explicit chat-plan context, matches against the **closest configured template to the bot's level**, using an 85% learned-rank overlap before following it. For explicit named/apply chat commands, the captured requested plan instead takes priority.
- Fills the intended primary tree and at most one secondary tree: an existing secondary from the current build, or one prescribed by the selected level-appropriate plan. It will leave points unused rather than unexpectedly start an unrelated third tree.
- Special Wrack safety: at level 60 an Affliction Warlock with Shadow Mastery 5/5, no existing Destruction ranks and no matched plan requiring Destruction prioritises **Demonology** filler once Affliction has at least 31 points, aiming towards 31/20/0. This preserves custom 31/20/0 builds. **It does not undo existing Affliction points**, so a premade that already spent 40 Affliction points can finish 40/11/0, not 31/20/0. To guarantee exact 31/20/0, select a suitable custom talent build.
- The remaining choices are deterministic and validated rank-by-rank by AzerothCore; they are not guaranteed to be mathematically optimal.
- Uses normal AzerothCore `Player::LearnTalent` rank/row/prerequisite checks; never grants unavailable talents, exceeds the allowed rows, or discards learned talent points.
- Respects the active spec slot, drops pending work on dual-spec switches and logout, and does not touch inactive-spec talents.
- If there are no legal remaining ranks, it **stops and leaves the points unused** rather than breaking prerequisites or creating an invalid build; a server warning gives the bot and remaining point count.
- Custom user-imported talent links can be processed after their ordinary no-cost reset; the closest premade template is used only if at least 85% of the currently learned talent ranks overlap it. Otherwise finishing choices are deterministic, not automatically optimal for an arbitrary custom build.
- No SQL or client DBC changes required. The module must be compiled and Worldserver restarted.
- **Authoritative chat-plan guard:** For named `talents spec <name>` whispers/party/raid requests, the module captures the bot's selected premade talent plan **before Playerbots executes the queued command**, using the highest configured template level **at or below** the bot's actual level. As Playerbots processes later templates (including level 80), talents outside the captured level-appropriate plan are rejected. The normal expansion row guard still applies independently.
- **Imported `talents apply <link>`:** Uses Playerbots' own Wowhead-link parser to capture the exact requested talent ranks. The initial assignment **and delayed completion** may only learn ranks in that plan. If the imported build is impossible at the current level/expansion, free points may intentionally remain; the module will not substitute unrelated talents.
- **Named premade completion:** When the initial template cannot fill all points due to expansion restrictions, the delayed completion may buy other valid ranks **only in the intended template's tree(s)**. It cannot invent a third tree or guarantee a mathematically optimal spec. For Wrack hybrids, explicitly importing a valid 31/20/0 link is the reliable way to request that exact distribution. The stock level-60 Affliction PvE template uses 51 Affliction points.
- **Concurrency protection:** Queues multiple captured chat intents in arrival order, tracks each bot's spec, uses a mutex to protect shared respec state, and clears it on spec-switch/logout; no state lock is held while AzerothCore purchases talents. Unconsumed intents expire.
- **Limitations:** The exact-plan guard is implemented for whispers and party/raid bot commands. Automated bot talent refreshes and alternate console/guild/channel command routes still use the original safe row restriction and existing completion logic, not explicit chat-plan enforcement. This is not an all-purpose talent-build optimizer.


**Validation status:** The earlier completion version was compiled and tested successfully with a level-60 Frost Mage (51 points spent). The new authoritative chat-plan guard has been source-reviewed but **has not yet been compiled or tested on the user's server**. Do not treat static checks as proof of runtime correctness.

### Playerbot instance consumables

The module contains an instance-scoped Playerbot consumables system for Classic-era raids and dungeons.

All consumable commands are available to normal players through:

```text
.bot consumables <profile>
```

Available profiles:

```text
.bot consumables 1-54
.bot consumables mara
.bot consumables sunken
.bot consumables brd
.bot consumables scholo
.bot consumables stratud
.bot consumables dm
.bot consumables lbrs
.bot consumables ubrs
.bot consumables mc
.bot consumables status
.bot consumables clear
```

#### Aura refresh thresholds

Re-running a consumables profile does not automatically reset every existing buff.

- Normal consumable auras are preserved while they have **more than 10 minutes remaining**.
- They are refreshed only when **10 minutes or less** remain.
- Buff-food / Well Fed effects use a shorter threshold: they are preserved while they have **more than 5 minutes remaining** and refreshed at **5 minutes or less**.
- Short tactical effects such as Juju Flurry and Juju Escape keep their special timed/tactical behaviour.
- Preserved auras remain in the active tracker so status/cleanup continue to work normally.
- The preparation summary reports how many existing aura effects were kept rather than unnecessarily refreshed.

#### Command cooldown

All preparation commands share a **10-minute cooldown** after a successful preparation.

This includes numbered dungeon profiles, named dungeon profiles, and raid profiles.

- `.bot consumables status` is never cooldown-limited.
- `.bot consumables clear` is never cooldown-limited.
- Failed/invalid preparation attempts do not start the cooldown.
- Logging out does not bypass an active cooldown.
- A real party/raid death or wipe resets the cooldown so the group can rebuff after recovering.
- Preparation cannot be run while the controlling player is dead; the player must resurrect first.
- `.bot consumables status` reports the remaining preparation cooldown while a profile is active.

#### Instance safety

Consumable profiles are instance-scoped.

- Raid/dungeon profiles can only be started while the controlling player is physically inside the correct instance.
- Named shared-map profiles also validate the correct wing/section.
- Tracked aura effects are cleared automatically when the controlling player leaves the allowed instance/wing.
- Controlled bots must also be physically inside the required instance/wing before they are prepared.
- If the controlling player is grouped/raiding, eligible alt/account bots and random Playerbots in that same group are prepared.
- Random Playerbots are never swept globally; they must be explicitly grouped/raided with the player.
- If the controlling player is not grouped, only eligible personally controlled alt/account bots inside the same valid instance scope are prepared.

#### Level-scaled dungeon profile — `.bot consumables 1-54`

A whole number from **1 through 54** can be supplied directly. For example:

```text
.bot consumables 14
.bot consumables 37
.bot consumables 52
.bot consumables 54
```

The system does not use fixed 10-level brackets. It calculates an individual effective level for each bot:

```text
minimum of:
- requested command level
- bot's actual level
- dungeon's LFG/target level cap
- 54
```

This means a level-34 bot never receives a level-40-only consumable because the player typed `.bot consumables 40`. Likewise, using `.bot consumables 54` in a low-level dungeon is reduced by that dungeon's target-level cap.

The generic profile supplies a deliberately modest package:

- one role/spec-appropriate elixir;
- one appropriate buff-food effect;
- one role-appropriate scroll;
- one Vanilla-sized stack of the best level-appropriate healing potion;
- one Vanilla-sized stack of the best level-appropriate mana potion for mana users.

The system keeps using the strongest already-unlocked option until a better one becomes legal; gaps between unlock levels do **not** mean the bot receives no buff.

Caster elixirs are spec-aware:

- Shadow Priest and Affliction/Demonology Warlock prefer **Elixir of Shadow Power** when level-appropriate.
- Frost Mage prefers **Elixir of Frost Power**.
- Fire Mage and Destruction Warlock prefer **Firepower / Greater Firepower**.
- Arcane Mage, Elemental Shaman, and Balance Druid use the general Arcane-elixir path.
- Healers use Intellect/Sages-style support instead of school-damage elixirs.

Scrolls are role-specific and are tracked for cleanup without generating false expiry warnings when a normal class buff replaces them.

#### Named dungeon profiles

Named profiles add a dungeon-specific protection effect on top of the normal class/spec package.

| Command | Allowed location | Specialist treatment |
|---|---|---|
| `.bot consumables mara` | Maraudon | Nature Protection / Greater Nature Protection |
| `.bot consumables sunken` | Sunken Temple | Nature Protection / Greater Nature Protection |
| `.bot consumables brd` | Blackrock Depths | Fire Protection / Greater Fire Protection |
| `.bot consumables scholo` | Scholomance | Shadow Protection / Greater Shadow Protection |
| `.bot consumables stratud` | Stratholme Undead/Service side | Shadow Protection / Greater Shadow Protection |
| `.bot consumables dm` | Dire Maul | Automatically detects East, West, or North |
| `.bot consumables lbrs` | Lower Blackrock Spire section | Standard endgame-dungeon package |
| `.bot consumables ubrs` | Upper Blackrock Spire section | Stronger package + Fire Protection |

Dire Maul automatically adapts by wing:

- **East** — Nature Protection.
- **West** — Shadow Protection.
- **North** — stronger physical/endgame inventory support without forcing an elemental protection potion.

UBRS and Dire Maul North use the enhanced dungeon package, which can additionally supply level-valid bandages, Limited Invulnerability Potions, caster/healer oils, or Rogue poisons as appropriate.

Dungeon profiles do **not** supply raid class reagents.

#### Molten Core — `.bot consumables mc`

The Molten Core profile can only be started on **Map 409 — Molten Core**, and only bots physically inside Molten Core are prepared.

It uses the larger raid package:

- class/spec-appropriate long-duration consumable effects;
- Greater Fire Protection;
- Vanilla-sized healing/mana potion stacks;
- Heavy Runecloth Bandages;
- Limited Invulnerability Potions;
- appropriate weapon stones, oils, and Rogue poisons;
- Cache of Mau'ari when Juju effects are required;
- Hunter pet Juju support when an active pet is present;
- raid-only class reagent top-ups.

Raid reagents are **top-up only**. The module never resets or reduces an existing amount. If a target is 20 and the bot already owns 19, exactly 1 is added.

Current Vanilla-style raid reagent targets include:

| Class | Raid reagent target |
|---|---|
| Druid | Ironwood Seed ×20; Wild Thornroot ×20 |
| Mage | Rune of Teleportation ×10; Rune of Portals ×10; Arcane Powder ×20; Light Feather ×20 |
| Paladin | Symbol of Kings ×100; Symbol of Divinity ×5 |
| Priest | Sacred Candle ×20; Light Feather ×20 |
| Rogue | Flash Powder ×20; Blinding Powder ×20 |
| Shaman | Ankh ×5; elemental totems ensured; Shiny Fish Scales ×20; Fish Oil ×20 |
| Warlock | Soul Shard reserve ×5 |
| Warrior / Hunter | no class reagent top-up |

The raid reagent logic is used only by raid profiles.

#### Vanilla inventory stack targets

Although the server runs AzerothCore WotLK 3.3.5a, this system deliberately uses Classic/Vanilla-sized inventory targets for the consumables it supplies rather than blindly using later-expansion stack sizes.

For example:

- healing and mana potions — 5;
- Limited Invulnerability Potion — 5;
- Heavy Runecloth Bandage — 20;
- sharpening/weightstones — 20;
- Rogue poisons — 20;
- Brilliant weapon oils — one charged oil item.

Existing quantities are respected. The system only adds the missing difference.

#### Juju behaviour

- **Juju Power** — normal tracked raid aura.
- **Juju Might** — normal tracked raid aura.
- **Juju Escape** — one tactical application; its natural expiry does not generate a missing-buff warning.
- **Juju Flurry** — three total applications:
  - immediately when `.bot consumables mc` is run;
  - again after 60 seconds;
  - a third time after another 60 seconds;
  - then stops.

Juju Flurry's normal gaps do not create missing-buff warnings. `.bot consumables clear`, leaving Molten Core, or replacing the active profile cancels the timed sequence.

Supported Classic class/spec families include:

- Warrior — Protection and DPS; Arms uses the Warrior DPS profile.
- Paladin — dungeon profiles support Holy, Protection, and Retribution; Molten Core currently supports Holy and Retribution.
- Hunter.
- Rogue.
- Priest — healing and Shadow.
- Shaman — Restoration, Elemental, and Enhancement.
- Mage — Arcane, Fire, and Frost handling.
- Warlock — Affliction/Demonology Shadow handling and Destruction Fire handling.
- Druid — Restoration, Balance, Feral tank, and Feral DPS.

Current Molten Core exclusions:

- **Protection Paladin** — no automatic Classic Molten Core profile yet.
- **Death Knight** — no Classic profile because the class did not exist in Vanilla.

#### `.bot consumables status`

Shows the active profile, tracked aura count, missing warning-enabled auras, and active timed consumable sequences.

#### `.bot consumables clear`

Removes effects tracked by this system and cancels timed sequences.

## Dependencies and integrations

### AzerothCore

Designed for **AzerothCore WotLK 3.3.5a**.

### Playerbots

`src/Systems/BotRaidConsumables.cpp` uses Playerbot APIs directly. The current module build therefore expects the server's Playerbots module/code to be available when this system is compiled.

Honor Overflow and Forced PvP also contain Playerbot-aware behaviour.

### Individual Progression

Touch of the Grave reads the Individual Progression configuration when calculating its damage/healing compensation. This prevents the custom racial from being unintentionally double-scaled by progression power adjustments.

### DBC files

Current class/racial work can require matching edits to:

- `Spell.dbc`
- `Talent.dbc`
- `SkillLineAbility.dbc`

Raw DBC files are intentionally excluded from this repository by `.gitignore`. Keep binary client data in the server/client patch distribution and document required rows in [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md).

## Installation / updating

1. **Back up first.**
   - Existing `mod-naxxramas-core` directory.
   - World and characters databases.
   - Current module configuration.
   - Known-working server/client DBC files.

2. Place or update this repository in the AzerothCore modules directory:

   ```text
   /root/azerothcore-wotlk/modules/mod-naxxramas-core/
   ```

3. Review [`docs/DBC-CHANGES.md`](docs/DBC-CHANGES.md) and apply any required DBC edits.

4. Ensure edited DBC files are present in both:
   - the server data files;
   - the client patch.

5. Review `conf/mod_naxxramas_core.conf.dist` and keep your installed module configuration in sync with any new settings.

6. Re-run CMake when required by the build setup, then compile AzerothCore normally.

7. Start `worldserver`.
   - SQL under `data/sql/db-world/` is for the world database.
   - SQL under `data/sql/db-characters/` is for the characters database.

8. Check the worldserver startup log for module/SQL errors before allowing players back onto the server.

## Module layout

```text
mod-naxxramas-core/
├── conf/
│   └── mod_naxxramas_core.conf.dist
├── data/
│   └── sql/
│       ├── db-characters/
│       │   └── 2026_09_24_00_honor_reset.sql
│       └── db-world/
│           ├── class/racial spell bindings
│           ├── event overrides
│           ├── Touch of the Grave
│           ├── Green Whelp Armor
│           └── Brewfest sober gossip
├── docs/
│   ├── DBC-CHANGES.md
│   └── TROUBLESHOOTING.md
├── src/
│   ├── Class/
│   │   └── Warrior/
│   │       ├── WarriorImprovedRend.cpp
│   │       └── WarriorRendFlurry.cpp
│   ├── Events/
│   │   ├── BrewfestDarkIronAttack.cpp
│   │   ├── BrewfestSober.cpp
│   │   └── HallowsEndShadeOfTheHorseman.cpp
│   ├── Items/
│   │   └── GreenWhelpArmor.cpp
│   ├── Racials/
│   │   ├── BloodElf/
│   │   │   └── BloodElfArcaneTorrent.cpp
│   │   ├── Forsaken/
│   │   │   └── TouchOfTheGrave.cpp
│   │   ├── Orc/
│   │   │   └── OrcBloodFury.cpp
│   │   └── Troll/
│   │       └── TrollBerserking.cpp
│   ├── Systems/
│   │   ├── AltMailDelay.cpp
│   │   ├── BotRaidConsumables.cpp
│   │   ├── ForcedPvP.cpp
│   │   ├── HonorOverflow.cpp
│   │   └── HonorReset.cpp
│   └── NaxxramasCore_loader.cpp
├── .gitignore
├── CHANGELOG.md
└── README.md
```

## Important talent migration note

Changing talent ranks can leave old characters or Playerbots with obsolete spell IDs in `character_talent`.

For the Improved Heroic Strike rework, the old ranks were:

```text
12282 - Rank 1
12663 - Rank 2
12664 - Rank 3
```

The new talent only uses `12282`. A character that still has `12663` or `12664` saved can fail during `_LoadTalents` because those spell IDs are no longer valid talent positions in the new `Talent.dbc`.

See [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) before deploying talent changes to an existing character database.

## Compatibility

- AzerothCore WotLK 3.3.5a
- Naxxramas Core patch line: **1.0.6.8.4**
- Current Playerbot consumables code expects Playerbots support.
- Touch of the Grave contains Individual Progression compensation.
- DBC-dependent features require matching server/client DBC data.

**Expanded addon visuals (unreleased; standalone addon NClassicBattlegrounds):** The same addon now hides Arena points
and team panels only before the modern-IP TBC-entry milestone (stage 8), and
hides Wintergrasp information until WotLK entry (stage 13). Honor remains
visible, and Battlemaster NPC queue controls are not changed. Use
`/ncbg off` to restore the default interface. Client validation pending.
