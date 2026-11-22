# Proposed F15 operator adapters

Owner: CosmicCuddle. Source examples only, not an installation instruction approval.

`python3 scripts/f15_operator_adapter.py --root PRIVATE_ABSOLUTE_ROOT --manager pm2 -- /ABSOLUTE/WORLDSERVER ARGS`
writes `pm2-proposed.json` privately without starting anything. For Authserver,
use `--manager tmux --socket DEDICATED_NAME -- /ABSOLUTE/AUTHSERVER ARGS` to write
`tmux-proposed.json`, containing a direct argument-vector launch plan. Root must
already exist as mode0700 with no symlink ancestors. Plans are0600/no-overwrite;
no command arguments or private paths are printed on success/refusal.

The PM2 plan targets the Python wrapper in fork mode, one instance, no interpreter
shell, tree killing disabled, autorestart disabled, clean status0 excluded from
restart and a proposed60s manager kill timeout. No wrapper child escalation is
enabled. Future owner-approved restart/timeout values must be selected from actual
server tests, not copied blindly from these proposed values. PM2_HOME must be
isolated in tests; production must preserve actual PM2 ownership and saved state.

The tmux plan uses a dedicated socket, no personal tmux config and direct command
arguments. It creates a NEW foreground wrapper which owns a NEW child; it does not
attach to a current tmux pane or claim ownership of an existing Authserver.
Ctrl-C can reach the foreground wrapper which forwards INT to its own child.
Closing/killing tmux or SIGKILL of the wrapper is not a guaranteed graceful stop:
the isolated child may survive, so do not use kill-session as the proposed stop API.
No automatic tmux respawn or process-group kill is added. Interactive server stdin
is unavailable because existing supervisor uses DEVNULL; preserve this limitation
in any owner deployment proposal.

## Disposable real-manager evidence

The opt-in Linux test gate installs PM2 version7.1.2 only into runner temporary
storage; tmux is a disposable runner tool. It uses private TemporaryDirectory
roots, PM2_HOME and unique tmux sockets, finite Python payloads and no server/DB.
Tests cover clean/nonzero rapid new runs, PM2 stop, tmux Ctrl-C with direct wrapper
ownership, concurrent World/Auth reports, redaction and private reports. Actual
versions/results are recorded in PR/queue. This is real manager fixture evidence,
not the owner's PM2/tmux version, real server semantics or live installation.

## Compatibility, disable and rollback

Requires POSIX Python and tested PM2/tmux argument semantics. Plan-generation
functions can be tested on Windows, but private-mode and real-manager gates require
Linux. Existing F15 report/raw ownership and30-day retention remain unchanged.
No production log or real Crash Logs path is accessed in fixtures.

Do not activate a generated plan without owner-approved exact binaries/arguments,
working directory/environment, DBC/config compatibility, verified backups, staging
and process-lifetime/stop/restart acceptance. This proposal deliberately does not
copy an owner's secrets/environment into a new saved manager manifest. Source
rollback abandons the child branch. Future approved rollback disables new launches,
stops only the specifically owned wrapper with its validated stop mechanism,
restores exact prior PM2/tmux launch records and preserves reports/raw/active logs.
Never delete owner PM2 state or a general tmux server as a rollback shortcut.

Sources checked for the proposed contract:
- https://pm2.keymetrics.io/docs/usage/signals-clean-restart/
- https://pm2.keymetrics.io/docs/usage/application-declaration/
- https://man.openbsd.org/tmux (direct multi-argument shell-command semantics)
- https://registry.npmjs.org/pm2/latest (version7.1.2 at implementation time)
