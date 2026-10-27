"""F15 Part29: pinned native AzerothCore logger routing reliability witnesses.

This reads ONLY immutable PUBLIC core source checked out by GitHub Actions.
No owner host, binaries, service, systemd, logs, SQL, config or subprocess.
Assertions are source-evidence gates, NOT proof installed configs match.
"""
import os
from pathlib import Path
import re
import unittest

PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"
SOURCE = Path(os.environ.get("F15_LOGGER_PIN_ROOT", "logger-pin"))

PATHS = {
    "world_main": "src/server/apps/worldserver/Main.cpp",
    "auth_main": "src/server/apps/authserver/Main.cpp",
    "world_conf": "src/server/apps/worldserver/worldserver.conf.dist",
    "auth_conf": "src/server/apps/authserver/authserver.conf.dist",
    "log": "src/common/Logging/Log.cpp",
    "appender": "src/common/Logging/Appender.cpp",
    "console": "src/common/Logging/AppenderConsole.cpp",
    "file": "src/common/Logging/AppenderFile.cpp",
    "logger": "src/common/Logging/Logger.cpp",
}


def read(name):
    p = SOURCE / PATHS[name]
    if not p.is_file():
        raise AssertionError("Missing immutable public core source: " + str(p))
    return p.read_text(encoding="utf-8")


def slim(text):
    return re.sub(r"\s+", " ", text)


class PinnedLoggingSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = {k: read(k) for k in PATHS}

    def test_world_uses_conditional_async_initialized_before_threadpool(self):
        p = self.p["world_main"]
        init = 'sLog->Initialize(sConfigMgr->GetOption<bool>("Log.Async.Enable", false) ? ioContext.get() : nullptr);'
        spawn = "threadPool->push_back(std::thread("
        self.assertIn(init, p)
        self.assertIn(spawn, p)
        self.assertLess(p.index(init), p.index(spawn))
        self.assertRegex(self.p["world_conf"], r"(?m)^Log\.Async\.Enable\s*=\s*0\s*$")
        # Config template and code fallback do NOT prove owner's setting.

    def test_auth_initializes_synchronous_logging_in_exact_pinned_main(self):
        p = self.p["auth_main"]
        self.assertIn("sLog->Initialize(nullptr);", p)
        self.assertNotIn('GetOption<bool>("Log.Async.Enable"', p)
        # Scope: this exact public Authserver Main.cpp, not private mods.

    def test_log_source_posts_async_without_waiting_for_delivered_receipt(self):
        p = self.p["log"]
        start = p.index("void Log::write(")
        end = p.index("Logger const* Log::GetLoggerByType(", start)
        body = slim(p[start:end])
        self.assertIn("if (_ioContext)", body)
        self.assertIn("Acore::Asio::post(*_ioContext,", body)
        self.assertIn("logOperation->call();", body)
        self.assertIn("else logger->write(msg.get());", body)
        self.assertNotIn("future.get", body)
        self.assertNotIn("fsync(", body)

    def test_world_shutdown_stops_io_pool_then_switches_synchronous(self):
        p = self.p["world_main"]
        a = p.index("threadPool.reset();")
        b = p.index("sLog->SetSynchronous();", a)
        self.assertLess(a, b)
        self.assertIn("ioContext->stop();", p)
        self.assertIn("ioContext->run();", p)
        # No claim a queued item was lost on a real server.

    def test_public_templates_have_unprefixed_console_appenders(self):
        self.assertRegex(
            self.p["world_conf"],
            r'(?m)^Appender\.Console=1,4,0,["]1 9 3 6 5 8["]\s*$')
        self.assertRegex(
            self.p["auth_conf"],
            r'(?m)^Appender\.Console=1,5,0,["]1 9 3 6 5 8["]\s*$')
        self.assertIn("APPENDER_FLAGS_PREFIX_LOGLEVEL", self.p["appender"])
        self.assertIn("if (flags & APPENDER_FLAGS_PREFIX_LOGLEVEL)",
                      self.p["appender"])
        # Level is not emitted into each line if this bit is unset.

    def test_public_template_files_are_opened_in_overwrite_mode(self):
        for name, snippets in (
            ("world_conf", [
                "Appender.Server=2,5,0,Server.log,w",
                "Appender.Playerbots=2,5,0,Playerbots.log,w",
                "Appender.Errors=2,2,0,Errors.log,w",
            ]),
            ("auth_conf", ["Appender.Auth=2,5,0,Auth.log,w"]),
        ):
            with self.subTest(which=name):
                for snippet in snippets:
                    self.assertIn(snippet, self.p[name])

    def test_file_constructor_opens_existing_name_with_mode_and_backup(self):
        s = slim(self.p["file"])
        self.assertIn('std::string mode = "a";', s)
        self.assertIn('mode.assign(args[4]);', s)
        self.assertIn('logfile = OpenFile(_fileName, mode, (mode == "w") && _backup);', s)
        self.assertIn('FILE* ret = fopen(fullName.c_str(), mode.c_str())', s)
        self.assertIn('if (flags & APPENDER_FLAGS_USE_TIMESTAMP)', s)
        # Actual owner's configured appenders are unknown.

    def test_runtime_maxsize_rotation_uses_backup_and_truncating_write(self):
        s = slim(self.p["file"])
        self.assertIn('_maxFileSize > 0', s)
        self.assertIn('else if (exceedMaxSize)', s)
        self.assertIn('logfile = OpenFile(_fileName, "w", true);', s)
        self.assertIn('rename(fullName.c_str(), newName.c_str());', s)
        # Separate inode names / open offsets require a dedicated tailer.

    def test_backup_rename_result_is_ignored_and_file_open_can_fail(self):
        s = slim(self.p["file"])
        self.assertIn('rename(fullName.c_str(), newName.c_str());', s)
        self.assertIn('if (!logfile) { return; }', s)
        self.assertIn('if (!file) { return; }', s)
        self.assertNotIn("if (rename(", s)
        # No claim named backup succeeded or report exists.

    def test_fflush_is_not_filesystem_durable_acknowledgement(self):
        p = self.p["file"]
        self.assertIn("fflush(logfile);", p)
        self.assertIn("fflush(file);", p)
        self.assertNotIn("fsync(", p)
        self.assertNotIn("fdatasync(", p)
        self.assertNotIn("FlushFileBuffers", p)

    def test_dynamic_file_name_uses_append_but_not_one_stable_target(self):
        p = slim(self.p["file"])
        self.assertIn('_dynamicName = std::string::npos != _fileName.find("%s");', p)
        self.assertIn('snprintf(namebuf, ACORE_PATH_MAX, _fileName.c_str(), message->param1.c_str());', p)
        self.assertIn('OpenFile(namebuf, "a", _backup || exceedMaxSize)', p)
        # Report collector must not guess a single logfile filename.

    def test_console_routing_is_only_a_hint_not_a_level_prefix(self):
        s = slim(self.p["console"])
        self.assertIn("message->level == LOG_LEVEL_ERROR || message->level == LOG_LEVEL_FATAL", s)
        self.assertIn("utf8printf(stdout_stream ? stdout : stderr,", s)
        self.assertIn("ResetColor(stdout_stream);", s)
        self.assertIn('fprintf((stdout_stream ? stdout : stderr), "\\x1b[0m");',
                      self.p["console"])
        # stderr and stdout are hints; level parsing needs declared prefix.

    def test_logger_and_appender_both_filter_messages(self):
        p = slim(self.p["logger"])
        a = slim(self.p["appender"])
        self.assertIn("if (!level || level < message->level || message->text.empty())", p)
        self.assertIn("if (!level || level < message->level)", a)
        self.assertIn("for (std::pair<uint8 const, Appender*> const& appender : appenders)", p)
        self.assertIn("appender.second->write(message);", p)
        self.assertIn('for (std::string_view appendName : Acore::Tokenize(tokens[1],', self.p["log"])
        # Finding an open file does not mean all filtered events reached it.

    def test_missing_root_logger_fallback_is_console_only(self):
        s = slim(self.p["log"])
        self.assertIn('if (loggers.find(LOGGER_ROOT) == loggers.end())', s)
        self.assertIn("Close(); // Clean any Logger or Appender created", s)
        self.assertIn('new AppenderConsole(NextAppenderId(), "Console",', s)
        self.assertIn('Logger* rootLogger = new Logger(LOGGER_ROOT, LOG_LEVEL_WARN);', s)
        self.assertIn('Logger* serverLogger = new Logger("server", LOG_LEVEL_INFO);', s)
        # This fallback has no configured file appender, so never assume one.

    def test_logger_reload_and_file_dir_are_loaded_from_config(self):
        s = slim(self.p["log"])
        self.assertIn('m_logsDir = sConfigMgr->GetOption<std::string>("LogsDir", "", false);', s)
        self.assertIn("ReadAppendersFromConfig(); ReadLoggersFromConfig();", s)
        self.assertIn("void Log::LoadFromConfig()", s)
        self.assertIn("Close();", s)

    def test_world_cli_and_stdin_are_separate_from_logging_pipe_origin(self):
        p = self.p["world_main"]
        self.assertIn('GetOption<bool>("Console.Enable", true)', p)
        self.assertIn('cliThread.reset(new std::thread(CliThread)', p)
        # No assumption a production wrapper can simply redirect stdin.
        self.assertRegex(self.p["world_conf"],
                         r"(?m)^Console\.Enable\s*=\s*1\s*$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
