# Part29 F13 — clicker-owned Atiesh GO lifetime after direct TeleportTo

**DRAFT, SOURCE-ONLY, DEFAULT OFF. DO NOT MERGE, INSTALL, ENABLE CONFIG, RUN REAL SERVER, ACCESS OWNER SQL/host or infer owner test PASS.** Isolated candidate based exactly on already-reviewed [DRAFT #186](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/186) `ea16700710698ca0515925838f3274c2da3760b8`. Frozen gameplay #160 remains immutable and unmerged. The F12 implementation, policy headers, GFPP atomic implementation, F14, AzerothCore, IP and Playerbots are unchanged.

## Pinned native proof: the post-teleport GO may already be scheduled for removal

Full public `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd` source directly establishes a synchronous cleanup chain:

1. `Player::TeleportTo` (`Player.cpp:1401–1644`), on a successful cross-map transfer, invokes `oldmap->RemovePlayerFromMap(this, false)` **before the function returns true** (`:1618–1619`). A same-map teleport can also remove teleport-interrupted auras earlier; whether that specific portal is aura-bound remains unknown.
2. `Map::RemovePlayerFromMap` (`Map.cpp:719–737`) calls `player->RemoveFromWorld()`.
3. `Player::RemoveFromWorld` (`Player.cpp:1758–1789`) delegates to `Unit::RemoveFromWorld`.
4. `Unit::RemoveFromWorld` (`Unit.cpp:12169–12216`) invokes `RemoveAllGameObjects()`; that method (`:6450–6462`) clears the owner, sets GO respawn to zero, and calls `go->Delete()` for each tracked owned GO.
5. `GameObject::Delete` (`GameObject.cpp:985–1006`) schedules GO map removal with `AddObjectToRemoveList()` in its normal branch. This proves **post-despawn logical access risk**, NOT necessarily that heap memory is freed immediately or that the owner's actual Atiesh object is always tracked this way.

The protected #160 F13 handler did: `if (player->TeleportTo(...)) go->AddUse();` — even when the clicker is the GO owner. For a clicker-owned spellcaster portal, `go` can thus be logically removed within `TeleportTo` before `AddUse` runs. A full linked Worldserver alone does not detect that lifecycle hazard.

## Minimal conservative correction and explicit tradeoff

Immediately before mount handling/teleport, snapshot `bool clickerOwnsPortal = go->GetOwnerGUID() == player->GetGUID();`. On a *successful* teleport, call `go->AddUse()` only if **not** clicker-owned (ownerless world/static GO or another group member's GO). On unsuccessful teleport, still report failure **without** any use count. If the GO belongs to the clicker, **never dereference it after TeleportTo**. Only that one F13 method is modified.

The conservative tradeoff is explicit: on a **same-map successful teleport of a clicker-owned GO that happens to remain alive**, skipping `AddUse` differs from native spellcaster successful-use counting; it is preferred to an unverified lifetime dereference in the default-OFF draft. This remains subject to owner gameplay acceptance, not a claim of exact native parity. If a real owner stage requires such same-map counting, a different pre-validated lifetime-aware design must be separately reviewed rather than reintroducing a dangling use. The code does **not** change party-only selection, GO/template/spell match, IP/Vanilla-stage gate, live exterior area-trigger row, orientation, mount handling, GM behavior or fallback on failed teleport.

## Tests and integration gate

- Original `tests/test_atiesh_karazhan_portal.py` updated with owner-capture and no-after-teleport read contracts; original policy/model suite and all other feature tests remain mandatory.
- New `tests/test_p29_f13_owned_go_lifetime.py` checks **six source-chain assertions** against the exact pinned public core: player far teleport removes from map, map/player/unit cleanup reaches owned GO removal, GO is scheduled for removal, cached pre-teleport owner identity, successful non-clicker-owned use count, and absence of clicker-owned post-teleport access. No actual game objects or server launched.
- Combined 5/5 source assembly blob gate pins exactly the two F13 source+test changes while all other reviewed GFPP/F12/F14 configurations/blobs remain frozen. Existing full pinned Worldserver C++17/20 source and full Worldserver compile/link must independently pass the **new child exact HEAD**. Previous #186 full-link CI does NOT prove this modified F13 code has linked.

## Separate owner staging acceptance (NOT RUN)

After explicit owner authorisation, installed-version audit, and **verified restorable nonproduction backups**, test Atiesh click with (a) clicker-owned portal, (b) portal owner is a *different* party member, and (c) ownerless/static portal if actually present. Confirm no crash/GO ghost/usecount anomaly, no internal Karazhan teleport, intended exterior landing with correct orientation, correct party/era/GM/stock fallbacks and rejected-teleport behavior, and no unrelated player or bot change. Keep logs/player identifiers privately, never in PUBLIC GitHub.

**Actual owner gameplay accepted: 0/5.** F13 remains untested on the owner's portal/template, F12 real doors remain untested, GFPP 120-second no-retry remains untested. A02 still NoWrite, A04 H1/H2 still unverified, F15 BLOCKED_AT_R0/nonoperational, Claude on break.