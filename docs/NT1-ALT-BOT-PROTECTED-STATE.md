# NT1 Alt Bot Protected-State Observation — read-only Stage D

**Status:** Unmerged stacked draft, based on offhand/pet guard PR #11. No production deployment, no full C++ build, no implemented destructive Alt Bot repair.

## Why this observation exists

Existing Priest Alt Bots with old Vanilla-illegal Talent.dbc IDs 1768 and 1202 cannot be restored using the old build and the current Vanilla-restricted talent API. Normal Apply intentionally refuses to reset those talents. Future authorised repair must not alter inactive talent specializations, unrelated learned spells, original equipped items, pets, glyphs, bags or bank state.

The existing resetTalents(true) core path can dismiss pets and MOVE OR MAIL offhand items. Checksums cannot undo such changes.

## What repairpreview captures, READ ONLY

The command .naxxbot talents repairpreview <online-altbot-name> <NT1-code> remains restricted to a real human, approved AltBotAllowedPlayers, class/DBC/IP eligibility and non-Random Playerbot target.

The new volatile AltBotProtectedState reports:

| Scope | Public API | Captured live values |
| --- | --- | --- |
| Character context | GetGUID, GetLevel, GetActiveSpec, GetSpecsCount | Current character and active/available spec identities |
| Both specs' talents | GetTalentMap with specMask | Non-removed talent rank-spell IDs, sorted separately by spec |
| Both specs' learned spells | GetSpellMap with specMask | Non-removed spell IDs, sorted separately by spec |
| Active-spec glyphs | GetGlyph(slot) | Glyph IDs in their active slots |
| Equipment | GetItemByPos and Item::GetGUID | Item GUID low counter for every one of the 19 equipped positions |

The diagnostic displays counts and separate deterministic, FNV-style 64-bit comparison fingerprints for the talent-and-spell state of both specs, all equipped slot-to-item GUID mappings and active-spec glyphs. This fingerprint is not cryptographic, not an authorization, not a backup, and not stored. It may change naturally when characters learn spells or change equipment.

No SQL, item movement, spells learned, spec activation, token creation or character save occurs in this diagnostic.

## Explicitly excluded state

- **Inactive-spec glyphs:** AzerothCore Player::GetGlyph(slot) reads the current ACTIVE spec only. This draft does NOT call ActivateSpec or SetActiveSpec to inspect inactive glyphs. The full offline character_glyphs database backup must preserve inactive slots.
- **Bags, bank, mail and item_instance details:** The checksum covers the 19 **equipped slot identities**, not every item or item property. Full character_inventory, item_instance and mail recovery evidence is mandatory.
- **Other character state:** Pet persistence, trainer spells beyond the in-memory spell-map observation, action bars, auras, cooldowns, glyph auras and any script hook effects are not guaranteed by these fingerprints.
- **Transactional recovery:** No offline backup, test-database restore, rollback capability or race-free confirmation is implemented here.

See the separate recovery checklist in docs/NT1-ALT-BOT-RECOVERY-CHECKPOINT.md. A successful checksum comparison only indicates the captured subset appears unchanged at those two moments. It is not an independent proof of complete character safety.

## Testing and acceptance

The read-only source test suite tests both spec masks and removed entries, stable sorting of unordered maps, active-glyph limitations, all 19 equipment GUID slots, nonpersistent checksums and no destructive C++ operations. Tests use source contracts; they cannot establish compiled/runtime behaviour.

Next gates before any repair:
1. Review against the user's exact AzerothCore / Playerbots revisions; compile and test only read-only commands on an approved, isolated build.
2. Produce and **restore** a full characters database backup on an isolated test DB, verifying both specs' glyphs/talents/spells, pet state and item GUID mapping.
3. Design explicit, separate, default-disabled repair with server-confirmed intent, no gear movement, reproducible rollback and Playerbots maintenance coordination.
4. Obtain explicit administrator permission before any attempted destructive repair on a disposable Alt Bot. Never imply that regular Apply currently repairs illegal Priest talents.

All draft branches remain unmerged; the live server is not modified.
