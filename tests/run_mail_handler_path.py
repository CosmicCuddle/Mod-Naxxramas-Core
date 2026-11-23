"""Actual Core34 HandleSendMail -> MailDraft -> Naxx hook -> queue handoff.

Packet extraction, inventory/DB/engine/script registry are explicit doubles.
No real packet codec, database commit, Worldserver link or owner state.
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

PIN = "9edf437e62218be610dfc4b3d797563217644ad1"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--core", required=True)
parser.add_argument("--compiler", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]


def read(path):
    return subprocess.check_output(["git", "show", PIN + ":" + path], cwd=args.core).decode("utf-8")


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


header = read("src/server/game/Mails/Mail.h")
mail = read("src/server/game/Mails/Mail.cpp")
handler = read("src/server/game/Handlers/MailHandler.cpp")
shared = read("src/server/shared/SharedDefines.h")
enums = "\n".join(re.search(r"enum " + name + r"\s*\{[^}]+\};", shared).group()
                  for name in ("MailResponseType", "MailResponseResult"))
methods = "\n".join(function(mail, signature) for signature in (
    "MailSender::MailSender(Player*", "MailDraft& MailDraft::AddItem(",
    "void MailDraft::deleteIncludedItems(", "void MailDraft::SendMailTo("))
methods += "\n" + "\n".join(function(handler, signature) for signature in (
    "bool WorldSession::CanOpenMailBox(", "void WorldSession::HandleSendMail("))
module = re.sub(r"^#include.*$", "", (root / "src/Systems/AltMailDelay.cpp").read_text(encoding="utf-8"),
                flags=re.M).replace(" override", "")
bridge = r'''
NaxxramasCoreAltMailDelay hook;
bool enableCustom = true, allowSend = true;
unsigned admissionCalls = 0, draftCalls = 0;
bool draftHadItems = false;
uint32 draftMoney = 0, draftCOD = 0, baselineDelay = 0;
struct ScriptMgr {
    bool OnPlayerCanSendMail(Player*, ObjectGuid, ObjectGuid, std::string&, std::string&, uint32&, uint32&, Item*) {
        ++admissionCalls; return allowSend;
    }
    void OnBeforeMailDraftSendMailTo(MailDraft* draft, MailReceiver const& receiver, MailSender const& sender,
                                   MailCheckMask& flags, uint32& delay, uint32& expiration, bool& remove, bool& send) {
        ++draftCalls; draftHadItems = draft->HasItems(); draftMoney = draft->GetMoney(); draftCOD = draft->GetCOD();
        baselineDelay = delay;
        if (enableCustom) hook.OnBeforeMailDraftSendMailTo(draft, receiver, sender, flags, delay, expiration, remove, send);
    }
} scriptMgr;
auto sScriptMgr = &scriptMgr;
'''
checks = (root / "tests/mail_handler_path_checks.hpp").read_text(encoding="utf-8")
with tempfile.TemporaryDirectory(prefix="mail-handler-") as temporary:
    path = Path(temporary)
    (path / "Mail.h").write_text(header, encoding="utf-8")
    (path / "Common.h").write_text(
        "#pragma once\n#include <cstdint>\n#include <string>\n#include <vector>\n#include <utility>\n"
        "using uint8=uint8_t;using uint16=uint16_t;using uint32=uint32_t;using uint64=uint64_t;"
        "using int8=int8_t;using int32=int32_t;\n", encoding="utf-8")
    (path / "DatabaseEnvFwd.h").write_text(
        "#pragma once\n#include <memory>\nstruct Transaction;"
        "using CharacterDatabaseTransaction=std::shared_ptr<Transaction>;\n", encoding="utf-8")
    (path / "ObjectGuid.h").write_text(r'''
#pragma once
#include <cstdint>
#include <string>
enum class HighGuid { Player };
struct ObjectGuid {
    using LowType = uint32_t;
    LowType id = 0;
    ObjectGuid() = default;
    ObjectGuid(HighGuid, LowType value) : id(value) { }
    template<HighGuid H> static ObjectGuid Create(LowType value) { return ObjectGuid(H, value); }
    LowType GetCounter() const { return id; }
    explicit operator bool() const { return id != 0; }
    bool IsGameObject() const { return id == 900; }
    bool IsAnyTypeCreature() const { return id == 901; }
    std::string ToString() const { return std::to_string(id); }
    bool operator==(ObjectGuid other) const { return id == other.id; }
    bool operator<(ObjectGuid other) const { return id < other.id; }
};
''', encoding="utf-8")
    source = path / "handler.cpp"
    fixture = (root / "tests/mail_handler_doubles.hpp").read_text(encoding="utf-8")
    source.write_text('#include "Mail.h"\n' + enums + fixture + module + bridge + methods + '\n' + checks,
                      encoding="utf-8")
    binary = path / ("handler.exe" if __import__("os").name == "nt" else "handler")
    compiler = [args.compiler] + (["c++"] if Path(args.compiler).stem == "zig" else [])
    subprocess.run(compiler + ["-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(path),
                               str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
