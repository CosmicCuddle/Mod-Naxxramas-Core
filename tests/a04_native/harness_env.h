// A04 harness environment: the pinned headers plus test-only collaborators.
//
// The real pinned LootMgr.h, ObjectGuid.h, ByteBuffer.h, SharedDefines.h,
// RefMgr.h and ItemTemplate.h are included unchanged, so Loot, LootItem,
// QuestItem and LootView are the original types. Everything below is a
// collaborator stub. Stubs only store or return fixture state and record
// calls; they make no loot or quest decision of their own. The loot and quest
// decisions all come from the original bodies in pinned_bodies.cpp.
#pragma once

#include "LootMgr.h"
#include "ItemTemplate.h"

#include <cstdio>
#include <map>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>

#define LOG_DEBUG(...) ((void)0)
#define LOG_ERROR(...) ((void)0)
#ifndef ASSERT
#include <cstdlib>
#define ASSERT(cond, ...) do { if (!(cond)) { std::fprintf(stderr, "ASSERT FAILED: %s\n", #cond); std::abort(); } } while (0)
#endif

// ---- Values checked against the pinned QuestDef.h by prepare_pinned.py ----
#define MAX_QUEST_LOG_SIZE 25
#define QUEST_ITEM_OBJECTIVES_COUNT 6
#define QUEST_SOURCE_ITEM_IDS_COUNT 4
enum QuestStatus : uint8
{
    QUEST_STATUS_NONE = 0,
    QUEST_STATUS_COMPLETE = 1,
    QUEST_STATUS_INCOMPLETE = 3,
};
enum QuestSpecialFlags : uint32 { QUEST_SPECIAL_FLAGS_DELIVER = 0x0200 };

// Only the ItemCount field is read by the extracted bodies.
struct QuestStatusData
{
    QuestStatus Status{QUEST_STATUS_NONE};
    uint16 ItemCount[QUEST_ITEM_OBJECTIVES_COUNT]{};
};
typedef std::unordered_map<uint32, QuestStatusData> QuestStatusMap;

class Quest
{
public:
    uint32 Id{0};
    int32 PrevQuestId{0};
    uint32 SpecialFlags{0};
    uint32 RequiredItemId[QUEST_ITEM_OBJECTIVES_COUNT]{};
    uint32 RequiredItemCount[QUEST_ITEM_OBJECTIVES_COUNT]{};
    uint32 ItemDrop[QUEST_SOURCE_ITEM_IDS_COUNT]{};
    uint32 ItemDropQuantity[QUEST_SOURCE_ITEM_IDS_COUNT]{};
    [[nodiscard]] int32 GetPrevQuestId() const { return PrevQuestId; }
    [[nodiscard]] bool HasSpecialFlag(uint32 flag) const { return (SpecialFlags & flag) != 0; }
    // Only reached for raid groups; the fixtures use a 2-player party.
    [[nodiscard]] bool IsAllowedInRaid(Difficulty) const { return false; }
};

// ---- Inventory result codes (names only; values are not used) ----
enum InventoryResult : uint8
{
    EQUIP_ERR_OK = 0,
    EQUIP_ERR_INVENTORY_FULL = 50,
    EQUIP_ERR_ALREADY_LOOTED = 51,
};
enum { NULL_BAG = 255, NULL_SLOT = 255 };
struct ItemPosCount { uint16 pos; uint32 count; };
typedef std::vector<ItemPosCount> ItemPosCountVec;

enum AdditionalSaving { ADDITIONAL_SAVING_INVENTORY_AND_GOLD = 0x01, ADDITIONAL_SAVING_QUEST_STATUS = 0x02 };
enum DisableType { DISABLE_TYPE_LOOT = 10 };

class Item
{
public:
    uint32 entry{0};
    uint32 count{0};
    static int32 GenerateItemRandomPropertyId(uint32) { return 0; }
};
inline uint32 GenerateEnchSuffixFactor(uint32) { return 0; }
inline uint32 urand(uint32 min, uint32) { return min; }

class WorldObject
{
public:
    virtual ~WorldObject() = default;
};

class Map
{
public:
    [[nodiscard]] Difficulty GetDifficulty() const { return REGULAR_DIFFICULTY; }
};

class Player;
class GroupReference
{
public:
    Player* source{nullptr};
    GroupReference* nextRef{nullptr};
    GroupReference* next() { return nextRef; }
    Player* GetSource() { return source; }
};

