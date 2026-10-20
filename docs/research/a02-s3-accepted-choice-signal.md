# A02 S3 — accepted hunter pet autocast choice

Research only. This branch does not turn the restore on. `AtomicModuleOnlyChoiceSourceExists()` stays false. There is no compile-only prototype of the two-phase candidate, because that candidate is **unsound**. Nothing here edits AzerothCore, Individual Progression, Playerbots, SQL, or DBC. The config default stays off. This is not an owner decision, and it is not CS01 acceptance.

| Label | Meaning |
| --- | --- |
| VERIFIED | Read at the pinned SHA named in the sentence, or shown by the adversarial model. |
| POTENTIAL ISSUE | The source can behave this way. It was not executed on a server. |
| UNKNOWN | Not determined from the pinned trees. |
| NOT TESTED | No worldserver, no client, no character database. |

Pins: core `a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7` and `8daffdabe9202c228e45d833c9a1d399597a15cd`, IP `4ff4b5fcc1480348f058c632573143e62d4e3a41`. The `src/server/game/Scripting` tree, including every `ScriptDefines` header, is byte-identical at the two core SHAs. `PetHandler.cpp`, `Pet.cpp`, `Pet.h`, `CharmInfo.cpp`, `WorldSession.cpp`, `World.cpp`, `Map.cpp`, `Opcodes.cpp`, `PlayerUpdates.cpp`, and `ServerScript.cpp` are byte-identical too. `PlayerStorage.cpp` is not: an aura-load guard inserted near line 5863 on `8daffda` shifts `Player::SaveToDB` by 7 lines. `Object.cpp` and `Unit.cpp` differ in combat and visibility code; the update-hook lines cited below still match. Hook lines were read on 2026-10-20. Worldserver link and in-game behaviour are **NOT TESTED**.

CS01 review 5585785794 audited ServerScript, PetScript, SessionScript, AllSpellScript, and UnitScript at `8daffda`. This pass re-read those five and surveyed every other public `ScriptDefines` family a module can register.

## Verdict

The two-phase candidate is **unsound**.

`CanPacketReceive` can record an attempted toggle (pet GUID, spell id, requested state). A later `OnPlayerUpdate` or `OnSessionUpdate` can see that the spell's live autocast state equals that request. That pair cannot deterministically separate an explicit OFF from a learn-default OFF.

The reason is not a race. After the handler has accepted `CMSG_PET_SPELL_AUTOCAST` with `AutocastEnabled == false` for a spell IP just learned, `Pet::ToggleAutocast(false)` does nothing when the id is absent from `m_autospells` (`Pet.cpp:2276-2286` at both SHAs) and `CharmInfo::SetSpellAutocast(false)` writes `ACT_DISABLED`, which `addSpell` already stored (`Pet.cpp:1810-1813`, `CharmInfo.cpp:297`). A packet the handler rejects leaves that same triple: `active == ACT_DISABLED`, id not in `m_autospells`, bar type `ACT_DISABLED`. `CanPacketReceive` runs before `opHandle->Call` (`WorldSession.cpp:461-464`). The handler result is not an argument of either observation hook. Any predicate of the attempt plus the public view returns the same answer for both cases.

A predicate that also requires the public view to change misses the real explicit OFF, because the accepted OFF did not change it. The model calls that pair `explicit_off_collision`. `two_phase_verdict()` is `unsound`. **VERIFIED** as that model. **POTENTIAL ISSUE** on a real server. **NOT TESTED** in game.

## Hook survey

No public hook fires after `HandlePetSpellAutocastOpcode` has accepted a toggle, and none fires from `Pet::ToggleAutocast`, `CharmInfo::SetSpellAutocast`, `Pet::_SaveSpells`, or `Pet::SavePetToDB`.

**VERIFIED** at both core SHAs, except the `PlayerStorage.cpp` lines, which are cited per SHA. The autocast handler is `PetHandler.cpp:955-1009`. It checks the pet, the spell, ownership, `HasSpell`, and `IsAutocastable` (`PetHandler.cpp:991`), then calls `ToggleAutocast` and `SetSpellAutocast` (`PetHandler.cpp:1003-1007`). That function contains no `sScriptMgr` call and no send. `ToggleAutocast` (`Pet.cpp:2247`), `_SaveSpells` (`Pet.cpp:1572`), `SavePetToDB` (`Pet.cpp:502`), and `SetSpellAutocast` (`CharmInfo.cpp:291`) contain no `sScriptMgr` call either. `Pet::SaveToDB` aborts (`Pet.h:167`). `OnCreatureSaveToDB` is `Creature::SaveToDB` (`Creature.cpp:1509`, declared `AllCreatureScript.h:57`). Hunter pet spells are not saved on that path.

`ModuleScript` (`ModuleScript.h:25`) has no virtual methods. A module cannot invent a core dispatcher by subclassing it. **VERIFIED** as that header.

### Families already audited, re-read here

| Family | Header | What it is, and why it is not an accept signal |
| --- | --- | --- |
| ServerScript | `ServerScript.h:38` | Eight virtual methods. `CanPacketReceive` is `ServerScript.h:75`, pre-handler. `OnPacketSent` is `ServerScript.h:85`, outgoing only. There is no `OnPacketReceived`. The boolean dispatcher returns false on the first script that rejects (`ScriptMgrMacros.h:76`, `ServerScript.cpp:62`), so a later script can drop a packet this module already saw. |
| PetScript | `PetScript.h:35` | The six methods are init, talent points, unlearn filters, talent reset, and `OnPetAddToWorld` (`PetScript.h:58`). `Pet.cpp` calls those only. None runs from the autocast handler. |
| SessionScript | `SessionScript.h:30` | The only method is `OnSessionUpdate` (`SessionScript.h:43`), called at `WorldSession.cpp:598` after the packet loop, and only when `ProcessUnsafe()` is true. That is the world-thread session update. It receives `(session, diff)`, not the opcode result. |
| AllSpellScript | `AllSpellScript.h:47` | `OnSpellCast` is `AllSpellScript.h:106`. `ToggleAutocast` does not cast and does not call `sScriptMgr`. An OFF toggle produces no spell cast. |
| UnitScript | `UnitScript.h:54` | `OnUnitUpdate` is `UnitScript.h:104`, called at `Unit.cpp:512` before `WorldObject::Update` (`Unit.cpp:517`). That is a tick, not an accept event. |

### Remaining families

Every other `ScriptDefines` header was read. None of their dispatchers is called from the accept path or from the pet spell save. The appendix lists every virtual method with file and line. Both core SHAs share those lines.

Observation hooks exist. They are not post-handler events:

