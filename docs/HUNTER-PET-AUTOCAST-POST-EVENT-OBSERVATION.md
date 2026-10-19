# HPA-G2 — Native post-Pet-event-loop observation (not post-IP completion)

**STATUS: Read-only audit, disabled by default. No Pet/Spell/SQL mutation.**

The pinned native path [Pet::Update](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Pet/Pet.cpp) returns early while `m_loading` is true, otherwise it normally delegates to `Creature::Update` and `Unit::Update`. [WorldObject::Update](https://github.com/Grimfeather/azerothcore-wotlk/blob/a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7/src/server/game/Entities/Object/Object.cpp) processes `m_Events.Update(diff)` **before** dispatching `WorldObjectScript::OnWorldObjectUpdate`. That public hook provides a well-defined read-only point after **one pet event-queue tick**, provided the normal update reached it. This does **not** imply the queued IP event was due, executed, skipped, or finished.

The existing module observer adds `HunterPetAutocastPostEventObserver` to the **same optional audit**. It filters the true `WorldObject → Unit → Pet`, verifies the currently linked Hunter owner and matching active Pet object, and emits **at most four** diagnostic log lines per Pet object (via that Pet's CustomData). Each records the native queue's `HasEvents()` and loading flag. It does not look up IP's private flag, schedule an extra event, infer readiness, record an ON/OFF preference, or call `ToggleAutocast`. The audit remains `NaxxramasCore.HunterPetAutocast.AuditEnabled=0` unless manually enabled in a separately approved staging environment.

## Why HasEvents cannot certify IP

- `EventProcessor::Update` **erases the current due event** before calling `Execute`. Consequently, `HasEvents()` can be `false` while an IP callback is actively executing, before the reconcile returns.
- `HasEvents()` can remain `true` after IP returns because an entirely unrelated spell or pet event is queued.
- `OnWorldObjectUpdate` can run after a tick **before** IP's delayed check becomes due, or after a tick on a Pet for which IP never scheduled a check.
- IP's private pending marker clears *before* reconciliation and is inaccessible as a public completion API.
- A Pet's normal update being skipped during loading creates another observation gap. Missing callbacks are not evidence of IP readiness, and source-specific retry behaviours should be verified on disposable staging.

The [pinned source check](../scripts/check_hunter_pet_post_event_surface_pinned.py) guarantees the callback ordering, early-loading return and queue visibility semantics for the known upstream revisions. [Synthetic offline counterexamples](../tests/test_hunter_pet_autocast_post_event_model.py) illustrate how either queue status can mislead.

**Conclusion:** This public hook improves staging observability but still cannot satisfy the authenticated post-IP-return contract [documented here](HUNTER-PET-AUTOCAST-TRUSTED-HANDOFF.md). A fully safe automatic restoration remains BLOCKED. Do not change the live realm or use elapsed time, empty-queue status, or log count as restoration triggers.