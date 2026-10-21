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
    """Fail closed on SQL that is not obviously read-only in example blocks.

    SQL fences are ALLOWLISTED, not checked against an incomplete blacklist:
    only SELECT, SHOW, DESCRIBE/DESC, EXPLAIN statement beginnings are
    considered candidates for read-only use. SELECT with INTO, FOR UPDATE
    or LOCK IN SHARE MODE is denied. Even permitted syntax is not a claim
    about stored functions, views, triggers, privileges, or live DB safety.

    Shell/unknown fences and <pre> examples are conservatively rejected
    when they carry a known SQL-writing token or any mysql/mariadb family
    client. Blockquotes and indented code are also scanned. Ordinary prose
    is ignored. This is a source/doc guard, NOT a SQL parser or executor.
    """
    client = re.compile(
        r"(?<![\w-])(?:mysql|mariadb)[\w.-]*",
        re.IGNORECASE,
    )
    forbidden = re.compile(
        r"\b(?:INSERT|UPDATE|DELETE|DROP|TRUNCATE|CREATE|ALTER|REPLACE|"
        r"CALL|GRANT|REVOKE|RENAME|EXECUTE|SOURCE|FLUSH|KILL|SHUTDOWN|"
        r"OPTIMIZE|PREPARE|DEALLOCATE|HANDLER|DO|RESET|PURGE|INSTALL|UNINSTALL)\b"
        r"|\bSET\b|\bLOAD\s+DATA\b|\bINTO\s+(?:OUTFILE|DUMPFILE)\b"
        r"|\b(?:LOCK|UNLOCK)\s+TABLES\b|\\\s*\.\s+\S",
        re.IGNORECASE,
    )
    read_only_start = re.compile(
        r"^(?:SELECT|SHOW|DESCRIBE|DESC|EXPLAIN)\b", re.IGNORECASE,
    )
    side_effect_query = re.compile(
        r"\bINTO\b|\bFOR\s+UPDATE\b|\bLOCK\s+IN\s+SHARE\s+MODE\b",
        re.IGNORECASE,
    )
    opener = re.compile(
        r"^[ \t]*(?P<fence>(?:\x60{3,}|~{3,}))[ \t]*(?P<info>[^\r\n]*)$"
    )
    sql_languages = {"", "sql", "mysql", "mariadb"}
    shell_languages = {
        "bash", "sh", "shell", "shell-session", "zsh", "fish", "console",
        "powershell", "ps1", "cmd", "bat", "batch", "dos",
    }

    def unwrap_quote(line: str) -> str:
        while re.match(r"^[ \t]*>[ \t]?", line):
            line = re.sub(r"^[ \t]*>[ \t]?", "", line, count=1)
        return line

    def without_comment_lines(text: str) -> str:
        # Do not interpret comments as actual commands; conservative
        # block-comment removal prevents a fake read-only prefix.
        source = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        return "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith(("--", "#"))
        ).strip()

    def unsafe_sql(text: str) -> bool:
        # MySQL/MariaDB executable comments are actual SQL, not comments:
        # /*!50700 ... */ and /*M!100100 ... */ must fail closed BEFORE
        # ordinary block comments are stripped or statement starts checked.
        if re.search(r"/\\*(?:!|M!)", text, re.IGNORECASE):
            return True
        # SQL-client meta commands may execute external programs or source
        # scripts; deny all backslash commands rather than guessing which
        # subset is harmless (including \\!, \\., \\G).
        if re.search(r"\\\\[^\\s]", text):
            return True
        source = without_comment_lines(text)
        if not source:
            return False
        if client.search(source) or side_effect_query.search(source):
            return True
        # Split whole statements, not individual lines: multiline SELECTs
        # and two read-only SELECT statements remain valid.
        for statement in source.split(";"):
            part = statement.strip()
            if not part:
                continue
            if not read_only_start.match(part):
                return True
            # Deny non-read-only commands hidden behind EXPLAIN, or after
            # another allowed keyword. False positives fail safely.
            if forbidden.search(part):
                return True
        return False

    def unsafe_shell_or_unknown(text: str) -> bool:
        if re.search(r"/\\*(?:!|M!)|\\\\[^\\s]", text, re.IGNORECASE):
            return True
        source = without_comment_lines(text)
        return bool(client.search(source) or forbidden.search(source))

    matches: list[str] = []
    # HTML preformatted examples are executable-looking documentation.
    for pre in re.finditer(r"<pre\b[^>]*>(.*?)</pre\s*>", markdown, re.I | re.S):
        body = re.sub(r"</?[^>]+>", " ", pre.group(1))
        if unsafe_sql(body):
            matches.append("UNSAFE HTML PRE EXAMPLE:\n" + body)
    if re.search(r"<pre\b", markdown, re.I) and (
        len(list(re.finditer(r"<pre\b", markdown, re.I))) >
        len(list(re.finditer(r"</pre\s*>", markdown, re.I)))
    ):
        matches.append("UNTERMINATED HTML PRE EXAMPLE")

    lines = [unwrap_quote(line) for line in markdown.splitlines()]
    index = 0
    while index < len(lines):
        match = opener.fullmatch(lines[index])
        if not match:
            line = lines[index]
            if (line.startswith("    ") or line.startswith("\t")) and (
                unsafe_shell_or_unknown(line)
            ):
                matches.append("INDENTED UNSAFE CODE: " + line)
            index += 1
            continue
        fence = match.group("fence")
        info = match.group("info").strip()
        language = info.split(None, 1)[0].lower() if info else ""
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
        raw_code = "\n".join(content)
        if language in sql_languages:
            unsafe = unsafe_sql(raw_code)
        elif language in shell_languages:
            unsafe = unsafe_shell_or_unknown(raw_code)
        else:
            # Never let an unusual fence label (including {sql}) exempt
            # obvious state-changing instructions or mysql clients.
            unsafe = unsafe_shell_or_unknown(raw_code)
        if not closed:
            # A dangling SQL/shell/unknown code block is ambiguous, even
            # if its content currently appears to be read-only.
            matches.append("UNTERMINATED CODE FENCE:\n" + raw_code)
        elif unsafe:
            matches.append(raw_code)
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

    def test_read_only_guard_rejects_extended_mysql_state_changes(self):
        for sql in (
            "SET GLOBAL general_log=ON;",
            "SET PERSIST max_connections=200;",
            "CALL dangerous_proc();",
            "GRANT ALL ON *.* TO testuser;",
            "REVOKE ALL PRIVILEGES ON *.* FROM testuser;",
            "RENAME TABLE old TO new;",
            "LOAD DATA INFILE '/tmp/x.csv' INTO TABLE character_pet;",
            "SELECT id INTO OUTFILE '/tmp/export' FROM character_pet;",
            "SELECT data INTO DUMPFILE '/tmp/export' FROM character_pet;",
            "LOCK TABLES character_pet WRITE;",
            "UNLOCK TABLES;",
            "EXECUTE prepared_stmt;",
        ):
            with self.subTest(sql=sql):
                self.assertNotEqual(
                    invalid_sql_statements_in_code_fences(
                        "\x60\x60\x60MySQL\n" + sql + "\n\x60\x60\x60\n"), [])

    def test_read_only_guard_rejects_mysql_client_inside_shell_fences(self):
        samples = (
            '\x60\x60\x60bash\nmysql -e "SELECT 1"\n\x60\x60\x60\n',
            '\x60\x60\x60sh\nsudo mariadb -e "DELETE FROM character_pet"\n\x60\x60\x60\n',
            '\x60\x60\x60console\n$ mysqladmin flush-hosts\n\x60\x60\x60\n',
            '\x60\x60\x60powershell\nmysql --execute "CALL risky()"\n\x60\x60\x60\n',
            '\x60\x60\x60bash\n# Do not run mysql commands\nMYSQL -e "select 1";\n\x60\x60\x60\n',
            '  > \x60\x60\x60BASH\n  > mysql -e "SELECT 1"\n  > \x60\x60\x60\n',
            '    mysql -e "SELECT 1"\n',
            '  >     SET GLOBAL general_log = ON;\n',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertNotEqual(
                    invalid_sql_statements_in_code_fences(sample), [])

    def test_read_only_guard_rejects_unterminated_shell_examples(self):
        self.assertNotEqual(
            invalid_sql_statements_in_code_fences(
                "\x60\x60\x60bash\nprintf 'read-only review'\n"), [])

    def test_read_only_guard_accepts_non_executing_prose_and_select_examples(self):
        sample = (
            "A paragraph mentions SET GLOBAL, CALL, GRANT and mysql -e; "
            "these are explanations, not runnable examples.\n"
            "\x60\x60\x60SQL\n-- Never DROP DATABASE\nSELECT entry FROM creature_template;\n\x60\x60\x60\n"
            "\x60\x60\x60bash\n# mysql -e 'DELETE FROM character_pet'\n"
            "printf 'no database access'\n\x60\x60\x60\n"
            "    SELECT TypeId FROM outdoorpvp_template;\n"
            "> \x60\x60\x60sql\n> SELECT 1;\n> \x60\x60\x60\n"
        )
        self.assertEqual(invalid_sql_statements_in_code_fences(sample), [])

    def test_sql_allowlist_denies_unknown_mutations_and_file_execution(self):
        cases = (
            "SET @@GLOBAL.general_log=1;",
            "SOURCE /tmp/x.sql;",
            r"\. /tmp/x.sql",
            "FLUSH PRIVILEGES;",
            "KILL 12;",
            "SHUTDOWN;",
            "OPTIMIZE TABLE character_pet;",
            "PREPARE s FROM @q;",
            "SELECT 1; DROP TABLE character_pet;",
            "SELECT x INTO @variable FROM character_pet;",
            "SELECT * FROM character_pet FOR UPDATE;",
            "SELECT * FROM character_pet LOCK IN SHARE MODE;",
            "EXPLAIN UPDATE character_pet SET name='X';",
            "UPDATE character_pet SET name='X'; SELECT 1;",
        )
        for sql in cases:
            with self.subTest(sql=sql):
                self.assertNotEqual(
                    invalid_sql_statements_in_code_fences(
                        "\x60\x60\x60sql\n" + sql + "\n\x60\x60\x60"), [])

    def test_sql_allowlist_accepts_multiline_read_only_statements(self):
        text = (
            "\x60\x60\x60SQL\n-- Comment about DROP TABLE\n"
            "SELECT entry, ScriptName\nFROM creature_template\nWHERE entry=23543;\n"
            "SHOW TABLES;\nDESCRIBE character_pet;\n"
            "DESC creature_template;\nEXPLAIN SELECT 1;\n\x60\x60\x60"
        )
        self.assertEqual(invalid_sql_statements_in_code_fences(text), [])

    def test_shell_and_unknown_fences_catch_all_mysql_client_variants(self):
        clients = (
            "mariadb-admin", "mariadb-import", "mysqlimport",
            "mysql_upgrade", "mysqlsh", "mysql.exe", "mysql", "mariadb",
        )
        languages = ("bash", "shell-session", "cmd", "bat", "plain")
        for language in languages:
            for client in clients:
                with self.subTest(language=language, client=client):
                    sample = (
                        "\x60\x60\x60" + language + "\n" +
                        client + " --execute 'SELECT 1'\n\x60\x60\x60"
                    )
                    self.assertNotEqual(
                        invalid_sql_statements_in_code_fences(sample), [])

    def test_raw_html_pre_and_unknown_fence_cannot_bypass_sql_guard(self):
        samples = (
            "<pre>SET @@GLOBAL.general_log=1;</pre>",
            "<PRE class='shell'>mariadb-admin flush-hosts</PRE>",
            "<pre><code>DROP TABLE character_pet;</code></pre>",
            "<pre>SELECT 1;",
            "\x60\x60\x60{sql}\nDROP TABLE t;\n\x60\x60\x60",
            "\x60\x60\x60some-other-label\nmysqlsh --uri user@host\n\x60\x60\x60",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertNotEqual(
                    invalid_sql_statements_in_code_fences(sample), [])

    def test_mysql_executable_comments_never_get_stripped_as_harmless(self):
        examples = (
            "SELECT 1 /*!50000 ; DROP TABLE characters */;",
            "SELECT * FROM characters /*! INTO OUTFILE '/tmp/x' */;",
            "SELECT 1 /*M!100100 ; DELETE FROM character_pet */;",
            "/*!50700 SHUTDOWN */",
            "SELECT 1 /* ordinary explanatory comment */ /*!50000 CALL foo() */;",
        )
        for sql in examples:
            with self.subTest(sql=sql):
                self.assertNotEqual(invalid_sql_statements_in_code_fences(
                    "\x60\x60\x60sql\n" + sql + "\n\x60\x60\x60"), [])

    def test_sql_client_commands_fail_closed_even_with_select_prefix(self):
        examples = (
            "SELECT 1\nsystem touch /tmp/x\n;",
            r"SELECT 1 \! touch /tmp/x",
            r"SELECT 1 \. /tmp/hidden.sql",
            r"SELECT 1 \G",
            r"SELECT 1 \T /tmp/server-output",
        )
        for sql in examples:
            with self.subTest(sql=sql):
                self.assertNotEqual(invalid_sql_statements_in_code_fences(
                    "\x60\x60\x60mysql\n" + sql + "\n\x60\x60\x60"), [])

    def test_mysql_executable_comment_and_backslash_in_unknown_fence(self):
        examples = (
            "\x60\x60\x60shell-session\nSELECT 1 /*!50000 DROP TABLE x */\n\x60\x60\x60",
            "\x60\x60\x60mystery\nSELECT 1 \\! touch /tmp/x\n\x60\x60\x60",
        )
        for text in examples:
            with self.subTest(text=text):
                self.assertNotEqual(invalid_sql_statements_in_code_fences(text), [])

    def test_preflight_workflow_triggers_for_any_module_sql_directory(self):
        # UpdateFetcher accepts first-level directory names containing
        # "characters", not only exact db-characters or db_characters.
        # A new folder or its deeper SQL updates must always rerun this
        # SOURCE-ONLY guard before claiming a safe manual migration.
        workflow = read(".github/workflows/five-feature-owner-smoke-preflight.yml")
        self.assertIn("      - 'data/sql/**'", workflow)
        self.assertNotIn("      - 'data/sql/db-characters/**'", workflow)
        self.assertNotIn("      - 'data/sql/db_characters/**'", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("upload-artifact", workflow)

    def test_auto_updater_guard_recognises_other_character_database_folder_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = (
                "db-characters-future/update_1.sql",
                "db_characters_v2/updates/subdirectory/update_2.sql",
                "not-characters-template/2026/updates/update_3.sql",
            )
            for relative in paths:
                path = root / "data" / "sql" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "CREATE TABLE " + AUTOCACHE_TABLE_NAME + " (id INT);\n",
                    encoding="utf-8",
                )
            found = unsafe_autocast_auto_migrations(root)
            self.assertEqual(
                {p.relative_to(root / "data" / "sql").as_posix() for p in found},
                set(paths),
            )

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
