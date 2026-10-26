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

## 4. Status and explicit gates

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
