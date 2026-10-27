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
PLAYERBOTS_ROOT = Path(os.environ.get("A02_PINNED_PLAYERBOTS", "playerbots"))
PLAYERBOTS_PIN = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"
PLAYERBOTS_FILES = {
    "scripts": "src/Script/Playerbots.cpp",
    "secure": "src/Script/PlayerbotsSecureLogin.cpp",
    "afk": "src/Script/PlayerbotsSelfBotAfk.cpp",
    "manager": "src/Bot/PlayerbotMgr.cpp",
    "manager_h": "src/Bot/PlayerbotMgr.h",
    "ai": "src/Bot/PlayerbotAI.cpp",
}

FILES = {
    "dispatch": "src/server/game/Server/WorldSession.cpp",
    "opcodes": "src/server/game/Server/Protocol/Opcodes.cpp",
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


def playerbots_source(name):
    path = PLAYERBOTS_ROOT / PLAYERBOTS_FILES[name]
    if not path.is_file():
        raise AssertionError("pinned public Playerbots source missing: " + str(path))
    return path.read_text(encoding="utf-8")


class PinnedHandlerAndHookOrder(unittest.TestCase):
    def test_native_handler_call_is_adjacent_after_accepted_packet_hooks(self):
        # Lexical source-drift guard: none of the four stock dispatch branches
        # may insert code between the positive hook result and native Call.
        s = source("dispatch")
        guard = re.compile(
            r"if\s*\(!sScriptMgr->CanPacketReceive\(this,\s*\*packet\)\)"
            r"\s*break;\s*opHandle->Call\(this,\s*\*packet\);"
        )
        self.assertEqual(s.count("if (!sScriptMgr->CanPacketReceive(this, *packet))"), 4)
        self.assertEqual(len(guard.findall(s)), 4)
        self.assertIsNone(guard.search(
            "if (!sScriptMgr->CanPacketReceive(this, *packet)) "
            "break; InterposedWriter(); opHandle->Call(this, *packet);"
        ))

    def test_three_pet_opcode_handlers_keep_expected_status_and_threads(self):
        # A change in any native opcode routing must invalidate C1 assumptions.
        s = source("opcodes")
        for opcode, processing, handler in (
            ("CMSG_PET_SPELL_AUTOCAST", "PROCESS_INPLACE", "HandlePetSpellAutocastOpcode"),
            ("CMSG_PET_ACTION", "PROCESS_THREADSAFE", "HandlePetAction"),
            ("CMSG_PET_SET_ACTION", "PROCESS_THREADUNSAFE", "HandlePetSetAction"),
        ):
            with self.subTest(opcode=opcode):
                pattern = (
                    r"(?m)^\s*/\*0x[0-9A-Fa-f]+\*/\s*DEFINE_HANDLER\(\s*"
                    + re.escape(opcode) + r"\s*,\s*STATUS_LOGGEDIN\s*,\s*"
                    + re.escape(processing) + r"\s*,\s*&WorldSession::"
                    + re.escape(handler) + r"\s*\);"
                )
                self.assertEqual(len(re.findall(pattern, s)), 1)

    def test_map_and_world_session_filters_keep_packet_routing(self):
        s = source("dispatch")
        m = re.search(
            r"(?ms)^bool MapSessionFilter::Process\(WorldPacket\* packet\)"
            r"\s*\{(.*?)^\}", s
        )
        w = re.search(
            r"(?ms)^bool WorldSessionFilter::Process\(WorldPacket\* packet\)"
            r"\s*\{(.*?)^\}", s
        )
        self.assertIsNotNone(m)
        self.assertIsNotNone(w)
        self.assertTrue(ordered(m.group(1),
            "if (opHandle->ProcessingPlace == PROCESS_INPLACE) return true;",
            "if (opHandle->ProcessingPlace == PROCESS_THREADUNSAFE) return false;",
            "return player->IsInWorld();"))
        self.assertTrue(ordered(w.group(1),
            "if (opHandle->ProcessingPlace == PROCESS_INPLACE) return true;",
            "if (opHandle->ProcessingPlace == PROCESS_THREADUNSAFE) return true;",
            "return !player->IsInWorld();"))
        # Thread affinity is CONDITIONAL on caller and session state.
        # This check does not certify ownership under eight map workers.

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
        self.assertIn("must not be modified", s)
        self.assertIn("after server startup.", s)

    def test_world_and_server_script_are_distinct_subclasses(self):
        self.assertIn("class ServerScript : public ScriptObject", source("server_h"))
        self.assertIn("class WorldScript : public ScriptObject", source("world_h"))
        # In a WorldScript callback 'this' is NOT the registered ServerScript*.
        # This test forbids neither runtime pointer capture nor a core patch,
        # it solely nails down the hierarchy on the public pin.


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
        # Do not use an arbitrary character window that can truncate the
        # second canonical-row commit as the upstream function grows.
        match = re.search(
            r"(?ms)^void Pet::SavePetToDB\(PetSaveMode mode\)\s*\{"
            r"(?P<body>.*?)^void Pet::DeleteFromDB\(", s
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertGreaterEqual(body.count("CharacterDatabase.CommitTransaction(trans);"), 2)
        self.assertIn("CHAR_DEL_CHAR_PET_BY_SLOT", body)
        self.assertIn("CHAR_REP_CHAR_PET", body)

    def test_pet_number_reseed_uses_canonical_max(self):
        s = compact(source("object"))
        self.assertIn('SELECT MAX(id) FROM character_pet', s)
        self.assertIn("_hiPetNumber = fields[0].Get<uint32>() + 1;", s)
        self.assertIn("return ++_hiPetNumber;", s)


class PinnedPlayerbotsC1C3Limitations(unittest.TestCase):
    def test_three_known_playerbots_packet_hooks_are_explicitly_registered(self):
        scripts = playerbots_source("scripts")
        self.assertIn(
            'SERVERHOOK_CAN_PACKET_RECEIVE', scripts
        )
        self.assertIn("new PlayerbotsServerScript();", scripts)
        self.assertIn("AddPlayerbotsSecureLoginScripts();", scripts)
        self.assertIn("AddPlayerbotsSelfBotAfkScripts();", scripts)
        for path, name, opcode in (
            ("secure", "PlayerbotsSecureLoginServerScript", "CMSG_PLAYER_LOGIN"),
            ("afk", "PlayerbotsSelfBotAfkServerScript", "CMSG_LOGOUT_REQUEST"),
        ):
            with self.subTest(script=name):
                body = playerbots_source(path)
                self.assertIn("class " + name + " : public ServerScript", body)
                self.assertIn("SERVERHOOK_CAN_PACKET_RECEIVE", body)
                self.assertIn("packet.GetOpcode() != " + opcode, body)
        # Known source registrations, NOT a complete installed module registry.

    def test_playerbots_prehandler_may_forward_packet_before_native_handler(self):
        scripts = compact(playerbots_source("scripts"))
        at = scripts.find("bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override")
        self.assertGreaterEqual(at, 0)
        section = scripts[at:at + 350]
        self.assertTrue(ordered(section,
            "if (Player* player = session->GetPlayer())",
            "if (PlayerbotMgr* playerbotMgr = GET_PLAYERBOT_MGR(player))",
            "playerbotMgr->HandleMasterIncomingPacket(packet);",
            "return true;"))
        manager = compact(playerbots_source("manager"))
        self.assertIn("void PlayerbotMgr::HandleMasterIncomingPacket(WorldPacket const& packet)", manager)
        ai = compact(playerbots_source("ai"))
        self.assertIn("masterIncomingPacketHandlers.AddPacket(packet);", ai)
        # It may enqueue bot work BEFORE native handling. This is not
        # proof that a bot wrote to the human Hunter's pet.

    def test_realplayer_lookup_is_not_positive_threadsafe_human_proof(self):
        manager = compact(playerbots_source("manager"))
        head = manager.index("PlayerbotAI* PlayerbotsMgr::GetPlayerbotAI(Player* player)")
        end = manager.index("PlayerbotMgr* PlayerbotsMgr::GetPlayerbotMgr(", head)
        body = manager[head:end]
        self.assertIn("if (!(sPlayerbotAIConfig.Enabled) || !player)", body)
        self.assertIn("return nullptr;", body)
        self.assertIn("_playerbotsAIMap.find(player->GetGUID());", body)
        self.assertNotIn("lock_guard", body)
        self.assertNotIn("shared_lock", body)
        self.assertIn("std::unordered_map<ObjectGuid, PlayerbotAIBase*> _playerbotsAIMap;",
                      compact(playerbots_source("manager_h")))
        ai = compact(playerbots_source("ai"))
        self.assertIn("return player && !GET_PLAYERBOT_AI(player);", ai)
        self.assertIn("return botAI && botAI->GetMaster() == player;", ai)
        # Null may also mean Playerbots.Enabled=false. No safe arbitrary
        # map-worker read or positive attested human mode follows.

    def test_selfbot_can_attach_and_detach_while_client_player_exists(self):
        manager = compact(playerbots_source("manager"))
        at = manager.index('if (!strcmp(cmd, "self"))')
        end = manager.index('if (!strcmp(cmd, "lookup"))', at)
        self_command = manager[at:end]
        self.assertTrue(ordered(self_command,
            "if (GET_PLAYERBOT_AI(master))",
            "delete GET_PLAYERBOT_AI(master);",
            "else if (sPlayerbotAIConfig.SelfBotLevel == 0)",
            "PlayerbotsMgr::instance().AddPlayerbotData(master, true);",
            "GET_PLAYERBOT_AI(master)->SetMaster(master);"))
        self.assertIn("ASSERT(_playerbotsAIMap.emplace(player->GetGUID(), botAI).second);", manager)
        ai = compact(playerbots_source("ai"))
        self.assertIn("PlayerbotsMgr::instance().RemovePlayerBotData(bot->GetGUID(), true);", ai)
        # Config only gates attachment when no AI exists; neither normal
        # client login nor a config value proves no attached SelfBot.

if __name__ == "__main__":
    unittest.main(verbosity=2)
