# Golemagg diagnostic log review — offline helper

**Prepared research branch; not installed, deployed, merged or run on the owner's Worldserver.** The existing Golemagg diagnostic draft PR #30 is **OFF by default** and still requires separate operator approval, installed-version comparison, restorable backups, a one-Altbot config gate and a Worldserver restart before any in-game sampling.

## Purpose

After a separately approved Grau-only raid pilot, summarize already-written Worldserver log lines containing the marker GolemaggActionAudit READ ONLY: from a **private, local copy**. This does not increase game logging frequency, change movement or fetch data from a server.

The existing observer samples at most 24 lines per qualifying bot/combat window with a 2.5-second minimum interval. The newer unmerged PR #30 at SHA 3c742a1 adds explicit fields retreat_stacks_20 and inside_retreat_12yd when the **pinned Playerbots Magma Splash policy** crosses 20 stacks and 12 yards. Earlier observer revisions lacked those booleans; the offline helper can infer threshold buckets from old stack/distance fields, but counts how many samples lack explicit values.

The local helper reports only totals:

- Valid/malformed observer line counts and distinct character count (never names)
- Samples with 20+ stacks and count of stack-bucket transitions
- Sampled crossings of the 12-yard boss distance bucket, excluding missing boss lookup
- Temporary boss lookup misses and samples when boss is at or under 10% HP
- Recent action tails *mentioning* Golemagg back-off (not proof the action executed)
- Count of sampled **retreat-condition snapshots**: living boss lookup present, boss HP **above 10%**, Magma Splash **at least 20 stacks**, and boss distance **under 12 yards**. This is source-informed context, not proof that the Playerbots strategy was selected or executed
- Separately count back-off *mentions* during a sampled condition versus mentions without a confirmed condition. **A recent action tail may describe an earlier action**, so these are not synchronized events or a contradiction by themselves
- Sample-number resets/replays which may indicate combat-window rollover
- **Unavailable recent action history samples** using the literal sentinel `(no recent action)`, proposed separately in [stacked read-only observer PR #40](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/40). This means the action log was empty when queried, **not that the bot performed no actions**. Such samples still count toward 20-stack/12-yard buckets, but never create a false back-off action mention

It does **not** display raw log lines, bot names, recent actions, target names, account data or any configuration. Original logs may contain personal data; keep them private and do not upload raw logs to GitHub discussions.

## Usage on a separately supplied local text file

For future operator review only, **not an instruction to enable the diagnostic or execute the script now**:

    python3 scripts/summarize_golemagg_action_audit.py /path/to/private-redacted-worldserver.log

Run on a local computer or disposable analysis workspace with Python 3.10+ and a trusted copy of the script. It reads only the specified local file, prints aggregate counts and exits; standard Python library only, no network or file writes.

- Exit 0: one or more valid observer samples.
- Exit 1: readable log but **no parseable** samples.
- Exit 2: missing or unreadable log.

**Compatibility:** new observer output has explicit threshold booleans; old output lacks them and is reported as legacy/inferred. The helper can also distinguish the proposed new PR #40 `(no recent action)` marker from a real recent action tail, without modifying the parent Golemagg PR #30 or requiring PR #40 to be merged. The two stacked PRs #35 and #40 are separate siblings and require careful later integration if approved. The helper cannot prove which revision is installed on the realm.

## Interpretation and safety limitations

Current observer threshold flags are checked against the actual stack and distance fields. A contradictory boolean (or non-finite HP/distance such as `nan`/`inf`) is considered an **unparsed** line rather than evidence. When boss lookup is missing, distance is unknown and **never** counted as within 12 yards; an unknown condition is counted only as *not confirmed*, not as proof of absence. Legacy samples without explicit threshold flags remain inferred and separately marked.

The pinned Playerbots HandleRemoteCommand("action") returns a **recent action-log tail**, not a causally linked exact execution event. Repeated mentions of "mc golemagg back off" do not demonstrate that it caused an oscillation. The relevant native strategy applies under conditions including non-tank bot, boss above 10% HP, Magma Splash 20+ stacks and roughly 12-yard retreat. Other AI movement actions, priorities, pathfinding, lag and loss of threat target could still be involved.

Transitions **between** the 2.5-second samples are unknown. Distance when boss threat lookup is missing is -1 and intentionally **excluded** from distance transition comparisons. Sample number resets are not connected across combat windows. This can corroborate or weaken a hypothesis, never certify a movement fix. Actual root cause still needs reviewed gameplay and exact installed Playerbots code.

Before any future on-realm collection: separately obtain explicit owner approval for source revision, install/restart/enable actions and scope; back up executable/config/source, prove restores, keep Hunter Ammo disabled, and disable audit after the authorised one-Grau test. No global AI interception or upstream Playerbots change authorised.


## 19 October 2026 — pinned MC back-off policy provenance for the offline summary

The read-only parser treats **20 Magma Splash stacks / 12 yards / boss HP above 10%** as one *sampled retreat-condition snapshot*. These numbers and the assumed bot role are now checked against exact pinned `mod-playerbots/mod-playerbots@037c01418b5d01506917a3db9b44fd56ac5f965c` source using `scripts/check_golemagg_retreat_policy_pinned.py`, its disposable tests and a sparse-checkout GitHub Action.

The check covers **five relevant native Playerbots files**—`MCHelpers.h`, `MCTriggers.cpp`, `MCActions.cpp`, `MCMultipliers.cpp`, and `MCStrategy.cpp`—plus this draft's existing Golemagg C++ observer constants and Python summary. It rejects drift in the exact stack/distance values, the no-tank/remaining-boss-health trigger, the actual `MoveAway` action and the re-engagement multiplier's explicitly named action types.

**Critical distinction:** The pinned Playerbots Golemagg multiplier denies `AttackAction`, `MeleeAction`, and `CastReachTargetSpellAction` when stacks are at least 20 before the burn phase. This is **not** a general engine-wide veto of `FollowAction`, `MoveToAction` or other movement strategies; the source checker makes no such claim. The explicit Golemagg retreat trigger additionally requires the bot to be within 12 yards; the multiplier need not require this distance. The boss's below/equal 10% burn phase turns off these back-off restrictions. **An observed run-in/run-out loop at low stacks, outside that distance, or in some other action family cannot automatically be attributed to this particular trigger.**

The source contract and synthetic policy model **do not inspect live bots**, replay actual AI execution, veto any action, assert that every action class is covered, or establish which movement planner issued the oscillating command. Recent-action-tail mentions and 2.5-second sampled snapshots remain asynchronous observations. The intended next step is an owner-approved **single-bot diagnostic** with independently verified installed SHAs, restorable backups and a bounded log excerpt, only if the owner later authorizes deployment. Do not merge or deploy this draft based on source CI.
