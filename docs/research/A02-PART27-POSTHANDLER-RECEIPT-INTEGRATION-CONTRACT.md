# A02 Part 27 — native post-handler accepted-command integration contract (SOURCE DESIGN ONLY)

**State:** DRAFT REVIEW, **NOT IMPLEMENTED IN CORE OR MODULE**. Owner has not approved a core hook, pet-birth persistence, IP edits, any live changes, or use of the feature. The actual legacy-v1 writer quarantine in #165 remains mandatory, and both A02 flags stay OFF. The purpose here is an implementable, source-anchored decision contract for owner review — not a simulated acceptance receipt.

## Exact review inputs

- AzerothCore `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`.
- Playerbots `mod-playerbots/mod-playerbots@d750b4b3a50effdf22bedc8032f0e8e5f7cb8091`; Individual Progression `Grimfeather/mod-individual-progression@dd96f2b77e3ebfa2a4726bf785525ba133f1ab61`. These are PUBLIC disposable CI pins, **not proof** of the owner's customized installation.
- [PetHandler.cpp:955–1010](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/PetHandler.cpp#L955-L1010) and [PetHandler.cpp:696–837](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Handlers/PetHandler.cpp#L696-L837); [Pet.cpp:2247–2291](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Entities/Pet/Pet.cpp#L2247-L2291).
- [PetScript.h](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Scripting/ScriptDefines/PetScript.h), and [WorldSession.cpp:459–465](https://github.com/Grimfeather/azerothcore-wotlk/blob/8daffdabe9202c228e45d833c9a1d399597a15cd/src/server/game/Server/WorldSession.cpp#L459-L465). Pinned scripts have **no** post-accepted pet autocast event; CanPacketReceive runs **before** the native handler.
- #164 @ `b480dff` has source and full Worldserver link CI success; #165 @ `0bec377` has actual production fail-closed guard; #166 @ `9f0af14` has only an unwired synthetic model with hypothetical trusted input. **Do not wire its fake booleans to native pre-handler packets.**

## What an owner-approved minimal CORE change would need to establish

This section is a **proposed contract, not a patch**. It would require a narrow new optional scripting event, registered/compiled against the exact pinned core, with a deliberate zero-subscriber fast path. An event is a **server-accepted client-command state transition**, not cryptographic proof of a physical human click or that the session currently lacks SelfBot automation.

### Path A — `HandlePetSpellAutocastOpcode` (best initial source seam)

1. Keep existing target GUID lookup, spell lookup, guardian/charm ownership check, same-entry controlled-unit loop and `HasSpell`/`IsAutocastable`/`CharmInfo` guards unchanged. A valid **incoming request** is not yet a receipt.
2. Inside the loop, **before** applying the toggle, capture an immutable consistent *actual target* state, not the requested boolean. Emit nothing if the target was not `checkPet`, owner is not an actual Hunter with their current guardian `Pet` (`HUNTER_PET`), or target is an unrelated same-entry controlled summon/charm. Do not use another unit's result as proof of the Hunter pet.
3. The exact AFTER seam is **following** both `summon->ToggleAutocast(spellInfo, requested)` and `charmInfo->SetSpellAutocast(spellInfo, requested)` for the same target in this handler. Inspect `Pet::m_spells[id].active`, `Pet::m_autospells` membership and matching `CharmInfo` actionbar entries (if present). The two existing fields are public in pinned `Pet.h`. Reject ambiguous duplicate bar entries, inconsistent pre-state or inconsistent after-state, absent/removed spell, no-op and unsupported spell. A valid transition must be consistent OFF→ON or ON→OFF, before and after. An off-bar spell may be accepted when no matching bar entry exists but both pet spell stores agree.
4. Only then **propose** one `AUTOCAST` accepted-transition record bound to that target and the executing `WorldSession`, with verified requested new bool. Do not emit a record for other controlled units changed by the same packet.

### Path B — `HandlePetSetAction` (more ambiguous)

1. Stock handler may process **two entries** for a bar move, command/reaction validation, and the same-entry controlled-unit loop. It may call `Pet::ToggleAutocast` merely because an actionbar entry was moved; the resulting state may not represent a fresh manual ON/OFF choice.
2. The accepted native *bar mutation* and a genuine *manual preference* are **different events**. Capture pre/post per actual targeted Hunter pet, but do not promote `ACT_ENABLED`, `ACT_DISABLED`, the count, or a changed bar entry to trusted preference without causal 3.3.5 client witness. For an initial minimal extension, **emit diagnostic-only SET_ACTION transition candidates, never automatic-restoration authority**. Even a one-entry SET_ACTION packet is not enough proof by itself.
3. Peer-review a distinct SET_ACTION policy with real right-click/off-bar/rank tests before any later promotion. Never collapse the two handlers into one generic pre/post observer.

### Proposed immutable receipt fields and bounds

Use value-only records: `owner GUID`, `actual pet GUID`, `PetNumber` **as a hint only**, `spell ID`, core-resolved chain, `enabled bool`, `sourceOpcode=AUTOCAST or SET_ACTION`, handler-local accepted-transition classification, and one server-issued monotonic revision/domain. Include a validated persistent pet **birth identity only after it truly exists**. No user chat text, private NPC/item/quest/loot data, session pointers, `Player*`, `Pet*` or raw `CharmInfo*` retained beyond synchronous handler execution.

- `AUTOCAST` is `PROCESS_INPLACE`, possibly executed on map or world worker; `SET_ACTION` is `PROCESS_THREADUNSAFE`. The callback runs **synchronously on the handler's existing thread**; no fake world-thread affinity. If records are handed off, copy values under a bounded, reviewed synchronization scheme. **No unlocked `_playerbotsAIMap` access from map workers** and preserve `MapUpdate.Threads=8`.
- A received opcode can still be generated by a bot-controlled session; a server handler receipt **alone does not positively attest human mode**. A future apply path must verify `Owner=Human` by a separately source-reviewed, concurrency-safe, positive mechanism at receipt **and** application time; absent evidence means `NoWrite`. `SelfBotLevel=0` is insufficient for attached SelfBots.
- Server-issued latest choice revision must be shared across dispatch threads and sessions, never ordered by receipt wall time, addon packet sequence, or a login-local counter. Latest accepted OFF invalidates older pending ON; if `LatestRevisionDomain` is retained, it means the domain of the **latest accepted choice**, carried across relog — not the current login's domain.
- The trusted pet birth record must distinguish recycled PetNumber across abandon/replace/tame, be durable across summon/relog, and have an explicitly approved persistence lifecycle. The model's `BirthToken`, `TrustedBirthAtReceipt`, `TrustedCurrentBirth`, and `TrustedManualReceipt` currently exist **only as fixtures**. Without a real authoritative durable binding, continuity across login/replacement stays **UNKNOWN and OFF**.
- Individual Progression chooses the **existing allowed spell rank** under owner Policy A. A02 must never learn or force a missing/forbidden rank. Read the *current* rank/chain on the owning update context and re-evaluate late/repeated IP transitions with bounded attempts. Never assume a 200ms sleep is an IP settlement oracle; budget exhaustion means deferred/no-write, not infinite retries.

## Source-backed negative cases that must fail before any enablement

- Wrong GUID, not player's current GuardianPet, same-entry other controlled unit, absent/passive/non-autocastable spell, no CharmInfo, inconsistent spell/autospell/bar state, already-on→on and already-off→off.
- SET_ACTION command move, two-slot swap, actionbar-only reshuffle or action button repeat; these **must not publish manual preference**. Actual physical 3.3.5a off-bar/right-click event mapping is still unknown.
- New manual OFF superseding delayed ON; simultaneous opcode order on world and map workers; pet abandoned/replaced with recycled PetNumber; relog and resummon of genuine same birth; IP rank down/up repeated; bot session or currently attached SelfBot; map workers running at eight.
- A02 default flags remain OFF; even manual flag toggling of legacy v1 stays blocked by `EligibleForAutomaticRestore` in #165. No source-test/model success counts as owner gameplay signoff.

## Explicit approval/decision gates — DO NOT EXECUTE

**Gate C1, separate owner approval:** smallest upstream CORE hook patch. Only then may an isolated throwaway source patch/compilation exercise be created; no live binary, IP edit, or installation follows by implication.

**Gate C2, separate owner approval:** durable pet-birth provenance/persistence approach, including any SQL/schema migration and backup/rollback. PetNumber name/family alone is insufficient.

**Gate C3, separate owner approval:** positive SelfBot-vs-human mechanism and safe boundary; assess Playerbots customizations without touching them.

**Gate C4, separate owner staging approval:** pinned combined full Worldserver build, backup/rollback, default-OFF integration and in-game 3.3.5a acceptance including GFPP 120s, A04 two symptoms, F12, F13 and regressions. Current project milestone 0/5 owner-signed; #160 remains frozen.

**Owner decision requested later:** May CS01 prepare a **source-only isolated core-hook patch under C1**? Do **not** infer permission from this document or review comments. Until C1/C2/C3, the engineering outcome is a precisely defined blocker, not working A02.
