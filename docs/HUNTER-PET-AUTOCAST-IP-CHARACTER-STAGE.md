# HPA — Actual Hunter character progression versus account-wide progression

**SOURCE-ONLY / SYNTHETIC TESTS. No live Hunter progression, SQL, IP event, or pet autocast has been read or changed.**

Sources: [IP IndividualProgression.cpp](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgression.cpp), [ProgressionState enum](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgression.h), and [checkHunterPetSpells](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp).

## Pinned IP contract

- `GetPlayerProgressionFromQuests(player)` scans that specific player's **rewarded hidden quests** from 66001 through 66018, returning the highest stage whose quest is rewarded; when none is rewarded it returns zero. A quest accepted/completed but not rewarded is not counted.
- `hasPassedProgression(player, milestone)` returns false when IP is disabled, player absent/not in world, milestone zero, or configured `progressionLimit` is nonzero but BELOW that requested milestone. Otherwise it compares the *character's rewarded-quest stage* to the milestone.
- `GetAccountProgression(accountId)` exists for **other purposes**; it looks across multiple characters. It is NOT the stage used by the pinned Hunter pet reconciliation. Never substitute account-wide highest progression for the Hunter's own stage.
- `checkHunterPetSpells(player)` requires `VanillaHunterPets` enabled, a Hunter currently in world, and not a configured bot account; it skips when `hasPassedProgression(player, PROGRESSION_TBC_TIER_5)` is true. The enclosing IP PetScript schedules its delayed event only when IP is enabled. Readiness is still unproven.
- For branches such as Boar Gore, `hasPassedProgression(player, PROGRESSION_PRE_TBC)` selects one mutually exclusive path. Pinned milestones: Molten Core=1; BWL completed=3; PRE_TBC=8; TBC_TIER_5=13; last WotLK stage=18.
- A selected rank also depends on **that Hunter's learned dummy spells** (reverse iteration of the IP-provided list, first known dummy chosen, minus 600000). A dummy learned by a different character never grants a rank to the Hunter.

## Two important traps

**Trap 1 — character vs account:** Hunter A at stage 3 and Hunter B at stage 13 on the same account do NOT have the same pet reconciliation eligibility. The system cannot use the account's maximum progression.

**Trap 2 — progression cap vs progression stage:** A Hunter with a rewarded stage-13 quest and a nonzero `ProgressionLimit=7` has raw character progression 13, but `hasPassedProgression(TBC_TIER_5)` returns **false** because 13 exceeds that cap. Do not replace the source algorithm with a simple `min(characterStage, limit)` model or assume the Hunter pet script skips based on raw tier alone.

## Optional read-only source-compatible diagnostic

The draft Naxx Core audit (disabled by default) now reports the owning Hunter's raw highest rewarded quest tier when the Pet is added and again at a later lifecycle sample. It scans exactly 66001–66018, returns `unavailable` rather than zero when the owner is not in world, and **never** reads or alters the quest log. This is not an IP runtime API, does not validate the configured progression limit, `VanillaHunterPets`, bot account, correct dummy spell or eligibility, and does not establish that IP finished. It is a staging observation only; a changed tier between samples is diagnostic evidence, not a trigger for any action.

## Safeguards and remaining unknowns

The [pinned source check](../scripts/check_hunter_pet_ip_character_stage_pinned.py) confirms the above against the checked-out IP revisions. The [offline character model](../tests/test_hunter_pet_autocast_ip_character_stage_model.py) exercises independent characters, stage zero, highest rewarded quest, IP disabled/unknown, progression cap, bot classification, Boar Gore and individual dummy-spell selection.

**Fail closed:** all runtime configuration and account classification must be determined authoritatively before any future action. A copied quest-stage observation is not an IP completion event; matching the synthetic permitted rank is not independent `SpellInfo::IsAutocastable`, native rank legality, human intent or durable pet identity. This investigation adds **no IP header dependency or restoration code** to Naxx Core.
