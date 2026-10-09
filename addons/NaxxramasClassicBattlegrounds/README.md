# Naxxramas Classic Battlegrounds (WoW 3.3.5a)

> **Archived copy:** This directory is retained only as a migration backup.
> The actively maintained addon is now **NClassicBattlegrounds**. The addon and installation instructions have moved to
> **[NClassicBattlegrounds](https://github.com/CosmicCuddle/NaxxramasClassicBattlegrounds)**.
> Do not update the Lua or TOC here; the renamed addon files are `NClassicBattlegrounds.lua` and `NClassicBattlegrounds.toc` in the standalone repository. This older directory is intentionally retained as a backup.


Optional client-only UI companion for the Naxxramas Core Classic Battlemaster
queue feature. **The server module is required to enforce queue restrictions.**

## Install

1. Back up any existing copy of the addon.
2. Copy this **whole** `NaxxramasClassicBattlegrounds` folder to
   `World of Warcraft/Interface/AddOns/`.
3. Make sure the folder contains the `.toc` and `.lua` files.
4. Enable the addon on the WoW character selection screen.
5. The **server-side** config should have
   `NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled = 1`
   and `...UnlockStage = 13`.
6. Log in and open Player vs. Player. Your PvP information remains visible.

Vanilla and TBC: the **Battlegrounds tab next to PvP** is hidden. The PvP panel remains intact, with Honor, kills and Arena information unchanged. Visiting a Battlemaster still opens the NPC's normal Battleground queue window. At WotLK entry (modern Individual Progression stage 13, hidden quest `66013`), the Battlegrounds tab reappears automatically once completed-quest data has refreshed.

The WoW 3.3.5a completed quest API throttles queries; allow about 75 seconds
for the next refresh after an in-game progression change.

## Commands

```text
/ncbg status
/ncbg refresh
/ncbg off
/ncbg on
```

`off` changes UI presentation **only**. It does not turn off the server's
Battlemaster queue restriction. Use `off` or uninstall this addon when the
server feature is disabled.

## Compatibility and scope

- WoW 3.3.5a, TOC Interface `30300`.
- Modern Individual Progression, stage 13 / rewarded hidden quests
  `66013` through `66018`.
- Preserves the original PvP Honor window, Arena information, queue status, and NPC Battlemaster dialog. Hides only the normal **Battlegrounds tab** while Vanilla/TBC progression is active.
- Does not replace `JoinBattlefield`, so disabling/modifying the addon
  cannot bypass the server.
- Does not remove any Blizzard FrameXML, edit DBCs, or ship an MPQ.
- **Awaiting in-game UI tests.**

Full deployment/test/rollback guide:
[Classic Battlemaster Queues](../../docs/CLASSIC-BATTLEMASTER-QUEUES.md).

## Expansion-specific PvP interface (addon update)

In **Vanilla** (Individual Progression below stage 8), the addon hides the
**Arena** points header, 2v2/3v3/5v5 panels, team toggle/overlay and details.
Honor, kills and the main PvP window stay visible. **TBC entry (stage 8)**
restores the Arena section.

The **Wintergrasp** timer/icon is hidden in Vanilla and TBC, including
Battlemaster dialogs, and restored on **WotLK entry (stage 13)**.

The existing **Battlegrounds tab** remains hidden in the normal PvP frame
until WotLK stage 13; a Battlemaster's NPC queue interface is unchanged.
No text overlays are added, and the Blizzard Join Battle buttons are not
modified.

The same `/ncbg off` command restores the unmodified client appearance
for all three optional visual restrictions. No server compilation is needed
for the addon update; replace its `.lua` file and use `/reload`.

**Unverified in-game:** the new Arena and Wintergrasp UI changes require
client testing (including transition at stages 8 and 13).
