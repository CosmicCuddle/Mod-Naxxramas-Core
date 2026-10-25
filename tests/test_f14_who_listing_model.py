"""F14 S1: executable model of the /who listing rule.

Models core WorldSession::HandleWhoOpcode (MiscHandler.cpp L220-L414 at
Grimfeather core 8daffdabe9202c228e45d833c9a1d399597a15cd) and the
proposed race predicate from docs/research/F14-WHO-LISTING-S1.md.
Nothing here compiles C++ or runs a server. The model pins the counting
contract a future module mirror must keep.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path
import importlib.util
import random
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "docs/research/F14-WHO-LISTING-S1.md"
CONF = ROOT / "conf/mod_naxxramas_core.conf.dist"
SCRIPT = ROOT / "scripts/check_f14_who_handler_fingerprint.py"

RACE_BLOODELF = 10
RACE_DRAENEI = 11
TBC_RACES = (RACE_BLOODELF, RACE_DRAENEI)
SEC_PLAYER = 0
SEC_GAMEMASTER = 2
SEC_ADMINISTRATOR = 3
MAX_LEVEL = 100
STRONG_MAX_LEVEL = 255
ALLIANCE, HORDE = 0, 1
ZONE_NAMES = {1519: "stormwind city", 1637: "orgrimmar", 3430: "eversong woods",
              3524: "azuremyst isle", 12: "elwynn forest"}


@dataclass(frozen=True)
class Row:
    """One WhoListPlayerInfo (WhoListCacheMgr.h L44-L56)."""
    guid: int
    name: str
    team: int = HORDE
    race: int = 2
    cls: int = 1
    level: int = 60
    zone: int = 1637
    guild: str = ""
    security: int = SEC_PLAYER
    visible: bool = True
    gender: int = 0


@dataclass(frozen=True)
class Observer:
    guid: int
    team: int = HORDE
    security: int = SEC_PLAYER
    two_side: bool = False         # RBAC_PERM_TWO_SIDE_WHO_LIST
    see_all_sec: bool = False      # RBAC_PERM_WHO_SEE_ALL_SEC_LEVELS
    vanilla: bool = True           # NaxxramasIpEra::IsVanillaProgression


@dataclass(frozen=True)
class Request:
    level_min: int = 0
    level_max: int = MAX_LEVEL
    name: str = ""
    guild: str = ""
    racemask: int = 0xFFFFFFFF
    classmask: int = 0xFFFFFFFF
    zones: tuple = ()
    strings: tuple = ()


@dataclass(frozen=True)
class World:
    gm_level_in_who_list: int = SEC_ADMINISTRATOR   # GM.InWhoList.Level
    max_returns: int = 49                           # MaxWhoListReturns


@dataclass(frozen=True)
class Policy:
    hide_tbc_races: bool = False   # proposed NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces
    gm_bypass: bool = True         # proposed NaxxramasCore.ExpansionRaceVisibility.GMBypass
    keep_self_row: bool = True     # owner decision O1, proposed default


def hidden(policy, observer, row):
    """Proposed rule R1-R5. True means omit the row from both counts."""
    if not policy.hide_tbc_races:                                    # R1
        return False
    if not observer.vanilla:                                         # R2
        return False
    if policy.gm_bypass and observer.security > SEC_PLAYER:          # R3
        return False
    if policy.keep_self_row and row.guid == observer.guid:           # R4 (O1)
        return False
    return row.race in TBC_RACES                                     # R5


def who(request, observer, rows, world=World(), policy=Policy(), where="after-race"):
    """HandleWhoOpcode. Returns None when the core sends nothing, else
    (displaycount, matchCount, written rows) as put at offsets 0 and 4.

    `where` places the module predicate; every placement before the
    matchCount++ must give the same packet.
    """
    if len(request.zones) > 10 or len(request.strings) > 4:          # L240, L253
        return None
    level_max = STRONG_MAX_LEVEL if request.level_max >= MAX_LEVEL else request.level_max
    name = request.name.lower()
    guild = request.guild.lower()
    strings = [s.lower() for s in request.strings]
    match = 0
    written = []
    for row in rows:
        if where == "first" and hidden(policy, observer, row):
            continue
        if row.team != observer.team and not observer.two_side:      # L296
            continue
        if not observer.see_all_sec and row.security > world.gm_level_in_who_list:  # L300
            continue
        if (observer.guid != row.guid and not row.visible) and \
                (observer.security == SEC_PLAYER or row.security > observer.security):  # L303-L305
            continue
        if row.level < request.level_min or row.level > level_max:
            continue
        if not (request.classmask & (1 << row.cls)):
            continue
        if not (request.racemask & (1 << row.race)):                 # L326
            continue
        if where == "after-race" and hidden(policy, observer, row):
            continue
        if request.zones and row.zone not in request.zones:
            continue
        if name and name not in row.name.lower():
            continue
        if guild and guild not in row.guild.lower():
            continue
        zone_name = ZONE_NAMES.get(row.zone, "")
        show = True
        for s in strings:
            if s:
                if s in row.guild.lower() or s in row.name.lower() or s in zone_name:
                    show = True
                    break
                show = False
        if not show:
            continue
        if where == "last" and hidden(policy, observer, row):
            continue
        if where == "mutant-after-increment":
            match += 1
            if hidden(policy, observer, row) or match > world.max_returns:
                continue
            written.append(row)
            continue
        match += 1                                                   # L393
        if match > world.max_returns:
            continue
        written.append(row)
    return len(written), match, tuple(written)


def corpus(seed, size=80):
    rng = random.Random(seed)
    races = [1, 2, 3, 4, 5, 6, 7, 8, 10, 11]
    rows = []
    for guid in range(1, size + 1):
        rows.append(Row(
            guid=guid,
            name="char%03d" % guid,
            team=rng.choice((ALLIANCE, HORDE)),
            race=rng.choice(races),
            cls=rng.choice((1, 2, 3, 4, 5, 7, 8, 9, 11)),
            level=rng.randint(1, 80),
            zone=rng.choice(sorted(ZONE_NAMES)),
            guild=rng.choice(("", "red", "blue", "quel")),
            security=rng.choice((SEC_PLAYER,) * 9 + (SEC_GAMEMASTER,)),
            visible=rng.random() > 0.05,
            gender=rng.randint(0, 1)))
    return rows


def random_request(rng):
    return Request(
        level_min=rng.choice((0, 10, 60)),
        level_max=rng.choice((MAX_LEVEL, 70, 80)),
        name=rng.choice(("", "char0", "char01")),
        guild=rng.choice(("", "re", "quel")),
        racemask=rng.choice((0xFFFFFFFF, 1 << RACE_BLOODELF, 1 << RACE_DRAENEI, 0b110)),
        classmask=rng.choice((0xFFFFFFFF, 1 << 2)),
        zones=rng.choice(((), (3430,), (1637, 1519))),
        strings=rng.choice(((), ("eversong",), ("quel", "blue"))))


def races(result):
    return {row.race for row in result[2]}


class StockParity(unittest.TestCase):
    """R1-R3: whenever the rule does not apply, the packet is stock."""

    def assert_stock(self, observer, policy):
        for seed in range(40):
            rows = corpus(seed)
            rng = random.Random(1000 + seed)
            for _ in range(10):
                request = random_request(rng)
                with self.subTest(seed=seed, request=request):
                    self.assertEqual(who(request, observer, rows, policy=policy),
                                     who(request, observer, rows))

    def test_switch_off_is_stock(self):
        self.assert_stock(Observer(guid=999, vanilla=True), Policy(hide_tbc_races=False))

    def test_tbc_or_later_observer_is_stock(self):
        self.assert_stock(Observer(guid=999, vanilla=False), Policy(hide_tbc_races=True))

    def test_gm_with_bypass_is_stock(self):
        gm = Observer(guid=999, security=SEC_GAMEMASTER, vanilla=True)
        self.assert_stock(gm, Policy(hide_tbc_races=True, gm_bypass=True))

    def test_broken_packets_send_nothing_either_way(self):
        rows = corpus(1)
        observer = Observer(guid=999)
        on = Policy(hide_tbc_races=True)
        for request in (Request(zones=tuple(range(11))), Request(strings=("a",) * 5)):
            self.assertIsNone(who(request, observer, rows))
            self.assertIsNone(who(request, observer, rows, policy=on))


class VanillaObserverHidesTbcRaces(unittest.TestCase):
    """R5: hidden rows leave both counts, for every query shape."""
    ON = Policy(hide_tbc_races=True)

    def test_no_tbc_race_row_and_counts_shrink_by_hidden(self):
        observer = Observer(guid=999, two_side=True)
        for seed in range(40):
            rows = corpus(seed)
            rng = random.Random(seed)
            for _ in range(10):
                request = random_request(rng)
                stock = who(request, observer, rows, world=World(max_returns=10 ** 6))
                mine = who(request, observer, rows, world=World(max_returns=10 ** 6), policy=self.ON)
                hidden_rows = [r for r in stock[2] if r.race in TBC_RACES]
                with self.subTest(seed=seed, request=request):
                    self.assertFalse(races(mine) & set(TBC_RACES))
                    self.assertEqual(mine[1], stock[1] - len(hidden_rows))
                    self.assertEqual(mine[0], mine[1])

    def test_targeted_queries_find_nothing(self):
        be = Row(guid=1, name="Sunstrider", race=RACE_BLOODELF, zone=3430, guild="Quel")
        dr = Row(guid=2, name="Velen", race=RACE_DRAENEI, team=ALLIANCE, zone=3524)
        orc = Row(guid=3, name="Thrall", race=2)
        rows = [be, dr, orc]
        observer = Observer(guid=999, two_side=True)
        for request in (Request(name="Sunstrider"), Request(name="sunst"),
                        Request(racemask=1 << RACE_BLOODELF), Request(racemask=1 << RACE_DRAENEI),
                        Request(classmask=1 << 1, zones=(3430,)), Request(guild="quel"),
                        Request(strings=("eversong",)), Request(strings=("azuremyst",)),
                        Request(name="Velen", guild="", zones=(3524,), strings=("velen",))):
            with self.subTest(request=request):
                self.assertEqual(who(request, observer, rows, policy=self.ON), (0, 0, ()))
                self.assertNotEqual(who(request, observer, rows)[1], 0)

    def test_hidden_rows_never_take_a_display_slot(self):
        observer = Observer(guid=999)
        rows = [Row(guid=g, name="h%02d" % g, race=RACE_BLOODELF if g % 4 == 0 else 2)
                for g in range(1, 81)]
        visible = [r for r in rows if r.race != RACE_BLOODELF]
        display, match, written = who(Request(), observer, rows, policy=self.ON)
        self.assertEqual(match, len(visible))            # 60 rows pass
        self.assertEqual(display, 49)                    # MaxWhoListReturns
        self.assertEqual(written, tuple(visible[:49]))   # first 49 visible, in cache order

    def test_predicate_placement_before_increment_is_free(self):
        observer = Observer(guid=999, two_side=True)
        for seed in range(30):
            rows = corpus(seed)
            rng = random.Random(seed)
            request = random_request(rng)
            results = {where: who(request, observer, rows, policy=self.ON, where=where)
                       for where in ("first", "after-race", "last")}
            with self.subTest(seed=seed):
                self.assertEqual(len(set(results.values())), 1)

    def test_filtering_after_the_increment_is_wrong(self):
        """The trap from #107: a late filter leaves matchCount too high."""
        observer = Observer(guid=999)
        rows = [Row(guid=1, name="a", race=RACE_BLOODELF), Row(guid=2, name="b")]
        good = who(Request(), observer, rows, policy=self.ON)
        bad = who(Request(), observer, rows, policy=self.ON, where="mutant-after-increment")
        self.assertEqual(good[:2], (1, 1))
        self.assertEqual(bad[:2], (1, 2))

    def test_bots_and_altbots_are_hidden_like_humans(self):
        # The cache row carries no bot flag, and the rule takes none:
        # a Random Bot or Altbot Blood Elf is the same row as a human one.
        self.assertEqual(list(Row.__dataclass_fields__),
                         ["guid", "name", "team", "race", "cls", "level", "zone",
                          "guild", "security", "visible", "gender"])
        self.assertEqual(hidden.__code__.co_argcount, 3)

    def test_faction_and_gm_filters_still_apply_first(self):
        observer = Observer(guid=999, team=HORDE)
        rows = [Row(guid=1, name="ally", team=ALLIANCE, race=1),
                Row(guid=2, name="gm", security=SEC_GAMEMASTER, visible=False, race=2)]
        self.assertEqual(who(Request(), observer, rows, policy=self.ON), (0, 0, ()))


