# A02 Part29 — both native pet autocast mutation routes (PINNED PUBLIC SOURCE)

**SOURCE-ONLY / REVIEW-ONLY / NO RESTORATION.** Separate child of #173 exact `8b35ae4023f1bfd14c199379056a928d86117065`; no runtime source, SQL/schema, addon, owner installation, Playerbots/IP, or server changes. This is a functional design correction, not acceptance of C1/C2/C3.

## New public-source finding and concrete consequences

At `Grimfeather/azerothcore-wotlk@8daffdabe9202c228e45d833c9a1d399597a15cd`, `PetHandler.cpp` contains **two different native writes** that can enable/disable pet spell autocast:

1. `WorldSession::HandlePetSpellAutocastOpcode` (lines around 955–1008) is invoked for `CMSG_PET_SPELL_AUTOCAST` (`PROCESS_INPLACE`). It checks the pet or charm association, resolves the spell template, rejects unknown/unlearned/non-autocastable spells, then toggles per-pet/autocast and `CharmInfo::SetSpellAutocast`. For same-entry controlled units it loops across the controlled set; a packet does not necessarily map one-to-one with a single pet-state write.
2. `WorldSession::HandlePetSetAction` (around 696–837), dispatched for `CMSG_PET_SET_ACTION` (`PROCESS_THREADUNSAFE`), also calls `Pet::ToggleAutocast(spellInfo, true/false)` under `ACT_ENABLED`/`ACT_DISABLED` action-bar changes. It parses one or two position/action pairs, checks the *first controlled* pet and valid action positions and known spells, and writes `CharmInfo::SetActionBar`. **It does not call `HandlePetSpellAutocastOpcode`** and does not repeat the explicit handler's `IsAutocastable()` validation at that location.

**Implication:** any A02 C1 design that observes **only** the explicit autocast opcode cannot assert completeness of server-visible native pet-autocast changes. Instrumentation/forensic testing must distinguish both routes and reject untrusted, bot/IP/stock reset origins. The action-bar packet's processing category is different, so thread assumptions from the explicit route are not transferable.

## Receipt boundary remains a hard blocker

`ScriptMgr.h` on this pin exposes `ServerScript::CanPacketReceive` (pre-handler) and outgoing packet hooks, **not an authoritative `OnAfterPetSpellAutocastAccepted` callback**. A successful pre-handler return is not evidence the native handler passed *its own* validation. A later matching state can equally result from Playerbots, IP rank updates, restored native pet state, or another packet. These source tests do not prove no possible extension exists elsewhere in the installed customized core, and do not assert that every action-bar packet necessarily toggles autocast.

Even full two-opcode interception would still require: **positive synchronized human/SelfBot provenance**, post-native accepted causal receipt, current IP-permitted rank/revision, verified pet birth distinguishing recycled PetNumbers across re-tame/import/recovery, restart-durable authorized preference, and explicit owner approval before any automatic writer. `TrustedManualReceipt=false` / `NoWrite` remains mandatory. An owner's earlier C1/C2 design direction did not authorize implementation/SQL, lower-assurance mode, installation or tests on a real server.

## Automated limited evidence

The new `tests/test_a02_p29_dual_native_autocast_paths.py` reads the **exact pinned public** `PetHandler.cpp`, `Opcodes.cpp`, `ScriptMgr.h`. It asserts the two writers, distinct checks and opcode worker categories, same-entry multi-pet fanout, the lack of a post-handler receipt in the **stock ServerScript interface**, plus deliberately limited synthetic negative witnesses. Its CI child modifies the existing #173 sparse checkout to include `PetHandler.cpp` and runs BOTH inherited lexical sentinels and this new suite at exact head.

**This is code/source-drift evidence only**. No native packet executed, no real player or bot, no Worldserver link, no actual core addon install, no private SQL/character/item/progression relationships, no schema changes, and no implicit release approval. Keep public repo data only.

## Architecture choice still needed

A safe native accepted manual receipt *and* real positive SelfBot mode (plus durable pet birth) require an installed-compatible authoritative event/source beyond the module's existing exposed pre-handler; otherwise a module-only diagnostic candidate cannot be promoted to automatic restoration without the owner explicitly electing a separately labelled weaker policy. Leave A02 disabled, and prefer proving a future source seam over implementing a C1 mirror that appears functional while its causal provenance is unknown.
