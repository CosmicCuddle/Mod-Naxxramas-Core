# Classic Battlemaster Queues (optional)

## What this restores

In Vanilla and TBC progression, queue for a Battleground by visiting a real,
nearby Battlemaster. Remote Battleground queues become available upon reaching
modern Individual Progression **stage 13** (WotLK entry). A global 3.3.5a client
continues to display the PvP tabs, Honor, kills and Battleground information.

- Server enforcement: `src/Systems/BattlemasterQueueProgression.cpp`.
- Optional UI helper (separate repository): [NClassicBattlegrounds](https://github.com/CosmicCuddle/N-ClassicBattlegrounds).
- Historical addon backup: `addons/NaxxramasClassicBattlegrounds/` (not actively maintained).
- Source changes require AzerothCore rebuild. The addon alone is cosmetic.
- No DBC, SQL, or upstream IP/Playerbots/AzerothCore edits.
- Does not change arena queueing or core PvP/honor calculations.
- **Unreleased / untested**: build and live validation required.

## Configuration

In the **active installed** `mod_naxxramas_core.conf` (not only `.dist`):

```ini
NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled = 0
NaxxramasCore.BattlegroundQueue.ClassicMode.UnlockStage = 13
NaxxramasCore.BattlegroundQueue.ClassicMode.ExemptGMs = 1
NaxxramasCore.BattlegroundQueue.ClassicMode.ExemptPlayerbots = 1
```

Safe default: 0. After taking backups, compiling and being ready to test,
change `Enabled` to 1 and restart the server.

Modern IP uses rewarded hidden quest `66013` (and later `66014..66018`)
as the WotLK entry stage. The C++ restriction respects
`IndividualProgression.Enable` and `IndividualProgression.ProgressionLimit`.
It uses `IndividualProgression.BotAccountsRegex` (default `^RNDBOT.*`) to
exempt Playerbots if configured. Group queue restrictions are checked for
each online member as well as the group leader.

**Compatibility:** This version targets **modern** ZhengPeiRu21
Individual Progression hidden-quest progression. Legacy builds using only
player-settings progression need integration before enabling this setting.

## Optional addon installation (WotLK 3.3.5a)

**Current addon name: `NClassicBattlegrounds`.** The old `NaxxramasClassicBattlegrounds` folder in this repository is an archived backup and must not be installed alongside the renamed addon. The standalone repository now uses the shortened name `N-ClassicBattlegrounds` on GitHub.

Download the **current addon** from [NClassicBattlegrounds](https://github.com/CosmicCuddle/N-ClassicBattlegrounds) using **Code → Download ZIP**.

1. Back up and remove any installed `NaxxramasClassicBattlegrounds`, `N-ClassicBattlegrounds`, or `NClassicBattlegrounds` addon folders so old and new copies cannot both load.
2. Extract the GitHub ZIP. Open the outer `N-ClassicBattlegrounds-main` folder.
3. Copy **only the inner** `NClassicBattlegrounds` folder to `World of Warcraft/Interface/AddOns/`. This folder contains:
   - `NClassicBattlegrounds.toc`
   - `NClassicBattlegrounds.lua`

**Important:** Installing the outer `N-ClassicBattlegrounds-main` folder, or an addon folder named `N-ClassicBattlegrounds`, prevents WoW from locating its `.toc` file. The installed folder must be `NClassicBattlegrounds` (without the hyphen).

The previous `addons/NaxxramasClassicBattlegrounds/` directory in this repository is an **archived backup** only. Do not use it for updates.

The TOC uses `## Interface: 30300`.

The addon requests the completed quests using the built-in 3.3.5a
`QueryQuestsCompleted` and `GetQuestsCompleted` API. It hides `PVPParentFrameTab2` (the **Battlegrounds tab next to PvP**) in the standard PvP window until completed quests contain `66013..66018`. It does not hide or alter the actual Join Battle or Join as Group controls, nor draw overlay text on top of the interface.

When the panel opens through a Battlemaster, its queue controls remain unchanged. The Honor tab and statistics remain. The standalone addon also hides the Arena points/teams in Vanilla (restored at TBC stage 8), and Wintergrasp timer until WotLK stage 13.

The completed-quest query is throttled in 3.3.5a. The addon retries after
roughly 75 seconds. Progression changes may therefore take up to one retry
period to appear in the UI; reloading the UI can trigger a fresh request.

Commands:

- `/ncbg status`: show the addon’s last known progression and display state.
- `/ncbg refresh`: request a quest refresh, subject to the client’s throttle.
- `/ncbg off`: disable only this character’s visual button hiding.
- `/ncbg on`: enable button hiding again.

The addon cannot read the server's config. It can be used **independently for visual-only testing** before enabling the server feature. Turning the addon off does *not* bypass an enabled server-side restriction. When Individual Progression is disabled, disable the addon too if you want the original unmodified WotLK interface.

The addon does not hook or replace `JoinBattlefield`. A player using macros or
a modified client must still pass the C++ server-side check.

## What the server validates

- The joining player has reached configured modern-IP unlock stage; OR
- A real, nearby and interactable Battlemaster NPC GUID was passed.
- The NPC is the Battlemaster of the **requested Battleground type**.
- Group joining requires a Battlemaster if **any non-exempt online member**
  has not yet unlocked remote queueing.
- GM and Playerbot exemptions are individually configurable.

This specifically uses AzerothCore’s
`OnPlayerCanJoinInBattlegroundQueue` hook, before queue insertion.
Remote joins rejected by Naxxramas Core produce a chat explanation without
creating a queue slot.

## Test checklist (before enabling permanently)

1. Back up `mod-naxxramas-core`, installed live config, and saved full DBCs.
   Keep the old module commit SHA as a rollback point.
2. Pull from GitHub, rebuild/install AzerothCore as usual, restart worldserver.
   Confirm no compilation errors.
3. Set Enabled=1 and restart; do **not** change core files.
4. With a **Vanilla** character (below stage 8), open PvP normally:
   Honor and the PvP tab still display; the **Battlegrounds tab is hidden**.
5. Try remote queue *without* the addon or via a macro: server denies.
   Confirm no queue slot/status was created.
6. Visit the matching **Battlemaster**: queue succeeds in person.
   Test a mismatched Battlemaster and spoofed/faraway NPC GUID: both deny.
7. Repeat TBC (stages 8..12): same results as Vanilla.
8. Repeat **stage 13** WotLK and one later WotLK milestone:
   remote joins work and the **Battlegrounds tab returns**.
9. Queue a group with a stage-13 leader and stage-12 member:
   remote join is rejected, but in-person Battlemaster queue works.
10. Test both factions, solo and group queueing, a Playerbot account matching
    `IndividualProgression.BotAccountsRegex`, and a GM.
11. Change Enabled=0, restart, and confirm stock remote queueing works again,
    even for Vanilla characters. Disable the addon using `/ncbg off`.
12. Verify normal Arena matchmaking, Honor resets, and PvP ranking work as before.

## Rollback

Set `NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled = 0` in the active
config, restart and use `/ncbg off` (or remove the addon). No character
data migration, DBC, or SQL rollback should be needed. To remove the compiled
script entirely, revert its loader registration and source with Git, rebuild,
and restart.

## Known limitations

- A client-only addon cannot enforce queue restrictions. The server does.
- Progression in the addon is read from the current character’s completed
  hidden quests; it cannot directly read IP’s `ProgressionLimit` or server
  enable flag. If you change those while testing, disable the addon or
  re-check its UI against the server.
- IP’s later milestones are all considered unlocked; a manually changed or
  legacy quest schema requires new compatibility work.
- Code was reviewed against current AzerothCore interface declarations and
  Blizzard’s 3.3.5a FrameXML, **not compiled or tested in game yet**.

## Additional optional PvP visuals

The same addon also hides **Arena points and Arena team panels** only during
Vanilla progression (below stage 8), then restores them on entry into TBC.
It hides **Wintergrasp** information below stage 13, even in the
Battlemaster NPC's separate Battleground window. The Honor panel is kept.
These UI changes never enforce server gameplay rules and are reversible
via `/ncbg off`. They have **not** been tested in-game yet.
