# Era Mount Cast — module-only alternative research

**9 October 2026 — architecture research, not implementation.**

## Decision

The administrator does **not** want custom AzerothCore core-source modifications that would make later core updates harder. **Do not apply** `patches/azerothcore-optional-after-calc-spell-cast-time.patch`. It is retained in version control as a historical experiment, **not** an approved deployment step.

Keep the current `src/Systems/EraMountCast.cpp` disabled. Its existing implementation is intentionally a **no-op** without the separate (unapproved) hook. The C++ compilation may complete without enabling any mount change.

## Exact desired behaviour

- Vanilla and TBC (IP stages 0–12): normal casted mounts take **3000 ms**.
- WotLK from IP stage 13: normal casted mounts take **1500 ms**.
- Mixed-progress groups are supported: progression checked **per player**.
- Respect IP module disabled state and progression cap.
- Prefer Playerbots exempt (using the configured bot-account regex).
- Preserve instant mounts, form transforms, non-mount abilities, spell-haste interactions and reliable interrupt behaviour.
- Avoid AzerothCore, Playerbots and Individual Progression upstream source modifications.
- Reversible/uninstallable; make backups before deployment. No new change to live server until reviewed.

## Current upstream source facts (inspected at user's commit b7f06a16ac7120b5abc2e8d3f96a94265a363224)

1. `Spell::prepare` calls `SpellInfo::CalcCastTime(m_caster, this)` and then builds the server timer and cast-start packet. `AllSpellScript::OnSpellPrepare` runs **too late** to set the authoritative timer and the client start packet coherently.
2. `SpellInfo::CalcCastTime` invokes `WorldObject::ModSpellCastTime` before preparing the packet. This internally calls the caster player's `ApplySpellMod(... SPELLMOD_CASTING_TIME ...)`.
3. `Player::AddSpellMod` accepts `SpellModifier` entries, but a hand-built entry whose `ownerAura` is null **cannot safely be used**: `Player::ApplyModToSpell` accesses `mod->ownerAura->IsUsingCharges()` for a non-null casting `Spell*`. This can dereference null. **Do not implement manually created aura-less SpellModifier objects.**
4. `AuraEffect::CalculateSpellMod` creates an Aura-owned `SpellModifier(GetBase())` for a real `SPELL_AURA_ADD_FLAT_MODIFIER` or `SPELL_AURA_ADD_PCT_MODIFIER` aura; this is the intended safe lifetime path.
5. `SpellInfo::IsAffectedBySpellMod` includes an existing `GlobalScript::OnIsAffectedBySpellModCheck` hook. A hook returning **false** forces the spell affected; returning **true** delegates to the normal family/mask matching. **The hook does not directly provide a veto** for unrelated spells.
6. Default family/mask fallback is significant: `SpellInfo::IsAffected` matches all spells when the modifier's source `SpellFamilyName` is **0**, and may match other spells from a nonzero family when the modifier's mask is zero. It is **not enough** to install a persistent family-zero/zero-mask modifier and forcibly match mounts. Other spells would also be affected.
7. A legitimate, narrowly-targeted cast-time aura might permit a module-only route, but requires a proven unique source spell and family/mask combination so **no non-mount spell receives the modifier**. Adding such a spell may require server/client DBC data; that part is not yet approved or verified.
8. Temporarily installing/removing a broad modifier around check/prepare is **not approved** without proof for aborted casts, concurrent/nested casts, cleanup, interrupts, disconnects, Playerbots and UI timers.
9. Reject shortcuts which delay mount completion by timers or silently recast triggered mounts: they'd risk mismatched client casting visuals and broken movement/interrupt rules.

## Before any replacement implementation

- Determine whether existing 3.3.5a source/client spell data provides a suitable aura with a **provably exclusive** family/mask match, or whether additional custom Spell.dbc entries would be necessary.
- Independently inspect the *active server* Spell.dbc and any custom mount spells. Do not assume all mounts are the same spell family or all start at 1500 ms.
- If viable, prototype a genuine Aura-owned spell modifier via module hooks, with debug initially **off** and feature config default **0**.
- Audit *every* spell affected by the chosen aura mask, not just sample mounts. No unintended non-mount change is acceptable.
- Build and verify the full test matrix from `docs/ERA-MOUNT-CAST.md` before activation.
- If the module-only route needs an unacceptable DBC/client patch or fails these safety criteria, keep original mount casting and explain the tradeoff; **do not fall back to core patch without fresh explicit approval**.

## Status

Research completed so far: source call order, lifetime/null-owner hazard, relevant existing spell-modifier hook and family/mask leakage risk. **No validated module-only implementation has been written, compiled, or tested.** The original optional system remains disabled and inert without the core patch.