| Hook | Declaration | Call |
| --- | --- | --- |
| `OnPlayerBeforeUpdate` | `PlayerScript.h:300` | `PlayerUpdates.cpp:58` |
| `OnPlayerUpdate` | `PlayerScript.h:302` | `PlayerUpdates.cpp:314` |
| `OnPlayerAfterUpdate` | `PlayerScript.h:301` | `PlayerUpdates.cpp:431` |
| `OnPlayerSave` | `PlayerScript.h:377` | old core `PlayerStorage.cpp:7263`, new core `PlayerStorage.cpp:7270` |
| `OnSessionUpdate` | `SessionScript.h:43` | `WorldSession.cpp:598` |
| `OnUnitUpdate` | `UnitScript.h:104` | `Unit.cpp:512` |
| `OnWorldObjectUpdate` | `WorldObjectScript.h:76` | `Object.cpp:1085`, after `m_Events.Update` at `Object.cpp:1076` |
| `OnCreatureUpdate` / `OnAllCreatureUpdate` | `AllCreatureScript.h:30` | `Creature.cpp:970`, after `Unit::Update` (`Creature.cpp:748`) |
| `OnCreatureSaveToDB` | `AllCreatureScript.h:57` | `Creature.cpp:1509`, world creature rows, not `pet_spell` |
| `OnMapUpdate` | `AllMapScript.h` | `Map.cpp` end of `Map::Update` |

`OnPlayerSave` runs before `pet->SavePetToDB` (old `PlayerStorage.cpp:7298`, new `PlayerStorage.cpp:7305`). The save hook does not receive the pet spell rows, and those rows still store learn-default OFF as `ACT_DISABLED`. A pet save hook, even if one existed on `_SaveSpells`, would see the same byte the collision already cannot tell apart.

`DatabaseScript` (`DatabaseScript.h:38`) is database load and module-database lifetime. `GlobalScript` (`GlobalScript.h:56`) is loot, instances, and spell-attribute load. `MiscScript` (`MiscScript.h:48`) is object construction, item flags, and instance save. `CommandScript` (`CommandScript.h:24`) and `AllCommandScript` (`AllCommandScript.h:33`) are chat commands. `WorldScript` (`WorldScript.h:43`) is config, startup, and `OnUpdate`. None of those is called from the pet autocast handler. Five headers declare a script class and no virtual method: `AllScriptsObjects.h`, `BattlegroundMapScript.h`, `DynamicObjectScript.h`, `ModuleScript.h`, and `WorldMapScript.h`. **VERIFIED** by the absence of `sScriptMgr` in that handler and by the hook list. **NOT TESTED** as a running script registry.

### Individual Progression

**VERIFIED** at IP `4ff4b5f`. `IndividualProgressionSpells.cpp` contains no `sScriptMgr` call. `checkHunterPetSpells` (`IndividualProgression.h:430`) is the reconcile itself: `unlearnSpell(id, false, true)` then `learnSpell(keepId)` (`IndividualProgressionSpells.cpp:86-90`). `PendingPetSpellCheck` is file-local at `IndividualProgressionSpells.cpp:1252` and is not declared in `IndividualProgression.h`. The delayed check is a `BasicEvent` on `pet->m_Events`, not a public hook. This branch does not propose an IP edit.

### When the observation hooks actually run

**VERIFIED** as this source order. **NOT TESTED** under `MapUpdater`.

`CMSG_PET_SPELL_AUTOCAST` is `PROCESS_INPLACE` (`Opcodes.cpp:886`). Both `MapSessionFilter` and `WorldSessionFilter` accept `PROCESS_INPLACE` (`WorldSession.cpp:71`, `WorldSession.cpp:93`). `World::Update` calls `UpdateSessions` (`World.cpp:1227`) before `sMapMgr->Update` (`World.cpp:1254`). A packet already queued is therefore handled on the world thread, and `OnSessionUpdate` runs in that same `WorldSession::Update`, still before map update.

A packet that arrives after that drain is handled later on the map thread, because the map filter also accepts `PROCESS_INPLACE`. `OnSessionUpdate` does not run for that call (`ProcessUnsafe()` is false). `OnPlayerUpdate` runs in `Map::Update` after that map session update (`Map.cpp:449-454` when `t_diff` is 0, otherwise `Map.cpp:489`) and before `UpdateNonPlayerObjects` (`Map.cpp:506`). Pet `m_Events`, including IP's delayed check, run from `Pet::Update` → `Creature::Update` → `Unit::Update` → `WorldObject::Update`, and `Pet::Update` returns before that chain while `m_loading` is set (`Pet.cpp:659`, `Pet.cpp:736`).

So both candidate hooks observe the pet before this tick's pet events. A rank swap in those events happens after the observation. One session update also stops after 150 packets (`WorldSession.cpp:412`); the rest wait for a later update. **POTENTIAL ISSUE** for any attempt kept until that later update.

`CMSG_PET_SET_ACTION` is a second writer. It is `PROCESS_THREADUNSAFE` (`Opcodes.cpp:503`) and calls `ToggleAutocast` (`PetHandler.cpp:801`, `PetHandler.cpp:819`) with no script hook. The two-phase candidate does not record it. Which opcode a 3.3.5 client sends for the spellbook autocast click is **UNKNOWN**.

## Adversarial model

`scripts/a02_s3_accepted_choice_signal.py` is the model. The negative tests call it. The candidate records every autocast packet at `CanPacketReceive` and later keeps the attempt when the live `active` byte equals the request, for the same pet GUID. It does not receive the handler result.

| Case | What the candidate sees | Model result |
| --- | --- | --- |
| Accepted OFF on a learn-default spell | Public triple unchanged. Equality matches OFF. | Confirmed. Handler was `accepted_noop`. |
| Rejected OFF (not autocastable, not owner, missing spell, or a later `CanPacketReceive` script returns false) | Same public triple. | Confirmed. Indistinguishable from the row above. |
| Delta variant (require the triple to change) | No change on either row. | Records neither. A real explicit OFF is missed. |
| No packet | No attempt. | Not confirmed. This does not separate the two rows that do have an attempt. |
| OFF to ON, handler accepts | `active` becomes `ACT_ENABLED`. | Confirmed. A rejected ON stays OFF and is not confirmed. This does not repair the OFF collision. |
| ON packet when the spell is already ON, or a rejected ON plus `CMSG_PET_SET_ACTION` setting ON in the same world-session loop | Final state is ON. | Equality confirms, including the rejected packet. |
| ON then OFF in one session update | Final state only. | The OFF attempt matches. The ON attempt does not. Final state is not a per-packet accept bit. |
| Rejected OFF for a spell the pet does not know yet, then IP learns that id as OFF after the observation | Same-tick session and player hooks do not see the id. The next session hook does, and the attempt is still pending. | Confirmed OFF for a packet the handler rejected. |
| Accepted OFF of the old rank, then IP replaces it | The old id is confirmed before pet events. After the swap the old id is gone and the new id is learn-default, with no attempt. | The confirmation does not follow the chain. |
| Packet handled on the map thread | Same-tick `OnSessionUpdate` does not see it. `OnPlayerUpdate` can. | `OnSessionUpdate` is not a same-tick observer for every `PROCESS_INPLACE` packet. |
| Pet swap or relog before the player hook | GUID no longer matches. | Guid-scoped attempt does not confirm. A player-scoped store confirms the new pet's learn-default OFF. The GUID check is required and still does not separate the OFF collision. |
| Dismiss | No pet. | Not confirmed. |

