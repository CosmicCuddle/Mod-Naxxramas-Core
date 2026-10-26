# A02 Part 26 — Unverified v1 relay runtime quarantine (DRAFT)

This branch is a child of [recipient-scoped #164](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/164). It is a **real code-level safety correction**, not functional human pet restoration.

**Security concern:** Before this change, setting `RestoreHumanChain=1` and `AddonOptIn=1` could cause `HunterPetAutocast.cpp` to auto-restore a per-player v1 preference set onto the pet currently summoned, even though the v1 payload lacks an authenticated current pet birth, settled permitted Individual Progression rank, accepted manual-click origin and positive human-not-SelfBot classification. This can override an accepted OFF with a stale ON. Defaults OFF do not remove the risk of an accidental opt-in.

**Implemented source behaviour:** A `PreferenceSnapshot` now has `VerifiedHumanManualOrigin = false`. The legacy v1 assembler never sets this. Its parser still decodes well-formed ON/OFF for diagnostic compatibility, but `EligibleForAutomaticRestore` requires BOTH v1 OptedIn and server-proven manual origin. The **actual production `OnWorldObjectUpdate`** checks this gate **before** `BuildAddonPlan` and before any `ToggleAutocast`. Thus the current legacy v1 receiver cannot ever write pet autocast settings, even if both experimental configuration flags are manually enabled. Existing stock Hunter behaviour remains unchanged. No database/DBC or pet rank mutations are added.

**Important:** The `VerifiedHumanManualOrigin` field is a FUTURE trusted-contract placeholder. Setting it to `true` in a synthetic test is NOT equivalent to genuine authority. No code currently makes it true, and no client packet or addon bit may ever set it directly. The future sender/receiver and current-human/AI mode path must be independently reviewed, source-verified and approved before any trusted producer is added. This is an intentional release safety lock, not a usable A02 fix.

## Tests and exact limitations

- A new native C++17/C++20 test parses real `OptInStore` v1 strings `NXCPAK\\tv1|...` via the code used by the module and checks ON, OFF, second player, login/relog, logout, clearing, and that **none** is eligible for a write.
- A new Python source test pins runtime guard placement before the plan and actual `Pet::ToggleAutocast`, plus the unmodified self-whisper receiver and default-OFF config. This is source-only.
- Existing C++ policy/addon suites and pinned Worldserver linking remain required. No fake 3.3.5 client, live server, real pet, SelfBot, IP completion or successful human restore is claimed.

## Remaining functional A02 gates

- Native `CMSG_PET_SPELL_AUTOCAST` requested ON/OFF and `CMSG_PET_SET_ACTION` require post-handler accept evidence and real human-mode classification; `ServerScript::CanPacketReceive` is pre-handler and may run with different map/world threading. See [#164 source investigation](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/164#issuecomment-6414366251).
- Durable pet-birth identity (not only name/recycled PetNumber), latest accepted manual OFF, cross-pet packet queue invalidation and real 3.3.5 client/handler provenance.
- Individual Progression's repeated delayed rank swaps require bounded, real book-transition-aware re-application only to the allowed existing rank; never learn a spell or presume an arbitrary 200ms settle time.
- In-game tests/host backups/rollback only after separate owner permission. Preserve main, #135, #163, #164, #160, private source, local Playerbots, core/IP/N-Core/config/SQL/DBC and `MapUpdate.Threads=8`.

No merge, release, deployment, config enablement or live host action authorised.
