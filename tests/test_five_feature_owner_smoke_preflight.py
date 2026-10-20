"""Source-only five-feature S5 preflight contract, NOT a Worldserver/DB test."""
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

CONF = read("conf/mod_naxxramas_core.conf.dist")
LOADER = read("src/NaxxramasCore_loader.cpp")
SHADE = read("src/Events/HallowsEndShadeOfTheHorseman.cpp")
SHADE_SQL = read("data/sql/db-world/2026_09_21_00_event_script_overrides.sql")
EP_INSTALL = read("docs/install/2026_10_13_00_ep_tower_lock_module_bind.sql")
EP_ROLLBACK = read("docs/rollback/2026_10_13_00_ep_tower_lock_module_unbind.sql")
GFPP = read("src/Systems/BotRaidConsumables.cpp")
QUEST = read("src/Systems/QuestLootProtection.cpp")
DOC = read("docs/test/five-feature-integrated-owner-smoke-preflight-2026-10-20.md")

FLAGS = (
    "NaxxramasCore.BotConsumables.HunterAmmo.Enabled",
    "NaxxramasCore.QuestLootProtection.Enabled",
    "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled",
    "NaxxramasCore.HallowsEnd.SoloFire.Enabled",
)

def invalid_sql_statements_in_code_fences(markdown: str) -> list[str]:
    """Reject mutating statements in SQL or unlabeled Markdown code fences.

    The owner preflight must remain read-only. Accept case-insensitive SQL
    info strings, indented fences, both fence markers and longer fences.
    A dangling SQL/unlabeled fence fails closed instead of hiding its content.
    Explanatory text outside a fence and SQL comment-only lines are ignored.
    This deliberately conservative guard is not a general SQL parser.
    """
    forbidden = re.compile(
        r"\b(?:INSERT|UPDATE|DELETE|DROP|TRUNCATE|CREATE|ALTER|REPLACE)\b",
        re.IGNORECASE,
    )
    opener = re.compile(r"^[ \t]*(?P<fence>(?:\x60{3,}|~{3,}))[ \t]*(?P<info>[^\r\n]*)$")
    matches: list[str] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        match = opener.fullmatch(lines[index])
        if not match:
            index += 1
            continue
        fence = match.group("fence")
        info = match.group("info").strip()
        language = info.split(None, 1)[0].lower() if info else ""
        check = language in ("", "sql", "mysql", "mariadb")
        # Closing fence must use the same marker and at least the opening
        # number of repeated characters, with only optional whitespace.
        closing = re.compile(
            r"^[ \t]*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$"
        )
        index += 1
        content: list[str] = []
        closed = False
        while index < len(lines):
            if closing.fullmatch(lines[index]):
                index += 1
                closed = True
                break
            content.append(lines[index])
            index += 1
        if not check:
            continue
        sql = "\n".join(
            line for line in content if not line.lstrip().startswith("--")
        )
        if not closed:
            matches.append("UNTERMINATED SQL FENCE:\n" + sql)
        elif forbidden.search(sql):
            matches.append(sql)
    return matches

AUTOCACHE_TABLE_NAME = "mod_naxxramas_hunter_pet_autocast"


def unsafe_autocast_auto_migrations(root: Path) -> list[Path]:
    """Find A02 cache SQL in paths scanned by the pinned module updater.

    Grimfeather 8daffda UpdateFetcher.cpp:157-185 initially selects module
    data/sql first-level directories containing the lower-case database
    token "characters"; GetFileList / FillFileListRecursively (approx. 70-104)
    then searches their descendants to MAX_DEPTH=10. Scan ALL descendant
    levels here conservatively, so a deeper future layout also fails closed.
    The file's "DO NOT APPLY" comment cannot disable updater discovery.
    This is A02-schema-specific, not a blanket SQL deployment validator.
    """
    sql_dir = root / "data" / "sql"
    if not sql_dir.is_dir():
        return []
    matches = []
    for child in sql_dir.iterdir():
        if not child.is_dir() or "characters" not in child.name:
            continue
        for sql in child.rglob("*.sql"):
            if sql.is_file() and AUTOCACHE_TABLE_NAME in sql.read_text(
                encoding="utf-8", errors="replace"
            ).lower():
                matches.append(sql)
    return sorted(matches)


