"""A02 source-only C1/C2 drift sentinels for the exact PUBLIC pinned core.

These read source files on a disposable GitHub runner. They DO NOT prove
the owner's installed script order, native acceptance, any real DB commit,
human/SelfBot mode, actual pet birth, or permission for module/SQL changes.
"""
import os
import re
import unittest
from pathlib import Path

PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"
ROOT = Path(os.environ.get("A02_PINNED_CORE", "acore"))
FILES = {
    "dispatch": "src/server/game/Server/WorldSession.cpp",
    "hooks": "src/server/game/Scripting/ScriptMgrMacros.h",
    "scripts": "src/server/game/Scripting/ScriptMgr.h",
    "server": "src/server/game/Scripting/ScriptDefines/ServerScript.cpp",
    "server_h": "src/server/game/Scripting/ScriptDefines/ServerScript.h",
    "world_h": "src/server/game/Scripting/ScriptDefines/WorldScript.h",
    "world": "src/server/game/World/World.cpp",
    "main": "src/server/apps/worldserver/Main.cpp",
    "db": "src/server/database/Database/DatabaseWorkerPool.cpp",
    "pet": "src/server/game/Entities/Pet/Pet.cpp",
    "object": "src/server/game/Globals/ObjectMgr.cpp",
}


def compact(text):
    return " ".join(text.split())


def ordered(text, *snippets):
    """An explicitly lexical sentinel, not a C++ AST or race proof."""
    cursor = 0
    for snippet in snippets:
        at = compact(text).find(compact(snippet), cursor)
        if at < 0:
            return False
        cursor = at + len(compact(snippet))
    return True


def source(name):
    path = ROOT / FILES[name]
    if not path.is_file():
        raise AssertionError("pinned source missing: " + str(path))
    return path.read_text(encoding="utf-8")


class PinnedHandlerAndHookOrder(unittest.TestCase):
    def test_native_handler_dispatch_immediately_follows_packet_hooks(self):
        self.assertTrue(ordered(source("dispatch"),
            "if (!sScriptMgr->CanPacketReceive(this, *packet)) break;",
            "opHandle->Call(this, *packet);"))
        self.assertFalse(ordered(
            "opHandle->Call(this, *packet); if (!sScriptMgr->CanPacketReceive(this, *packet)) break;",
            "if (!sScriptMgr->CanPacketReceive(this, *packet)) break;",
            "opHandle->Call(this, *packet);"))

    def test_hook_macro_is_ordered_and_short_circuits_on_false(self):
        s = compact(source("hooks"))
        self.assertIn("for (auto const& script : ScriptRegistry<scriptType>::EnabledHooks[hookType]) { if (action) return false; }", s)
        self.assertIn("#define CALL_ENABLED_BOOLEAN_HOOKS(", s)

    def test_server_hook_entrypoint_uses_boolean_visitor(self):
        s = compact(source("server"))
        self.assertIn("CALL_ENABLED_BOOLEAN_HOOKS(ServerScript, SERVERHOOK_CAN_PACKET_RECEIVE, !script->CanPacketReceive(session, packet));", s)
        self.assertIn("if (enabledHooks.empty())", s)

    def test_hook_vector_stores_exact_server_script_pointers(self):
        s = compact(source("scripts"))
        self.assertIn("typedef std::vector<std::vector<TScript*>> EnabledHooksVector;", s)
        self.assertIn("static EnabledHooksVector EnabledHooks;", s)
        self.assertIn("EnabledHooks[v].emplace_back(script);", s)
        self.assertIn("it must not be modified after server startup.", s)

    def test_world_and_server_script_are_distinct_subclasses(self):
        self.assertIn("class ServerScript : public ScriptObject", source("server_h"))
        self.assertIn("class WorldScript : public ScriptObject", source("world_h"))
        # In a WorldScript callback 'this' is NOT the registered ServerScript*.
        # This test forbids neither runtime pointer capture nor a core patch,
        # it solely nails down the hierarchy on the public pin.

    def test_last_registered_hook_is_not_proven_by_source(self):
        # Even if the order *can* be checked, the actual last element is a
        # property of installed module registration, UNKNOWN in this checkout.
        self.assertTrue(ordered(source("scripts"),
                                "static EnabledHooksVector EnabledHooks;",
                                "EnabledHooks[v].emplace_back(script);"))
        self.assertTrue(ordered("different scripts may register later",
                                "different scripts may register later"))


class PinnedStartupAndDatabaseContract(unittest.TestCase):
    def test_pet_number_load_precedes_preinit_hook(self):
        s = source("world")
        self.assertTrue(ordered(s, "sObjectMgr->LoadPetNumber();",
                                "sScriptMgr->OnBeforeWorldInitialized();"))

    def test_script_database_load_precedes_preinit_hook(self):
        self.assertTrue(ordered(source("world"), "sScriptMgr->LoadDatabase();",
                                "sScriptMgr->OnBeforeWorldInitialized();"))

    def test_network_starts_before_onstartup(self):
        self.assertTrue(ordered(source("main"), "StartWorldNetwork(",
                                "sScriptMgr->OnStartup();"))
        self.assertFalse(ordered("sScriptMgr->OnStartup(); StartWorldNetwork(",
                                 "StartWorldNetwork(", "sScriptMgr->OnStartup();"))

    def test_directexecute_does_not_return_confirmed_execute_result(self):
        s = compact(source("db"))
        at = s.find("void DatabaseWorkerPool<T>::DirectExecute(std::string_view sql)")
        self.assertGreaterEqual(at, 0)
        body = s[at:at + 350]
        self.assertIn("connection->Execute(sql);", body)
        self.assertNotIn("return connection->Execute(sql);", body)

    def test_query_null_conflates_absent_rows_and_query_error(self):
        s = compact(source("db"))
        self.assertIn("if (!result || !result->GetRowCount() || !result->NextRow())", s)
        self.assertIn("return QueryResult(nullptr);", s)
        # A positive scalar COUNT(*) readback can distinguish success from
        # missing result on this pin; it does NOT prove no second DB writer.

    def test_pet_save_has_two_distinct_async_transaction_commits(self):
        s = source("pet")
        at = s.find("void Pet::SavePetToDB(PetSaveMode mode)")
        self.assertGreaterEqual(at, 0)
        body = s[at:at + 4200]
        self.assertGreaterEqual(body.count("CharacterDatabase.CommitTransaction(trans);"), 2)
        self.assertIn("CHAR_DEL_CHAR_PET_BY_SLOT", body)
        self.assertIn("CHAR_REP_CHAR_PET", body)

    def test_pet_number_reseed_uses_canonical_max(self):
        s = compact(source("object"))
        self.assertIn('SELECT MAX(id) FROM character_pet', s)
        self.assertIn("_hiPetNumber = fields[0].Get<uint32>() + 1;", s)
        self.assertIn("return ++_hiPetNumber;", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
