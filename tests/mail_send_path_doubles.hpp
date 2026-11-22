#include "Mail.h"
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <initializer_list>
#include <memory>
#include <sstream>
class Item {ObjectGuid guid;public:explicit Item(uint32 id):guid(HighGuid::Player,id){}ObjectGuid GetGUID(){return guid;}uint32 GetEntry(){return 123;}void SaveToDB(CharacterDatabaseTransaction){} };
struct Session {int GetSecurity(){return 0;}};
class Player {public:Session session;std::vector<Mail*> mails;std::vector<Item*> items;Session* GetSession(){return &session;}void AddMail(Mail* m){mails.push_back(m);}void AddMItem(Item* i){items.push_back(i);}void AddNewMailDeliverTime(time_t){}~Player(){for(auto m:mails)delete m;for(auto i:items)delete i;} };
namespace ObjectAccessor {inline Player* online=nullptr;inline Player* FindConnectedPlayer(ObjectGuid){return online;}inline Player* FindPlayerByLowGUID(uint32){return nullptr;}}
struct Cache {uint32 a=5,b=5;uint32 GetCharacterAccountIdByGuid(ObjectGuid g){return g.GetCounter()==1?a:b;}} cache;
auto sCharacterCache=&cache;
constexpr int MAILHOOK_ON_BEFORE_MAIL_DRAFT_SEND_MAIL_TO=0,CONFIG_MAIL_DELIVERY_DELAY=0;
struct World {uint32 delay=3600;uint32 getIntConfig(int){return delay;}} world;
auto sWorld=&world;
struct MailScript {MailScript(const char*,std::initializer_list<int>){} };
constexpr uint32 DAY=86400;constexpr int BATTLEGROUND_TYPE_NONE=0;
constexpr int CHAR_INS_MAIL=1,CHAR_INS_MAIL_ITEM=2,CHAR_DEL_ITEM_INSTANCE=3,CHAR_UPD_ITEM_OWNER=4;
struct CharacterDatabasePreparedStatement {int kind;std::map<int,std::string> values;template<class T>void SetData(int n,T const& v){std::ostringstream s;s<<+v;values[n]=s.str();}void SetData(int n,std::string const& v){values[n]=v;}};
struct Transaction {std::vector<CharacterDatabasePreparedStatement> rows;void Append(CharacterDatabasePreparedStatement* p){rows.push_back(*p);}};
struct DB {std::vector<std::unique_ptr<CharacterDatabasePreparedStatement>> statements;CharacterDatabasePreparedStatement* GetPreparedStatement(int kind){statements.emplace_back(new CharacterDatabasePreparedStatement{kind,{}});return statements.back().get();}} CharacterDatabase;
struct ObjectMgr {uint32 GenerateMailID(){return 42;}} objectMgr;auto sObjectMgr=&objectMgr;
struct BG {int GetBattleMasterBG(uint32){return BATTLEGROUND_TYPE_NONE;}} bg;auto sBattlegroundMgr=&bg;
struct MailMgr {void OnMailSent(uint32){}} mailMgr;auto sMailMgr=&mailMgr;
namespace GameTime {inline std::chrono::seconds GetGameTime(){return std::chrono::seconds(1000);}}
MailReceiver::MailReceiver(Player* p,ObjectGuid::LowType id):m_receiver(p),m_receiver_lowguid(id){}
void MailDraft::prepareItems(Player*,CharacterDatabaseTransaction){if(m_mailTemplateId)std::abort();m_mailTemplateItemsNeed=false;} // explicit template-generation seam, no template cases claimed
