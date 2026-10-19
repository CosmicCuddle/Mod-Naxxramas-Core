# Hunter Pet Autocast — Native producer and handoff feasibility (18 Oct 2026)

**SOURCE-VERIFIED DESIGN / REVIEW PROPOSAL ONLY.** No upstream AzerothCore, Individual Progression (IP) or Playerbots modifications have been approved or made. No C++ producer, DB preferences, pet toggling, installation, in-game test or restoration exists. This document is prepared on a **separate research branch** to avoid disturbing individual draft PR #26 and the combined Worldserver CI.

## Exact pinned source baselines reviewed

| Component | Pinned Git commit | Relevant source |
| --- | --- | --- |
| Grimfeather IP | `4ff4b5fcc1480348f058c632573143e62d4e3a41` | [IndividualProgressionSpells.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp), [IndividualProgression.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgression.cpp) |
| Playerbots | `037c01418b5d01506917a3db9b44fd56ac5f965c` | [PetsAction.cpp](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/PetsAction.cpp), [PlayerbotAI.cpp](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/PlayerbotAI.cpp) |
| Naxx Core read-only bridge | Draft PR #26 `590a52b32a89092f2ace8011333a385741ae72b0` | [HunterPetAutocastPlayerbotBridgeContract.h](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/blob/590a52b32a89092f2ace8011333a385741ae72b0/src/Systems/HunterPetAutocastPlayerbotBridgeContract.h) and synthetic C++ regression. |

**Source identity matters.** These facts are verified on the pinned trees only, not the installed realm's possibly different commits or config. Individual draft #26 [full pinned CI #39157241184](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/39157241184) passed, but this builds the *audit and standalone v3 model*, not a real producer.

## 1. IP scheduling is not an authoritative post-reconcile signal

**Verified:** IP's `IndividualPlayerProgression_PetScript::ScheduleDelayedSpellCheck` creates `new DelayedPetSpellCheck(owner->GetGUID())`. The event fields are only `_ownerGuid` and `_attempts`. In `DelayedPetSpellCheck::Execute`, the callback re-fetches `player->GetPet()` **at execution time**; it does not carry the particular Pet originally scheduled. The owner may have no pet, a re-summoned pet, or a different pet after a stable swap. The event must not assert that the original Pet was reconciled merely because execution completed.

**Verified:** If `pet->isBeingLoaded()` and `_attempts < 10`, IP reschedules after 200ms. If ten attempts are exhausted, the event proceeds even if the Pet is still loading. Therefore an event return **cannot always mean ready**. The private `PendingPetSpellCheck::pending` flag is cleared **before** `checkHunterPetSpells(player)`; clearing the flag is **not** proof that reconciliation ran successfully.

**Verified:** `IndividualProgression::checkHunterPetSpells(Player*)` returns `void` and has multiple early returns: unavailable/out-of-world or disabled `VanillaHunterPets`, `isBotAccount`, non-Hunter, progression past TBC Tier 5, no pet, no creature/template/family. A hypothetical callback attached after calling this `void` function would falsely imply a successful reconciliation for these skip paths unless it carries an explicit outcome and retains Pet identity.

**Bot account nuance:** IP's `isBotAccount` obtains the **actual account name** and `std::regex_match`es `IndividualProgression.BotAccountsRegex`, whose pinned default is `^RNDBOT.*`. It does **not** simply test whether Playerbots is controlling this Player. A controlled Altbot may or may not be excluded depending on the operator's actual account name/config. **Do not infer** either status in code or documentation; first verify effective operator settings in a separately approved staging investigation. Do not collect/log account names in a proposed observer.

### Minimum IP result contract (requires separate upstream approval)

Propose an event **only after** exact-original-Pet validation and a distinct outcome, e.g.:

| Outcome category | Meaning for a no-write Naxx consumer |
| --- | --- |
| `CompletedEligible` | Correct owner/Pet/generation, no loading, Hunter and progression rules enabled, relevant family/rank reconciliation returned, and independently verified current legal spellbook snapshot |
| `RetryQueued` | The particular original Pet remains loading; no completion event yet |
| `SkippedOwnerMissing` / `SkippedPetChanged` | Return without readiness; retire original generation |
| `SkippedDisabledOrIneligible` | IP disabled, bot account blocked, wrong class/stage/family or other early return. No restoration |
| `AbortedLoadingOrStaleGeneration` | Retry cap exhausted while loading, pet incarnation/generation changed, or event outdated. Fail closed |
| `CompletedNoOp` | Only if IP **actually assessed** the eligible original Pet and found a lawful fixed point; not from a blind early return |

