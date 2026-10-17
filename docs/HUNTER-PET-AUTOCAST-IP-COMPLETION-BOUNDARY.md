# HPA-G3 — IP completion and native spell event observability boundary

**READ-ONLY RESEARCH, not a feature.** All source assertions refer to the pinned Grimfeather AzerothCore / Individual Progression revision. The corresponding offline model uses synthetic spellbooks and does not execute a live realm.

## What the existing module can and cannot observe

1. Native `Pet::learnSpell` sends `PetLearnedSpell` only if `m_loading == false`. When the same rank is already known, `addSpell` can fail and `learnSpell` sends no packet. This notification cannot prove the origin is Individual Progression or that IP's entire check is complete.
2. Native `Pet::unlearnSpell` calls `removeSpell`, but the `PetUnlearnedSpell` outgoing notification is **commented out**. No public `PetScript::OnPetUnlearnSpell` or `OnPetLearnSpell` callback exists in this pinned hook interface.
3. The native `WorldSession::SendPacket` script hook runs before checking the socket, so a headless/bot-context learned-spell packet can still be observed. This does not authenticate a human or IP origin.
4. IP's `DelayedPetSpellCheck` retries while `isBeingLoaded()` and attempts are below ten. When attempts reach ten, it can call Hunter spell reconciliation **even while the pet is still loading**, meaning a remove/relearn sequence need not emit a learn packet.
5. Pet spellbook and actionbar snapshots occur at chosen times. An unlearn/relearn that begins and finishes **between snapshots** may be invisible, including a case where the spell was OFF both before and after.

## Identical observations, different histories

| History | Before/after known rank | Learned packet | Human preference proof |
|---|---|---|---|
| Legal rank unchanged | Identical | None | Not established |
| Unlearn and relearn rank while pet loading | Identical | None | Not established |
| Two identical learn packets from different call origins | May be identical | Seen, but untagged | Not established |
| Explicit OFF versus new fresh spell defaulting OFF | Identical active OFF | May differ | Not established |

The [offline test](../tests/test_hunter_pet_autocast_unlearn_observability_model.py) demonstrates several observational equivalences. The [pinned-source guard](../scripts/check_hunter_pet_unlearn_observability_pinned.py) verifies which native source contracts make these possible.

## Consequence for restoration

**No timing-only, stable-spellbook-only or learned-packet-only solution can prove IP completion in every case.** Per-family fixed-point checking under frozen known inputs remains useful as evidence that a *repeat* of that particular IP rule would be a no-op, but this is not a public completion signal and does not cover changes by other scripts or subsequent new rank unlocks.

Without modifying IP or AzerothCore, Naxx Core can improve its read-only evidence but has not found an authoritative post-IP completion callback. An upstream post-reconcile lifecycle hook with explicit ownership, event generation, legal-rank outcome and callback ordering would require **separate user approval for changes outside Naxx Core**; it is not being created here. A restricted session-only alternative would still require proven human intent, safe pet identity and independently verified completion conditions.

**Safety gate unchanged:** never teach a rank, toggle ON/OFF, write SQL, infer OFF as player choice, install anything or claim in-game acceptance based on this research. Any staging investigation requires prior explicit permission and a verified characters-database backup and restore.