class Group
{
public:
    std::vector<GroupReference> refs;
    LootMethod lootMethod{GROUP_LOOT};
    ItemQualities lootThreshold{ITEM_QUALITY_UNCOMMON};
    ObjectGuid masterLooter;
    void SetMembers(std::vector<Player*> const& members)
    {
        refs.assign(members.size(), GroupReference());
        for (size_t i = 0; i < members.size(); ++i)
        {
            refs[i].source = members[i];
            refs[i].nextRef = i + 1 < members.size() ? &refs[i + 1] : nullptr;
        }
    }
    GroupReference* GetFirstMember() { return refs.empty() ? nullptr : &refs[0]; }
    [[nodiscard]] LootMethod GetLootMethod() const { return lootMethod; }
    [[nodiscard]] ItemQualities GetLootThreshold() const { return lootThreshold; }
    [[nodiscard]] ObjectGuid GetMasterLooterGuid() const { return masterLooter; }
    [[nodiscard]] bool isRaidGroup() const { return false; }
    [[nodiscard]] bool isBFGroup() const { return false; }
};

// What a stub Player saw happen to it (server-to-client effects).
struct PlayerEvents
{
    std::vector<int> equipErrors;           // InventoryResult values sent
    int lootReleases{0};                    // SendLootRelease calls
    std::vector<int> removedSlots;          // SMSG_LOOT_REMOVED slots
    std::vector<std::pair<uint32, uint32>> received;  // (item, count) actually stored
};

class Player : public WorldObject
{
public:
    // Fixture state.
    ObjectGuid guid;
    std::string name;
    TeamId team{TEAM_ALLIANCE};
    Group* group{nullptr};
    ObjectGuid lootGuid;
    bool atLootDistance{true};
    bool bagsFull{false};
    uint32 questSlots[MAX_QUEST_LOG_SIZE]{};
    QuestStatusMap m_QuestStatus;            // same name as the real member
    std::map<uint32, bool> m_QuestStatusSave;
    std::set<uint32> rewardedQuests;
    std::map<uint32, uint32> bagCount, bankCount;
    PlayerEvents ev;
    std::vector<Item> storedItems;
    Map map;

    // Collaborators read by the original bodies.
    [[nodiscard]] ObjectGuid GetGUID() const { return guid; }
    [[nodiscard]] TeamId GetTeamId(bool = false) const { return team; }
    [[nodiscard]] bool HasSkill(uint32) const { return false; }
    [[nodiscard]] bool HasSpell(uint32) const { return false; }
    [[nodiscard]] Group* GetGroup() const { return group; }
    [[nodiscard]] Map* GetMap() const { return const_cast<Map*>(&map); }
    [[nodiscard]] bool InBattleground() const { return false; }
    [[nodiscard]] ObjectGuid GetLootGUID() const { return lootGuid; }
    [[nodiscard]] uint32 GetQuestSlotQuestId(uint16 slot) const { return questSlots[slot]; }
    [[nodiscard]] QuestStatus GetQuestStatus(uint32 q) const
    {
        auto it = m_QuestStatus.find(q);
        return it == m_QuestStatus.end() ? QUEST_STATUS_NONE : it->second.Status;
    }
    [[nodiscard]] bool GetQuestRewardStatus(uint32 q) const { return rewardedQuests.count(q) != 0; }
    [[nodiscard]] uint32 GetItemCount(uint32 item, bool inBankAlso, Item* = nullptr) const
    {
        auto get = [item](std::map<uint32, uint32> const& m) { auto it = m.find(item); return it == m.end() ? 0u : it->second; };
        return get(bagCount) + (inBankAlso ? get(bankCount) : 0u);
    }
    [[nodiscard]] bool HasItemCount(uint32 item, uint32 count, bool inBankAlso) const { return GetItemCount(item, inBankAlso) >= count; }
    [[nodiscard]] bool IsAtLootRewardDistance(WorldObject const*) const { return atLootDistance; }

