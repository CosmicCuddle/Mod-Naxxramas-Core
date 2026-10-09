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

Vanilla and TBC: the standard remote Battleground join buttons disappear.
Visiting a Battlemaster restores them in that NPC dialog. At WotLK entry
(modern Individual Progression stage 13, hidden quest `66013`), the remote
join buttons reappear automatically after the client receives completed quest
data.

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
- Leaves original PvP Honor window, Arena information, Battleground tab,
  queue status, and NPC Battlemaster dialog intact.
- Does not replace `JoinBattlefield`, so disabling/modifying the addon
  cannot bypass the server.
- Does not remove any Blizzard FrameXML, edit DBCs, or ship an MPQ.
- **Awaiting in-game UI tests.**

Full deployment/test/rollback guide:
[Classic Battlemaster Queues](../../docs/CLASSIC-BATTLEMASTER-QUEUES.md).