Cross-map state in this model stays on the pet GUID. A process-global map keyed only by spell id is the unguarded store above. Keeping the attempt pet-local does not create a bit the core does not store.

**VERIFIED** as these model results. **POTENTIAL ISSUE** if this candidate were implemented. **NOT TESTED** on a worldserver.

## Optional interface, for a later owner decision

No post-handler hook exists. The smallest core addition that would tell an accepted OFF from a learn-default OFF is a hook that runs only after the handler has passed its checks and has called both writes, on that same stack, with the requested bit still in hand:

```cpp
// Not in either pinned core. Not implemented. Not an owner decision.
virtual void OnPetSpellAutocastAccepted(Player* player, Unit* pet, uint32 spellId, bool autocastEnabled) { }
```

The call would sit in `HandlePetSpellAutocastOpcode` immediately after `SetSpellAutocast`, inside the loop, where `HasSpell`, `IsAutocastable`, and `charmInfo` have already succeeded. A rejected packet would not reach it. `autocastEnabled` would still be false when the resulting `ACT_DISABLED` matches the learn default. `pet` would be the unit just written, not a later `GetPet()`.

That sketch has these limits, which a future decision would still have to face:

- `CMSG_PET_SET_ACTION` writes autocast through the same `ToggleAutocast` pair and would not hit this hook.
- The hook means the handler accepted the request. `ToggleAutocast(false)` may still be a no-op.
- It does not run from `learnSpell`, so IP's learn-default stays silent. A later pet event can still replace the rank. The hook does not attach the choice to the chain.
- `PROCESS_INPLACE` runs on the world thread or the map thread, whichever dequeued the packet. A module would write only that pet's own state.
- `ModuleScript` cannot add the call. This is a core edit. It is out of scope for this module.

This branch does not add the hook, does not patch core, and does not enable the restore.

## What the tests pin

The Python suite is the adversarial model, the negative cases in the table, and a source contract. The contract refetches both core SHAs and the IP SHA. An added or moved virtual method, an `sScriptMgr` call inside the autocast handler, or a shifted citation fails closed. The module translation unit is unchanged: it still does not subscribe to `CanPacketReceive`, `OnPlayerUpdate`, or `OnSessionUpdate`.

**NOT TESTED:** worldserver link, client packet capture, summon, relog, rank change, and the character database.

## Appendix — virtual methods at both core SHAs

`ScriptDefines` is byte-identical at `a66f1be` and `8daffda`. Each line is `header:line method`.

### ALEScript.h

- `ALEScript.h:36 OnWeatherChange`
- `ALEScript.h:39 CanAreaTrigger`

### AccountScript.h

- `AccountScript.h:45 OnAccountLogin`
- `AccountScript.h:48 OnBeforeAccountDelete`
- `AccountScript.h:51 OnLastIpUpdate`
- `AccountScript.h:54 OnFailedAccountLogin`
- `AccountScript.h:57 OnEmailChange`
- `AccountScript.h:60 OnFailedEmailChange`
- `AccountScript.h:63 OnPasswordChange`
- `AccountScript.h:66 OnFailedPasswordChange`
- `AccountScript.h:69 CanAccountCreateCharacter`

### AchievementCriteriaScript.h

- `AchievementCriteriaScript.h:31 OnCheck`

### AchievementScript.h

- `AchievementScript.h:45 SetRealmCompleted`
- `AchievementScript.h:47 IsCompletedCriteria`
- `AchievementScript.h:49 IsRealmCompleted`
- `AchievementScript.h:51 OnBeforeCheckCriteria`
- `AchievementScript.h:53 CanCheckCriteria`

### AllBattlegroundScript.h

- `AllBattlegroundScript.h:70 OnBattlegroundStart`
- `AllBattlegroundScript.h:73 OnBattlegroundEndReward`
- `AllBattlegroundScript.h:76 OnBattlegroundUpdate`
- `AllBattlegroundScript.h:79 OnBattlegroundAddPlayer`
- `AllBattlegroundScript.h:82 OnBattlegroundBeforeAddPlayer`
- `AllBattlegroundScript.h:85 OnBattlegroundRemovePlayerAtLeave`
- `AllBattlegroundScript.h:87 OnQueueUpdate`
- `AllBattlegroundScript.h:89 OnQueueUpdateValidity`
- `AllBattlegroundScript.h:91 OnAddGroup`
- `AllBattlegroundScript.h:94 CanFillPlayersToBG`
- `AllBattlegroundScript.h:96 IsCheckNormalMatch`
- `AllBattlegroundScript.h:98 CanSendMessageBGQueue`
- `AllBattlegroundScript.h:110 OnBeforeSendJoinMessageArenaQueue`
- `AllBattlegroundScript.h:119 OnBeforeSendExitMessageArenaQueue`
- `AllBattlegroundScript.h:127 OnBattlegroundEnd`
- `AllBattlegroundScript.h:134 OnBattlegroundDestroy`
- `AllBattlegroundScript.h:141 OnBattlegroundCreate`
- `AllBattlegroundScript.h:148 OnBattlegroundSetup`
- `AllBattlegroundScript.h:163 CanAddGroupToMatchingPool`
- `AllBattlegroundScript.h:176 GetPlayerMatchmakingRating`

### AllCommandScript.h

- `AllCommandScript.h:41 OnHandleDevCommand`
- `AllCommandScript.h:49 OnTryExecuteCommand`
- `AllCommandScript.h:51 OnBeforeIsInvokerVisible`

### AllCreatureScript.h

