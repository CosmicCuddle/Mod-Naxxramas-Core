# F15 event report schema v1 and R0 owner-fact checklist (source-only draft)

**Status:** DRAFT research and test code. Nothing is installed, enabled or written to disk. The code builds a report document in memory from one observation of a **disposable** child process (the producer in #170), and checks such documents.

**Not in scope, and not done:**
- no real Worldserver or Authserver launch (Q3/S4 closed);
- no report path, file write or permissions (R4);
- no restart or readiness check (R2);
- no journal, file or GDB adapter;
- no access to the owner's host.

**Base:** #170 at `480e08d`, which is stacked on #167 `91faf6a` and contract #162 `2f27ac3`. This branch adds four new files and changes nothing that already exists.

| File | Purpose |
|---|---|
| `tools/f15/report_schema.py` | Pure builder, canonical form, strict parser and validator. Imports only `json`, `hashlib`, `re` and `__future__`. |
| `tests/test_f15_report_schema.py` | 39 tests. Reports are built from real observations of the #170 fixture children. |
| `docs/research/F15-REPORT-SCHEMA-V1.md` | This document. |
| `.github/workflows/f15-report-schema.yml` | Exact-head CI with scope guards. |

## 1. One document per observation

`build_report(observation, …)` returns either a sealed document or `None` when the facts support no event, for example a clean exit with no declared WARN-or-worse line. The document is a closed JSON object:

| Key | Content | Trust |
|---|---|---|
| `schema`, `schema_version` | `"naxx-f15-event"`, `1` | constant |
| `event_types` | non-empty list, in the fixed order below | **must equal** what the facts support |
| `producer` | `tool` (the producer's path), `source_sha` (40 hex), `launch_mode` | `launch_mode` can only be `"A-disposable"` |
| `declared` | `kind:"caller_declaration"`, `role`, `stdin_mode`, `prefix_loglevel`, `prefix_timestamp` | what the caller **said**, not facts |
| `incarnation` | `boot_id`, `pid`, `starttime`, `ppid`, `pgid` (`pgid == pid`, since mode A starts a new session) | kernel |
| `exit` | `attestation:"owned-child-waitid"`, `kind`, `exit_code`, `signal_number`, `planned`, `classification` | kernel; the classification is **recomputed** by the validator |
| `streams.stdout`, `streams.stderr` | attestation, EOF and deadline flags, the byte and line counters from #170, and `records` | owned pipes |
| `limits` | `cross_stream_order:"unknown"`, `stdout_may_be_block_buffered:true`, `stdout_tail_lost_on_crash_possible`, `group_scan_complete`, `group_members_seen_after_exit` (count only), `text_policy:"message_text_omitted"` | what the evidence cannot show |
| `time` | `recorded_utc` (`YYYY-MM-DDTHH:MM:SSZ`), `use:"display_only"` | wall clock, display only |
| `integrity` | `algorithm:"sha256"`, `canonicalization:"naxx-f15-json-v1"`, `digest`, `proves:"integrity_only"` | see §3 |

**Records** carry `line`, `stream`, `severity`, `severity_source`, `severity_hint`, `hint_source`, `truncated` and `message_bytes`. **They carry no message text** (§2).

### Event types, derived and never chosen

| Event | Derived only from |
|---|---|
| `crash` | `exit.classification == "fatal_signal"`, i.e. a kernel-reported SIGSEGV, SIGABRT, SIGBUS, SIGFPE, SIGILL or SIGSYS |
| `exit_unexpected` | `nonzero_exit_not_signal` (including exit 139) or `signal_requires_policy` (for example an unplanned SIGTERM) |
| `source_incomplete` | a stream with `deadline_hit` and no EOF; a descendant still holds the pipe |
| `declared_error_lines` | at least one record with a **declared-prefix** ERROR or FATAL |
| `declared_warning_lines` | at least one record with a **declared-prefix** WARN |

**Renamed from my #143 proposal.** `error_burst` and `warning_burst` are now `declared_error_lines` and `declared_warning_lines`. One observation has no per-line time, so it cannot show a burst. Rate limiting and bursts stay with the S4b model (#140) and are not reimplemented here.

An observation that ends in a handoff (`ObservationTimeout`, `ObservationFailed`, `StartFailed`) has no attested exit, so **v1 has no report for it**. The reaper's counters are diagnostics only.

## 2. Privacy: no log text in v1

- Console lines can contain player or account names, IP addresses, file paths and SQL fragments. A redaction policy does not exist yet, so v1 has **no field that can hold text**. Records keep only position, stream, severity facts and the retained length (`message_bytes`).
- The schema is closed: an extra `message` key, an `argv` key or any other unknown key is refused. A test checks that the fixture's words never appear in the serialised report.
- `boot_id` and `pid` identify the host and process. They are not secrets, but the report as a whole is private material, and its storage is an R4 decision.
- Stripping ANSI codes is **not** redaction.
- Adding text later needs a reviewed redaction policy and a `schema_version` bump.

## 3. Rules the validator enforces

**These rules check internal consistency only.** Anyone who can write a whole document can also fake `attestation:"owned-child-waitid"`, `declared`, `source_sha` or `recorded_utc`, then recompute the digest. The "Trust" column in §1 says where each value is *meant* to come from; `validate()` cannot confirm that a kernel wait actually happened, or who wrote the document. A trusted producer/writer boundary is future R4 work and needs the owner's approval.

- **Strict JSON.** Exact key sets; integers only (no floats or NaN); no duplicate keys; at most 1 MiB; at most 4096 records per stream; nesting no deeper than 8 (the schema needs 5). `parse()` accepts only the exact canonical bytes: sorted keys, no whitespace, UTF-8.
- **Malformed input is refused, never raised (CS01 review on #171).** `parse()` turns all of the following into `ReportRefused`:
  - bad UTF-8 or JSON;
  - an integer literal over Python's digit limit;
  - nesting deeper than the limit (checked first by an iterative pre-scan that ignores brackets inside strings);
  - any leftover `RecursionError`.

  Given a deep, cyclic or oversized object, `validate()` returns an error list instead of raising. Other exceptions are deliberately not caught, so a programming defect stays visible.
- **No crash from text.** `crash` comes from the kernel exit fact only. The classification is recomputed from `kind`, `exit_code`, `signal_number` and `planned`, so a document cannot call a SIGTERM a fatal signal, or an exit code of 139 a SIGSEGV.
- **Event list must be complete and exact.** A crash cannot be left out, and nothing unsupported can be added.
- **Planned stops.** Only SIGINT or SIGTERM may be declared planned. A fatal signal declared planned is refused by both the builder and the validator. This is **stricter than the producer**, which records any declared signal.
- **Severity needs a declared prefix.** Any severity other than `unknown` needs `severity_source:"declared_prefix"` and a declared `prefix_loglevel`. `lines_below_warn` must be 0 without it. Stream hints are fixed per stream and never become severities or events.
- **Accounting holds.** `drained = retained + framing + dropped`; framing equals the number of terminated lines; record line numbers increase and stay within the stream; `source_incomplete == deadline_hit and not eof`; `stdout_tail_lost_on_crash_possible` is true exactly for a signal death.
- **Integrity, not authenticity.** `digest` is SHA-256 over the canonical bytes without the `integrity` block. It shows the bytes were not changed after sealing. It does **not** show who sealed them (#151); anyone who can write a report can seal one.

**Mirrors.** The schema module mirrors the producer's constants instead of importing it. Tests fail if the attestation strings, hints, roles, stdin modes, fatal-signal numbers, levels or the dataclass fields drift apart.

## 4. R0 owner-fact checklist, for BOTH daemons

Each fact is read-only, involves no secret values, and needs the owner's separate R0 permission. **Nothing is collected by this branch.**

| # | Fact (worldserver and authserver separately) | Selects | Pinned source (`8daffda`) |
|---|---|---|---|
| 1 | How it is started (systemd unit, script loop, tmux/screen, GDB wrapper, other) and who restarts it | adapter mode; whether R1 mode A is even possible | the real parent decides R1 identity |
| 2 | Where stdout and stderr go under that launcher (TTY, journal, file, `/dev/null`) | whether console capture exists | ERROR/FATAL → stderr, the rest → stdout (`AppenderConsole.cpp` L174) |
| 3 | worldserver only: `Console.Enable`, and what stdin is | stdin choice; the `held_open` hazard | EOF → `StopNow(0)` (`CliRunnable.cpp` L236–238); `join()` with no cancel (`Main.cpp` L578). authserver has no CLI |
| 4 | Effective `Appender.Console…` lines: level, **flags**, colours | whether `prefix_loglevel` or a timestamp may be declared | prefix only with `0x02` (`Appender.cpp` L70) |
| 5 | Effective file appenders, `Logger.*` routing, `LogsDir`; mode `w`/`a`; flags `0x08`/`0x10` | a file adapter, rotation and truncation | `w` truncates at start; `0x10` backs up; `0x08` timestamps names |
| 6 | Crash artefacts: `ulimit -c`, `kernel.core_pattern` (systemd-coredump?), any GDB or crash-dump wrapper | crash evidence beyond the wait status | GDB text is not attestation |
| 7 | Installed binary identity: core, IP and Playerbots SHAs; build type | reproducibility | public pins are not the owner's build |
| 8 | Service user(s); owner and mode of the parent of `/root/cosmic_core/logs/Crash Logs/` | R4 broker design (no root by default) | #162 R4 |

## 5. Limits

- Every positive test uses disposable Python children. Nothing here shows how a real daemon behaves.
- A report is only as true as the caller's declarations in `declared`. The schema labels them as declarations; it cannot check them.
- One observation covers one incarnation. Crash loops, restarts and deduplication across reports are R2/R4 work.
- Integrity is not authenticity, and no signing key exists.