    // Effects: recorded, and a stored item lands in the bags.
    void SendEquipError(InventoryResult msg, Item*, Item*, uint32 = 0) { ev.equipErrors.push_back(msg); }
    void SendLootRelease(ObjectGuid) { ++ev.lootReleases; }
    void SendNotifyLootItemRemoved(uint8 slot) { ev.removedSlots.push_back(slot); }
    InventoryResult CanStoreNewItem(uint8, uint8, ItemPosCountVec& dest, uint32, uint32 count, uint32* = nullptr) const
    {
        if (bagsFull)
            return EQUIP_ERR_INVENTORY_FULL;
        dest.push_back({0, count});
        return EQUIP_ERR_OK;
    }
    // Same order as pinned Player::StoreNewItem (PlayerStorage.cpp L2642-2664):
    // sum dest counts, create the item, original ItemAddedQuestCheck, then StoreItem.
    Item* StoreNewItem(ItemPosCountVec const& dest, uint32 item, bool, int32, AllowedLooterSet&)
    {
        uint32 count = 0;
        for (ItemPosCount const& pos : dest)
            count += pos.count;
        ItemAddedQuestCheck(item, count);
        bagCount[item] += count;  // StoreItem
        ev.received.push_back({item, count});
        storedItems.push_back(Item{item, count});
        return &storedItems.back();
    }
    void SendNewItem(Item*, uint32, bool, bool, bool = false) {}
    void UpdateLootAchievements(LootItem*, Loot*) {}

    // Quest bookkeeping called by ItemAdded/RemovedQuestCheck. These stand in
    // for Player::CanCompleteQuest/CompleteQuest/IncompleteQuest: they only
    // move the status between INCOMPLETE and COMPLETE from the item counters,
    // which is all the 922/176 fixtures (one item objective) need.
    [[nodiscard]] bool CanCompleteQuest(uint32 q) const;
    void CompleteQuest(uint32 q) { m_QuestStatus[q].Status = QUEST_STATUS_COMPLETE; }
    void IncompleteQuest(uint32 q) { m_QuestStatus[q].Status = QUEST_STATUS_INCOMPLETE; }
    void AdditionalSavingAddMask(uint32) {}
    void UpdateForQuestWorldObjects() {}

    // Original pinned bodies (pinned_bodies.cpp).
    bool HasQuestForItem(uint32 itemid, uint32 excludeQuestId = 0, bool turnIn = false, bool* showInLoot = nullptr) const;
    LootItem* StoreLootItem(uint8 lootSlot, Loot* loot, InventoryResult& msg);
    void ItemAddedQuestCheck(uint32 entry, uint32 count);
    void ItemRemovedQuestCheck(uint32 entry, uint32 count);
};

// ---- Global managers ----
struct ObjectMgrStub
{
    std::map<uint32, ItemTemplate> items;
    std::map<uint32, Quest> quests;
    ItemTemplate const* GetItemTemplate(uint32 id) const { auto it = items.find(id); return it == items.end() ? nullptr : &it->second; }
    Quest const* GetQuestTemplate(uint32 id) const { auto it = quests.find(id); return it == quests.end() ? nullptr : &it->second; }
};
struct DisableMgrStub
{
    template <typename T> bool IsDisabledFor(DisableType, uint32, T) const { return false; }
};
struct ConditionMgrStub
{
    bool conditionsMet{true};  // only consulted for items that carry conditions
    bool IsObjectMeetToConditions(Player*, ConditionList const& c) const { return c.empty() || conditionsMet; }
};
// Stock default with no enabled scripts: boolean hooks return true
// (pinned ScriptMgrMacros.h CALL_ENABLED_BOOLEAN_HOOKS), void hooks do nothing.
struct ScriptMgrStub
{
    bool OnAllowedForPlayerLootCheck(Player const*, ObjectGuid) const { return true; }
    bool OnPlayerCanSendErrorAlreadyLooted(Player*) const { return true; }
    void OnAfterLootTemplateProcess(Loot*, LootTemplate const*, LootStore const&, Player*, bool, bool, uint16) const {}
    void OnPlayerBeforeFillQuestLootItem(Player*, LootItem&) const {}
    void OnPlayerLootItem(Player*, Item*, uint32, ObjectGuid) const {}
};
struct LootItemStorageStub
{
    int removed{0};
    void RemoveStoredLootItem(ObjectGuid, uint32, uint32, Loot*, uint32) { ++removed; }
};

extern ObjectMgrStub g_objectMgr;
extern DisableMgrStub g_disableMgr;
extern ConditionMgrStub g_conditionMgr;
extern ScriptMgrStub g_scriptMgr;
extern LootItemStorageStub g_lootItemStorage;
#define sObjectMgr (&g_objectMgr)
#define sDisableMgr (&g_disableMgr)
#define sConditionMgr (&g_conditionMgr)
#define sScriptMgr (&g_scriptMgr)
#define sLootItemStorage (&g_lootItemStorage)

namespace ObjectAccessor
{
    Player* FindPlayer(ObjectGuid guid);
}
