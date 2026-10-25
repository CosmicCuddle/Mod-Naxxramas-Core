# F15 S4h — Owned disposable child stderr pipe (OFFLINE-ONLY)

**Status: research DRAFT. No merge, operational reporter, host access or deployment.**

This is a narrow R3 evidence experiment supporting the operational design contract in [PR #151](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/151). It does not duplicate the offline burst/cooldown policy in #140, immutable error storage #141, readiness #142, recovery #149, pending restart reservations #152 or Linux kernel waitpid evidence #154.

## Precisely what exists

- The parent creates an anonymous stderr pipe for one fixed, allowlisted, disposable Python child launched through the current Python interpreter. There is **no user-supplied executable**, shell, service unit, socket destination or log file.
- A selector reads small chunks from that owned pipe; framing clips lines, caps retained warning/error events, enforces a finite total input byte budget (default 64 KiB), and separately accounts for discarded records, clipped lines, ignored INFO/DEBUG text and a terminated stream with unknown remaining bytes. Invalid UTF-8 is replaced and control bytes cannot be replayed as terminal controls.
- The parent distinguishes only WARN and ERROR lines; these are **untrusted process-supplied text** even when the parent owns the pipe. A fake SIGSEGV string remains a log line. A return code of 139 is not classified as a kernel SIGSEGV. Timeout applies only to the Python fixture child.
- No error report or history is persisted or written to the owner's intended privileged destination. This is not a crash detector, readiness proof, writer or restarter.

## Test evidence and gate

Run: PYTHONDONTWRITEBYTECODE=1 python3 -I -B tests/test_f15_offline_owned_stderr_s4h.py -v

Thirteen synthetic Python unittest witnesses cover: separate WARN/ERROR; ignored INFO/DEBUG; forged fatal text; exit 139 not attesting a signal; invalid UTF-8 and controls; a 20,000-byte single-line overflow; a 100-message flood with explicit drop counts; a byte-flood quota that stops capture and flags incomplete evidence; a rejected unlimited quota; split writes across an anonymous pipe; empty output; missing final newline; and refusal to spawn if given an unsupported service name. All input is deliberately synthetic and generated only by self-launched Python children.

A dedicated exact-head GitHub workflow must separately pass all thirteen tests with no skip; **do not report hosted success until its actual SHA/job/log are inspected**.

## Limits before an operational reporter

The parent knows which **pipe endpoint** it created, not that any future real Worldserver/Authserver binary produced particular text. A program or descendant can forward or forge lines; a wrapper may hide the actual server process exit. These fixtures do not authenticate process incarnation, Linux wait status, launcher/GDB topology, AzerothCore logger routing, rotation/truncation of real files, secrets or player-identifier redaction, privilege isolation, restart readiness, or report durability. The parent's return code is not a replacement for the separate trusted-child waitpid policy in #154.

Operational progress still requires explicit owner permission for redacted read-only launcher/logger discovery, a source reviewed least-privilege adapter, isolated staging and separately approved backups, deployment and acceptance. The server, services, SQL, DBC, core, Individual Progression, locally modified Playerbots files, N-Core and MapUpdate.Threads=8 are untouched. F15 automatic World/Auth crash **AND** error reporting is **NOT operational**.

## Byte-budget review qualification (Part 25)

When more bytes arrive than the configured 4 KiB–1 MiB bounded quota, the parent truncates the incoming stream, sets `byte_limit_exceeded=True` in its fixture result, terminates only its own test child, and retains at most the allowed bytes/records. This is a **loss indicator**, not an exact count of unobserved bytes, application health proof, or a policy suitable for a live server: a real supervisor must not kill a Worldserver/Authserver merely because a log quota fills. The host adapter must instead implement bounded backpressure, attribution, coalescing and alerting with a separately reviewed no-service-interference design. No Worldserver/Authserver process was run or killed by this experiment.