- `AllCreatureScript.h:30 OnAllCreatureUpdate`
- `AllCreatureScript.h:33 OnBeforeCreatureSelectLevel`
- `AllCreatureScript.h:36 OnCreatureSelectLevel`
- `AllCreatureScript.h:43 OnCreatureAddWorld`
- `AllCreatureScript.h:50 OnCreatureRemoveWorld`
- `AllCreatureScript.h:57 OnCreatureSaveToDB`
- `AllCreatureScript.h:67 CanCreatureGossipHello`
- `AllCreatureScript.h:79 CanCreatureGossipSelect`
- `AllCreatureScript.h:92 CanCreatureGossipSelectCode`
- `AllCreatureScript.h:95 CanCreatureQuestAccept`
- `AllCreatureScript.h:98 CanCreatureQuestReward`
- `AllCreatureScript.h:101 GetCreatureAI`
- `AllCreatureScript.h:104 OnFfaPvpStateUpdate`

### AllGameObjectScript.h

- `AllGameObjectScript.h:34 OnGameObjectAddWorld`
- `AllGameObjectScript.h:40 OnGameObjectSaveToDB`
- `AllGameObjectScript.h:46 OnGameObjectRemoveWorld`
- `AllGameObjectScript.h:53 OnGameObjectUpdate`
- `AllGameObjectScript.h:56 CanGameObjectGossipHello`
- `AllGameObjectScript.h:59 CanGameObjectGossipSelect`
- `AllGameObjectScript.h:62 CanGameObjectGossipSelectCode`
- `AllGameObjectScript.h:65 CanGameObjectQuestAccept`
- `AllGameObjectScript.h:68 CanGameObjectQuestReward`
- `AllGameObjectScript.h:71 OnGameObjectDestroyed`
- `AllGameObjectScript.h:74 OnGameObjectDamaged`
- `AllGameObjectScript.h:77 OnGameObjectModifyHealth`
- `AllGameObjectScript.h:80 OnGameObjectLootStateChanged`
- `AllGameObjectScript.h:83 OnGameObjectStateChanged`
- `AllGameObjectScript.h:86 GetGameObjectAI`

### AllItemScript.h

- `AllItemScript.h:30 CanItemQuestAccept`
- `AllItemScript.h:33 CanItemUse`
- `AllItemScript.h:36 CanItemRemove`
- `AllItemScript.h:39 CanItemExpire`
- `AllItemScript.h:42 OnItemGossipSelect`
- `AllItemScript.h:45 OnItemGossipSelectCode`

### AllMapScript.h

- `AllMapScript.h:49 OnPlayerEnterAll`
- `AllMapScript.h:57 OnPlayerLeaveAll`
- `AllMapScript.h:68 OnBeforeCreateInstanceScript`
- `AllMapScript.h:76 OnDestroyInstance`
- `AllMapScript.h:83 OnCreateMap`
- `AllMapScript.h:90 OnDestroyMap`
- `AllMapScript.h:98 OnMapUpdate`
- `AllMapScript.h:107 CanSendObjectUpdatesToPlayer`

### AllSpellScript.h

- `AllSpellScript.h:56 OnCalcMaxDuration`
- `AllSpellScript.h:58 OnSpellCheckCast`
- `AllSpellScript.h:60 CanPrepare`
- `AllSpellScript.h:62 CanScalingEverything`
- `AllSpellScript.h:64 CanSelectSpecTalent`
- `AllSpellScript.h:66 OnScaleAuraUnitAdd`
- `AllSpellScript.h:68 OnRemoveAuraScaleTargets`
- `AllSpellScript.h:70 OnBeforeAuraRankForLevel`
- `AllSpellScript.h:72 OnIsAuraExclusiveBySpecificWith`
- `AllSpellScript.h:82 OnDummyEffect`
- `AllSpellScript.h:92 OnDummyEffect`
- `AllSpellScript.h:102 OnDummyEffect`
- `AllSpellScript.h:104 OnSpellCastCancel`
- `AllSpellScript.h:106 OnSpellCast`
- `AllSpellScript.h:108 OnSpellPrepare`

### AreaTriggerScript.h

- `AreaTriggerScript.h:32 OnTrigger`
- `AreaTriggerScript.h:43 _OnTrigger`

### ArenaScript.h

- `ArenaScript.h:50 CanAddMember`
- `ArenaScript.h:52 OnGetPoints`
- `ArenaScript.h:54 OnBeforeArenaCheckWinConditions`
- `ArenaScript.h:56 CanSaveToDB`
- `ArenaScript.h:58 OnArenaStart`
- `ArenaScript.h:60 OnBeforeArenaTeamMemberUpdate`
- `ArenaScript.h:62 CanSaveArenaStatsForMember`
- `ArenaScript.h:70 OnAddMember`

### ArenaTeamScript.h

- `ArenaTeamScript.h:43 OnGetSlotByType`
- `ArenaTeamScript.h:44 OnGetArenaPoints`
- `ArenaTeamScript.h:45 OnTypeIDToQueueID`
- `ArenaTeamScript.h:46 OnQueueIdToArenaType`
- `ArenaTeamScript.h:47 OnSetArenaMaxPlayersPerTeam`

### AuctionHouseScript.h

- `AuctionHouseScript.h:47 OnAuctionAdd`
- `AuctionHouseScript.h:50 OnAuctionRemove`
- `AuctionHouseScript.h:53 OnAuctionSuccessful`
- `AuctionHouseScript.h:56 OnAuctionExpire`
- `AuctionHouseScript.h:59 OnBeforeAuctionHouseMgrSendAuctionWonMail`
- `AuctionHouseScript.h:62 OnBeforeAuctionHouseMgrSendAuctionSalePendingMail`
- `AuctionHouseScript.h:65 OnBeforeAuctionHouseMgrSendAuctionSuccessfulMail`
- `AuctionHouseScript.h:68 OnBeforeAuctionHouseMgrSendAuctionExpiredMail`
- `AuctionHouseScript.h:71 OnBeforeAuctionHouseMgrSendAuctionOutbiddedMail`
- `AuctionHouseScript.h:74 OnBeforeAuctionHouseMgrSendAuctionCancelledToBidderMail`
- `AuctionHouseScript.h:77 OnBeforeAuctionHouseMgrUpdate`

### BattlefieldScript.h

- `BattlefieldScript.h:54 OnBattlefieldPlayerEnterZone`
- `BattlefieldScript.h:63 OnBattlefieldPlayerLeaveZone`
- `BattlefieldScript.h:71 OnBattlefieldPlayerJoinWar`
- `BattlefieldScript.h:79 OnBattlefieldPlayerLeaveWar`
- `BattlefieldScript.h:91 OnBattlefieldBeforeInvitePlayerToWar`
- `BattlefieldScript.h:102 OnBattlefieldWarEnd`
- `BattlefieldScript.h:113 OnBattlefieldPlayerKill`

### BattlegroundScript.h

- `BattlegroundScript.h:32 GetBattleground`

### CommandScript.h

- `CommandScript.h:31 GetCommands`

### ConditionScript.h

- `ConditionScript.h:32 OnConditionCheck`

### CreatureScript.h