class ReadOnlyFiveFeaturePreflight(unittest.TestCase):
    def test_exact_optional_flags_start_disabled_in_candidate_dist(self):
        for flag in FLAGS:
            with self.subTest(flag=flag):
                matches = re.findall(
                    rf"(?m)^\s*{re.escape(flag)}\s*=\s*(\d+)\s*$", CONF
                )
                self.assertEqual(matches, ["0"])

    def test_multiplier_is_config_value_not_an_enable_flag(self):
        self.assertRegex(
            CONF, r"(?m)^NaxxramasCore\.HallowsEnd\.SoloFire\.PeriodMultiplier\s*=\s*3\s*$"
        )
        self.assertIn("one real player", DOC.lower())

    def test_loader_still_registers_all_required_module_hooks(self):
        for method in (
            "AddBotRaidConsumablesScripts();",
            "AddQuestLootProtectionScripts();",
            "AddNaxxramasEasternPlaguelandsTowerLockScripts();",
            "AddHallowsEndShadeOfTheHorsemanScripts();",
        ):
            with self.subTest(method=method):
                self.assertEqual(LOADER.count(method), 2)  # declaration + call

    def test_source_contract_includes_actual_quest_and_gfpp_hooks(self):
        self.assertIn("CMSG_AUTOSTORE_LOOT_ITEM", QUEST)
        self.assertIn("NaxxramasCore.QuestLootProtection.Enabled", QUEST)
        self.assertIn("NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled", GFPP)
        self.assertIn("OneShotFireProtection", GFPP)

    def test_shade_sql_maps_exact_npc_to_registered_script(self):
        self.assertIn("RegisterCreatureAI(", SHADE)
        self.assertIn("npc_naxxramas_hallows_end_soh", SHADE)
        self.assertRegex(
            SHADE_SQL,
            r"(?s)UPDATE `creature_template`\s+SET `ScriptName`\s*=\s*"
            r"'npc_naxxramas_hallows_end_soh'\s+WHERE `entry`\s*=\s*23543\s*;",
        )
        self.assertNotIn("23686", SHADE_SQL)

    def test_ep_bind_is_explicit_manual_and_rollback_is_scoped(self):
        self.assertIn("MANUAL, OWNER-APPROVED INSTALL ONLY", EP_INSTALL)
        self.assertIn("WHERE `TypeId` = 6", EP_INSTALL)
        self.assertIn("AND `ScriptName` = 'outdoorpvp_ep'", EP_INSTALL)
        self.assertIn("SET `ScriptName` = 'outdoorpvp_naxxramas_ep_lock'", EP_INSTALL)
        self.assertIn("SET `ScriptName` = 'outdoorpvp_ep'", EP_ROLLBACK)
        self.assertIn("AND `ScriptName` = 'outdoorpvp_naxxramas_ep_lock'", EP_ROLLBACK)

    def test_doc_has_read_only_queries_and_no_mutating_sql(self):
        self.assertIn("SELECT `entry`, `ScriptName`", DOC)
        self.assertIn("SELECT `TypeId`, `ScriptName`", DOC)
        self.assertIn("SELECT", DOC)
        self.assertEqual(invalid_sql_statements_in_code_fences(DOC), [])

    def test_read_only_sql_guard_rejects_mixed_case_mutations(self):
        for sql in (
            "delete from pet_spell;",
            "UPDATE `character_pet` SET `name` = 'x';",
            "Insert Into bag VALUES (1);",
            "CREATE table new_cache (id int);",
            "drop TABLE cache;",
        ):
            with self.subTest(sql=sql):
                sample = "```sql\n" + sql + "\n```\n"
                self.assertNotEqual(
                    invalid_sql_statements_in_code_fences(sample), [])

    def test_sql_guard_rejects_alternate_fence_case_and_indentation(self):
        for sample in (
            "\x60\x60\x60SQL\nDELETE FROM pet_spell;\n\x60\x60\x60\n",
            "\x60\x60\x60Sql\nCrEaTe table x (id INT);\n\x60\x60\x60\n",
            "   \x60\x60\x60sql\nALTER TABLE pet_spell ADD a INT;\n   \x60\x60\x60\n",
            "\t\x60\x60\x60MYSQL\nDROP TABLE x;\n\t\x60\x60\x60\n",
            "  ~~~~mariadb\nTRUNCATE TABLE pet_spell;\n  ~~~~\n",
            "\x60\x60\x60\x60SQL\nUPDATE pet_spell SET active = 1;\n\x60\x60\x60\x60\n",
            "\x60\x60\x60\nINSERT INTO pet_spell VALUES (1);\n\x60\x60\x60\n",
        ):
            with self.subTest(sample=sample):
                self.assertNotEqual(invalid_sql_statements_in_code_fences(sample), [])

    def test_sql_guard_fails_closed_on_unterminated_sql_fence(self):
        for sample in (
            "\x60\x60\x60SQL\nSELECT * FROM character_pet;\n",
            "  ~~~mysql\nSELECT * FROM pet_spell;\n",
        ):
            with self.subTest(sample=sample):
                self.assertNotEqual(invalid_sql_statements_in_code_fences(sample), [])

    def test_sql_guard_allows_case_variant_select_only_and_prose(self):
        sample = (
            "Explanation: CREATE TABLE and DROP are mentioned in prose.\n"
            "  \x60\x60\x60SQL\n-- NEVER UPDATE pet_spell\n"
            "select spell, active from pet_spell;\n  \x60\x60\x60\n"
            "~~~mysql\n-- delete from cache\nSELECT id FROM character_pet;\n~~~\n"
        )
        self.assertEqual(invalid_sql_statements_in_code_fences(sample), [])

    def test_read_only_sql_guard_ignores_explanatory_text(self):
        sample = ("Discussion of CREATE TABLE and DELETE FROM is prose.\n"
                  "```sql\n-- Do not run INSERT; read only\n"
                  "select entry, ScriptName from creature_template;\n```\n")
        self.assertEqual(invalid_sql_statements_in_code_fences(sample), [])

    def test_unapproved_hunter_cache_schema_not_automatically_discoverable(self):
        self.assertEqual(
            unsafe_autocast_auto_migrations(ROOT), [],
            "A02 cache schema MUST stay outside module data/sql db-characters folders "
            "until the owner has expressly approved a backed-up SQL migration.",
        )

    def test_auto_updater_finds_even_commented_no_apply_sql(self):
        # The pinned UpdateFetcher only examines filesystem paths. Comments
        # do NOT prevent the database updater from applying CREATE TABLE.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for dirname in ("db-characters", "db_characters"):
                parent = root / "data" / "sql" / dirname
                parent.mkdir(parents=True)
                (parent / "never_auto.sql").write_text(
                    "-- DO NOT APPLY\\n"
                    "CREATE TABLE " + AUTOCACHE_TABLE_NAME + " (id INT);\\n",
                    encoding="utf-8",
                )
            self.assertEqual(len(unsafe_autocast_auto_migrations(root)), 2)

    def test_auto_updater_recursively_discovers_unapproved_nested_sql(self):
        # Pinned core's FillFileListRecursively scans nested MODULE updates.
        # Old non-recursive test incorrectly returned [] for all examples.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsafe = (
                "db-characters/updates/2026_10_20_cache.sql",
                "db_characters/archive/2026/10/cache.sql",
                "db-characters/updates/deep/one/two/three/four/cache.sql",
            )
            for relative in unsafe:
                path = root / "data" / "sql" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "-- DO NOT APPLY\nCREATE TABLE " +
                    AUTOCACHE_TABLE_NAME.upper() + " (id INT);\n",
                    encoding="utf-8",
                )
            found = unsafe_autocast_auto_migrations(root)
            self.assertEqual(
                {p.relative_to(root / "data" / "sql").as_posix() for p in found},
                set(unsafe),
            )

    def test_auto_updater_does_not_scan_unrelated_first_level_sql_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "data" / "sql" / "db-world" / "updates"
            parent.mkdir(parents=True)
            (parent / "unrelated.sql").write_text(
                "CREATE TABLE " + AUTOCACHE_TABLE_NAME + " (id INT);",
                encoding="utf-8",
            )
            self.assertEqual(unsafe_autocast_auto_migrations(root), [])

    def test_owner_approved_manual_sql_location_is_not_auto_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "docs" / "install"
            parent.mkdir(parents=True)
            (parent / "hunter_pet_autocast_cache_manual.sql").write_text(
                "CREATE TABLE " + AUTOCACHE_TABLE_NAME + " (id INT);",
                encoding="utf-8",
            )
            self.assertEqual(unsafe_autocast_auto_migrations(root), [])

    def test_no_s4_or_s5_signoff_is_implied(self):
        for phrase in (
            "NOT STARTED", "NOT TESTED", "No deployment", "owner permission",
            "one comprehensive module upgrade", "One-bucket extinguish is NOT implemented",
            "A01 Golemagg", "A02 human Hunter", "A03 NT1",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DOC)

if __name__ == "__main__":
    unittest.main()
