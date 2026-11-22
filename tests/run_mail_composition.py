"""Compile actual Core34 accessor + actual Naxx337 hook with engine doubles."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

PIN = "9edf437e62218be610dfc4b3d797563217644ad1"
parser = argparse.ArgumentParser()
parser.add_argument("--core", required=True)
parser.add_argument("--compiler", required=True)
args = parser.parse_args()
header = subprocess.check_output(["git", "show", PIN + ":src/server/game/Mails/Mail.h"], cwd=args.core).decode()
draft = header.split("class MailDraft", 1)[1].split("struct MailItemInfo", 1)[0]
accessor = re.search(r"bool HasItems\(\) const\s*\{[^}]+\}", draft).group()
assert "m_items.empty()" in accessor
source = (Path(__file__).resolve().parents[1] / "src/Systems/AltMailDelay.cpp").read_text(encoding="utf-8")
source = re.sub(r"^#include.*$", "", source, flags=re.M).replace(" override", "")
fixture = r"""
#include <cstdint>
#include <vector>
#include <initializer_list>
#include <iostream>
using uint32=uint32_t;
enum class HighGuid { Player };
struct ObjectGuid { using LowType=uint32; uint32 id; ObjectGuid(HighGuid,uint32 v):id(v){} };
using MailCheckMask=uint32;
constexpr int MAIL_NORMAL=0, MAIL_STATIONERY_GM=61;
constexpr uint32 MAIL_CHECK_MASK_RETURNED=1, MAIL_CHECK_MASK_COD_PAYMENT=2;
constexpr int MAILHOOK_ON_BEFORE_MAIL_DRAFT_SEND_MAIL_TO=0, CONFIG_MAIL_DELIVERY_DELAY=0;
struct MailDraft { std::vector<int> m_items; ACCESSOR };
struct MailReceiver { uint32 id=2; uint32 GetPlayerGUIDLow()const{return id;} };
struct MailSender { uint32 id=1; int type=0, stationery=0; int GetMailMessageType()const{return type;} int GetStationery()const{return stationery;} uint32 GetSenderId()const{return id;} };
struct Cache { uint32 a=5,b=5; uint32 GetCharacterAccountIdByGuid(ObjectGuid g){return g.id==1?a:b;} } cache;
auto sCharacterCache=&cache;
struct World { uint32 delay=3600; uint32 getIntConfig(int){return delay;} } world;
auto sWorld=&world;
struct MailScript { MailScript(const char*,std::initializer_list<int>){} };
""".replace("ACCESSOR", accessor)
checks = r"""
int main(){
 NaxxramasCoreAltMailDelay hook; int count=0;
 auto check=[&](int items, bool nullDraft, int type,int stationery,uint32 flags,uint32 sender,uint32 receiver,uint32 a,uint32 b,uint32 initial,uint32 expected){
  MailDraft d; d.m_items.resize(items); MailSender s; s.id=sender;s.type=type;s.stationery=stationery;
  MailReceiver r; r.id=receiver;cache.a=a;cache.b=b;
  uint32 delay=initial, expiration=17;bool remove=false,send=true;
  hook.OnBeforeMailDraftSendMailTo(nullDraft?nullptr:&d,r,s,flags,delay,expiration,remove,send);
  ++count;if(delay!=expected || expiration!=17 || remove || !send) {std::cerr<<"case "<<count<<" failed";std::exit(1);}
 };
 // Draft money/body do not participate in the hook. Empty draft cases represent
 // text-only, gold-only and text+gold; these are not native MailHandler tests.
 for(int i=0;i<3;++i) check(0,false,0,0,0,1,2,5,5,0,0);
 for(int n:{1,2,12}) check(n,false,0,0,0,1,2,5,5,0,3600);
 check(1,true,0,0,0,1,2,5,5,19,19);
 for(uint32 flags:{1u,2u,3u})check(1,false,0,0,flags,1,2,5,5,19,19);
 check(1,false,1,0,0,1,2,5,5,19,19); // system/AH type
 check(1,false,0,61,0,1,2,5,5,19,19);
 check(1,false,0,0,0,1,1,5,5,19,19);
 check(1,false,0,0,0,0,2,5,5,19,19);
 check(1,false,0,0,0,1,0,5,5,19,19);
 check(1,false,0,0,0,1,2,0,5,19,19);
 check(1,false,0,0,0,1,2,5,0,19,19);
 check(1,false,0,0,0,1,2,5,6,19,19);
 check(0,false,0,0,0,1,2,5,5,19,19);
 world.delay=0;check(1,false,0,0,0,1,2,5,5,0,0);
 std::cout<<count<<" executable hook cases PASS\n";
}
"""
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp); cpp=root/"mail.cpp"; exe=root/("mail.exe" if __import__("os").name=="nt" else "mail")
    cpp.write_text(fixture+source+checks,encoding="utf-8")
    compiler=[args.compiler]+(["c++"] if Path(args.compiler).stem=="zig" else [])
    subprocess.run(compiler+["-std=c++17","-Wall","-Wextra","-Werror",str(cpp),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
