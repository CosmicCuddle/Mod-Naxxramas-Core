# F14 P5 — identity facts adapter (NOT WIRED, default OFF)

**Status:** DRAFT child of #197 `b44029d`. Assigned in #143 6471095561. The #197 policy header is unchanged.

The adapter is **never called**:
- no script, hook or packet registration;
- no active snapshot;
- no `/who` or world-visibility wiring;
- no config.

Runtime behaviour is unchanged. Policy B (the human exception) is still unapproved. This is build evidence only; mandatory gameplay outcomes remain 0/5.

## What it does

`NaxxramasPlayerIdentity::SampleFacts(token, Player*)` fills the seven `Facts` flags from public APIs at core `8daffda` + Playerbots `d750b4b`:

| Flag | Source |
|---|---|
| `inWorld` | `Player::IsInWorld()` |
| `hasSession` | `Player::GetSession() != nullptr` |
| `socketOpen` | `!WorldSession::IsSocketClosed()`; bot sessions always have a null socket |
| `playerbotsEnabled` | `sPlayerbotAIConfig.Enabled` |
| `botAiAttached` | `PlayerbotsMgr::instance().GetPlayerbotAI(player) != nullptr` |
| `botMasterIsSelf` | `ai->GetMaster() == player` |
| `randomBotListed` | `sRandomPlayerbotMgr.IsRandomBot(player)` |

- **Safety properties:**
  - It returns plain `bool`s by value and keeps no pointer, static or other state.
  - It never looks at name, race, level, account, GUID or another map's player.
  - It writes nothing.
- **Fallback:** a null player, or a build without all four Playerbots headers, gives empty `Facts`. Those classify as **Unknown**, so policy B degrades to A.

## World-thread-only contract (compile-time)

`SampleFacts` requires a `WorldThreadSampling` token:
- the token's only constructor is private and user-provided, and the class is `final`;
- its only friend, `WorldThreadSamplingGrant`, is **declared but defined nowhere in `src/`**.

So no module code can call the adapter yet. A future caller must define the grant in a separately reviewed world-thread hook, such as `OnWorldUpdate`, which runs after `MapMgr::Update` has waited for the workers.

Two checks hold this in place:
- `tests/f14_identity_facts_no_grant.cpp` must **fail to compile** in C++17 and C++20 for every bypass: `{}`, `()`, a local, a subclass, and `{}` as an argument. The control compiles.
- A source test finds no grant definition in `src/`.

**Found and fixed while writing this:** a private `= default` constructor still allowed `WorldThreadSampling{}` and `SampleFacts({}, p)` in **C++17**, through aggregate initialisation. The user-provided constructor closes that. A test compiles the old form to show the hole.

## Evidence (local, exact head)

- **Real translation unit** compiled at the pinned build (`compile_commands.json`, core `8daffda` + Playerbots `d750b4b` + IP `dd96f2b`). `nm` shows the real `PlayerbotsMgr::GetPlayerbotAI`, `RandomPlayerbotMgr::IsRandomBot` and `WorldSession::IsSocketClosed` references, so the Playerbots path was taken.
- **Full pinned Worldserver link** (see the PR for the result).
- **Native fixture** `tests/f14_identity_facts_adapter_tests.cpp` compiles the **real** adapter `.cpp` against small stubs.
  - **With Playerbots** (36 checks):
    - Human, SelfBot, RandomBot and AltBot are each identified positively;
    - null, out-of-world, sessionless and dropped-socket players are Unknown;
    - a config-masked AltBot or RandomBot is never Human;
    - contradictions (socketed random bot, foreign AI on a socket, linkdead SelfBot) fail closed;
    - read-only and no-retained-pointer checks;
    - integration with `IdentityBoard` and policy B.
  - **Without Playerbots** (6 checks): empty Facts, nothing read, Unknown, and B degrades to A.
  - Built with GCC C++17/20 strict and ASan+UBSan.
- **Old-vs-new witness:** Playerbots' own `IsRealPlayer` rule (`!GET_PLAYERBOT_AI`) calls a config-masked AltBot or RandomBot, and a dropped human, "real player". The adapter plus `Classify` gives Unknown for all three.
- **Mutants:** `tests/f14_identity_facts_mutants.py` makes 12 must-fail edits. All are caught.
- **Source contracts:** `tests/test_f14_identity_facts_adapter.py` (10 tests) checks:
  - unwired, and no grant defined;
  - token hardening;
  - no registration;
  - only allow-listed read calls;
  - no guessing inputs;
  - no state;
  - empty-Facts fallback;
  - loader and config untouched.

## Not claimed

- That every installed Playerbots fork keeps these contracts. The pins are `d750b4b`.
- Correctness of the world-thread sampling hook, the publish cadence or `maxAge`. None of these exist yet.
- Anything about visibility in game.
