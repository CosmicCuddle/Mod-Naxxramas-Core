# Human Hunter pet autocast — private offline evidence review

**19 October 2026 · research draft only · not a persistence fix**

This optional helper lives in Naxxramas Core, stacked on [read-only Hunter audit PR #26](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/26). It analyzes only **operator-supplied local text** after separately approved, restore-proven staging. There is no Worldserver, Individual Progression, Playerbots, SQL/DBC, database, network or character mutation.

## What it reports

The script `scripts/summarize_hunter_pet_human_autocast_audit.py` accepts a **local** Worldserver log path. It summarizes existing module log shapes without printing the contents of the log, character IDs, PetNumbers, spell IDs or command-source IDs.

- Native autocast ON/OFF **matching-state-only** observations after player-facing toggle packets, separately for `CMSG_PET_SPELL_AUTOCAST` and same-slot `CMSG_PET_SET_ACTION`. The module checks a later matching native state, but **does not authenticate the actor** or save intent.
- Before/after same-callback **all-ability-family** generic snapshots. It counts rank-ID changes, `PetSpell.active` numeric-state changes and `m_autospells` membership changes independently, so Bite/Growl/etc. are not conflated with Lightning Breath.
- Learned-spell packets. They can originate in IP **or another legal learning path**, and do not identify IP's caller or completion.
- Sampled stability family changes, as separate context. Duplicate rank-family or truncated snapshots are marked **ambiguous**, never treated as comparable.

An unchanged sample is **not** proof autocast survived IP. A state changing from ON to OFF does **not** prove the human disabled it; IP unlearn/relearn can default a rank to OFF. Conversely, a later ON after a toggle packet does not establish persistence across relog or a genuine player action. Owner IDs contribute to distinct counting but are never printed individually.

## Operator procedure (separate staged approval required)

1. Before any staged enable, obtain **explicit owner authorization**, record installed Naxx/AzerothCore/IP/Playerbots SHAs, and verify restorable Worldserver/effective config/full characters DB backups. No live automatic diagnostic.
2. In staging only, execute the existing acceptance matrix in [HUNTER-PET-AUTOCAST-ACCEPTANCE.md](HUNTER-PET-AUTOCAST-ACCEPTANCE.md): human ON and OFF, same-rank relog and IP replacement, two separate pets and multiple autocastable abilities.
3. Retain logs **privately** on a trusted machine; never attach raw logs to GitHub. Use `python3 scripts/summarize_hunter_pet_human_autocast_audit.py /path/to/local-redacted-worldserver.log` from a local Naxx source checkout.
4. Compare aggregate counts with manually observed in-game results. The script cannot infer past explicit preference if no packet was observed, cannot prove the same pet across separated events, and cannot know when IP completed.
5. Do not implement functional ON/OFF restoration until a trustworthy **module-only before-and-after IP handoff** exists. No timers that repeatedly retoggle, no bot AI modifications and no learned-rank invention.

## Validation scope

A separate read-only GitHub workflow runs ten **synthetic** cases and checks real module C++ output labels, never downloads any private log. This is source/model S3, not actual IP observation, real autocast repair, a new S4 binary change, staged S6 acceptance or release permission.

[Human-only safe fix decision](HUNTER-PET-PLAYER-FIRST-MINIMAL-FIX-DECISION-2026-10-19.md) · [single authoritative module tracker #28](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28).
