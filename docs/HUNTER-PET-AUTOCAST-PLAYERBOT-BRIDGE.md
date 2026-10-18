# Hunter Pet Autocast — Proposed Playerbots notification consumer (standalone)

**STATUS: MODEL ONLY. No upstream notification producer, callbacks, preference persistence, or restoration are installed.**

This proposed integration deliberately lives in **Naxx Core draft PR #26**, not in Playerbots, IP or AzerothCore. The C++20 header [HunterPetAutocastPlayerbotBridgeContract.h](../src/Systems/HunterPetAutocastPlayerbotBridgeContract.h) is **not linked into the Worldserver module**; [its tests](../tests/hunter_pet_autocast_playerbot_bridge.cpp) execute in isolation.

## Upstream producer contract (not implemented)

Playerbots would need a narrow, independently authenticated, versioned **per-spell post-native-operation notification**, not the existing Engine action listener's aggregate boolean. The pinned [action listener investigation](HUNTER-PET-AUTOCAST-BOT-ACTION-LISTENER.md) proves that the listener can report success without executing an action, can override another result, and owns listener pointers. Exposing a raw `Engine*` or attaching an unmanaged listener would be unsafe.

A real producer must supply a credible **strictly increasing operation sequence shared across all spell IDs and origins for the same bot/Pet lifecycle** (not separate per ability), plus a verifiable origin: `BotDefault`, `FactoryOrTame`, `OtherAI`, or an authenticated, actually applied master command. Master chat ingress on its own is insufficient: Playerbots filters, defers and can internally generate commands. The producer must associate each result with the exact current bot, session, actual Pet incarnation, spell ID / rank family, known lawful rank, native autocastability and **before and after** native ON/OFF state read on the same Pet instance. A claimed native state change must equal the actual BEFORE/AFTER difference; a command that leaves the state unchanged is not a native transition. A separately proven **accepted and applied master request** can still express an explicit ON/OFF choice even when that state already exists; a chat receipt alone proves neither acceptance nor intent.

**IMPORTANT:** The model uses booleans such as `trustedProducer` and `ipReconciliationCompleted` as *hypothetical test inputs only*. Setting them in Naxx does not authenticate anything or create an IP callback. There is no demonstrated runtime source for them.

## Fail-closed consumer contract

- **Skip:** missing exact-spell master native-acceptance proof (including for an unchanged request), AI-labelled events carrying contradictory master attestation, contradictory BEFORE/AFTER versus native-change flag (including an idempotent command falsely claimed as a changed spell), unrecognised version, wrong process/bot/session/pet event generation, mismatched active Pet, missing or wrong spell/rank family, stale or replayed operation sequence, unknown source, untrusted producer, illegal or unknown spell, unsupported native autocast, unverified post-IP completion or changed later native state.
- **AutomatedObservationOnly:** properly attributed bot policy, factory/tame or other AI activity can be observed but **must never** be recorded as a master's preference.
- **MasterConflictNeedsBotCoordination:** a hypothetically authenticated, actually applied master preference conflicts with Playerbots' configured default and a coordinated override has not been established. No timer or repeated ToggleAutocast.
- **MasterCandidateOnly:** even a complete hypothetically authenticated, *native-accepted* (changed or idempotent), current-rank, post-IP and policy-coordinated master choice is **only a review candidate**, never authority to store or restore.

**Contract v2:** `masterRequestApplied` is a separate hypothetical trusted upstream proof of native validation and application to the exact Pet, spell and requested state, including a legitimate no-op. `nativeChangeApplied` still means **only** that BEFORE and AFTER native ON/OFF differed. The module cannot manufacture either proof, and an idempotent choice is never evidence of a native transition. Bot/AI events must not carry master attestations.

The model's one-consumer sequence counter prevents duplicate/replayed accepted notifications within that object's lifetime. **It does not solve durable pet identity, process restarts or cross-module event authenticity**; an actual producer and lifecycle contract must exist first.

## Remaining approvals and practical next work

An actual Playerbots callback, native per-spell applied-results, trusted master-command attribution and a bot-policy override mechanism require **separately approved upstream work**. A correct after-IP reconciliation source and durable pet incarnation are separate unresolved requirements. Then a disposable staging realm, exact installed revision check, verified characters DB backup and successful restoration rehearsal would precede any installation.

**No server modifications, SQL, upstream code changes or gameplay autocast restoration have been made.**
