# F14 P15 — P12 and P14 tested together (test-only, unwired)

Status: tests and docs only. No change to `src/`, config, SQL, DBC, core,
Playerbots or Individual Progression. No hook, and F14 stays default OFF. The
sibling branches are read, never edited, merged or cherry-picked into any
branch.

| Input | Head | Role |
|---|---|---|
| #202 | `205d958` | Parent: classifier, `IdentityBoard`, facts adapter |
| #224 P12 | `33bf0d3` | Masked SelfBot matrix (5 added paths) |
| #228 P14 | `eec8211` | `/who` seam against #145 (6 added paths) |
| #145 | `01c6b32` | `WhoListingPolicy.h`, blob `e66f72c`, via #228's extractor |

Pins: core Grimfeather `8daffdab`, Playerbots `d750b4b3`. Owner-accepted
gameplay is still 0/5.

## Short answer

- **The siblings compose without conflict.** They add disjoint paths, and
  neither touches `src/`, `conf/` or the shared stubs. `git merge-tree` of the
  two heads is clean (tree `c426cd5`). Both siblings' own tests pass on that
  combined tree.
- **Combining them changes no policy.** The combined pipeline is: stub players →
  real adapter → `Classify` → `IdentityBoard` → P14 seam over #145's real
  writer. Its output matches a hand-written visibility table. The table comes
  from today's #197 rules; nothing new was added. **No STOP was needed.**
- **One composed consequence the owner should see:** under policy B, while
  Playerbots is config-masked, a SelfBot's Blood Elf or Draenei row is
  **shown** in `/who`. This follows from P12: it classifies as Human, and its
  AI is not running. P12 options M1–M4 decide whether that stays. Mutants
  confirm that M2 and M3 would each change this visibly.

## What the combined test checks (`tests/f14_combined_matrix_tests.cpp`, 27 checks)

Population, with the observer a human Blood Elf who logged in after the last
sample (so it is missing from the board):

| GUID | Who | Race | Enabled | Masked (`Enabled = 0`) |
|---|---|---|---|---|
| 101 | SelfBot (client + own AI) | Blood Elf | SelfBot | **Human** (P12) |
| 102 | ordinary human | Draenei | Human | Human |
| 103 | RandomBot | Blood Elf | RandomBot | Unknown |
| 104 | AltBot of 102 | Draenei | AltBot | Unknown |
| 105 | human, client dropped | Blood Elf | Unknown | Unknown |
| 106 | RandomBot | Orc | RandomBot | Unknown |
| 107 | observer | Blood Elf | not on board | not on board |

Expected `/who` rows, written out by hand:

| Policy | Enabled | Masked |
|---|---|---|
| A (HideAllTbcRaces) | 106, 107 | 106, 107 |
| B (HideBotsOnly) | 102, 106, 107 | **101**, 102, 106, 107 |
| B with SelfBot as human | 101, 102, 106, 107 | 101, 102, 106, 107 |

Each tick follows the pinned core order (P14 facts C1–C3):
1. the world thread rebuilds the who rows;
2. **8 map workers** (`MapUpdate.Threads = 8`) answer 8 `/who` queries
   under every policy in parallel;
3. the workers are joined;
4. the world thread samples the facts and publishes the board.

Replies therefore use the previous tick's board.

| Tick | Board | Checked |
|---|---|---|
| T0 | none | B = A, A = #145 shipped, hiding off = stock, all workers agree |
| T1 | T0, enabled | B, B+SelfBot, A against the table; Lookup(101) = SelfBot; observer Unknown |
| reload | — | masked SelfBot and masked human facts identical; masked SelfBot classifies as Human |
| T2 | T1, enabled | one tick of lag: still the enabled table |
| T3 | T2, masked | masked table; Lookup(101) = Human, RandomBot and linkdead Unknown |
| T4 | T3, stale (> `maxAge`, world thread stalled) | B = A |
| T5 | T3, apparently in the future | B = A |
| T6 | T3, exactly `maxAge` old | masked table (still trusted) |

The observer's own Blood Elf row is shown in every case, even though the
board does not know it.

Builds: C++17 and C++20 with `-Werror`, ASan+UBSan, and **ThreadSanitizer**
(8 worker threads).

## Must-fail mutants (`tests/f14_combined_mutants.py`, 9/9 caught)

| Mutant | Caught by |
|---|---|
| M2: fail closed while Playerbots is off | 5 checks |
| M3: ungated AI lookup | 5 checks |
| seam ignores identity | 6 checks |
| observer row not exempt | 17 checks |
| stale board trusted | 1 check |
| future board trusted | 1 check |
| SelfBot option ignored | 1 check |
| board published before the map phase (same-tick read) | 2 checks |
| who rows rebuilt during the map phase | ThreadSanitizer data race (20/20 local runs) |

## Sibling regression on the combined tree (CI)

`tests/f14_combined_inputs.py` checks:
- both heads, their exact added paths and reviewed blob hashes;
- that the paths are disjoint;
- the clean merge-tree.

It writes the combined tree into a scratch directory (never committed) and
runs #228's own extractor from it. The workflow then runs, inside that
combined tree:
- P12: its pinned-Playerbots facts, its 27-check matrix (C++17/20 and
  sanitizers) and its 8 mutants;
- P14: its pinned-core facts, its 23-check seam test (C++17/20 and
  sanitizers) and its 9 mutants;
- #197 and #202 inherited tests.

## Open (not decided here)

- Owner decisions: policy A or B, SelfBot as human, the P12 masked case
  (M1–M4) and `maxAge`.
- No hook exists. `WorldThreadSamplingGrant` and `HideRowFor` remain
  hypothetical; #145's `CanPacketReceive` intercept is not exercised.
- Race still reaches clients through the name query and the model (P14 C8).
- Source order and a synthetic 8-thread model are not a runtime trace of the
  owner's Worldserver.