- `CreatureScript.h:33 OnGossipHello`
- `CreatureScript.h:36 OnGossipSelect`
- `CreatureScript.h:39 OnGossipSelectCode`
- `CreatureScript.h:42 OnQuestAccept`
- `CreatureScript.h:45 OnQuestSelect`
- `CreatureScript.h:48 OnQuestComplete`
- `CreatureScript.h:51 OnQuestReward`
- `CreatureScript.h:54 GetDialogStatus`
- `CreatureScript.h:57 GetAI`
- `CreatureScript.h:60 OnFfaPvpStateUpdate`

### DatabaseScript.h

- `DatabaseScript.h:53 OnAfterDatabasesLoaded`
- `DatabaseScript.h:60 OnAfterDatabaseLoadCreatureTemplates`
- `DatabaseScript.h:69 OnModuleDatabasesLoading`
- `DatabaseScript.h:74 OnModuleDatabasesKeepAlive`
- `DatabaseScript.h:79 OnModuleDatabasesClosing`
- `DatabaseScript.h:86 OnDatabaseWarnAboutSyncQueries`
- `DatabaseScript.h:93 OnDatabaseGetDBRevision`

### FormulaScript.h

- `FormulaScript.h:47 OnHonorCalculation`
- `FormulaScript.h:50 OnGrayLevelCalculation`
- `FormulaScript.h:53 OnColorCodeCalculation`
- `FormulaScript.h:56 OnZeroDifferenceCalculation`
- `FormulaScript.h:59 OnBaseGainCalculation`
- `FormulaScript.h:62 OnGainCalculation`
- `FormulaScript.h:65 OnGroupRateCalculation`
- `FormulaScript.h:68 OnAfterArenaRatingCalculation`
- `FormulaScript.h:71 OnBeforeUpdatingPersonalRating`

### GameEventScript.h

- `GameEventScript.h:39 OnStart`
- `GameEventScript.h:42 OnStop`
- `GameEventScript.h:45 OnEventCheck`

### GameObjectScript.h

- `GameObjectScript.h:33 OnGossipHello`
- `GameObjectScript.h:36 OnGossipSelect`
- `GameObjectScript.h:39 OnGossipSelectCode`
- `GameObjectScript.h:42 OnQuestAccept`
- `GameObjectScript.h:45 OnQuestReward`
- `GameObjectScript.h:48 GetDialogStatus`
- `GameObjectScript.h:51 OnDestroyed`
- `GameObjectScript.h:54 OnDamaged`
- `GameObjectScript.h:57 OnModifyHealth`
- `GameObjectScript.h:60 OnLootStateChanged`
- `GameObjectScript.h:63 OnGameObjectStateChanged`
- `GameObjectScript.h:66 GetAI`

### GlobalScript.h

- `GlobalScript.h:63 OnItemDelFromDB`
- `GlobalScript.h:64 OnMirrorImageDisplayItem`
- `GlobalScript.h:67 OnAfterRefCount`
- `GlobalScript.h:68 OnAfterCalculateLootGroupAmount`
- `GlobalScript.h:69 OnBeforeDropAddItem`
- `GlobalScript.h:70 OnItemRoll`
- `GlobalScript.h:71 OnBeforeLootEqualChanced`
- `GlobalScript.h:72 OnInitializeLockedDungeons`
- `GlobalScript.h:73 OnAfterInitializeLockedDungeons`
- `GlobalScript.h:76 OnBeforeUpdateArenaPoints`
- `GlobalScript.h:80 OnArenaWeekReset`
- `GlobalScript.h:83 OnAfterUpdateEncounterState`
- `GlobalScript.h:86 OnBeforeWorldObjectSetPhaseMask`
- `GlobalScript.h:89 OnIsAffectedBySpellModCheck`
- `GlobalScript.h:92 OnSpellHealingBonusTakenNegativeModifiers`
- `GlobalScript.h:95 OnLoadSpellCustomAttr`
- `GlobalScript.h:98 OnAllowedForPlayerLootCheck`
- `GlobalScript.h:101 OnAllowedToLootContainerCheck`
- `GlobalScript.h:104 OnInstanceIdRemoved`
- `GlobalScript.h:107 OnBeforeSetBossState`
- `GlobalScript.h:110 AfterInstanceGameObjectCreate`
- `GlobalScript.h:114 CanCreateLfgProposal`

### GroupScript.h

- `GroupScript.h:48 OnAddMember`
- `GroupScript.h:51 OnInviteMember`
- `GroupScript.h:54 OnRemoveMember`
- `GroupScript.h:57 OnChangeLeader`
- `GroupScript.h:60 OnDisband`
- `GroupScript.h:62 CanGroupJoinBattlegroundQueue`
- `GroupScript.h:64 OnCreate`

### GuildScript.h

- `GuildScript.h:51 OnAddMember`
- `GuildScript.h:54 OnRemoveMember`
- `GuildScript.h:57 OnMOTDChanged`
- `GuildScript.h:60 OnInfoChanged`
- `GuildScript.h:63 OnCreate`
- `GuildScript.h:66 OnDisband`
- `GuildScript.h:69 OnMemberWitdrawMoney`
- `GuildScript.h:72 OnMemberDepositMoney`
- `GuildScript.h:75 OnItemMove`
- `GuildScript.h:77 OnEvent`
- `GuildScript.h:79 OnBankEvent`
- `GuildScript.h:81 CanGuildSendBankList`

### InstanceMapScript.h

- `InstanceMapScript.h:34 GetInstanceScript`

### ItemScript.h

- `ItemScript.h:32 OnQuestAccept`
- `ItemScript.h:35 OnUse`
- `ItemScript.h:38 OnRemove`
- `ItemScript.h:41 OnCastItemCombatSpell`
- `ItemScript.h:44 OnExpire`
- `ItemScript.h:47 OnGossipSelect`
- `ItemScript.h:50 OnGossipSelectCode`

### LootScript.h

- `LootScript.h:44 OnLootMoney`

### MailScript.h

- `MailScript.h:37 OnBeforeMailDraftSendMailTo`

### MiscScript.h

- `MiscScript.h:56 OnConstructObject`
- `MiscScript.h:58 OnDestructObject`
- `MiscScript.h:60 OnConstructPlayer`
- `MiscScript.h:62 OnDestructPlayer`
- `MiscScript.h:64 OnConstructGroup`
- `MiscScript.h:66 OnDestructGroup`
- `MiscScript.h:68 OnConstructInstanceSave`
- `MiscScript.h:70 OnDestructInstanceSave`
- `MiscScript.h:72 OnItemCreate`
- `MiscScript.h:74 CanApplySoulboundFlag`
- `MiscScript.h:76 CanItemApplyEquipSpell`
- `MiscScript.h:78 CanSendAuctionHello`
- `MiscScript.h:80 ValidateSpellAtCastSpell`
- `MiscScript.h:82 ValidateSpellAtCastSpellResult`
- `MiscScript.h:84 OnAfterLootTemplateProcess`
- `MiscScript.h:86 OnPlayerSetPhase`
- `MiscScript.h:88 OnInstanceSave`
- `MiscScript.h:96 GetDialogStatus`

