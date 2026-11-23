// Explicit engine/packet/DB doubles for unchanged native mail method bodies.
#include "Mail.h"
#include <any>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <set>
#include <sstream>
template<class... Args> void FixtureLog(Args const&...) { }
#define LOG_WARN(...) FixtureLog(__VA_ARGS__)
#define LOG_DEBUG(...) FixtureLog(__VA_ARGS__)
#define LOG_ERROR(...) FixtureLog(__VA_ARGS__)
#define LOG_INFO(...) FixtureLog(__VA_ARGS__)
#define LOG_GM(...) FixtureLog(__VA_ARGS__)
enum { TYPEID_UNIT, TYPEID_GAMEOBJECT, TYPEID_PLAYER, TEAM_NEUTRAL,
    GAMEOBJECT_TYPE_MAILBOX, UNIT_NPC_FLAG_MAILBOX, CONFIG_TRIAL_RESTRICTION_MAIL,
    CONFIG_MAIL_LEVEL_REQ, CONFIG_MAIL_DELIVERY_DELAY, LANG_MAIL_SENDER_REQ,
    EQUIP_ERR_CAN_ONLY_DO_WITH_EMPTY_BAGS, EQUIP_ERR_MAIL_BOUND_ITEM,
    EQUIP_ERR_ARTEFACTS_ONLY_FOR_OWN_CHARACTERS, ITEM_FLAG_CONJURED,
    ITEM_FIELD_DURATION, ITEM_UNCHANGED, ITEM_CHANGED, ACHIEVEMENT_CRITERIA_TYPE_GOLD_SPENT_FOR_MAIL };
