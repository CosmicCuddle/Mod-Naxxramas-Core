"""Full pinned Core mail header + actual AddItem and Naxx hook; dependency doubles."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

PIN = "9edf437e62218be610dfc4b3d797563217644ad1"
p = argparse.ArgumentParser()
p.add_argument("--core", required=True)
p.add_argument("--compiler", required=True)
a = p.parse_args()
def core(path):
    return subprocess.check_output(["git", "show", PIN + ":" + path], cwd=a.core).decode("utf-8")
header = core("src/server/game/Mails/Mail.h")
mail = core("src/server/game/Mails/Mail.cpp")
add = re.search(r"MailDraft& MailDraft::AddItem\(Item\* item\)\s*\{[^}]+\}", mail).group()
module = (Path(__file__).resolve().parents[1] / "src/Systems/AltMailDelay.cpp").read_text(encoding="utf-8")
module = re.sub(r"^#include.*$", "", module, flags=re.M).replace(" override", "")
fixture = r"""
#include "Mail.h"
#include <iostream>
#include <cstdlib>
#include <initializer_list>
class Item { ObjectGuid guid; public: explicit Item(uint32 id):guid(HighGuid::Player,id){} ObjectGuid GetGUID(){return guid;} };
struct Cache { uint32 a=5,b=5; uint32 GetCharacterAccountIdByGuid(ObjectGuid g){return g.GetCounter()==1?a:b;} } cache;
auto sCharacterCache=&cache;
constexpr int MAILHOOK_ON_BEFORE_MAIL_DRAFT_SEND_MAIL_TO=0, CONFIG_MAIL_DELIVERY_DELAY=0;
struct World { uint32 delay=3600; uint32 getIntConfig(int){return delay;} } world;
auto sWorld=&world;
struct MailScript { MailScript(const char*,std::initializer_list<int>){} };
"""
checks = r"""
int main(){
 NaxxramasCoreAltMailDelay hook; int count=0;
 auto check=[&](int items,uint32 money,std::string body, MailCheckMask flags,MailMessageType type,MailStationery stationery,uint32 sa,uint32 ra,uint32 initial,uint32 expected){
  MailDraft draft("subject",body);Item item1(100),item2(101);
  if(items>0)draft.AddItem(&item1);if(items>1)draft.AddItem(&item2);
  draft.AddMoney(money).AddCOD(items?50:0);
  if(draft.HasItems()!=(items>0) || draft.GetMoney()!=money || draft.GetBody()!=body)std::exit(2);
  MailReceiver receiver(2);MailSender sender(type,1,stationery);cache.a=sa;cache.b=ra;
  uint32 delay=initial,expiration=17;bool remove=false,send=true;
  hook.OnBeforeMailDraftSendMailTo(&draft,receiver,sender,flags,delay,expiration,remove,send);
  ++count;if(delay!=expected || expiration!=17 || remove || !send)std::exit(3);
 };
 for(auto body:{std::string(),std::string("body")})for(uint32 money:{0u,12345u})
  for(int items:{0,1,2})check(items,money,body,MAIL_CHECK_MASK_NONE,MAIL_NORMAL,MAIL_STATIONERY_DEFAULT,5,5,0,items?3600:0);
 for(auto flags:{MAIL_CHECK_MASK_RETURNED,MAIL_CHECK_MASK_COD_PAYMENT})
  check(1,100,"body",flags,MAIL_NORMAL,MAIL_STATIONERY_DEFAULT,5,5,19,19);
 for(auto type:{MAIL_AUCTION,MAIL_CREATURE,MAIL_GAMEOBJECT,MAIL_CALENDAR})
  check(1,100,"body",MAIL_CHECK_MASK_NONE,type,MAIL_STATIONERY_DEFAULT,5,5,19,19);
 check(1,0,"",MAIL_CHECK_MASK_NONE,MAIL_NORMAL,MAIL_STATIONERY_GM,5,5,19,19);
 for(auto pair:{std::pair<uint32,uint32>{0,5},{5,0},{5,6}})
  check(1,0,"",MAIL_CHECK_MASK_NONE,MAIL_NORMAL,MAIL_STATIONERY_DEFAULT,pair.first,pair.second,19,19);
 check(0,0,"",MAIL_CHECK_MASK_NONE,MAIL_NORMAL,MAIL_STATIONERY_DEFAULT,5,5,19,19);
 world.delay=0;check(1,0,"",MAIL_CHECK_MASK_NONE,MAIL_NORMAL,MAIL_STATIONERY_DEFAULT,5,5,0,0);
 std::cout<<count<<" full-header actual-draft cases PASS\n";
}
"""
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)
 (root/"Mail.h").write_text(header,encoding="utf-8")
 (root/"Common.h").write_text("#pragma once\n#include <cstdint>\n#include <string>\n#include <vector>\n#include <utility>\nusing uint8=uint8_t;using uint16=uint16_t;using uint32=uint32_t;using int8=int8_t;\n")
 (root/"DatabaseEnvFwd.h").write_text("#pragma once\nusing CharacterDatabaseTransaction=void*;\n")
 (root/"ObjectGuid.h").write_text("#pragma once\n#include <cstdint>\nenum class HighGuid {Player};struct ObjectGuid{using LowType=uint32_t;LowType id;ObjectGuid(HighGuid,LowType i):id(i){} LowType GetCounter()const{return id;}bool operator<(ObjectGuid const& b)const{return id<b.id;}};\n")
 cpp=root/"mail.cpp";cpp.write_text(fixture+add+module+checks,encoding="utf-8")
 exe=root/("mail.exe" if __import__("os").name=="nt" else "mail")
 command=[a.compiler]+(["c++"] if Path(a.compiler).stem=="zig" else [])
 subprocess.run(command+["-std=c++17","-Wall","-Wextra","-Werror","-I",str(root),str(cpp),"-o",str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
