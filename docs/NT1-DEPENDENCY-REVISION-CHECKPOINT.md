# NT1 Safety Audit — Exact Dependency Revision Gate

**Status:** Draft PR #16 only; no approval to merge, compile, install, restart, or touch live character data.

## Why this checkpoint exists

The new NT1 `safetypreview` and `repairpreview` code has passed Python/static/synthetic source checks. Public AzerothCore `master` methods are compatible with the reviewed source **in principle**, but the running server may use different AzerothCore, Playerbots, Individual Progression or DBC revisions. The correct local revisions must be identified before declaring C++ viability.

Never treat a GitHub source test, checksum, `git rev-parse`, or a successful compilation as proof of equipment/pet preservation or character-database recovery.

## Read-only operator information (collect later, before an APPROVED build)

These shell commands **only inspect Git metadata and directories**. They do not pull, checkout, reset, compile, restart, update config or query the characters DB. Do not execute any destructive command as part of this checkpoint.

```bash
# AzerothCore source version and local uncommitted files
git -C /root/azerothcore-wotlk rev-parse HEAD
git -C /root/azerothcore-wotlk status --short

# Find the installed module directory names; do not assume the IP path
ls -1 /root/azerothcore-wotlk/modules

# Naxxramas Core module version and local uncommitted files
git -C /root/azerothcore-wotlk/modules/mod-naxxramas-core rev-parse HEAD
git -C /root/azerothcore-wotlk/modules/mod-naxxramas-core status --short
```

Once the Playerbots and Individual Progression folder names are known from the module listing, apply `git -C /exact/module/path rev-parse HEAD` and `git -C /exact/module/path status --short` to **each**. A nested module might inherit its parent repository, so confirm the reported Git top-level directory with `git -C /exact/module/path rev-parse --show-toplevel`.

Also record whether any server-side custom patches affect `Player::resetTalents`, `Player::ActivateSpec`, `Player::AutoUnequipOffhandIfNeed`, talent spell masks, and Playerbots talent completion. Source `HEAD` alone does not establish which binary was installed; retain the compiled binary's source/build provenance separately.

## Source APIs to compare against exact checkouts

- `Item::GetTemplate() const`, `Item::GetEntry()`, `Player::GetItemByPos(bag, slot) const`
- `Player::HasTalent(spellId, spec) const`, `Player::GetTalentMap()`, `Player::GetSpellMap()`, spec masks, `GetSpecsCount()`, `GetActiveSpec()`
- `Player::GetGlyph(slot) const` (current spec ONLY), `Player::GetQuestStatus(questId) const`
- `Unit::CanDualWield()`, `Player::CanTitanGrip()`, `Player::HasSpell(674)`
- `ChatHandler::PSendSysMessage` formatting, `ClassName` fallback, `INVTYPE_*`, `ITEM_SUBCLASS_*`, `MAX_TALENT_SPECS`
- Playerbots' real online AI/master/Random Bot API and external talent completion hooks; Individual Progression hidden rewarded quest IDs (66001–66018), stage thresholds (8/13) and configured limit

Public source reference: [AzerothCore Player.cpp](https://github.com/azerothcore/azerothcore-wotlk/blob/master/src/server/game/Entities/Player/Player.cpp). Public implementation of `HasTalent(spell,spec)` looks up `m_talents`, checks removed state and `IsInSpec(spec)`. Public `AutoUnequipOffhandIfNeed` can put original offhand items in inventory **or mail** if no storage is available; this is why the existing Alt Bot offhand Apply guard must remain fail-closed.

## Acceptance sequence — each stage separately recorded

1. **Current GitHub review:** source + Python/static/synthetic tests; PR #16 draft, main untouched.
2. **Exact dependency check:** collect installed source SHAs and any dirty files; compare against API requirements. No compilation implied.
3. **Approved single bundled build:** back up module/config, current binary and dependency locations before any checkout. No local forced reset; compile exact source, record logs. A successful compile is not a runtime safety test.
4. **Approved in-game READ-ONLY tests:** after a compiled and configured Mode 4 build, verify authorized issuer, Alt Bot allowlist, Random Bot rejection, both-spec DBC ranks, gear GUID fingerprints, pet warnings, and 3.3.5a chat length/readability for all ten classes.
5. **Destructive experiments remain separately prohibited** until a consistent stopped-worldserver `characters` DB dump has been successfully restored into an isolated database, including both-spec talents/spells, glyphs, actions, stabled pets, item instance identities and bag/bank/mail mappings, and the administrator expressly approves the experiment.

No stage grants automatic approval for the next stage. `AccessMode=2` on the last-shared live configuration still exposes experimental `apply`. Do not run Apply to test this draft. Mode 4 is available only in a binary compiled from a source revision that includes it.

## Verified PR #16 source results (12 October 2026)

Commit `41de01db0ebc12538c64a77a371b971cc6c176db`:
- [Combined 152/152 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334648)
- [Alt Bot recovery 75/75 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334657)
- [Read-only diagnostics 12/12 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334631)
- [NT1L1 Mage projection 25/25 PASS](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38254334751)

**Counts overlap; no C++ compilation, in-game character inspection, binary install, database backup or isolated restoration was performed.**

## New optional read-only source-check script (PR #16 draft)

A source-only preflight with mock-tested Git/API introspection has been prepared in `scripts/audit_nt1_dependency_apis.py`. See [NT1 Dependency API Preflight](NT1-DEPENDENCY-API-PREFLIGHT.md) for read-only usage, interpretation, directory placeholders, and limits. It is not installed on the live server; exact dependency SHAs remain unknown. It does **not** build C++, fetch/pull modules, touch config, query or write the character database, inspect the running binary, or authorize any talent Apply.
