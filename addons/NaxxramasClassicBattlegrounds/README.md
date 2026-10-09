# Naxxramas Classic Battlegrounds (WoW 3.3.5a)

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
