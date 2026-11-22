"""Compile actual Mail.h/AddItem/SendMailTo/deleteIncludedItems + Naxx hook.
DB, clock, player/cache and template generation are explicit doubles; no live DB.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
PIN="9edf437e62218be610dfc4b3d797563217644ad1"
p=argparse.ArgumentParser();p.add_argument("--core",required=True);p.add_argument("--compiler",required=True);p.add_argument("--verify-old-baseline-fails",action="store_true");a=p.parse_args()
def read(path):return subprocess.check_output(["git","show",PIN+":"+path],cwd=a.core).decode("utf-8")
header=read("src/server/game/Mails/Mail.h");mail=read("src/server/game/Mails/Mail.cpp")
def method(signature):
 start=mail.index(signature);end=mail.index("\n}",start)+2;return mail[start:end]
methods="\n".join(method(s) for s in ("MailDraft& MailDraft::AddItem(","void MailDraft::deleteIncludedItems(","void MailDraft::SendMailTo(","void MailDraft::SendReturnToSender("))
root_source=Path(__file__).resolve().parents[1]
module_source=(subprocess.check_output(["git","show","80e9de1c39a6dc995188a80c31a5e785d0f2a6f9:src/Systems/AltMailDelay.cpp"],cwd=root_source).decode("utf-8") if a.verify_old_baseline_fails else (root_source/"src/Systems/AltMailDelay.cpp").read_text(encoding="utf-8"))
module=re.sub(r"^#include.*$","",module_source,flags=re.M).replace(" override","")
fixture=(root_source/"tests/mail_send_path_doubles.hpp").read_text(encoding="utf-8")
bridge=r"""
NaxxramasCoreAltMailDelay hook;bool enableCustom=true;
struct ScriptMgr {void OnBeforeMailDraftSendMailTo(MailDraft* d,MailReceiver const& r,MailSender const& s,MailCheckMask& flags,uint32& delay,uint32& expiration,bool& remove,bool& send){if(enableCustom)hook.OnBeforeMailDraftSendMailTo(d,r,s,flags,delay,expiration,remove,send);}} scriptMgr;
auto sScriptMgr=&scriptMgr;
"""
checks=r"""
int main(){int count=0;
for(bool online:{false,true})for(bool custom:{false,true})for(int n:{0,1,2})for(uint32 money:{0u,12345u})for(auto body:{std::string(),std::string("body")}){
 Player receiver;ObjectAccessor::online=online?&receiver:nullptr;enableCustom=custom;
 MailDraft draft("subject",body);for(int i=0;i<n;++i)draft.AddItem(new Item(100+i));draft.AddMoney(money);
 auto tx=std::make_shared<Transaction>();draft.SendMailTo(tx,MailReceiver(2),MailSender(MAIL_NORMAL,1));
 uint32 expected=1000+(custom&&n?3600:0);
 if(tx->rows.size()!=size_t(1+n)||tx->rows[0].values[10]!=std::to_string(expected)||tx->rows[0].values[11]!=std::to_string(money)||tx->rows[0].values[7]!=body||draft.HasItems())return 1;
 if(online&&(receiver.mails.size()!=1||receiver.mails[0]->deliver_time!=expected||receiver.items.size()!=size_t(n)))return 2;
 ++count;
}
ObjectAccessor::online=nullptr;
for(auto type:{MAIL_NORMAL,MAIL_AUCTION,MAIL_CREATURE,MAIL_GAMEOBJECT})for(auto flags:{MAIL_CHECK_MASK_RETURNED,MAIL_CHECK_MASK_COD_PAYMENT}){
 enableCustom=true;MailDraft draft("subject","body");draft.AddItem(new Item(100));auto tx=std::make_shared<Transaction>();draft.SendMailTo(tx,MailReceiver(2),MailSender(type,1),flags,19);
 if(tx->rows[0].values[10]!="1019"||tx->rows[0].values[13]!=std::to_string(int(flags)))return 3;++count;
}
for(int n:{0,1,2}){
 MailDraft draft("return","body");for(int i=0;i<n;++i)draft.AddItem(new Item(200+i));draft.AddMoney(123);
 auto tx=std::make_shared<Transaction>();draft.SendReturnToSender(5,1,2,tx);
 bool found=false;for(auto const& row:tx->rows)if(row.kind==CHAR_INS_MAIL){found=true;if(row.values.at(10)!="1000"||row.values.at(13)!=std::to_string(int(MAIL_CHECK_MASK_RETURNED)))return 4;}
 if(!found||draft.HasItems())return 5;++count;
}
std::cout<<count<<" actual SendMailTo source cases PASS\n";}
"""
with tempfile.TemporaryDirectory() as tmp:
 r=Path(tmp);(r/"Mail.h").write_text(header,encoding="utf-8")
 (r/"Common.h").write_text("#pragma once\n#include <cstdint>\n#include <string>\n#include <vector>\n#include <utility>\nusing uint8=uint8_t;using uint16=uint16_t;using uint32=uint32_t;using int8=int8_t;\n")
 (r/"DatabaseEnvFwd.h").write_text("#pragma once\n#include <memory>\nstruct Transaction;using CharacterDatabaseTransaction=std::shared_ptr<Transaction>;\n")
 (r/"ObjectGuid.h").write_text("#pragma once\n#include <cstdint>\nenum class HighGuid{Player};struct ObjectGuid{using LowType=uint32_t;LowType id;ObjectGuid(HighGuid,LowType i):id(i){}template<HighGuid H>static ObjectGuid Create(LowType id){return ObjectGuid(H,id);}LowType GetCounter()const{return id;}bool operator<(ObjectGuid const& b)const{return id<b.id;}};\n")
 cpp=r/"send.cpp";cpp.write_text(fixture+module+bridge+methods+checks,encoding="utf-8");exe=r/("send.exe" if __import__("os").name=="nt" else "send")
 command=[a.compiler]+(["c++"] if Path(a.compiler).stem=="zig" else [])
 subprocess.run(command+["-std=c++17","-Wall","-Wextra","-Werror","-I",str(r),str(cpp),"-o",str(exe)],check=True)
 result=subprocess.run([str(exe)])
 if a.verify_old_baseline_fails:
  assert result.returncode == 1, "old baseline must fail delivery-field matrix, not compilation or another check"
  print("Historical main hook reproduces attachment-free custom-delay regression")
 else:
  result.check_returncode()