### MovementHandlerScript.h

- `MovementHandlerScript.h:38 OnPlayerMove`

### OutdoorPvPScript.h

- `OutdoorPvPScript.h:32 GetOutdoorPvP`

### PetScript.h

- `PetScript.h:43 OnInitStatsForLevel`
- `PetScript.h:45 OnCalculateMaxTalentPointsForLevel`
- `PetScript.h:47 CanUnlearnSpellSet`
- `PetScript.h:49 CanUnlearnSpellDefault`
- `PetScript.h:51 CanResetTalents`
- `PetScript.h:58 OnPetAddToWorld`

### PlayerScript.h

- `PlayerScript.h:248 OnPlayerJustDied`
- `PlayerScript.h:251 OnPlayerCalculateTalentsPoints`
- `PlayerScript.h:254 OnPlayerReleasedGhost`
- `PlayerScript.h:257 OnPlayerSendInitialPacketsBeforeAddToMap`
- `PlayerScript.h:260 OnPlayerBattlegroundDesertion`
- `PlayerScript.h:263 OnPlayerCompleteQuest`
- `PlayerScript.h:266 OnPlayerPVPKill`
- `PlayerScript.h:269 OnPlayerPVPFlagChange`
- `PlayerScript.h:272 OnPlayerCreatureKill`
- `PlayerScript.h:275 OnPlayerCreatureKilledByPet`
- `PlayerScript.h:278 OnPlayerKilledByCreature`
- `PlayerScript.h:282 OnPlayerCreatureKillCredit`
- `PlayerScript.h:285 OnPlayerLevelChanged`
- `PlayerScript.h:288 OnPlayerFreeTalentPointsChanged`
- `PlayerScript.h:291 OnPlayerTalentsReset`
- `PlayerScript.h:294 OnPlayerCanLearnTalent`
- `PlayerScript.h:297 OnPlayerAfterSpecSlotChanged`
- `PlayerScript.h:300 OnPlayerBeforeUpdate`
- `PlayerScript.h:301 OnPlayerAfterUpdate`
- `PlayerScript.h:302 OnPlayerUpdate`
- `PlayerScript.h:305 OnPlayerMoneyChanged`
- `PlayerScript.h:308 OnPlayerBeforeLootMoney`
- `PlayerScript.h:311 OnPlayerBeforeSendLoot`
- `PlayerScript.h:314 OnPlayerGiveXP`
- `PlayerScript.h:317 OnPlayerReputationChange`
- `PlayerScript.h:320 OnPlayerReputationRankChange`
- `PlayerScript.h:323 OnPlayerGiveReputation`
- `PlayerScript.h:326 OnPlayerLearnSpell`
- `PlayerScript.h:329 OnPlayerForgotSpell`
- `PlayerScript.h:332 OnPlayerDuelRequest`
- `PlayerScript.h:335 OnPlayerDuelStart`
- `PlayerScript.h:338 OnPlayerDuelEnd`
- `PlayerScript.h:341 OnPlayerBeforeSendChatMessage`
- `PlayerScript.h:344 OnPlayerEmote`
- `PlayerScript.h:346 OnPlayerTextEmote`
- `PlayerScript.h:349 OnPlayerSpellCast`
- `PlayerScript.h:352 OnPlayerLoadFromDB`
- `PlayerScript.h:355 OnPlayerLogin`
- `PlayerScript.h:358 OnPlayerBeforeLogout`
- `PlayerScript.h:361 OnPlayerLogout`
- `PlayerScript.h:365 OnPlayerCanMarkAccountOffline`
- `PlayerScript.h:368 OnPlayerCreate`
- `PlayerScript.h:371 OnPlayerDelete`
- `PlayerScript.h:374 OnPlayerFailedDelete`
- `PlayerScript.h:377 OnPlayerSave`
- `PlayerScript.h:380 OnPlayerBindToInstance`
- `PlayerScript.h:383 OnPlayerUpdateZone`
- `PlayerScript.h:386 OnPlayerUpdateArea`
- `PlayerScript.h:389 OnPlayerMapChanged`
- `PlayerScript.h:392 OnPlayerBeforeTeleport`
- `PlayerScript.h:395 OnPlayerUpdateFaction`
- `PlayerScript.h:398 OnPlayerAddToBattleground`
- `PlayerScript.h:401 OnPlayerQueueRandomDungeon`
- `PlayerScript.h:404 OnPlayerRemoveFromBattleground`
- `PlayerScript.h:407 OnPlayerAchievementComplete`
- `PlayerScript.h:410 OnPlayerBeforeAchievementComplete`
- `PlayerScript.h:413 OnPlayerCriteriaProgress`
- `PlayerScript.h:416 OnPlayerBeforeCriteriaProgress`
- `PlayerScript.h:419 OnPlayerAchievementSave`
- `PlayerScript.h:422 OnPlayerCriteriaSave`
- `PlayerScript.h:425 OnPlayerGossipSelect`
- `PlayerScript.h:428 OnPlayerGossipSelectCode`
- `PlayerScript.h:431 OnPlayerBeingCharmed`
- `PlayerScript.h:434 OnPlayerAfterSetVisibleItemSlot`
- `PlayerScript.h:437 OnPlayerAfterMoveItemFromInventory`
- `PlayerScript.h:440 OnPlayerAfterMoveItemToInventory`
- `PlayerScript.h:443 OnPlayerEquip`
- `PlayerScript.h:446 OnPlayerUnequip`
- `PlayerScript.h:449 OnPlayerJoinBG`
- `PlayerScript.h:452 OnPlayerJoinArena`
- `PlayerScript.h:455 OnPlayerGetMaxPersonalArenaRatingRequirement`
- `PlayerScript.h:458 OnPlayerLootItem`
- `PlayerScript.h:461 OnPlayerBeforeFillQuestLootItem`
- `PlayerScript.h:464 OnPlayerStoreNewItem`
- `PlayerScript.h:467 OnPlayerCreateItem`
- `PlayerScript.h:470 OnPlayerQuestRewardItem`
- `PlayerScript.h:473 OnPlayerCanPlaceAuctionBid`
- `PlayerScript.h:476 OnPlayerGroupRollRewardItem`
- `PlayerScript.h:479 OnPlayerBeforeOpenItem`
- `PlayerScript.h:482 OnPlayerBeforeQuestComplete`
- `PlayerScript.h:485 OnPlayerQuestComputeXP`
- `PlayerScript.h:488 OnPlayerBeforeDurabilityRepair`
- `PlayerScript.h:491 OnPlayerBeforeBuyItemFromVendor`
- `PlayerScript.h:494 OnPlayerBeforeStoreOrEquipNewItem`
- `PlayerScript.h:497 OnPlayerAfterStoreOrEquipNewItem`
- `PlayerScript.h:499 OnPlayerAfterUpdateMaxPower`
- `PlayerScript.h:501 OnPlayerAfterUpdateMaxHealth`
- `PlayerScript.h:503 OnPlayerBeforeUpdateAttackPowerAndDamage`
- `PlayerScript.h:504 OnPlayerAfterUpdateAttackPowerAndDamage`
- `PlayerScript.h:506 OnPlayerBeforeInitTalentForLevel`
- `PlayerScript.h:508 OnPlayerFirstLogin`
- `PlayerScript.h:510 OnPlayerSetMaxLevel`
- `PlayerScript.h:512 OnPlayerCanJoinInBattlegroundQueue`
- `PlayerScript.h:513 OnPlayerShouldBeRewardedWithMoneyInsteadOfExp`
- `PlayerScript.h:516 OnPlayerBeforeTempSummonInitStats`
- `PlayerScript.h:519 OnPlayerBeforeGuardianInitStatsForLevel`
- `PlayerScript.h:522 OnPlayerAfterGuardianInitStatsForLevel`
- `PlayerScript.h:525 OnPlayerBeforeLoadPetFromDB`
- `PlayerScript.h:527 OnPlayerCanJoinInArenaQueue`
- `PlayerScript.h:529 OnPlayerCanBattleFieldPort`
- `PlayerScript.h:531 OnPlayerCanGroupInvite`
- `PlayerScript.h:533 OnPlayerCanGroupAccept`
- `PlayerScript.h:535 OnPlayerCanSellItem`
- `PlayerScript.h:537 OnPlayerCanSendMail`
- `PlayerScript.h:539 OnPlayerPetitionBuy`
- `PlayerScript.h:541 OnPlayerPetitionShowList`
- `PlayerScript.h:545 OnPlayerBeforePetitionSign`
- `PlayerScript.h:547 OnPlayerRewardKillRewarder`
- `PlayerScript.h:549 OnPlayerCanGiveMailRewardAtGiveLevel`
- `PlayerScript.h:551 OnPlayerDeleteFromDB`
- `PlayerScript.h:553 OnPlayerCanRepopAtGraveyard`
- `PlayerScript.h:555 OnPlayerIsClass`
- `PlayerScript.h:557 OnPlayerGetMaxSkillValue`
- `PlayerScript.h:559 OnPlayerHasActivePowerType`
- `PlayerScript.h:572 OnPlayerUpdateGatheringSkill`
- `PlayerScript.h:582 OnPlayerUpdateCraftingSkill`
- `PlayerScript.h:584 OnPlayerUpdateFishingSkill`
- `PlayerScript.h:586 OnPlayerCanAreaExploreAndOutdoor`
- `PlayerScript.h:588 OnPlayerVictimRewardBefore`
- `PlayerScript.h:590 OnPlayerVictimRewardAfter`
- `PlayerScript.h:592 OnPlayerCustomScalingStatValueBefore`
- `PlayerScript.h:594 OnPlayerCustomScalingStatValue`
- `PlayerScript.h:596 OnPlayerApplyItemModsBefore`
- `PlayerScript.h:598 OnPlayerApplyEnchantmentItemModsBefore`
- `PlayerScript.h:600 OnPlayerApplyWeaponDamage`
- `PlayerScript.h:602 OnPlayerCanArmorDamageModifier`
- `PlayerScript.h:604 OnPlayerGetFeralApBonus`
- `PlayerScript.h:606 OnPlayerCanApplyWeaponDependentAuraDamageMod`
- `PlayerScript.h:608 OnPlayerCanApplyEquipSpell`
- `PlayerScript.h:610 OnPlayerCanApplyEquipSpellsItemSet`
- `PlayerScript.h:612 OnPlayerCanCastItemCombatSpell`
- `PlayerScript.h:614 OnPlayerCanCastItemUseSpell`
- `PlayerScript.h:616 OnPlayerApplyAmmoBonuses`
- `PlayerScript.h:618 OnPlayerCanEquipItem`
- `PlayerScript.h:620 OnPlayerCanUnequipItem`
- `PlayerScript.h:622 OnPlayerCanUseItem`
- `PlayerScript.h:624 OnPlayerCanSaveEquipNewItem`
- `PlayerScript.h:626 OnPlayerCanApplyEnchantment`
- `PlayerScript.h:628 OnPlayerGetQuestRate`
- `PlayerScript.h:630 OnPlayerPassedQuestKilledMonsterCredit`
- `PlayerScript.h:632 OnPlayerCheckItemInSlotAtLoadInventory`
- `PlayerScript.h:634 OnPlayerNotAvoidSatisfy`
- `PlayerScript.h:636 OnPlayerNotVisibleGloballyFor`
- `PlayerScript.h:638 OnPlayerGetArenaPersonalRating`
- `PlayerScript.h:640 OnPlayerGetArenaTeamId`
- `PlayerScript.h:642 OnPlayerIsFFAPvP`
- `PlayerScript.h:645 OnPlayerFfaPvpStateUpdate`
- `PlayerScript.h:647 OnPlayerIsPvP`
- `PlayerScript.h:649 OnPlayerGetMaxSkillValueForLevel`
- `PlayerScript.h:651 OnPlayerNotSetArenaTeamInfoField`
- `PlayerScript.h:653 OnPlayerCanJoinLfg`
- `PlayerScript.h:655 OnPlayerCanEnterMap`
- `PlayerScript.h:657 OnPlayerCanInitTrade`
- `PlayerScript.h:667 OnPlayerCanSetTradeItem`
- `PlayerScript.h:669 OnPlayerSetServerSideVisibility`
- `PlayerScript.h:671 OnPlayerSetServerSideVisibilityDetect`
- `PlayerScript.h:673 OnPlayerResurrect`
- `PlayerScript.h:676 OnPlayerBeforeChooseGraveyard`
- `PlayerScript.h:688 OnPlayerCanUseChat`
- `PlayerScript.h:701 OnPlayerCanUseChat`
- `PlayerScript.h:714 OnPlayerCanUseChat`
- `PlayerScript.h:727 OnPlayerCanUseChat`
- `PlayerScript.h:740 OnPlayerCanUseChat`
- `PlayerScript.h:750 OnPlayerLearnTalents`
- `PlayerScript.h:758 OnPlayerEnterCombat`
- `PlayerScript.h:765 OnPlayerLeaveCombat`
- `PlayerScript.h:773 OnPlayerQuestAbandon`
- `PlayerScript.h:781 OnPlayerQuestAccept`
- `PlayerScript.h:791 OnPlayerCanFlyInZone`
- `PlayerScript.h:794 AnticheatSetCanFlybyServer`
- `PlayerScript.h:795 AnticheatSetUnderACKmount`
- `PlayerScript.h:796 AnticheatSetRootACKUpd`
- `PlayerScript.h:797 AnticheatSetJumpingbyOpcode`
- `PlayerScript.h:798 AnticheatUpdateMovementInfo`
- `PlayerScript.h:799 AnticheatHandleDoubleJump`
- `PlayerScript.h:800 AnticheatCheckMovementInfo`
- `PlayerScript.h:809 OnPlayerCanSendErrorAlreadyLooted`
- `PlayerScript.h:817 OnPlayerAfterCreatureLoot`
- `PlayerScript.h:824 OnPlayerAfterCreatureLootMoney`
- `PlayerScript.h:826 OnPlayerCanUpdateSkill`
- `PlayerScript.h:827 OnPlayerBeforeUpdateSkill`
- `PlayerScript.h:828 OnPlayerUpdateSkill`
- `PlayerScript.h:829 OnPlayerSetSkill`
- `PlayerScript.h:838 OnPlayerCanResurrect`
- `PlayerScript.h:848 OnPlayerCanGiveLevel`
- `PlayerScript.h:857 OnPlayerSendListInventory`
- `PlayerScript.h:866 OnPlayerGetReputationPriceDiscount`
- `PlayerScript.h:875 OnPlayerGetReputationPriceDiscount`
- `PlayerScript.h:883 OnPlayerLearnTaxiNode`
- `PlayerScript.h:891 OnPlayerBeforeGetLevelForXPGain`
- `PlayerScript.h:902 OnPlayerAfterTakeItemFromMail`
- `PlayerScript.h:929 OnPlayerCanLearnSpell`
- `PlayerScript.h:943 OnPlayerBeforeReceiveSpellListFromTrainer`
- `PlayerScript.h:955 OnPlayerGetTrainerSpellState`
- `PlayerScript.h:968 OnPlayerAfterTrainSpell`

