"""P1 narrow OFF-by-default second-stage Warlock portal source contract.

ONLY source assertions and synthetic branch data. Not a native C++ execution,
owner gameplay run, GO-spell DBC verification or live database probe.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/Systems/MeetingStoneProgression.cpp").read_text()
CONF = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()

HOOK = SRC.split("bool CanGameObjectGossipHello(Player* player, GameObject* go) override", 1)[1].split("\n};", 1)[0]
PILOT = HOOK.split('if (go->GetGoType() == GAMEOBJECT_TYPE_MEETINGSTONE &&',1)[1].split(
    '\n        if (go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE',1)[0]


def assert_contract(pilot=PILOT, hook=HOOK, cfg=CONF):
    assert re.search(r'^\s*NaxxramasCore\.WarlockRitual\.SecondStagePilot\.Enabled\s*=\s*0\s*$',cfg,re.M)
    assert len(re.findall(r'^\s*NaxxramasCore\.WarlockRitual\.SecondStagePilot\.Enabled\s*=',cfg,re.M))==1
    assert '"NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", false' in hook
    assert 'go->GetEntry() == WARLOCK_SECOND_PORTAL_ENTRY' in hook
    assert 'go->GetGoType() == GAMEOBJECT_TYPE_MEETINGSTONE' in hook
    assert 'constexpr uint32 WARLOCK_SECOND_PORTAL_ENTRY = 194097;' in hook
    assert 'constexpr uint32 WARLOCK_SECOND_PORTAL_CREATION_SPELL = 61993;' in hook
    assert 'constexpr uint32 WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL = 61994;' in hook
    assert 'go->GetSpellId() != WARLOCK_SECOND_PORTAL_CREATION_SPELL' in pilot
    assert '!go->GetOwnerGUID()' in pilot
    assert '!go->GetGOInfo()' in pilot
    assert 'ObjectAccessor::FindPlayer(player->GetTarget())' in pilot
    assert '!targetPlayer || targetPlayer == player ||' in pilot
    assert '!targetPlayer->IsInSameRaidWith(player)' in pilot
    assert 'go->GetGOInfo()->meetingstone.minLevel' in pilot
    assert 'player->GetLevel() < minLevel || targetPlayer->GetLevel() < minLevel' in pilot
    assert 'sSpellMgr->GetSpellInfo(WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL)' in pilot
    assert 'player->CastSpell(player, WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL, false);' in pilot
    assert 'return true;' in pilot
    assert pilot.count('CastSpell(') == 1, "only one nontriggered cast in isolated route"
    assert len(re.findall(r'^\s*NaxxramasCore\.MeetingStones\.ClassicMode\.Enabled\s*=\s*1\s*$',cfg,re.M))==1
    assert '"NaxxramasCore.MeetingStones.ClassicMode.Enabled", true' in hook
    assert 'if (!IsVanillaProgression(player))' in hook
    assert hook.find('go->GetEntry() == WARLOCK_SECOND_PORTAL_ENTRY') < hook.find(
        'go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE')
    assert pilot.find('GetSpellId()') < pilot.find('FindPlayer(') < pilot.find('minLevel') < pilot.find('CastSpell(')
    assert 'GAMEOBJECT_TYPE_SUMMONING_RITUAL' not in hook
    assert 'SetGoType(' not in hook and 'SetFlag(' not in hook
    assert 'WorldDatabase.' not in hook and 'CharacterDatabase.' not in hook
    return True


class WarlockPortalPilotContract(unittest.TestCase):
    def test_unchanged_loader_and_exact_off_config(self):
        self.assertEqual(LOADER.count('AddMeetingStoneProgressionScripts();'),1)
        self.assertTrue(assert_contract())

    def test_all_other_gameobjects_keep_original_logic(self):
        orig = HOOK.split(
            '\n        if (go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE',1)[1]
        self.assertIn('!sConfigMgr->GetOption<bool>(',orig)
        self.assertIn('"NaxxramasCore.MeetingStones.ClassicMode.Enabled", true',orig)
        self.assertIn('if (!IsVanillaProgression(player))',orig)
        self.assertIn('return false; // Hand off to AzerothCore for TBC/WotLK.',orig)
        self.assertIn('Summoning stones are currently unavailable.',orig)
        self.assertIn('return true;',orig)

    def test_invalid_pilot_cases_fail_closed_and_no_core_fallback(self):
        self.assertIn('return true;',PILOT.split('ObjectAccessor::FindPlayer(')[0])
        self.assertRegex(PILOT,re.compile(
            r'if \(!targetPlayer \|\| targetPlayer == player \|\|\s*'
            r'!targetPlayer->IsInSameRaidWith\(player\)\)\s*return true;',re.S))
        self.assertRegex(PILOT,re.compile(
            r'if \(player->GetLevel\(\) < minLevel \|\| '
            r'targetPlayer->GetLevel\(\) < minLevel\)\s*return true;'))
        self.assertTrue(PILOT.rstrip().endswith('return true;\n        }'))

    def test_synthetic_policy_matrix_not_live_events(self):
        def route(kind,entry,enabled,spawned,valid):
            if kind != 23 or entry != 194097 or not enabled:
                return "existing native/progression path"
            if not spawned or not valid:
                return "consume without cast"
            return "61994 nontriggered continuation"
        for kind,entry in ((18,194108),(23,191029),(23,194097),(11,194097)):
            self.assertEqual(route(kind,entry,False,True,True),"existing native/progression path")
        self.assertEqual(route(23,194097,True,True,True),"61994 nontriggered continuation")
        for condition in ((False,True),(True,False),(False,False)):
            self.assertEqual(route(23,194097,True,*condition),"consume without cast")
        self.assertEqual(route(23,191029,True,True,True),"existing native/progression path")

    def test_mutations_fail_source_contract(self):
        cases = (
            ("pilot toggle default ON", "NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled = 0",
             "NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled = 1","cfg"),
            ("wrong GO ID", "go->GetEntry() == WARLOCK_SECOND_PORTAL_ENTRY",
             "go->GetEntry() != WARLOCK_SECOND_PORTAL_ENTRY","hook"),
            ("wrong portal numeric ID", "WARLOCK_SECOND_PORTAL_ENTRY = 194097","WARLOCK_SECOND_PORTAL_ENTRY = 194108","hook"),
            ("missing GO type", "go->GetGoType() == GAMEOBJECT_TYPE_MEETINGSTONE",
             "go->GetGoType() == GAMEOBJECT_TYPE_SUMMONING_RITUAL","hook"),
            ("pilot accidentally ON", '"NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", false',
             '"NaxxramasCore.WarlockRitual.SecondStagePilot.Enabled", true',"hook"),
            ("no owner gate", "!go->GetOwnerGUID()","false","pilot"),
            ("wrong origin spell", "go->GetSpellId() != WARLOCK_SECOND_PORTAL_CREATION_SPELL",
             "go->GetSpellId() == WARLOCK_SECOND_PORTAL_CREATION_SPELL","pilot"),
            ("no target lookup","ObjectAccessor::FindPlayer(player->GetTarget())",
             "ObjectAccessor::FindConnectedPlayer(player->GetTarget())","pilot"),
            ("self target permitted","!targetPlayer || targetPlayer == player ||",
             "!targetPlayer ||","pilot"),
            ("no group gate","!targetPlayer->IsInSameRaidWith(player)",
             "false","pilot"),
            ("no user level gate","player->GetLevel() < minLevel || targetPlayer->GetLevel() < minLevel",
             "targetPlayer->GetLevel() < minLevel","pilot"),
            ("no target level gate","player->GetLevel() < minLevel || targetPlayer->GetLevel() < minLevel",
             "player->GetLevel() < minLevel","pilot"),
            ("wrong continuation","WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL = 61994",
             "WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL = 23598","hook"),
            ("triggered cast","WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL, false",
             "WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL, true","pilot"),
            ("missing spell existence gate","sSpellMgr->GetSpellInfo(WARLOCK_SECOND_PORTAL_CONTINUATION_SPELL)",
             "true","pilot"),
        )
        self.assertEqual(len(cases),15)
        for name,old,new,where in cases:
            with self.subTest(name=name):
                self.assertIn(old,{"pilot":PILOT,"hook":HOOK,"cfg":CONF}[where])
                kwargs={"pilot":PILOT,"hook":HOOK,"cfg":CONF}
                kwargs[where]=kwargs[where].replace(old,new,1)
                # If editing only PILOT also reflect mutation in HOOK, and vice versa,
                # so the assertion tests the meaningful altered source coherently.
                if where=="pilot": kwargs["hook"]=HOOK.replace(old,new,1)
                if where=="hook": kwargs["pilot"]=PILOT.replace(old,new,1)
                with self.assertRaises((AssertionError,ValueError)):
                    assert_contract(**kwargs)


if __name__=="__main__":
    unittest.main()