class OpenOwnerCases(unittest.TestCase):
    """O1-O3 stay explicit; the default only follows the owner's words."""

    def setUp(self):
        self.me = Row(guid=7, name="Lirael", race=RACE_BLOODELF, zone=3430)
        self.other = Row(guid=8, name="Kael", race=RACE_BLOODELF, zone=3430)
        self.observer = Observer(guid=7, vanilla=True)

    def test_o1_own_row_kept_by_default(self):
        result = who(Request(), self.observer, [self.me, self.other], policy=Policy(hide_tbc_races=True))
        self.assertEqual(result, (1, 1, (self.me,)))
        self.assertEqual(who(Request(name="Lirael"), self.observer, [self.me],
                             policy=Policy(hide_tbc_races=True))[:2], (1, 1))

    def test_o1_strict_variant_drops_own_row_from_both_counts(self):
        strict = Policy(hide_tbc_races=True, keep_self_row=False)
        self.assertEqual(who(Request(), self.observer, [self.me, self.other], policy=strict), (0, 0, ()))

    def test_o2_other_vanilla_tbc_race_hidden_without_an_exception(self):
        result = who(Request(name="Kael"), self.observer, [self.me, self.other],
                     policy=Policy(hide_tbc_races=True))
        self.assertEqual(result, (0, 0, ()))

    def test_gm_without_bypass_is_filtered(self):
        gm = Observer(guid=999, security=SEC_GAMEMASTER)
        result = who(Request(), gm, [self.other], policy=Policy(hide_tbc_races=True, gm_bypass=False))
        self.assertEqual(result, (0, 0, ()))


class NoteContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.note = NOTE.read_text(encoding="utf-8")
        cls.conf = CONF.read_text(encoding="utf-8")

    def test_pins_recorded(self):
        for sha in ("8daffdabe9202c228e45d833c9a1d399597a15cd",
                    "dd96f2b77e3ebfa2a4726bf785525ba133f1ab61",
                    "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091",
                    "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"):
            self.assertIn(sha, self.note)

    def test_rules_and_open_cases_are_named(self):
        for token in ("R1", "R2", "R3", "R4", "R5", "O1", "O2", "O3", "O4", "O5", "O6"):
            self.assertRegex(self.note, r"\*\*%s\b" % token)

    def test_keys_added_in_s2_with_proposed_defaults(self):
        # S1 proposed these keys; S2 (CS01 #128 6398544565) adds them with
        # the same defaults, and only the F14 script reads them.
        self.assertIn("NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0", self.note)
        for line in ("NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0",
                     "NaxxramasCore.ExpansionRaceVisibility.GMBypass = 1"):
            self.assertEqual(self.conf.splitlines().count(line), 1, line)
        readers = [path.name for path in list((ROOT / "src").rglob("*.cpp")) + list((ROOT / "src").rglob("*.h"))
                   if "\"NaxxramasCore.ExpansionRaceVisibility." in path.read_text(encoding="utf-8")]
        self.assertEqual(readers, ["WhoListing.cpp"])

    def test_no_playerbots_scope_key(self):
        keys = re.findall(r"NaxxramasCore\.ExpansionRaceVisibility\.\w+", self.note)
        self.assertEqual(sorted(set(keys)), ["NaxxramasCore.ExpansionRaceVisibility.GMBypass",
                                             "NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces"])

    def test_fingerprint_matches_note(self):
        spec = importlib.util.spec_from_file_location("f14fp", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn(module.EXPECTED_HANDLER_SHA256, self.note)
        self.assertIn(module.EXPECTED_OPCODE_SHA256, self.note)
        self.assertEqual(module.REVIEWED_CORE, "8daffdabe9202c228e45d833c9a1d399597a15cd")

    def test_model_defaults_match_proposal(self):
        self.assertFalse(Policy().hide_tbc_races)
        self.assertTrue(Policy().gm_bypass)
        self.assertEqual(World(), World(gm_level_in_who_list=SEC_ADMINISTRATOR, max_returns=49))


if __name__ == "__main__":
    unittest.main()
