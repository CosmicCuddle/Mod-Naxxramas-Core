# Hunter pet abilities — IP source coverage

**Read-only, source-pinned investigation. No spells or autocast settings are changed.**

Source: [Pinned Grimfeather Individual Progression](https://github.com/Grimfeather/mod-individual-progression/blob/4ff4b5fcc1480348f058c632573143e62d4e3a41/src/IndividualProgressionSpells.cpp), Hunter pet spell-reconciliation function.

IP has **26 family branches** and **89 active reconciliation calls**. Of those, **52** contain at least one Hunter dummy spell from which IP can select a retained rank, and **37** have no dummy list and only remove disallowed listed ranks. Calls in commented code are excluded. Conditional branches are separate *source* calls, not simultaneous gameplay operations.

| IP pet family | Reconciliation calls | With dummy candidates | Removal only |
|---|---:|---:|---:|
| Wolf | 5 | 3 | 2 |
| Cat | 4 | 3 | 1 |
| Spider | 2 | 1 | 1 |
| Bear | 3 | 2 | 1 |
| Boar | 5 | 4 | 1 |
| Crocolisk | 2 | 1 | 1 |
| Carrion Bird | 4 | 3 | 1 |
| Crab | 2 | 1 | 1 |
| Gorilla | 3 | 2 | 1 |
| Raptor | 3 | 2 | 1 |
| Tallstrider | 4 | 2 | 2 |
| Scorpid | 2 | 2 | 0 |
| Turtle | 2 | 2 | 0 |
| Bat | 4 | 3 | 1 |
| Hyena | 3 | 2 | 1 |
| Bird of Prey | 4 | 3 | 1 |
| Wind Serpent | 3 | 3 | 0 |
| Dragonhawk | 3 | 3 | 0 |
| Ravager | 4 | 3 | 1 |
| Warp Stalker | 3 | 3 | 0 |
| Sporebat | 4 | 2 | 2 |
| Nether Ray | 3 | 2 | 1 |
| Serpent | 4 | 0 | 4 |
| Moth | 5 | 0 | 5 |
| Chimaera | 4 | 0 | 4 |
| Silithid | 4 | 0 | 4 |
| **TOTAL** | **89** | **52** | **37** |

## Critical interpretation

- One call can list many spell ranks and is not necessarily one unique ability. Some calls are conditional on IP progression. Family branch names come from the pinned source.
- The 37 removal-only calls cannot supply a replacement rank. Never turn a removed spell's autocast ON based on these lists.
- The 52 dummy-backed calls still require the individual Hunter's legitimate progression and learned dummy. A spell appearing in the list is neither learned-spell evidence nor proof of native autocast capability.
- The final feature must support **all native autocast-capable Hunter pet abilities**, not merely these IP-managed call sites. Never grant a rank, or enable a passive/non-autocastable spell.
- The source coverage check is not a completion signal from IP and does not resolve permanent pet identity.

CI runs [check_hunter_pet_ip_ability_scope_pinned.py](../scripts/check_hunter_pet_ip_ability_scope_pinned.py). A changed IP source must trigger human code review, not an automatic expansion of pet ranks or autocast settings.
