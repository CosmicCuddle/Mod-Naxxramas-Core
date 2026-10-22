# P1 — Warlock Ritual of Summoning versus dungeon Meeting Stones (source-only)

**Status (22 October 2026):** CS01 and CS02 independent S1 source reviews agree that
the existing `main` module already treats these as separate object types.
No new gameplay exception should be invented without a demonstrable failure.
See [issue #84](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/84).

## Exact inspected code

- Module: `src/Systems/MeetingStoneProgression.cpp` at
  `75315783e4921b47809d96094f4885f68ff42146`.
  `CanGameObjectGossipHello` returns **false** unless the object is
  `GAMEOBJECT_TYPE_MEETINGSTONE`. A Warlock-created GO of type
  `GAMEOBJECT_TYPE_SUMMONING_RITUAL` is not denied by this hook.
- Pinned Grimfeather AzerothCore `8daffdabe9202c228e45d833c9a1d399597a15cd`:
  `GameObject.cpp` distinguishes ritual type **18** (around line 1850)
  from meeting-stone type **23** (around line 1942). The native ritual
  requires the usual owner/channel/group/participants checks; the
  native meeting-stone case uses spell **23598** and its own minimum level.
- CS02 additionally inspected IP and native spell routing; see
  [the independent findings](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/84#issuecomment-6339797238).

## What this isolated test does — and does NOT do

`python3 -m unittest discover -s tests -p 'test_meeting_stone_ritual_isolation.py' -v`
checks that the **real module source** preserves the early type-23-only guard,
the existing config/Vanilla progression gate, and the return-false handoff to
native AzerothCore. It makes **no source or DB edits**.

These are source assertions, **not** evidence of actual Warlock GO template
type, client interaction, Playerbots cooperation, installed IP compatibility,
or successful group summoning on the owner's realm.

## Next user-approved runtime acceptance

At a later convenient privately approved in-game session:

1. A Vanilla-stage Warlock channels **Ritual of Summoning** with two valid
   grouped helpers; portal spawns and helpers can operate it.
2. Confirm the target can be summoned using native group/channel/instance
   restrictions; record the *specific* failed stage if not.
3. Confirm an ordinary dungeon Meeting Stone still blocks a Vanilla-stage
   player with the intended progression message.
4. Test TBC-stage behavior separately if needed.

If the Warlock ritual fails, investigate the actual portal template and native
prerequisites using **read-only** evidence. SQL writes, spell edits,
core/IP/Playerbots changes, live config and process restarts require separate
explicit owner approval. Do not close #84 solely because source CI passed.

**Deployment/release:** No gameplay modifications or deployment are proposed.
This draft provides a regression guard to protect already-correct routing.
