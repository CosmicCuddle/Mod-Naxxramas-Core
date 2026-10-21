# F10 — optional 3.3.5a Spell.dbc READ-ONLY acceptance probe

**Status: S1 research/tooling only. 21 October 2026 — CosmicScript01.**

This is NOT a change to client or server Spell.dbc, NOT a spell creation or
DBC installation, and NOT proof of Hallow's End one-bucket gameplay.

## Why

Existing [#74 exact-source-head six-feature full linked Worldserver](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/74)
was independently reviewed and compiled, but the one-bucket feature still
needs a backed-up, owner-approved **private game scenario**. In the
reviewed [F10 S2 source research](F10-hallows-end-one-bucket-S2.md),
core spell 42339 can call the stock script, which casts **42348**.
We have not verified whether that stock splash takes effect before or after
our later hook on a real server. Stock small-fire handling may already call
\`RemoveAllAuras\`; our module writer only names fire aura **42074**.

AzerothCore's 3.3.5a Spell.dbc layout documents **speed** as little-endian
32-bit float at *zero-based field 47*, and **Effect1–3** at fields 71–73:
https://www.azerothcore.org/wiki/spell .
The documentation describes speed 0 as instant missile travel, but this
metadata does not establish complete **server execution ordering**.

## What the draft tool does

\`scripts/inspect_f10_spell_dbc_readonly.py\`:

- Opens the specific **existing, already backed-up** 3.3.5a \`Spell.dbc\`
  supplied by the owner ONLY for reading. It does not alter a file,
  overwrite values, write exports, upload the DBC, install data, connect to
  SQL or start the server.
- Verifies classic \`WDBC\` header, exact **234 fields** / 936-byte record,
  byte counts, contiguous rows and nonempty string block. Unsupported
  layouts fail closed. This is a WotLK 3.3.5a-only source heuristic, not
  a generic DBC editor.
- Finds **42074**, **42339**, **42348** exactly once each. Requires effect 0
  of 42339 to be \`SPELL_EFFECT_DUMMY\` (3); otherwise refuses to interpret
  the one-bucket hook path. Rejects duplicates, missing IDs, nonfinite
  or negative speeds.
- Prints their numeric speed/effect fields and a **SHA-256 of the inspected
  input** for local provenance. Classifies 42348 speed as ZERO or POSITIVE.
  Both outputs explicitly say actual core ordering, installed-version
  parity and in-game behavior remain UNKNOWN/NOT TESTED.

### Future user-approved inspection (NOT approved or performed now)

Only once the user has approved the private testing stage, established
verified offline backups of BOTH installed server/client DBCs, and agreed
the tested versions match:

\`\`\`bash
python3 scripts/inspect_f10_spell_dbc_readonly.py \
    --dbc /path/to/offline-backed-up/Spell.dbc
\`\`\`

Run against the copy, NOT against live client/server files. The script
does not generate or validate a backup and does not compare two files for
identity. To check client/server parity, run the probe on **each separately
backed-up** file and compare their printed SHA-256 hashes; equality is
necessary but does not prove an installed client has loaded the file.

No actual DBC has been fetched, parsed, edited or supplied for this PR.
A public repository advertised a 3.3.5a Spell.dbc reference, but we could
not obtain and verify its binary here. We deliberately leave **42348 speed
UNKNOWN**. Do not fill it in from another game version or guess at
splash ordering.

## Controlled source-only CI

\`.github/workflows/f10-spell-dbc-readonly-fixtures.yml\` runs
\`tests/test_f10_spell_dbc_readonly.py\` against **in-memory-created synthetic
WDBC fixtures in temporary runner directories only**. It checks correct
positive/zero speed classification, unchanged synthetic input bytes,
effect 0, duplicate/missing IDs, corrupt/truncated/unsupported record
layout, empty string block, invalid speed, absent paths and a
writerless reader. CI NEVER passes or reads an actual Spell.dbc.

## Still-blocking private acceptance

The operator would separately have to approve: known matching client/server
Spell.dbc + hashes; safe game backup and rollback; one active Shade and one
real player (with bots present if needed); 42339 accepted cast on normal
trigger 23686 with 42074; observe 42348 stock splash timing, unrelated
auras, spread child fires, training fire preservation and exactly one
bucket extinguish; then relog/another event cycle and negative cases
(two humans, bot caster, mismatched Shade, unignited trigger). All these
are **NOT TESTED** by this probe and remain blocked pending owner consent.

**Never** merge this draft, install any DBC, execute SQL, restart a server
or enable a gameplay config automatically. — CosmicScript01