### ServerScript.h

- `ServerScript.h:45 OnNetworkStart`
- `ServerScript.h:46 OnNetworkStart`
- `ServerScript.h:49 OnNetworkStop`
- `ServerScript.h:52 OnSocketOpen`
- `ServerScript.h:56 OnSocketClose`
- `ServerScript.h:65 CanPacketSend`
- `ServerScript.h:75 CanPacketReceive`
- `ServerScript.h:85 OnPacketSent`

### SessionScript.h

- `SessionScript.h:43 OnSessionUpdate`

### SpellScriptLoader.h

- `SpellScriptLoader.h:34 GetSpellScript`
- `SpellScriptLoader.h:37 GetAuraScript`

### TicketScript.h

- `TicketScript.h:43 OnTicketCreate`
- `TicketScript.h:44 OnTicketUpdateLastChange`
- `TicketScript.h:45 OnTicketClose`
- `TicketScript.h:46 OnTicketStatusUpdate`
- `TicketScript.h:47 OnTicketResolve`

### TransportScript.h

- `TransportScript.h:32 OnAddPassenger`
- `TransportScript.h:35 OnAddCreaturePassenger`
- `TransportScript.h:38 OnRemovePassenger`
- `TransportScript.h:41 OnRelocate`

### UnitScript.h

