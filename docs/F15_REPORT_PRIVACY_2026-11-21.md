# F15 report privacy hardening

Owner: CosmicCuddle. Source-only child of frozen draft #336 at
`64e06361e1daaf5db6cfcfd2b07bc7375650c675`. The frozen branch is unchanged.

## Behaviour

The prior renderer exposed quoted/whitespace-separated credential tails,
Authorization bearer values, Core database connection strings and URI userinfo.
Context trimming could drop a credential key before redaction. Other report
metadata did not use context redaction, and history values could inject rows.

Redact all rendered metadata and context before applying size limits. Recognize
sensitive assignment/command keys, Core DatabaseInfo keys, URI userinfo and
private-key blocks. Withhold the rest of a sensitive line; an unfinished quoted
or folded value withholds the remaining input with an explicit marker. This is
conservative and can omit useful text. It cannot identify every unknown secret;
private report permissions and controlled input remain essential.

Context retains the newest redacted UTF-8 bytes, including the truncation marker
within the 32768-byte budget. Invalid surrogate input is replaced safely. History
classification/exit fields are redacted and flattened to one record.

## Evidence and limits

15 local Windows tests pass, including actual frozen-parent leak reproductions,
pure report projection, useful diagnostics preservation, oversized context,
UTF-8 boundaries, idempotence and history injection. AST comparison verifies all
existing storage functions remain unchanged. The projection imports no fcntl shim
and executes no storage operations; it is not POSIX storage validation.

A bounded Ubuntu Actions job runs the full existing `test_f15_*.py` suite using
disposable fixtures only. Its exact run outcome must be recorded in the PR and
review queue; adding the workflow does not establish a pass. The job has a
five-minute timeout, read-only token and no artifact/cache uploads.

## Preservation and rollback

No storage, locking, private permissions, retention ownership, raw forensic
capture, PM2/tmux lifecycle or installation changes. Existing reports/history
are not rewritten; retry content mismatches continue to fail closed. Preserve
original private forensic evidence. The designated Crash Logs directory and
30-day retention policy remain inherited from #336.

Abandon or revert this source child to roll back. No host changes occurred.
Native PM2/tmux end-to-end crash/restart evidence, staging and owner-approved
installation remain outstanding. This increment does not complete F15.