namespace rbac { enum { RBAC_PERM_COMMAND_MAILBOX, RBAC_PERM_TWO_SIDE_INTERACTION_MAIL, RBAC_PERM_LOG_GM_TRADE }; }
constexpr uint32 GOLD = 10000, DAY = 86400;
constexpr int BATTLEGROUND_TYPE_NONE = 0, MAILHOOK_ON_BEFORE_MAIL_DRAFT_SEND_MAIL_TO = 0;
struct WorldPacket {
    std::vector<std::any> fields;
    size_t offset = 0;
    bool finished = false;
    template<class T> WorldPacket& operator>>(T& value) { value = std::any_cast<T>(fields.at(offset++)); return *this; }
    template<class T> void read_skip() { T value; *this >> value; }
    void rfinish() { finished = true; }
};
class Object {
public:
    ObjectGuid guid{HighGuid::Player, 1};
    int GetTypeId() const { return TYPEID_PLAYER; }
    uint32 GetEntry() const { return 0; }
    ObjectGuid GetGUID() const { return guid; }
};
class Player;
struct WorldSession {
    Player* _player = nullptr;
    uint32 account = 5;
    bool trial = false;
    std::set<int> permissions;
    int GetSecurity() const { return 0; }
    uint32 GetAccountId() const { return account; }
    std::string GetRemoteAddress() const { return "fixture"; }
    bool IsTrialAccount() const { return trial; }
    bool HasPermission(int permission) const { return permissions.count(permission); }
    Player* GetPlayer() const { return _player; }
    bool CanOpenMailBox(ObjectGuid);
    void HandleSendMail(WorldPacket&);
};
struct ItemTemplate { std::string Name1 = "fixture item"; bool conjured = false; bool HasFlag(int) const { return conjured; } };
class Item {
    ObjectGuid guid;
public:
    explicit Item(uint32 id) : guid(HighGuid::Player, id) { }
    ItemTemplate prototype;
    bool bag = false, tradable = true, accountBound = false, soulbound = false, wrapped = false;
    uint32 duration = 0;
    int state = ITEM_UNCHANGED;
    ObjectGuid GetGUID() const { return guid; }
    uint32 GetEntry() const { return 123; }
    uint32 GetCount() const { return 1; }
    ItemTemplate const* GetTemplate() const { return &prototype; }
    bool IsNotEmptyBag() const { return bag; }
    bool CanBeTraded(bool) const { return tradable; }
    bool IsBoundAccountWide() const { return accountBound; }
    bool IsSoulBound() const { return soulbound; }
    bool IsWrapped() const { return wrapped; }
    uint32 GetUInt32Value(int) const { return duration; }
    uint8 GetBagSlot() const { return 0; }
    uint8 GetSlot() const { return uint8(guid.GetCounter() - 100); }
    int GetState() const { return state; }
    void FSetState(int value) { state = value; }
    void SetNotRefundable(Player*) { }
    void DeleteFromInventoryDB(CharacterDatabaseTransaction) { }
    void SetOwnerGUID(ObjectGuid) { }
    void SaveToDB(CharacterDatabaseTransaction) { }
};
class Player : public Object {
public:
    WorldSession session;
    uint32 funds = 1000000, team = 0, level = 60;
    bool interact = true, gm = false;
    unsigned moved = 0, saved = 0, results = 0;
    int lastResult = -1;
    std::map<uint32, Item*> inventory;
    std::vector<Mail*> mails;
    std::vector<Item*> items;
    Player() { session._player = this; }
    WorldSession* GetSession() { return &session; }
    std::string GetName() const { return "fixture sender"; }
    uint32 GetLevel() const { return level; }
    bool IsGameMaster() const { return gm; }
    uint32 GetTeamId() const { return team; }
    static uint32 TeamIdForRace(uint8 race) { return race; }
    uint16 GetMailSize() const { return uint16(mails.size()); }
    bool HasEnoughMoney(uint32 money) const { return funds >= money; }
    void ModifyMoney(int32 amount) { funds += amount; }
    void UpdateAchievementCriteria(int, uint32) { }
    void SaveInventoryAndGoldToDB(CharacterDatabaseTransaction) { ++saved; }
    void SendMailResult(int, MailResponseType, MailResponseResult result, int = 0) { ++results; lastResult = result; }
    bool GetGameObjectIfCanInteractWith(ObjectGuid, int) const { return interact; }
    bool GetNPCIfCanInteractWith(ObjectGuid, int) const { return interact; }
    Item* GetItemByGuid(ObjectGuid id) { auto it = inventory.find(id.GetCounter()); return it == inventory.end() ? nullptr : it->second; }
    void MoveItemFromInventory(uint8, uint8 slot, bool) { inventory.erase(100 + slot); ++moved; }
    void AddMail(Mail* mail) { mails.push_back(mail); }
    void AddMItem(Item* item) { items.push_back(item); }
    void AddNewMailDeliverTime(time_t) { }
    ~Player() { for (auto pair : inventory) delete pair.second; for (auto item : items) delete item; for (auto mail : mails) delete mail; }
};
namespace ObjectAccessor {
    inline Player* online = nullptr;
    inline Player* FindConnectedPlayer(ObjectGuid) { return online; }
    inline Player* FindPlayerByLowGUID(uint32) { return nullptr; }
}
struct CharacterCacheEntry { uint8 Race = 0; uint16 MailCount = 0; };
struct Cache {
    uint32 senderAccount = 5, receiverAccount = 5, receiverId = 2;
    CharacterCacheEntry recipient;
    ObjectGuid GetCharacterGuidByName(std::string const&) { return ObjectGuid(HighGuid::Player, receiverId); }
    uint32 GetCharacterAccountIdByGuid(ObjectGuid id) { return id.GetCounter() == 1 ? senderAccount : receiverAccount; }
    CharacterCacheEntry const* GetCharacterCacheByGuid(ObjectGuid) { return &recipient; }
} cache;
auto sCharacterCache = &cache;
struct World {
    uint32 delay = 3600, minimumLevel = 1;
    bool trialRestrictions = false;
    bool getBoolConfig(int) const { return trialRestrictions; }
    uint32 getIntConfig(int config) const { return config == CONFIG_MAIL_LEVEL_REQ ? minimumLevel : delay; }
} world;
auto sWorld = &world;
struct ChatHandler { explicit ChatHandler(WorldSession*) { } void SendNotification(int, uint32) { } };
inline bool normalizePlayerName(std::string&) { return true; }
inline void CleanStringForMysqlQuery(std::string&) { }
namespace Acore { template<class... Args> std::string StringFormat(char const*, Args const&...) { return "fixture item log"; } }
struct MailScript { MailScript(char const*, std::initializer_list<int>) { } };
constexpr int CHAR_INS_MAIL = 1, CHAR_INS_MAIL_ITEM = 2, CHAR_DEL_ITEM_INSTANCE = 3;
struct CharacterDatabasePreparedStatement {
    int kind;
    std::map<int, std::string> values;
    template<class T> void SetData(int index, T const& value) { std::ostringstream text; text << +value; values[index] = text.str(); }
    void SetData(int index, std::string const& value) { values[index] = value; }
};
struct Transaction {
    std::vector<CharacterDatabasePreparedStatement> rows;
    void Append(CharacterDatabasePreparedStatement* statement) { rows.push_back(*statement); }
};
struct DB {
    unsigned commits = 0;
    CharacterDatabaseTransaction committed;
    std::vector<std::unique_ptr<CharacterDatabasePreparedStatement>> statements;
    CharacterDatabaseTransaction BeginTransaction() { return std::make_shared<Transaction>(); }
    void CommitTransaction(CharacterDatabaseTransaction transaction) { committed = transaction; ++commits; }
    template<class... Args> void Execute(char const*, Args const&...) { }
    CharacterDatabasePreparedStatement* GetPreparedStatement(int kind) {
        statements.emplace_back(new CharacterDatabasePreparedStatement{kind, {}}); return statements.back().get();
    }
} CharacterDatabase;
struct ObjectMgr { uint32 GenerateMailID() { return 42; } } objectMgr;
auto sObjectMgr = &objectMgr;
struct BG { int GetBattleMasterBG(uint32) { return BATTLEGROUND_TYPE_NONE; } } bg;
auto sBattlegroundMgr = &bg;
struct MailMgr { void OnMailSent(uint32) { } } mailMgr;
auto sMailMgr = &mailMgr;
namespace GameTime { inline std::chrono::seconds GetGameTime() { return std::chrono::seconds(1000); } }
MailReceiver::MailReceiver(Player* player, ObjectGuid::LowType id) : m_receiver(player), m_receiver_lowguid(id) { }
void MailDraft::prepareItems(Player*, CharacterDatabaseTransaction) { if (m_mailTemplateId) std::abort(); m_mailTemplateItemsNeed = false; }