- `UnitScript.h:61 OnHeal`
- `UnitScript.h:64 OnDamage`
- `UnitScript.h:68 ModifyPeriodicDamageAurasTick`
- `UnitScript.h:71 ModifyMeleeDamage`
- `UnitScript.h:74 ModifySpellDamageTaken`
- `UnitScript.h:77 ModifyHealReceived`
- `UnitScript.h:80 DealDamage`
- `UnitScript.h:82 OnBeforeRollMeleeOutcomeAgainst`
- `UnitScript.h:84 OnAuraApply`
- `UnitScript.h:86 OnAuraRemove`
- `UnitScript.h:88 IfNormalReaction`
- `UnitScript.h:90 CanSetPhaseMask`
- `UnitScript.h:92 IsCustomBuildValuesUpdate`
- `UnitScript.h:94 ShouldTrackValuesUpdatePosByIndex`
- `UnitScript.h:96 OnPatchValuesUpdate`
- `UnitScript.h:104 OnUnitUpdate`
- `UnitScript.h:106 OnDisplayIdChange`
- `UnitScript.h:108 OnUnitEnterEvadeMode`
- `UnitScript.h:109 OnUnitEnterCombat`
- `UnitScript.h:110 OnUnitExitCombat`
- `UnitScript.h:111 OnUnitDeath`
- `UnitScript.h:112 OnUnitSetShapeshiftForm`

### VehicleScript.h

- `VehicleScript.h:30 OnInstall`
- `VehicleScript.h:33 OnUninstall`
- `VehicleScript.h:36 OnReset`
- `VehicleScript.h:39 OnInstallAccessory`
- `VehicleScript.h:42 OnAddPassenger`
- `VehicleScript.h:45 OnRemovePassenger`

### WeatherScript.h

- `WeatherScript.h:32 OnChange`

### WorldObjectScript.h

- `WorldObjectScript.h:47 OnWorldObjectDestroy`
- `WorldObjectScript.h:54 OnWorldObjectCreate`
- `WorldObjectScript.h:61 OnWorldObjectSetMap`
- `WorldObjectScript.h:68 OnWorldObjectResetMap`
- `WorldObjectScript.h:76 OnWorldObjectUpdate`

### WorldScript.h

- `WorldScript.h:50 OnOpenStateChange`
- `WorldScript.h:53 OnAfterConfigLoad`
- `WorldScript.h:56 OnLoadCustomDatabaseTable`
- `WorldScript.h:59 OnBeforeConfigLoad`
- `WorldScript.h:62 OnMotdChange`
- `WorldScript.h:65 OnShutdownInitiate`
- `WorldScript.h:68 OnShutdownCancel`
- `WorldScript.h:71 OnUpdate`
- `WorldScript.h:74 OnStartup`
- `WorldScript.h:77 OnShutdown`
- `WorldScript.h:82 OnAfterUnloadAllMaps`
- `WorldScript.h:89 OnBeforeFinalizePlayerWorldSession`
- `WorldScript.h:94 OnBeforeWorldInitialized`
