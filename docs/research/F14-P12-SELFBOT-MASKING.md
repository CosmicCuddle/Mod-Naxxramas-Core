# F14 P12 — SelfBot masked by `Playerbots.Enabled = 0` (test-only)

Status: research and tests only. No change to `src/`, config, SQL, DBC, core,
Playerbots or Individual Progression. F14 stays unwired and default OFF.

Parent: `claude/cs03-f14-identity-facts-adapter` at `205d958` (#202), which
contains #197's classifier. Counterexample under study: #197 comment
6470766605 (an active SelfBot can read as Human when Playerbots is disabled).

Pins: Playerbots `d750b4b3a50e`, core Grimfeather `8daffdab`.

## Short answer

The ambiguity is real and cannot be removed from inside this module. While
`Playerbots.Enabled` is false, a SelfBot attached before the switch produces
**exactly the same facts** as an ordinary connected human, because every
Playerbots accessor the adapter may use returns "nothing" while disabled.

There is also a source-backed positive fact: in that state the SelfBot's AI is
**not running**. It is ticked only through the same gated lookup. The masked
character is therefore controlled by its human player, and classifying it as
`Human` describes who is playing it. No behaviour fix is proposed.

## Pinned source facts (checked by `tests/f14_selfbot_masking_facts.py`)

| # | Fact | Source at `d750b4b` |
|---|---|---|
| F1 | `GetPlayerbotAI` returns nullptr while `!Enabled` | `src/Bot/PlayerbotMgr.cpp` L1858–1862 |
| F2 | `GetPlayerbotMgr` has the same gate | `src/Bot/PlayerbotMgr.cpp` L1878–1882 |
| F3 | The AI is updated only if that lookup is non-null | `src/Script/Playerbots.cpp` L248–254 |
| F4 | `GET_PLAYERBOT_AI` / `GET_PLAYERBOT_MGR` use those getters | `src/Script/Playerbots.h` L31–32 |
| F5 | Every `.playerbots bot` command is refused while disabled ("You cannot control bots yet") | `src/Bot/PlayerbotMgr.cpp` L927–931 |
| F6 | `self` deletes the AI if present, else attaches one with the player as master | `src/Bot/PlayerbotMgr.cpp` L1100–1120 |
| F7 | `SelfBotLevel > 2` runs `self` at login | `src/Bot/PlayerbotMgr.cpp` L1733–1734 |
| F8 | `Initialize` reads `Enabled` from `Playerbots.Enabled` | `src/PlayerbotAIConfig.cpp` L79–83 |
| F9 | `bot reload` re-runs `Initialize`, behind the F5 gate | `src/Bot/PlayerbotMgr.cpp` L1074–1079 |
| F10 | `rndbot reload` re-runs `Initialize`, behind its own `!Enabled` gate | `src/Bot/RandomPlayerbotMgr.cpp` L2503–2506, L2532–2534 |
| F11 | `Initialize` has exactly three callers: startup (`Playerbots.cpp` L531), F9 and F10 | whole `src/` tree |
| F12 | The AI map is private; the only public getters are the gated ones | `src/Bot/PlayerbotMgr.h` L122–137 |
| F13 | `IsRandomBot(Player*)` returns false for a SelfBot | `src/Bot/RandomPlayerbotMgr.cpp` L2239–2244 |

The checker also runs one negative fixture per fact (a mutated copy of the
cited source) and requires each to fail.

### Consequences

- **How masking happens.** A running server with `Enabled = 1` has a SelfBot
  attached. A GM edits `playerbots.conf` to `Enabled = 0` and runs either
  reload (F9, F10). The attached AI is not removed (there is no eviction on
  reload), but every accessor now hides it (F1, F2, F12).
- **The mask is one-way within a process.** Once `Enabled` is false, both
  reload commands are refused (F5, F10), and core `.reload config` does not
  call `Initialize` (F11). The only way back is a restart, which starts with an
  empty AI map. The player is then Human until `self` or `SelfBotLevel > 2`
  re-attaches an AI (F6, F7).
- **While masked the AI is inert.** `OnPlayerAfterUpdate` (F3) skips it, and
  the player cannot toggle it (F5).
- **A server started with `Enabled = 0`** never attaches any AI, so there is no
  SelfBot to mask. Only a runtime reload produces the counterexample.

## What the test proves (`tests/f14_selfbot_masking_tests.cpp`, 27 checks)

The test compiles the real `PlayerIdentityFacts.cpp`, `Classify` and
`HideTbcRow` against the existing #202 stubs. The stubs keep the F1 gate, and
the test helpers mirror F3, F5, F6, F9 and F10.

| Case | Result |
|---|---|
| Baseline, enabled | SelfBot; AI ticked; policy B hides it unless `selfBotCountsAsHuman` |
| (a) masked attached SelfBot | Facts: socket open, Playerbots off, no AI → `Human`, shown under B. AI not ticked. Attachment still present. |
| (b) ordinary human, disabled | Facts byte-identical to (a) → `Human`. No gated accessor separates them. |
| (c) self toggle | Refused while masked; reload also refused. After restart: toggle → SelfBot (ticked), toggle again → Human (not ticked). |
| (d) socket drop / contradiction | Masked SelfBot with closed socket → Unknown, hidden. Linkdead SelfBot while enabled → Unknown. Socket plus an AI mastered by someone else → Unknown. |
| (e) policy B verdict | The masked sample published on `IdentityBoard` reads back as Human (shown). |

Must-fail mutants (`tests/f14_selfbot_masking_mutants.py`, 8/8 caught)
include the two alternatives below, applied to copies of the code. Both turn
the test red, so adopting either would be a visible decision, not drift.

## Decision matrix (owner / CS01)

No new gameplay policy is needed for the current code to be correct, so this
is **not a STOP**. It is recorded in case a stricter rule is wanted.

| Option | What changes | Masked SelfBot | Ordinary human while disabled | Cost / constraint |
|---|---|---|---|---|
| **M1 (recommended): accept** | Nothing | Shown as Human; its AI is not running | Shown as Human | None. Matches who is controlling the character. Lasts until restart. |
| M2: fail closed while disabled | `Classify` returns Unknown for any socket owner when `!playerbotsEnabled` | Hidden | **Hidden** (every human) | Policy B then hides all TBC humans whenever Playerbots is off. That is blanket hiding, which CS01 ruled out. |
| M3: read the ungated map | A Playerbots accessor that ignores `Enabled` | Shown as SelfBot → hidden | Shown as Human | Needs a Playerbots change (not permitted). It would also hide a character whose AI is not running. |
| M4: operator rule | Docs: change `Playerbots.Enabled` only by restart | No mask | Human | No code. Removes the case operationally, but cannot be enforced by the module. |

Recommendation: **M1**, optionally with the M4 note in operator docs.

## Not verified

- Runtime behaviour (no server run). All of the above is a source reading plus
  a synthetic test.
- The test models the gates; it does not link against Playerbots. The facts
  checker ties the model to the pinned source text.
- Newer Playerbots revisions than `d750b4b`.