The names above are **proposed**, not real enums or functions in IP. The event must preserve original pet incarnation and scheduling generation, verify the same current Pet before/after call, and revoke readiness when new IP work is queued. The actual result cannot be fabricated by Naxx based on packets, elapsed time, stable spellbook or private flags.

## 2. Playerbots has multiple native Pet::ToggleAutocast call paths

**Verified:** `TogglePetSpellAutoCastAction::Execute` in pinned `PetsAction.cpp` iterates the Pet's spells and calls `pet->ToggleAutocast(spellInfo, shouldApply)` to reassert known bot defaults unless the spell is on the disabled list. It can change multiple spells and returns one aggregate `toggled` boolean. This is **AI policy**, never authenticated human preference.

**Verified:** Pinned `PlayerbotAI.cpp` also contains **at least two distinct** `pet->ToggleAutocast(spellInfo, !autocast)` paths in `CastSpell` overloads. A `TellMaster` text message after a toggle describes an action; it does not prove that the request originated from an authorised human master. Native spell toggle state is a *result*, not an origin proof.

**Verified:** `HandleCommand` first checks security, message type, prefix and filter, and may queue commands as `ChatCommandHolder`. `HandleCommands` later uses `ExternalEventHelper::ParseChatCommand(command, owner)`. There are also internal bot-generated command sources. The origin/provenance must flow through the *accepted, deferred action* itself, not be guessed from an observed chat message or latest Pet state.

### Minimum Playerbots producer contract (requires separate upstream approval)

A single producer/ownership boundary must cover **every native toggle call path that can affect this feature**, not just one AI action. After native validation, it would emit one strictly sequenced **per-spell** applied/accepted result with:

- Actual source category: `BotDefault`, factory/tame, internal AI or **security-accepted/authenticated master**; preserve the originating command token through deferral.
- Immutable owner/bot session and **original Pet incarnation + lifecycle generation**, requested spell ID and legal rank family; check against *current* Pet at emission.
- Before and after **native** autocast state for the same Pet/spell, independently distinguishing an applied **idempotent accepted master request** from a state transition.
- A monotonic per-Pet lifecycle operation sequence shared by all spells and origins. Replay, missing sequence, unknown origin and concurrent/stale generation must fail closed.
- Explicit current IP readiness/rank/autocastability evidence obtained from an authoritative interface; Playerbots cannot grant or attest eligibility merely because it still has an old spell ID.
- An AI-owned policy-coordination acknowledgement whenever the desired master ON/OFF differs from its automatic `has pet` defaults; neither a Naxx repeated toggle timer nor permanently disabling all AI pet behaviour is acceptable.

**No such complete producer exists in the pinned public module surface.** An `Engine::ActionExecutionListener::After(bool)` aggregate does not identify an actually applied native per-spell human preference. `Engine*` belongs to Playerbots and its direct access is protected, with ownership/lifetime risk.

## 3. Trusted signal wiring sequence, with hard stops

1. **Observe only on a disposable staging clone.** Record actual installed source/config revisions. For any stage touching pet state, arrange a complete verified-restorable **characters DB** backup, plus executable and config rollback. This research branch itself needs none.
2. **Pet identity first.** Verify a non-recycled persistent Pet incarnation across stable swap, deletion/replacement and Worldserver restart. A PetNumber or pointer is not a sufficient permanent preference key. If impossible on existing core, stop and seek separately approved minimal pet lifecycle interface.
3. **IP outcome second.** Preserve original Pet through delayed work and carry explicit completed/skipped/aborted outcome, tested with loading retries, account regex exclusions, wrong family, rank change and pet replacement. Do not report readiness on a bypass/early return.
4. **Playerbots producer third.** Trace *all native toggle paths*, with exact spell, master provenance and after-state checks; test automated default ON/OFF as **observation only**, command idempotence, multiple ability IDs, AI reinitialisation and out-of-order events.
5. **Bot-policy precedence fourth.** Define an AI-owned override token/expiry so verified explicit master OFF is not immediately re-enabled by the default bot policy. Do not repeat `ToggleAutocast` in a Naxx timer.
6. **Naxx storage LAST.** Only after trusted end-to-end event production exists, separately design preference retention per real Pet incarnation + spell family and legal-rank re-validation, SQL migration/rollback, permission gates, fail-closed resummon/revive/relog/restart, and operator pilot acceptance.

**Approval boundary:** This is an architecture and test contract for discussion. Do NOT edit or PR to IP, Playerbots or AzerothCore, add persistent preference tables, change bot AI policy, merge, install or enable features without separately explicit owner approval for the specific cross-module task. If the producer/identity proof cannot be delivered, keep the existing read-only default-off diagnostic; a convincing synthetic green test is not grounds to deploy persistence.
