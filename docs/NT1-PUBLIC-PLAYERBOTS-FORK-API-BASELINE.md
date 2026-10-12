# NT1 Public Playerbots Fork API Baseline — 12 October 2026

**Review scope:** Public GitHub source, NOT the administrator's live AzerothCore, Playerbots, Individual Progression, binary or DBC installation. This baseline is reproducible and pinned to the reviewed commits.

## Public source versions reviewed

- [Playerbots-compatible AzerothCore `Playerbot` commit `2a2211cd8f3d157da432ec0175ddd4b8a191931f`](https://github.com/mod-playerbots/azerothcore-wotlk/tree/2a2211cd8f3d157da432ec0175ddd4b8a191931f).
- [Playerbots module `master` commit `79bd428115c8f33b74b13de23b133d49c3f75c60`](https://github.com/mod-playerbots/mod-playerbots/tree/79bd428115c8f33b74b13de23b133d49c3f75c60).

Public file evidence from the Playerbots-compatible core:

| Reviewed file | Git blob SHA | Relevant evidence |
|---|---|---|
| [`Player.h`](https://github.com/mod-playerbots/azerothcore-wotlk/blob/2a2211cd8f3d157da432ec0175ddd4b8a191931f/src/server/game/Entities/Player/Player.h) | `5a29ac7b40ade7a11f1fcf36623dc7530ea39595` | `HasTalent(spell,spec) const`, `GetTalentMap() const`, `GetSpellMap() const`, `GetGlyph(slot) const`, `GetItemByPos(bag,slot) const`, `PlayerTalent::specMask/talentID` |
| [`Player.cpp`](https://github.com/mod-playerbots/azerothcore-wotlk/blob/2a2211cd8f3d157da432ec0175ddd4b8a191931f/src/server/game/Entities/Player/Player.cpp) | `138e7eab4905ec366338a54cc18e6cfe749a3670` | `resetTalents`, `HasTalent`, `ActivateSpec`, `AutoUnequipOffhandIfNeed`, talent-reset hooks and MailDraft fallback |
| [`Unit.h`](https://github.com/mod-playerbots/azerothcore-wotlk/blob/2a2211cd8f3d157da432ec0175ddd4b8a191931f/src/server/game/Entities/Unit/Unit.h) | `3f9a0ff07307e6fe5453b7614ab5a9fd82fdada9` | `CanDualWield() const` |
| [`Item.h`](https://github.com/mod-playerbots/azerothcore-wotlk/blob/2a2211cd8f3d157da432ec0175ddd4b8a191931f/src/server/game/Entities/Item/Item.h) | `572467aa2a4f84480352befadddc9cd194b1d258` | `GetTemplate() const` |
| [`Chat.h`](https://github.com/mod-playerbots/azerothcore-wotlk/blob/2a2211cd8f3d157da432ec0175ddd4b8a191931f/src/server/game/Chat/Chat.h) | `0cc1de91b3475dc7c1ce5bcbde8b6ba1842287ad` | `PSendSysMessage(char const* fmt, Args...)` formatting |

Public Playerbots module headers reviewed:

- `src/Bot/PlayerbotAI.h`: `GetMaster()`.
- `src/Bot/PlayerbotMgr.h`: `GetPlayerbotAI(Player*)`.
- `src/Bot/RandomPlayerbotMgr.h`: `IsRandomBot(Player*)`.

These public files contain the expected *textual* interfaces. The checker does not compile against them, and public branch commits are not assertions about the user's local source.

## Particularly important reset side effects

The publicly reviewed `Player::resetTalents` body calls the talent-reset script hook, can remove a pet, clears Titan's Grip/Dual Wield where appropriate and calls `AutoUnequipOffhandIfNeed`. The public offhand function can move an equipped offhand item into bags **or mail it** if inventory cannot accept it. `ActivateSpec` is likewise state-changing; never switch a character's spec merely to read inactive talents.

**Therefore:** keep the existing Naxxramas Core Alt Bot NT1 Apply block for any occupied offhand item or active pet. The public source is not evidence that a future reset is reversible; a full consistent offline `characters` database backup and an **isolated tested restore** are mandatory before any destructive experiment.

## What the local preflight does next

Use [NT1 Dependency API Preflight](NT1-DEPENDENCY-API-PREFLIGHT.md) to identify potential local module directories and inspect **actual** source signatures and Git working-tree changes. The first discovery step only lists directory candidates and selects none. The full preflight requires explicit paths; even a green text signature still needs source review and one **separately approved** bundled C++ build.

**Still unknown:** the operator's actual core/Playerbots/IP/Naxxramas Core source commits, private patches, DBC versions, build flags, installed binary SHA and live mode. These cannot be inferred from public GitHub branches. No command in this document authorizes merging draft PR #16 or making any live data changes.


## Public-baseline review checkpoint and source CI

Commit `18adb9b2b6f76056cc82d14fd77ff62f8b387e3a` passed overlapping GitHub Actions source/synthetic suites on 12 October 2026: [combined NT1 **197/197 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38267119953) (including 30 dependency-audit regression tests), [Alt Bot recovery **90/90 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38267119967), [read-only diagnostics **12/12 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38267119900) and [Mage projection **25/25 PASS**](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/38267119926). Suite counts **overlap**. The public fork-source baseline is a pinned external code review, NOT the operator's installed checkout. No actual C++ compilation, local Linux audit, in-game 3.3.5a test, character database backup/restoration or live changes have been made. PR #16 remains DRAFT/unmerged.
