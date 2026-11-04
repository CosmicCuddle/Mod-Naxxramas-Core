# F14 — hide only verified Blood Elf / Draenei Random Playerbots from Vanilla observers (pure, not wired)

**Status:** DRAFT. This is a pure C++ policy model with tests, a child of #197 at `b44029d`.

- **Not wired.** Nothing in the module includes `src/Systems/F14VerifiedRandomBotPolicy.h`. There is no hook, config key, `/who` code or packet code, so F14 stays **OFF**.
- **No changes elsewhere.** No core, Playerbots, Individual Progression (IP), SQL, DBC or config changes.
- **No claims.** It makes no claim about runtime or observer packets, and gameplay acceptance remains 0/5.

**Assignment:** CS01, #143 comment 6636550351. **Claim:** #143 comment 6637430473.

## 1. The owner rule (30 Oct selection)

Hide a Blood Elf (10) or Draenei (11) character **only** when it is a **positively verified, selected Random Playerbot**, and **only** from an **ordinary Vanilla-stage observer**.

Everyone else stays **visible by default**:
- human Blood Elf / Draenei players;
- AltBots and SelfBots;
- Unknown or stale identities;
- GMs;
- the observer's own row;
- TBC-or-later observers.

Unknown or stale identity is never treated as a Random Playerbot.

## 2. What changes relative to #197

| Rule | Hides | Status |
|---|---|---|
| #197 policy A `HideAllTbcRaces` | every Blood Elf / Draenei row except the observer's own | **Historical test baseline. Not approved for runtime enablement.** |
| #197 policy B `HideBotsOnly` | every Blood Elf / Draenei row except positively Human (so AltBot, SelfBot and Unknown are hidden too) | **Historical test baseline. Not approved for runtime enablement.** |
| **New** `HideFromVanillaObserver` | only a verified selected Random Playerbot, only for a confirmed non-GM Vanilla observer | owner-selected model; still unwired |

#197's five files are **byte-identical** here, and CI checks their blob SHAs. A and B are kept so earlier research and tests still build. The new header's comment and this document both mark them as not approved for runtime use.

## 3. The model (`src/Systems/F14VerifiedRandomBotPolicy.h`)

`HideFromVanillaObserver(Observer, Row)` returns **true only if all six conditions hold**:

1. `observer.era == ObserverEra::Vanilla`, positively known.
2. `observer.confirmedNonGameMaster`: the observer is positively known not to be a GM.
3. `row.confirmedNotObserver`: the row is positively known not to be the observer's own.
4. `row.race` is 10 or 11.
5. `row.identity == Identity::RandomBot`, from #197's `Classify` / `IdentityBoard::Lookup`.
6. `row.verifiedSelectedRandomBot`: a **separate, explicit proof** that this character is a selected Random Playerbot.

Every field defaults to the "show" value: era `Unknown`, flags `false`, identity `Unknown`. An out-of-range enum value also shows the row. A missing, stale or contradictory fact can therefore only make a row **visible**.

**Why a separate proof field (condition 6).** #197's `RandomBot` classification is built from runtime signals: no client socket (headless), Playerbots enabled, AI attached, master not self, and `IsRandomBot` listing. CS01 asked that positive *selected* rndbot evidence be kept distinct from headless, socket and config heuristics. The `Facts` model cannot prove "selected and verified" by itself, so this model adds a conservative explicit field instead of inventing an identity. **The model does not compute that field.** In the current plan its source would be IP's login-verified rndbot GUID identity (IP drafts #62–#64), which is the stage and identity authority. Until a caller supplies it, nothing is hidden.

## 4. Tests (`tests/f14_verified_rndbot_policy_tests.cpp`, 627 checks)

- **Cross product (71,680 inputs).** The dimensions are:
  - 5 era values, including 2 out of range;
  - GM yes/no;
  - own-row yes/no;
  - all 256 races;
  - 7 identity values, including 2 out of range;
  - verified yes/no.

  Exactly **two** inputs hide: Blood Elf and Draenei, each with all six conditions true.
- **Each condition is necessary.** Starting from the hiding case, clearing any single field shows the row. Default `Observer{}` / `Row{}` shows. A verified RandomBot of any non-TBC race shows.
- **Negative witnesses (CS01's list).** On both races, Unknown, Human, SelfBot and AltBot rows stay visible to a Vanilla player, even when the verified flag is wrongly set.
- **Observers.** Vanilla hides only the verified bot. TBC+, unknown era, GM, and out-of-range era values all see it.
- **Through #197 `Classify`:**
  - a headless Random Playerbot without verification is visible;
  - the same bot with verification is hidden;
  - a Playerbots-disabled (masked) bot, a dropped human, a socket-plus-random contradiction and an out-of-world player are all visible;
  - across all 128 `Facts` combinations, a row hides only when `Classify` gives `RandomBot` **and** it is verified.
- **Through #197 `IdentityBoard`:** never-published, unsampled, stale, future-dated and invalidated lookups all give Unknown, so the row is visible. Old policy B would have hidden them.
- **Strictly narrower than A and B.** Whatever the new rule hides, A and B also hide. The tests also show rows A or B hide that the new rule keeps visible:
  - a human row (A hides);
  - AltBot, SelfBot and Unknown rows (B hides);
  - an unverified RandomBot (both hide).
- **Compile time.** `static_assert`s cover the defaults and the single hiding case.
- **Build matrix:** GCC C++17/C++20 (`-Wall -Wextra -Werror -pedantic -Wshadow -Wconversion`), Clang C++17, ASan+UBSan.
- **Mutants:** `tests/f14_verified_rndbot_mutants.py` applies 16 must-fail edits, and all 16 are caught. They cover:
  - each condition dropped or widened;
  - Draenei dropped from the race check;
  - verification ignored;
  - each default flipped;
  - "never hides".
- **Inherited:** #197's own suite (2,936 checks) still passes unchanged.

## 5. Not done here, and who owns it

- **Observer effective era, the login-verified rndbot GUID identity, the `/who` and world callbacks, and the stage8 floor:** IP (#62–#64). This model only defines the decision once those facts exist.
- **Core immediate refresh, and creature/attacker/corpse lifecycle integration:** CS01 / Maintenance.
- **Not built:**
  - no competing Naxx `/who` packet filter;
  - no #145 hide-all enablement;
  - no wiring of #202's adapter or #228's seam to this rule.

  #228's test-only seam still calls #197's `HideTbcRow` (A/B); changing that would need a separate, reviewed assignment.
- **Not proven:** any runtime or observer-packet behaviour. Race is also visible through name query and character model (see #228).

## 6. Custom Modifications Register entry

| Field | Value |
|---|---|
| ID | F14-VRB (child of #197) |
| Files | `src/Systems/F14VerifiedRandomBotPolicy.h` (new), plus tests, CI and this document |
| Runtime effect | none (not included by any source; no config key) |
| Default | OFF / not present at runtime |
| Depends on | `src/Systems/PlayerIdentityPolicy.h` from #197, unchanged |
| Upstream touched | none (no core, Playerbots, IP, SQL or DBC) |
| Supersedes for runtime use | #197 policies A and B (kept only as historical test baselines) |
| Owner approval needed for | any wiring, enablement or deployment |
| Rollback | delete the five new files; nothing else references them |
