# NT1 Playerbot Talent Map Integrity — Read-Only Anomaly Review

**Status:** Draft PR #16 only; no merge, compilation or gameplay action approved.

## Purpose

Talent-era inspection finds recognized Talent.dbc ranks that do not belong in the issuing human's selected Vanilla/TBC/WotLK era. It **does not** by itself detect unusual records in the player's in-memory `PlayerTalentMap`.

The new `PrintAltBotTalentMapIntegrity` reviews each **owned specialization** in the map, without activating it. It reports two independent anomaly classes:

1. **Unmatched rank spells:** a live talent-map spell record's stored Talent.dbc ID does not resolve to a talent/rank spell in the currently loaded server DBC, or that talent's TalentTab does not match the bot's class. A record may be unmatched simply because DBC files changed since the character was created. This is **not** proof of corruption, nor grounds for deleting the record.
2. **Multiple-rank talents:** more than one non-removed rank-spell for the same recognized Talent.dbc ID appears in the **same spec**. A rank-spell shared between two different specs is normal and should **not** be double-counted. Records marked removed are skipped.

Unknown spell IDs are sorted and **at most three** are displayed per affected spec, avoiding large chat output. Both specs retain separate counts, and abnormal active/owned spec metadata raises a warning. The existing `repairpreview` report now labels active spec numbers **1-based**, consistent with other read-only messages.

### User-facing commands

```text
.naxxbot talents safetypreview <online-altbot-name>
.naxxbot talents repairpreview <online-altbot-name> <NT1-code>
```

The integrity report appears **only after** the established real-human, bot-control (for non-GMs), non-Random Bot and exact `AltBotAllowedPlayers` checks. Mode 4 is the preferred normal-player read-only mode **only after the source is approved, compiled and installed**; the active previously shared mode 2 still permits experimental Apply.

This reporter calls `GetTalentMap`, `sTalentStore` and `sTalentTabStore` only. It does not repair, learn, unlearn, activate specs, move gear, dismiss pets, write SQL or change configuration. **Any offhand** and **any active pet** continue to block ordinary Alt Bot NT1 Apply. Other effects of a reset remain unknown.

### Interpretation and limits

- A zero anomaly count **does not prove** the build is legal, restore-ready, or safe. Talents can still violate tier, prerequisite, points or progression rules, and the talent map can omit data not loaded into memory.
- The issuer-era scan and the map integrity scan answer different questions. In particular, issuer IP era is not automatically the bot's own progression tier.
- Inactive glyphs, action bars, offline/stabled pets, item-instance GUIDs, bags, bank, mail, auras and missing/spell-granted abilities still need a consistent **offline character database backup plus an isolated tested restore** before any destructive experiment.
- The public AzerothCore `PlayerTalent` fields and `GetTalentMap() const` were source-reviewed, **not compiled against the operator's specific checkout**. Exact AzerothCore/Playerbots/IP revision gates are in [NT1 Dependency Revision Checkpoint](NT1-DEPENDENCY-REVISION-CHECKPOINT.md).

### Regression acceptance

`tests/test_nt1_altbot_talent_map_integrity.py` covers in-memory source APIs, spec-mask bounds, removed ranks, valid shared two-spec talent, conflicting ranks in one spec, unknown DBC/class data, example ordering and size, and security order. These are Python source-contract/synthetic tests, **not C++ or in-game tests**.

No automatic repair route is included. All warnings are forensic clues only, never permission to reset talents or overwrite existing character data.

### Verified source CI after talent-map anomaly additions

Commit `a81f217e1191274f467e5b3912aa7777986576fa`: [combined 167/167](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38257101158), [Alt recovery 90/90](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38257101154), [read-only diagnostics 12/12](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38257101115), [Mage 25/25](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38257101207), all **PASS**. Counts overlap. Tests inspect source and synthetic input only; they do not compile the user's AzerothCore/Playerbots/IP revisions, exercise in-game talent/map APIs, or test characters database restoration. No live server or character changes. PR #16 remains DRAFT, open and unmerged. Next gate is exact installed dependency revision evidence prior to any approved bundled compile.
