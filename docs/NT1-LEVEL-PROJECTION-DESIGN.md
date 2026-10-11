# NT1L1 Level-Adaptive Talent Projection — Server Design and Preview Prototype

**Status:** Read-only development branch; separate draft PR stacked after the shared-preflight draft PR #7. No automatic Apply, no new equipment changes, no SQL or configuration defaults. **A server compile and real in-game validation have not yet occurred.**

## Purpose and strict format distinction

Legacy `NT1:<era>:<class>:<id>-<final-rank>...` specifies **final ranks**, not an unambiguous rank-purchase sequence. Sorting a legacy NT1 by talent ID or low DBC row cannot recover the intended levelling order, especially for hybrid builds or early cross-tree spending.

New **opt-in** `NT1L1:<era>:<class>:<id>-<added-ranks>.<id>-<added-ranks>...` specifies the **deliberate rank purchase order**. Each dot-separated entry grants that many consecutive ranks to the named Talent.dbc ID, in the position it appears. A talent ID may appear more than once; later occurrences continue its prior rank (up to MAX_TALENT_RANK). These entries are not the same as the NT1 final-rank allocations. Talent IDs use lowercase base-36, and added-ranks are a single ASCII digit 1–5. The order is user-authored or administrator-reviewed, **not fabricated from the website's NT1 order**.

Illustrative *syntax only* (NOT a legal 51-point build):

```text
NT1L1:vanilla:mage:11-3.12-2.11-2
```

That example says “3 points in talent ID 37, 2 in talent ID 38, then 2 more in talent ID 37.” It will be rejected if a rank would exceed the DBC maximum, a prerequisite is missing, the chosen rows are locked, or the source is not a complete 51-point Vanilla plan. **Do not use it as a game-ready code.**

### Read-only command

```text
.naxxbot talents project <online-botname> <NT1L1-code>
```

- Uses the existing `AccessMode` 0/1/2 gate, current online human, bot target and non-GM account/master restrictions.
- Validates code class, era, all source Talent.dbc IDs, ranks, Spell.dbc rank spells, row limits and prerequisites step by step, in the author's **exact** priority sequence, including ranks beyond the recipient's current point budget.
- Requires a **complete standard source template**: Vanilla 51 points, TBC 61, WotLK 71. The protocol is version 1; realms with a nonstandard source talent-point ceiling are rejected rather than guessed.
- Uses `bot->CalculateTalentsPoints()` for the level-adjusted target budget. Captures the first `N` explicitly ordered *legal* rank steps, forms a canonical derived NT1 final-rank code, and runs it through the existing pure read-only `ParseCode` for a second complete validation. Target must spend exactly `N/N` points. Example on a level-30 Vanilla Mage with a legal 51-rank source: **21/21**.
- Checks the issuing character's exact current Individual Progression era (modern hidden quests 66001–66018; TBC at 8, WotLK at 13), and then reports the usual `CheckApplyReadiness` result from PR #7. If a lower-level TBC or WotLK bot fails the existing stricter **bot-level** Apply era restriction, the result is `PREFLIGHT BLOCKED`, **not** an expansion bypass.
- Prints target, level, points, three talent-tree totals, **paged Talent.dbc ID-rank pairs** (to avoid overlong chat lines), and a `PREFLIGHT READY` or `PREFLIGHT BLOCKED` status, followed by an explicit “read-only, nothing changed” statement.
- Does **not** teach ranks, reset talents, call `ApplyValidated`, create items, persist an NT1 profile or produce an authorization token.
- Existing `.naxxbot talents preview ... NT1:...` and `.naxxbot talents apply ... NT1:...` are not changed. Existing Apply rejects `NT1L1` (wrong `NT1` wire version); there is intentionally no `apply-priority` or `apply-project` command.

### Full-source equivalence

A ranked `NT1L1` source determines its **own** complete final talent allocation. It is not automatically proof that it corresponds to any separately saved website `NT1` preset. Before assigning a priority schedule to an existing preset, an authoring tool should replay the entire sequence, canonicalize the full-rank output and compare each final `Talent.dbc ID -> final rank` pair against the website NT1 (independent of entry order).

