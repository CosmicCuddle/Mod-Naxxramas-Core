# Hunter pet autocast persistence — Naxxramas Core feasibility gate

**State (16 October 2026): RESEARCH + DISABLED READ-ONLY AUDIT PROTOTYPE. The prototype ONLY observes confirmed autocast-toggle transitions; no restoration, persistence, SQL, live gameplay test, merge or deployment.**
**Destination:** `CosmicCuddle/Mod-Naxxramas-Core` exclusively. `Mod-Naxxramas-Hunter-Pets` is a read-only research reference, **not** the runtime destination.
**Owner request:** Restore the last explicit ON/OFF autocast choice for **every legitimately known, autocast-capable Hunter pet ability**, independently for every pet and rank family, after IP finishes its normal remove/relearn process. Lightning Breath is a pilot, not a restriction. Non-autocastable abilities have no autocast setting to preserve. **Do not** change IP's rank restoration or suppress its normal learned-spell notifications.

## 1. Exact source evidence (read only)

The source pins below are **GitHub CI baselines**, not independently verified as the running worldserver build. Verify the owner's actual deployed commits before running any trial.

| Source | Observation |
| --- | --- |
| [Grimfeather AzerothCore Pet.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp) lines 216–500 | Existing pets are added to the map **before** the asynchronous DB spell load; `Pet::isBeingLoaded()` becomes false toward callback completion. `OnPetAddToWorld` is NOT a post-load event. |
| Same Pet.cpp lines 1559–1600, 1766–1918, 2247–2288 | Pet spells hold `PetSpell.active`; `ToggleAutocast(spellInfo, enabled)` affects `m_autospells` and persisted pet spell flags, **does not learn a spell**. `learnSpell` may send `SMSG_PET_LEARNED_SPELL`. |
| [Grimfeather CharmInfo.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Unit/CharmInfo.cpp) lines 149–185, 249–300 | Native actionbar supports the first-rank spell chain and `SetSpellAutocast`; restoring server autocast **alone** does not demonstrate that the 3.3.5 client button agrees. |
| [Grimfeather PetHandler.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Handlers/PetHandler.cpp) lines 696–839 and 955–1007 | **Both** `CMSG_PET_SET_ACTION` and `CMSG_PET_SPELL_AUTOCAST` can express a user's ON/OFF choice. The native handler validates pet ownership, spell knowledge and whether autocast is allowed. |
| [Grimfeather PetPackets.cpp](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Server/Packets/PetPackets.cpp) lines 35–40 | Autocast opcode reads pet GUID, spell ID, and boolean; its packet is not the actionbar opcode. |
| [Grimfeather ServerScript.h](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Scripting/ScriptDefines/ServerScript.h) | `CanPacketReceive` is available, but runs **before** native handler acceptance; never persist an unverified requested state from this hook. |
| [Grimfeather IndividualProgressionSpells.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp) lines 36–97, 330–341, 1250–1350 | IP picks the highest *legitimately learned* Hunter dummy rank and removes other ranks, then learns the permitted spell if missing. For Wind Serpents, Lightning Breath R5 is 25011 and R6 is 25012. It schedules a 200ms delayed Pet BasicEvent, retries up to 10 times while `isBeingLoaded()`, then runs pet reconciliation. |
| Same IP source line 41; [IndividualProgression.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgression.cpp) lines 351–360 | IP skips Hunter spell reconciliation for accounts matched by its bot-account regex. Do **not** assume a Playerbot Altbot follows the same path as a normal Hunter. |
| [Pinned Playerbots PetsAction.cpp](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/PetsAction.cpp) lines 342–405 | `TogglePetSpellAutoCastAction` calls `pet->ToggleAutocast(spellInfo, shouldApply)` **directly**, not through either client packet hook. Its blanket `shouldApply=true` for most autocastable spells is an AI policy decision, NOT evidence the player opted ON. It also removes stale entries directly from `m_autospells`. |
| [Pinned Hunter noncombat strategy](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Class/Hunter/Strategy/GenericHunterNonCombatStrategy.cpp) lines 27–31 | The `has pet` trigger can invoke `toggle pet spell` with priority 60. This may conflict with a player's intentionally disabled autocast. **A module-only hook does not distinguish an AI direct toggle from a user preference.** |

