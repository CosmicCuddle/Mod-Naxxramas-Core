# A02 Part 27 — Owner-selected module-only candidate design and database persistence decision record

**State: SOURCE-ONLY DESIGN / NO IMPLEMENTATION APPROVAL / NO SQL / NO LIVE SERVER.**
**26 October 2026.** This supersedes the *preferred implementation path*, not the trust safety requirements, in the earlier post-handler contract. The independent native-core source review remains valid as a technical comparison.

## 1. Authoritative decision received and its exact limits

CS02 relayed in [team issue #48, 26 Oct, 14:56 GMT](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6419405984) the following **owner direction**:

- **C1 direction:** choose **module-only observation**, not a new upstream-core callback. Mirror stock handler conditions in `CanPacketReceive`, capture a pre-handler **candidate**, and compare on the next map update. Document and test source-drift risk. **No source implementation is thereby approved.**
- **C2 direction:** remembered preference should survive **server restarts** in a **new database table**, initially keyed in concept by player and PetNumber. **No SQL script, schema deployment, migration, or server access approved.** Separate owner review, backup, rollback and installation permission are still required.

This is the owner-selected approach, but it does **not** override prior requirements: **do not call a candidate a server-accepted human choice, do not set `TrustedManualReceipt`, and do not enable #165's automatic write path without evidence.** Default feature flags remain OFF. A source-only demonstration and later owner choice about weakened assurance are separate gates.

## 2. What the module can observe and what it cannot prove

The pinned public core `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` dispatches packet scripts before native handling. `HandlePetSpellAutocastOpcode` may reject, loop other same-entry controlled units, and only later mutate the spell stores and bar. `PROCESS_INPLACE` can run on map/world workers; `CMSG_PET_SET_ACTION` has different thread and actionbar semantics.

### Proposed module-only **candidate** pipeline (review only)

1. **Before handler:** identify exact packet opcode `CMSG_PET_SPELL_AUTOCAST`, player, controlled Hunter pet GUID, actual spell and normalized requested ON/OFF. Mirror *all pinned acceptance prerequisites* including guardian/pet current ownership, `Pet::HasSpell`, spell existence/autocastable, `CharmInfo`, source packet form and the action's actual supported rank. A valid mirror is **not yet** an accepted command.
2. **Record value-only prestate:** owner and pet GUIDs, PetNumber *hint*, possibly birth proof *if independently available*, summon generation, spell ID/chain, requested ON/OFF, pre `m_spells.active`, pre `m_autospells` membership, bar diagnostic, bounded update/request revision. The mirror must reject inconsistent core spell stores and no-op candidates. A pre-bar mismatch is diagnostic only.
3. **Do not claim post-handler causality:** the next map update checks the *same pet incarnation* and same allowed current rank/chain, both spell stores and any matching actionbar poststate, and that requested state differs from validated prestate. Reject/reclassify ambiguous or unknown pet/rank/mode and interposed events. This is a **matching observation**, not proof the native handler accepted the packet.
4. **Human mode:** a client packet is compatible with an attached SelfBot. The public Playerbots `IsRealPlayer/IsSelfBot` helper uses an unguarded map at pinned head; never read it from arbitrary map worker without separately reviewed serialization and positive source. Until C3, `OwnerMode=Unknown`.
5. **Apply authority:** candidates produce at most `CandidateMatched` for **diagnostics**; `TrustedManualReceipt=false` and `EligibleForAutomaticRestore=false`. No legacy v1 writes, no automatic restoring on pet summon, no SQL preference promotion. Any owner-approved weaker mode would require its own distinct policy name, warning, tests and authorization — it cannot be silently called equivalent to genuine native acceptance.

### Required counterexamples before implementation can be approved

- **Interposed-writer false positive:** client request passes module mirror but fails/rejected in native handler; before next update Playerbots, IP or script changes the pet to the requested state. Poststate matches **without native acceptance**.
- **Interposed-writer false negative:** native handler accepts ON; independent writer changes OFF before next update. Poststate mismatch **despite acceptance**.
- **Rank timing:** IP may unlearn one rank and later learn another after its deferred 200-ms event; no fixed sleep is a proof of settlement. An attempt must not learn or force a rank.
- **Map thread ordering:** `PROCESS_INPLACE` packet and map update ordering across eight workers; torn records or read/write races fail closed. No unlocked `_playerbotsAIMap` reads.
- **Pet replaced/recycled:** identical pet name/family/number, different actual birth; do not carry the remembered preference without authoritative binding. The latest manual OFF must supersede older ON only for **same owner + validated birth + spell chain**.
- **Actionbar and other units:** repeated/no-op packet, passive/absent spell, same-entry other controlled unit, off-bar spell, double bar slot, `CMSG_PET_SET_ACTION` two-slot drag: none can silently mint trust.

The first two traces are **observationally indistinguishable at the update point** without another trusted causal boundary; no number of synthetic test passes can make them proof. That is the fundamental remaining A02 limitation of the owner's preferred no-core-hook route.

## 3. C2 direction: restart-durable preferences, not just a PetNumber table

**No real schema or SQL is committed here.** This is a field-level requirements list for a future owner-private migration design.

Suggested abstract record fields (not DDL): player identity, current persistent pet-number hint, **independent proven birth identity**, spell-chain key, choice ON/OFF, latest accepted revision and revision domain, evidence origin and assurance level, row version for concurrency, invalidation/tombstone state and bounded audit metadata. Schema identity, indexing, permissions, migration and retention remain unapproved.

**Why player+PetNumber alone is insufficient as a trusted lifetime key:**

- Pinned `Pet.cpp:1572–1577` explicitly describes PetNumber reuse in some situations, and `ObjectMgr.cpp:8117–8129` reseeds numbers from database MAX on restart. The owner's real server state is not verified; this is a **possible reuse mechanism**, not a claim that reuse happened.
- Additional pinned public source review in [team #48](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6419417582) identifies **asynchronous pet persistence**: `SavePetToDB` uses separate enqueued transactions for spell/auras and base `character_pet` row. Sidecar writes in a third transaction do not give an atomic birth commit, and `CommitTransaction` is not completion confirmation. No owner DB has been inspected.
- If an independent **durable** birth binding cannot be demonstrated after restart, load the row as **Unverified / NoWrite**, never as a trusted remembered preference just because a player+PetNumber value matches.
- New birth token generation must have durable lifecycle creation and invalidation rules. A client-generated token or old addon identity is not a server-certified birth. Prefer reject/defer over guessing.
- An optional staging-only prototype could record preferences as **non-applied telemetry** keyed by player+PetNumber to measure collisions, but its privacy and SQL changes also require separate approval.

**Before any owner-private DDL or migration:** backups and recorded restore path; no writes against live DB; character_pet lifecycle and transaction audit; migration of v1 data must default untrusted; explicit delete/abandon/re-tame/restart/recovery tests; verify a new pet with the same name/number cannot inherit old choices; fail-closed after DB timeout/partial commit; operator-access and rollback. The new table must not compromise the existing eight map threads or block gameplay on synchronous DB calls.

## 4. New peer-verified async ordering and temporary-resummon findings

**Pinned public source, not owner's actual installation:**

- The same `CharacterDatabase` pool has one FIFO work queue with a configurable count of independent asynchronous DB workers; **the default is one, the owner's effective count is UNKNOWN**. When more than one worker executes different dequeued operations, *completion* need not follow *dequeue* order. An independent [N-Core source-bound C++ fixture](https://github.com/CosmicCuddle/N-Core/actions/runs/40348692127) compiled the actual pinned `PCQueue.h` with two workers and demonstrated dequeue `1,2` followed by completion `2,1`. This does **not** demonstrate actual MySQL pet-transaction reordering or failure.
- Module-specific database pools have their **own queue**, so a sidecar transaction enqueued there cannot be assumed ordered with the character-pet row commit, even if each pool individually has one worker. `AsyncCommitTransaction` confirms its **own** operation only. Pinned `Pet::SavePetToDB` uses **two fire-and-forget commits** without an atomic pet birth-bound module hook. Review details in [team research](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6419904431) and the [separate N-Core queue witness](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6419901648).
- Therefore neither a sidecar callback, a `character_pet` presence read-back, single-worker FIFO by itself, nor returned `SavePetToDB` certifies permanent birth. **If canonical and sidecar birth state cannot be proven atomically or revalidated with adequate failure handling, the persisted row must remain Unverified/NoWrite.** Do not silently turn SQL durability into evidence of identity.
- [CS03's #169 source review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/169#issuecomment-6419605947) documents normal temporary unsummon/recreation during mounting, dismounting and far teleports. This can create many `Pet*` incarnations for one human choice. The existing #169 20-attempt budget is **per incarnation**, so repeated object changes could renew that limit. This is a demonstrated **source-model edge case**, not proof of real server toggle loops.
- CS01's separate [DRAFT #172](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/172) explores an additional in-memory cumulative limit **per verified birth, chain and latest accepted revision**. Its latest exact-head [CI 40366314938](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40366314938) at `f9d0faf` independently passed **104/104 C++17** and **104/104 C++20** standalone assertions, with a synthetic IP-allowed **rank ID changing on each pet incarnation** without resetting the same normalized ability-chain budget. The fixture deliberately loses its budget on process restart and supplies fictional trusted fields. No policy selection, real pet integration, persistent counter or owner permission follows from this pass.
- [CS02's independent #169 tracked-model review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/169#issuecomment-6422206120) reproduced only **40/60** attempted writes when alternating two chains with a 20-per-chain bound, versus the prior unsafe 60/60 raw shared-budget probe. CS02 notes that **a single normalized spell-chain key, not rank-specific spell IDs**, must own each slot, and 50 newly accepted revisions could still produce many cumulative attempts. This is not a time-based global rate limiter; no source-only tests can establish real trusted accepted human revisions.
- Owner decision still required on *both* whether a cross-incarnation limit is wanted **and** whether that count must survive restart. Without independently trusted durable birth/revision, no restore may be authorised regardless of the number of green synthetic tests.

## 4A. Part27 peer challenges — bounded confidence, not an invented native receipt

### C1: CS02's narrower deterministic native-handler window

[CS02's pinned source review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/168#issuecomment-6422207249) correctly identifies that `WorldSession.cpp:459–465` invokes `CanPacketReceive` and, if it returns true, immediately invokes `opHandle->Call` **on the same dispatch thread**. Pinned `HandlePetSpellAutocastOpcode` then follows a finite visible set of validations and deterministic state mutations. Public pinned Playerbots appears not to veto this opcode. This makes the **module-only route worth evaluating further**, rather than assuming a long scheduling gap exists before native dispatch.

However, source-local immediacy is **not by itself** a proven accepted-command receipt. A script hook can short-circuit after the recording module's callback; a later callback could change relevant state or veto, the installed custom server may differ from the public pin, and the map update is still later than the handler and any IP/AI/script writes. A passing precheck plus matching later state cannot distinguish these paths. The earlier counterexamples remain *possible*, not confirmed incidents on the owner's actual server.

**Source-only implementation acceptance matrix before a future owner-approved C1 candidate:**

1. Confirm exact installed core/module commit and `CMSG_PET_SPELL_AUTOCAST` handler body, packet layout, call site and all other enabled `CanPacketReceive` implementations; automatically detect drift. Source pin alone is not a proof of actual deployment.
2. Prove the candidate's hook order and whether **any later hook** can veto/mutate after it records; neither static public Playerbots inspection nor a later state snapshot proves this across all installed custom scripts. If unknown, **diagnostic / NoWrite**.
3. Validate the exact current Hunter guardian pet and per-target spell store transition, not any extra same-entry controlled unit or SET_ACTION bar movement. A matching bar after the fact is necessary where present, but doesn't identify the causal writer.
4. Establish serialized pre-observation/next-update ownership under **all eight map threads**, positive human-vs-attached-SelfBot mode at both boundaries, and rank consistency after IP work. No unlocked bot-map reads.
5. Inject controlled counterexample traces in an approved **offline fake dispatcher** first: rejection by a later hook followed by an independent store toggle, accepted request followed by a later undo, source drift, rank replace, pet swap and stale OFF/ON. Require that no synthetic **matched** candidate is silently promoted into a genuine accepted manual receipt.
6. If the owner separately authorizes an explicitly **lower-assurance** policy, give it a separate status/flag, disallow legacy-v1 promotion and enforce all remaining birth/human/IP checks; never rename `CandidateMatched` to `TrustedManualReceipt` by implication.

This reconciles the owner-selected **no-core-hook** direction with a testable path for reducing uncertainty, without claiming a mathematically impossible native callback exists at the current module seam.

### C2: CS02's proposed startup orphan reconciliation — conditional alternative only

[CS02's follow-up](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/48#issuecomment-6426071970) proposes deleting orphaned sidecar records at every restart *before logins* so PetNumber reuse cannot inherit a prior owner's preference. The public source offers supporting **limited** facts:

- `ObjectMgr::LoadPetNumber` reads `MAX(id)` from `character_pet` and reseeds the in-memory monotonic counter; `GeneratePetNumber` increments it under a mutex. On a **single uninterrupted server process using only this allocator**, new numbers do not reuse a previous one.
- Pinned `World.cpp:711–713` calls `LoadPetNumber` during startup, and `World.cpp:1033` invokes `OnBeforeWorldInitialized` later. That is a *candidate* reconciliation point, **not** confirmation of owner-supplied login gating, DB schema or verified cleanup completion.
- Existing and newly identified delete paths are **not** all `Pet::DeleteFromDB`: `Pet::SavePetToDB` can broadly delete owner's current/overflow pet rows, and character removal deletes by owner; orphan cleanup may cover more than a single pet hook. A canonical row may be absent after an asynchronous transaction failure or disconnection, even when the player expected it saved.

**What a safe conditional startup sweep would have to prove** (not implemented or owner-approved):

1. Exactly one effective Worldserver owns the character DB lifecycle; no overlapping old/new process, external character import/restore, GM id reassignment or concurrent module sidecar writer. Explicitly account for custom Playerbots/Individual Progression and non-stock scripts.
2. Sidecar/canonical identity checks cover BOTH owner and PetNumber and run **to successful confirmed completion before any pet preference can be loaded or any session logs in**; inability to read either store, interrupted cleanup, partial failure or migration mismatch means **all automatic restores stay OFF**. Never use a fire-and-forget delete then assume completion.
3. Validate that a previously deleted top-number row cannot leave a sidecar record surviving the same startup sweep before the allocator can issue that recycled id. Include synthetic last-ID reuse, broad slot delete, player delete, crash/restart, async late write, and a full DB backup/rollback test plan.
4. Verify the owner's actual DB/store topology. A module DB pool has an independent queue and may not be able to perform a safe atomic cross-database join against `CharacterDatabase`. No assumed SQL triggers, foreign keys or global ordering.
5. A surviving `(owner, PetNumber)` pair is **continuity evidence under these controlled assumptions**, not independently certified pet birth, authenticated manual input or proof of a committed canonical pet-save transaction. Out-of-band restores or a reused same pair with a different physical pet would defeat orphan-only comparison; reject and quarantine if such operations are possible without a reconciliation epoch.
6. The **remaining stale live preference** problem is separate: a canonical row may be asynchronously removed after the last sidecar read. A source-only bounded reconciliation design cannot make a subsequently deleted pet trustworthy by reading a previously valid pair. Do not promote to `TrustedCurrentBirth` absent a separately approved, invalidation-aware model.

**Decision:** evaluate this as a promising **owner-selected module-only C2 research option**, not reject it a priori, but do **not** label it a permanent canonical birth certificate. No SQL, deletion routine, startup hook or server access is authorized by these notes.

## 5. Status and explicit gates

| Gate | Direction or status | Work currently authorized |
|---|---|---|
| C1 module-only | **Owner direction relayed via CS02;** use pre-handler candidate + later snapshot, no core hook | Source design and peer review. **No module implementation approved**. No trusted acceptance established |
| C2 durable DB | **Owner direction relayed via CS02;** new table with restart persistence | Field-level design/rollback research. **No actual schema, SQL or host access approved** |
| C3 positive human/SelfBot | Not resolved | No unsafe map lookups, no trust promotion |
| C4 staging & gameplay | Not approved | No build deployment, no installation or owner gameplay changes |
| #165 fail-closed v1 writer | Full pinned Worldserver link PASS at `0bec377` | Preserve absolutely; default OFF |
| #169 attempt ledger | Synthetic 224/224 strict C++17 and C++20 PASS at `5530f53` | Unwired model only; no accepted receipt/pet writes |

**Unresolved owner trade-off:** If the project must have *reliable automatic restoration of accepted human ON/OFF*, the module-only candidate does not meet the previous causal proof requirement. A separate explicit owner decision is needed on whether to (a) keep automatic restore disabled and use diagnostic observation only, (b) accept a clearly labelled lower-assurance opt-in mode after specific tests, or (c) reconsider a narrow native hook. We do **not** assume or silently select any of these.

**Public repository protection:** no private owner DB schema, SQL, NPC/item/quest/loot/Individual Progression source relationships, paths, credentials or installation data. Nothing merged or deployed.