Do not trust client-provided preset names or URLs as authority. The later confirmation protocol should bind the original source, the reviewed priority-plan identity and exact server-projected derived ranks under one expiring ticket. Long codes may exceed the 3.3.5a **255-character full chat-command limit**; do not truncate. The future addon protocol needs short server-stored plan IDs or an explicitly reviewed chunked transport rather than silently changing talent allocation.

### Key source-validation rules

1. Reject absent/incorrect `NT1L1` version, unsupported era/class, malformed IDs, ranks 0 or >5, unsupported level, incorrect source total and oversized input.
2. Reject off-era rows/capstones using existing `AvailableInEra`; do not modify its IP or row restrictions.
3. For each next rank, require the loaded spell rank and satisfy the current DBC dependency rank before purchasing.
4. For each next rank at row `R`, require at least `5 * R` prior rank points in **strictly earlier rows of that same tree** at that moment (not eventual future spending).
5. Capture exactly the first `bot->CalculateTalentsPoints()` rank steps; never fill missing points with “best guesses,” and never exceed them.
6. Reparse the complete derived NT1 through the current server DBC validator. A failure stops the preview; it does not modify the target.
7. Apply the real human's Individual Progression and live ownership/master checks; `NT1L1` readiness is informational, not a durable permission or guarantee.
8. **Alt Bot gear remains untouched** and cannot be generated by this or any future NT1 auto-gearing extension.

### Example response *format* (illustrative, NOT in-game verified)

```text
NT1L1 projection for Examplemage (level 30 mage, era vanilla): 21 / 21 points from ordered 51-point source.
Projected tree points (server order): <arcane> / <fire> / <frost>.
Projected Talent.dbc ID-rank entries: <actual-projected-DBC-ID-rank-pairs>
NT1L1 PREFLIGHT READY (read-only only): there is NO automatic level-projection Apply command.
NT1L1 projection only: no talents, equipment or bot data changed.
```

A blocked preview can still show a valid projection but then explain why Apply would be currently ineligible (e.g. Random Bot group/master, Alt Bot allowlist, IP, current bot-era, SQL table or original spec snapshot).

### Acceptance test matrix after review and compilation

| Scenario | Expected read-only result |
| --- | --- |
| Reviewed legal Vanilla 51-step Mage priority source, eligible level-30 Mage | 21/21 projected, legal exact priorities and correct tree totals |
| Same source, eligible level-60 Mage | Full 51/51 projected; final result equals its full source |
| Source contains wrong class or expansion | Reject without state changes |
| Source includes a tier-3 talent before having 15 earlier-row points | Reject immediately, even if the *final* source allocation would be legal |
| Source buys a dependency before prerequisite's required rank | Reject |
| Source repeats talent beyond DBC rank limit | Reject |
| 49-point Vanilla source when 51 required | Reject incomplete source |
| Incorrect source of 52 points | Reject overallocated source |
| Level 30 with available 21 points but any projected 20/21 | Reject incomplete target; no auto-fill |
| Alt Bot caller not on allowlist | Shows projection if parsed but `PREFLIGHT BLOCKED`, not an Apply action |
| Random Playerbot not mastered/grouped by issuer | Shows projection but `PREFLIGHT BLOCKED` |
| TBC code while human is Vanilla | Reject IP era |
| WotLK source for level-30 bot | Reject or preflight block on existing stricter bot/era policy; never bypass |
| Mode 0 | Both project and existing import commands disabled |
| Saved, exported or browsed preset | No server mutation and no automatic project/apply invocation |

**Unverified:** C++ compilation, AzerothCore/Playerbots runtime behavior, actual legal priority fixture generation, 3.3.5a message transport for longer templates, addon integration and the full matrix above. Do not merge or deploy until those are reviewed.

### Future (separate PRs)

- Priority editor / authoring export and verified equivalence with each site preset.
- Machine-readable, server-bound `APPLY_READY` result with one-use expiry token and explicit confirmation.
- Only **after** token and recovery work: separately approved guarded, level-projected Apply.
- Separate Random Playerbot-only equipment role/generation safeguards, disabled by default.