| [Hunter Pets source-pinned lifecycle audit](https://github.com/CosmicCuddle/Mod-Naxxramas-Hunter-Pets/blob/main/docs/SOURCE-PINNED-PET-LIFECYCLE-AUDIT.md) | Existing blueprint independently identifies the early `OnPetAddToWorld` and pet-identity/persistence risks. **Reference only.** |

**Evidence boundary:** Code proves the hooks/methods exist, not that the owner's *current installed* Playerbots emits the relevant packets, that the IP event always beats a module timer, or that a native pet number cannot be reused.

## 1B. Native actionbar persistence and post-IP observability

The pinned `Pet.cpp::SavePetToDB` saves `pet_spell.active` and serializes the current pet action bar into `character_pet.abdata` during native pet saves. On existing-pet load, the saved action bar is restored **before** `OnPetAddToWorld` and **before** async `_LoadSpells`. Thus **the earliest on-add actionbar state may preserve a last user-selected autocast setting**, even when IP's later cleanup removes the ability from the action bar. This is a hypothesis requiring staging observations, not proof every saved pet bar contains a faithful preference.

The pinned `Pet::removeSpell(spell, false, true)` removes a matching actionbar entry; IP's `checkHunterPetSpells` calls `unlearnSpell(..., false, true)` on all disallowed ranks. Later `Pet::learnSpell` may reconstruct a legal rank with default autocast OFF. These paths explain how a saved ON preference **could be lost** even when native saving previously worked. Neither path guarantees a stable persisted preference after an IP reconciliation cycle.

**Additional targeted read-only evidence:** AzerothCore `Pet::learnSpell` sends `SMSG_PET_LEARNED_SPELL` when the pet is not loading. Individual Progression's `checkHunterPetSpells` can emit this when it legitimately re-learns Lightning Breath R5. The isolated module registers `ServerScript::OnPacketSent` for *only* this packet while `AuditEnabled=1` and logs all autocastable Hunter pet learned-spell packet IDs (bounded to 32 distinct IDs pending per pet), checking whether each is still known at the next Player update. It **never** blocks, modifies or replaces learned-spell notifications. Seeing the packet demonstrates a learn event, **not** that IP originated it or that its complete reconciliation is over. A rank that was already known may not emit a packet at all.

**Revive caveat and NEW read-only audit:** `Pet::setDeathState(Alive)` may revive the existing Pet without `OnPetAddToWorld`. The audit now observes dead→alive transitions via `PlayerScript::OnPlayerAfterUpdate` for an actively owned Hunter pet (up to four observed revivals per **pet object**), records bounded generic autocast states at death and revival, and queues one +2500ms snapshot on that same pet's event clock. It does **not** teach, toggle, persist, claim IP readiness or infer an authoritative user preference. Normal lethal-damage Hunter pet death is now also observed by the pinned `UnitScript::OnUnitDeath` hook, so an ordinary death followed by revival entirely between Player updates still supplies a recorded death signal. Player-update polling remains a fallback if that hook was not called; an audit that begins with an already-dead pet also records death. Unusual scripted deaths that bypass both signals may still be missed. None of these samples confirms post-IP readiness or human intention. Pet replacement, logout and changed revival sequence make queued observations skip. Staging must determine whether the probe sees revives and whether IP acts afterward. A robust restoration trigger remains unproven.

**Added read-only diagnostic:** A `PetScript::OnPetAddToWorld` observer records the original Lightning Breath R5/R6 actionbar ID and ON/OFF state, and a bounded `PlayerScript::OnPlayerAfterUpdate` probe records when `pet->isBeingLoaded()` becomes false and takes a single later snapshot (normally at ≥3 seconds; stops by 10 seconds even if loading persists). The observer exists only under the explicit `AuditEnabled` setting, default `0`. It never toggles, teaches, writes or claims IP completion. A staging capture must establish whether these snapshots bracket the real IP event and whether the earlier actionbar stores a reliable explicit choice.

**More precise post-IP ordering proof:** the pinned IP event clears its internal pending flag **before** calling Hunter pet spell reconciliation. Even if a future module could read that private marker, false cannot mean complete. The new pinned-source CI check documents this explicit ordering blocker; it does not read IP internals at runtime or authorize a fixed delay.

**Further timing evidence:** a single +2500ms **pet-owned event-clock sample** accompanies the existing bounded Player-update snapshot. Pinned Pet/Creature/Unit/WorldObject update and EventProcessor sources show why the pet clock matters, but IP can reschedule from current event time after a long tick; it is **not** a post-IP ready signal. See the linked HPA-G3 identity/readiness gate.

**Multi-ability native-toggle audit:** both client packet observers now append to a bounded 32-candidate per-Hunter read-only queue instead of replacing the prior candidate. Two different abilities toggled in the same update are assessed independently against their later native states. Exact duplicate candidates coalesce; opposing choices for the same ability remain separate, and a dropped-overflow indication is logged once per update. The audit **never** treats a matching state as unquestionable human intent and **does not save or replay any preference**.

**New generic read-only snapshots:** on-add, one-shot pet-clock and finite later probes capture all native autocast-capable Hunter pet abilities (bounded to 64 learned spells per sample), plus autocast-capable actionbar entries even before native loading finishes. Each learned record shows spell ID, a SpellMgr rank-family candidate, native enabled/disabled value and membership in m_autospells. **This is not proof of IP legality, explicit intent or post-IP readiness.** Lightning Breath remains the extra R5/R6 pilot. The learned-spell packet diagnostic now also accepts all autocastable Hunter pet spell IDs and coalesces up to 32 distinct packet observations per pet update. Missing/truncated or observed learned-spell packets never prove IP completion, spell legality or human intent.

### Research-only pet identity option

**New HPA-G3 source/model gate:** [HUNTER-PET-AUTOCAST-IDENTITY-GATE.md](HUNTER-PET-AUTOCAST-IDENTITY-GATE.md) demonstrates actual native pet-number reuse after deletion + restart, why normal pet saving makes row triggers difficult, and why no sidecar/SQL design is safe to approve yet. Offline counterexamples run in pinned CI; they are not gameplay proof.


A cached copy of the native actionbar **does not** by itself solve relog/restart persistence after IP has removed the entry, and even a sidecar table keyed by `owner GUID + PetNumber` could apply old settings if a PetNumber is recycled. An eventual module-owned persistent record must either prove an independent per-pet lifecycle identity or fail closed on ambiguity. No table, migration or actual restoration has been created yet.

## 1A. Read-only prototype now committed to this isolated draft

- `src/Systems/HunterPetAutocastAudit.cpp`: enabled only when `NaxxramasCore.HunterPetAutocast.AuditEnabled = 1`; its default is 0.
- It watches `CMSG_PET_SPELL_AUTOCAST` (13-byte native layout), comparing the pre-handler spell state with the next Player update. It logs a **confirmed transition** only when the spell is still the same known Hunter pet spell and core native active + autocast-list state changed as requested.
- It also logs finite read-only pet-load/actionbar timeline samples to test the missing post-IP completion signal. These are **observations** and do not establish that the IP callback has finished.
- It also observes `SMSG_PET_LEARNED_SPELL` for all learned autocastable Hunter pet abilities (up to 32 distinct pending IDs) and checks knowledge again at the next update, without suppressing or changing the packet. Source attribution to IP is **not** claimed.
- It does **not** intercept core packets, change autocast, change action bars, teach/unlearn ranks, persist preferences, add SQL, show chat messages, reconcile IP or perform a delayed restoration.
- **Added narrow read-only `CMSG_PET_SET_ACTION` observation:** inspect only 16-byte single-slot updates at spell-bar positions 3–6 where the same spell already occupies the same position, initial actionbar/autocast states agree, and the client requests the opposite enabled/disabled state. Next Player update must confirm both the native autocast-list/spell state **and** that exact bar slot. Ignore 24-byte two-slot moves, reorders, new spells, unchanged states and malformed inputs. This is evidence of native acceptance, not permanent proof of human intent.
- **Not yet covered:** direct Playerbot calls, some ambiguous action-bar command forms and real connected/Altbot packet behaviour. `OnPlayerAfterUpdate` callback order needs staging verification; a different automatic actor could still change the state before the deferred confirmation.
- `tests/test_hunter_pet_autocast_audit.py` tests source safety contracts only; pinned GitHub CI is configured to compile and link the exact translation unit. At this revision, a CI result must be checked before claiming compilation passed.

## 2. Required behaviour

- Preserve IP's normal re-learn path, correct Vanilla unlocks and legitimate pet spell learning messages.
- **Never** call `Pet::learnSpell`, `Pet::addSpell`, `unlearnSpell`, `removeSpell`, edit the pet_spell rows, manipulate Spell.dbc, grant Rank 6, or alter IP's dummy Hunter spell ownership.
- Only call `Pet::ToggleAutocast` on a spell the **current pet already knows**, when it is autocastable and is the vetted rank for the Hunter's effective IP stage. Apply `CharmInfo::SetSpellAutocast` to keep the actionbar consistent. Send the **existing** pet spellbook refresh only if a change was made and the correct load/reconciliation phase is proven.
- Unknown preference = **do nothing**. A legitimate deliberate OFF selection must stay OFF. Absolutely no `always enable Lightning Breath` shortcut.
- Per owner + persistent individual pet identity + *canonical spell rank family*, rather than storing preference by current rank spell ID. Do not leak preferences between pets, player accounts, stable slots or reused pet numbers.
- No global rank/ability rewriting, no Warlock/DK/non-Hunter behaviour changes, no bot equipment/talent modifications.
- Low-noise: no player chat; no polling every tick for every player; no writes except **confirmed change of explicit preference** (with an eventual approved module-owned persistence store).
- Disabled-by-default, separate rollout flags for ordinary Hunters and Altbots. Never infer an Altbot's eligibility from its controller's IP era. Unknown/non-Vanilla/no-IP stage must fail closed for this experimental Vanilla-only behaviour.

## 3. Proposed architecture (NOT YET CODE)

### A. Confirm the owner's choice

Observe `CMSG_PET_SPELL_AUTOCAST` and `CMSG_PET_SET_ACTION` **without consuming or mutating them**; use a packet copy and strict bounded validation. Treat this only as **candidate intent**: `CanPacketReceive` executes *before* the core validates the action.

On the **next eligible player update** or safe deferred callback, verify the **same pet instance / owner / spell** still exists and that its native `m_spells[spellId].active`, `m_autospells` and relevant `CharmInfo` entry match the requested action. If the core did not accept the toggle, discard it. Capture both ON and OFF as explicit choices. Avoid capturing a transient state created by IP, and never infer intent from a fresh spell defaulting to OFF.

**Confirmed Playerbots gap:** pinned `TogglePetSpellAutoCastAction` calls `Pet::ToggleAutocast` directly from the Hunter `has pet` AI trigger, generally asking to enable most autocastable spells. That bypasses both packet hooks and can override a deliberately chosen OFF state. **Do not treat this AI-chosen ON as user intent.** Human players/packet-driven bot commands can be distinguished through confirmed client command capture; Altbots require a separately proven explicit user preference path and a policy for competing bot AI actions. If no safe module-only arbitration exists, mark that Altbot scenario unsupported rather than periodically fighting the bot AI.

### B. Resolve a stable individual pet identity

The native `PetNumber` is persisted across dismiss/stable but may be recycled for a different pet (see Hunter Pets persistence research). `CreatureId`/family alone is not enough: a Hunter may have two pets of the same species. Before any durable preference records, prove module-only creation/retirement recognition and an idempotent generation marker bound to (owner, PetNumber). **If recycled identity cannot be proven, fail closed instead of applying somebody else's ON state.**

Native `pet_spell.active` and native actionbar values are useful **observations**, but IP's remove/relearn process means they cannot be the sole authoritative record of a previous explicit choice. A module-owned table (with reversible migration) may ultimately be required for relog and server-restart persistence. No SQL is created or applied in this research PR.

### C. Restore *after* IP has settled

`OnPetAddToWorld` can **schedule** a bounded, pet-scoped one-shot check, but cannot perform restoration. `isBeingLoaded()==false` proves core loading ended, **NOT** that IP's delayed event has run. The inspected IP code schedules 200ms delayed checks and caps its load retry at 10, but event scheduling under all load, revive, stable and bot paths still requires staging proof.

Experimental candidate: wait beyond IP's *source-audited* bounded retry sequence, then check the same pet generation, native loading flag, IP stage, existing learned rank and unchanged spell set over a short settling interval. If IP completion cannot be sufficiently demonstrated, **skip restoration**, record a rate-limited diagnostic only when explicitly enabled, and leave the pet's state unchanged. A naïve permanent 3-second timer is **not** a complete guarantee or general API contract. Do not try to modify IP's internal `ipp_PendingPetSpellCheck` CustomData entry.

Only after a safe readiness proof: load the confirmed stored preference for the currently known **legal** rank family, skip if already equal, otherwise call the public native autocast and charm-actionbar APIs once. No rank/ability mutation. Do not modify ranks merely to make restoration possible.

### D. Safe rollout / rollback proposal

Future configuration, off by default:
```ini
NaxxramasCore.HunterPetAutocast.Enabled = 0
NaxxramasCore.HunterPetAutocast.IncludeAltBots = 0
NaxxramasCore.HunterPetAutocast.Debug = 0
```

Stage 1: **read-only observer and offline tests**, no gameplay effects, no DB. Prototype currently supplies the separate `AuditEnabled=0` flag, not the future feature flags below.
Stage 2: approved **disabled-by-default** draft proof-of-concept and pinned Grimfeather compilation, still no production rollout.
Stage 3: isolated test realm with explicitly approved module-owned persistence migration (after characters DB backup and restore check), ordinary Hunter first; Altbots separately.
Stage 4: controlled production test only after owner approves actual install and config enable. Disable feature and restore snapshot if any rank progression, pet ownership, save or stable issue is observed.

**Generic preference resolution proof (offline only):** [`test_hunter_pet_autocast_generic_model.py`](../tests/test_hunter_pet_autocast_generic_model.py) models independent ON/OFF preferences for multiple autocastable ability families and rejects illegal/unknown ranks, ambiguous duplicate ranks, unverifiable pet incarnation and Playerbot AI cases. All spell IDs in those tests are **synthetic**; the test does not create a pet, validate a real DBC/spell-chain mapping or implement C++ restoration. The required durable identity and post-IP completion contracts remain blocked.

**IP source coverage matrix:** [HUNTER-PET-IP-ABILITY-SCOPE.md](HUNTER-PET-IP-ABILITY-SCOPE.md) distinguishes 26 IP pet-family branches and 89 active reconciliation calls (52 with dummy candidates; 37 removal-only). This is not a complete native autocast catalog and does not authorize any rank or setting change.

**Native root-cause evidence:** [HUNTER-PET-AUTOCAST-STATE-LIFECYCLE.md](HUNTER-PET-AUTOCAST-STATE-LIFECYCLE.md) documents how core normally saves autocast active values, but a genuinely removed/relearned spell can default to OFF during IP reconciliation. It distinguishes this from core's high-rank inheritance and explicitly forbids treating default OFF as player intent. Pinned CI checks the exact source assumptions without modifying spells.

**Standalone fail-closed C++ candidate gate (not registered):** [HUNTER-PET-AUTOCAST-DECISION-GATE.md](HUNTER-PET-AUTOCAST-DECISION-GATE.md) and [HunterPetAutocastDecisionGate.h](../src/Systems/HunterPetAutocastDecisionGate.h) encode the hypothetical minimum proofs for both ON/OFF, separate same-object from across-load identity, and reject missing human/IP/rank proofs. CI compiles and runs the pure C++ test without touching pets, SQL or the runtime observer. This is a *no-write policy specification*, not a persistence solution or permission to restore.

**Read-only native load-attempt hook:** the Hunter player observer now logs a `PLAYERHOOK_ON_BEFORE_LOAD_PET_FROM_DB` event as evidence that an existing pet's `Pet::LoadPetFromDB` reached its pre-creation hook. Its parameters are never changed, the hook does not guarantee the load succeeded, and its absence is not evidence of a freshly tamed pet. [Identity research](HUNTER-PET-AUTOCAST-IDENTITY-GATE.md) and pinned source checks document those limitations. It does not solve the pet-incarnation blocker.

**Scoped, no-write alternative under research:** the standalone [decision-gate model](HUNTER-PET-AUTOCAST-DECISION-GATE.md) now separates same live Pet object, same Worldserver process after resummon, and across-restart identity. A hypothetical RAM-only cache could recognise pets for one uninterrupted server process if it captured choices during that same process and proved PetNumber allocator continuity. There is NO implemented cache, no source-proof across every external module/overflow path, no permanent persistence, and the independent human-intent/IP-ready blockers still prevent autocast restoration.

**Bounded per-family read-only stability probe:** The pinned `PetSpellMap` is an unordered map; this probe sorts spell IDs before building the per-family snapshots so iteration order cannot manufacture a change.  A pet-scoped, max-10-sample observer compares each known native-autocastable ability family's spell ID, active flag, autocast-list membership and actionbar state (max 64 spells, then aborts). It reports only family-specific changes and a final unchanged-run count. Ten identical samples still DO NOT prove IP completed; IP may have scheduled a later event, and the observer never toggles/saves anything. [Offline timing counterexamples](../tests/test_hunter_pet_autocast_stability_model.py) demonstrate why an unchanged window is not readiness.

**Source-proven conditional no-op direction (research only):** [HUNTER-PET-AUTOCAST-IP-FIXED-POINT.md](HUNTER-PET-AUTOCAST-IP-FIXED-POINT.md) and its offline model show that IP does not remove/relearn an already-known selected rank with no extra disallowed ranks **if** the Hunter's dummy spells, effective progression, pet family and complete applicable reconciler calls remain unchanged. This is an idempotence precondition, NOT confirmation that IP has executed or will not execute later. Missing durable pet identity and human intent still block restoration. A new pinned CI guard detects upstream changes in these IP rules.

**Per-Hunter progression gate research:** [HUNTER-PET-AUTOCAST-IP-CHARACTER-STAGE.md](HUNTER-PET-AUTOCAST-IP-CHARACTER-STAGE.md) documents IP's stage derived from the Hunter's own rewarded hidden quests 66001–66018 (not an account-wide maximum), its per-milestone progression-limit guard, bot and `VanillaHunterPets` conditions, and learned dummy selection. A pinned source checker + synthetic model enforce these assumptions. The standalone C++ `CandidateOnly` policy now explicitly rejects account-tier-only and quest-stage-only eligibility evidence in favor of a hypothetical independently verified *owner-specific applicable IP rule*. This does not inspect a real Hunter or solve post-IP readiness, and never toggles any autocast.

**Read-only owner progression evidence in the audit:** the existing disabled-on-default runtime observer now logs the Hunter's raw highest rewarded hidden quest tier at pet add and at its later bounded lifecycle sample. When owner/world state is unavailable it logs `unavailable`, not tier zero. This supplies useful independent staging observations only, not IP's effective cap/account/bot/dummy context, human intent or after-reconciliation evidence. The [character-stage investigation](HUNTER-PET-AUTOCAST-IP-CHARACTER-STAGE.md) records limits.

**Pinned negative completion proof:** [HUNTER-PET-AUTOCAST-IP-COMPLETION-BOUNDARY.md](HUNTER-PET-AUTOCAST-IP-COMPLETION-BOUNDARY.md) documents how native unlearn notifications are commented out, learn notifications are suppressed while pet loading (or no-op learning), and IP may run after its bounded loading retry cap. Two distinct rank histories can therefore have indistinguishable spellbook/packet observations. Offline counterexamples and a pinned native source CI guard confirm **no module-only public IP completion proof has been established**. Do not treat packet presence/absence or unchanged family snapshots as after-IP handoff.

**Proposed upstream completion handoff, NOT implemented:** [HUNTER-PET-AUTOCAST-TRUSTED-HANDOFF.md](HUNTER-PET-AUTOCAST-TRUSTED-HANDOFF.md) specifies what a trustworthy IP post-reconciliation signal would need to carry: original Pet-object and owner-session identity, event generation/process epoch, eligible-result outcome and *after-return* ordering, plus duplicate/stale-signal rejection. Pinned IP's delayed event only stores owner GUID and attempts and clears its private pending marker before calling the reconciler. A **standalone unregistered C++ model** now tests these failure cases and returns only `CandidateOnly` when every hypothetical proof is supplied. No real IP hook exists or was added, and installing one would need separate owner approval outside the Naxx Core scope.

**Read-only module-only post-event probe:** pinned AzerothCore does have a [WorldObjectScript post-event-queue hook](HUNTER-PET-AUTOCAST-POST-EVENT-OBSERVATION.md). A bounded per-Pet diagnostic now records native queue emptiness after up to four actual Pet update ticks (when the audit is explicitly enabled). It does **not** identify an IP event. Because events are popped before execution and other events may remain queued, neither `HasEvents()==false` nor `true` proves IP completion. The pinned ordering checker and offline counterexamples guard against promoting this useful observation into a restoration trigger.

**Native acceptance vs human provenance separated:** pinned [packet/handler source investigation](HUNTER-PET-AUTOCAST-INTENT-PROVENANCE.md) confirms public `CanPacketReceive` fires BEFORE native pet-command validation, and no public post-handler accepted-toggle script hook is exposed. A matching state afterward can instead result from another actor's direct `Pet::ToggleAutocast`; native acceptance alone would not prove a HUMAN actor either. The standalone C++ policy now requires separately verified native handler application and explicit human attribution. Offline counterexamples and a new pinned CI guard reject these ambiguous histories; no preference storage or gameplay mutation was added.

**Actual pinned Playerbots behaviour confirmed:** [Playerbot policy research](HUNTER-PET-AUTOCAST-PLAYERBOT-POLICY.md) identifies exact `Pet::ToggleAutocast` call sites in `PetsAction`, `PlayerbotAI`, `TameAction` and `PlayerbotFactory`, all outside the native CMSG path. The bot's `TogglePetSpellAutoCastAction` sets most known autocastable spells ON while keeping a defined disabled set OFF, so it can overturn an external ON/OFF choice. The pinned Hunter non-combat `HunterPetStrategy` queues this action on the `has pet` trigger at priority 60.0; the exact active strategy/cadence on a live bot is still unverified. A pinned bot-source guard and synthetic conflict tests are added to CI. **Hunter Playerbots are a required separate design track**, not covered by the current human-only fail-closed decision gate; no bot runtime policy or AI code changed.

**Default Hunter bot strategy verified and standalone precedence model:** Pinned `AiFactory::AddDefaultNonCombatStrategies` adds `pet` by default for Hunters, and pinned `HasPetTrigger` checks for an unmounted bot with a pet target. Configured strategy changes can later alter this. The [unregistered C++20 precedence model](HUNTER-PET-AUTOCAST-BOT-PRECEDENCE.md) and synthetic timeline tests distinguish observed bot defaults from hypothetical authenticated master commands, reject mismatched native state, and flag conflicts needing bot-policy coordination. None of these synthetic proof flags has an authoritative runtime producer, no autocast is toggled, and all previous blockers remain.

## 4. Hard release blockers

1. No trusted way to distinguish **player OFF** from **newly learned spell defaults to OFF**: do not silently re-enable unknown spells. A new preference must be captured by a confirmed explicit toggle.
2. No demonstrably safe post-IP decision point: no restore attempt. **The core's `m_loading` false flag alone is insufficient**.
3. Cannot map ability chain to actual installed 3.3.5 spell ranks and confirm the actor's own effective IP Vanilla eligibility: skip.
4. Cannot distinguish recycled PetNumber or separate same-family stabled pets: do not apply a stored preference.
5. Bot direct-calls bypass packet capture, or the bot has no authoritative IP state: exclude bot until separate proof.
6. No staging evidence for persisted ON **and** OFF through summon, revive, stable, relog and process restart: not ready for release.
7. Any requirement for AzerothCore, IP, Playerbots, Hunter Pets or other repository changes: STOP, report the technical boundary to the owner.

## 5. Next proof steps

- Pin the **actual installed** Grimfeather/IP/Playerbots revisions (read-only) before deploy decisions; GitHub CI pins are not production verification.
- Implement optional, read-only *packet-intent versus native accepted state* instrumentation in an isolated draft branch, with no persistent writes.
- Instrument IP load/ready versus its delayed reconciliation for a disposable test pet; validate timing on existing/after-revive/stable/Altbot paths.
- Determine a safe persistent pet generation identity before proposing SQL; audit CharacterDatabase migration/rollback semantics with real schema.
- Use [the companion acceptance matrix](HUNTER-PET-AUTOCAST-ACCEPTANCE.md). No live server action without separate owner approval.
