# Playerbot talent completion — acceptance tests

**Status: NOT YET COMPILED OR IN-GAME VERIFIED.** This is a test checklist, not a claim that the feature works.

## Scope and prerequisites

- Test on the branch `feature/playerbot-talent-completion` and keep `main` unchanged.
- Back up the module/configuration and use a test realm or disposable bots.
- Keep `AiPlayerbot.LimitTalentsExpansion = 1`.
- Copy `NaxxramasCore.BotTalentCompletion.Enabled = 1` into the **active installed** Naxxramas Core config for testing, then restart Worldserver after compiling.
- Test at level 60 first; expected free points at level 60 are normally 51 (assuming no server bonus talent-point changes).
- This feature intentionally follows **level**, not Individual Progression tier. Expansion transitions at the same capped level are out of scope for this test.
- Use in-game WHISPERS to each bot: `talents spec list`, then `talents spec <exact name>`; optionally `talents apply <valid link>`.

## Essential invariants (all tests)

1. No talent with zero-based row > 6 is learned at level 60.
2. On zero-based row 6, only column 1 (middle) may be learned.
3. No talent in an inactive dual-spec slot is modified by a completion of the active slot.
4. A successful completion must leave the pre-existing legal talents intact; there must be no second reset or loss of the requested specialization.
5. All added ranks are validated by AzerothCore's `Player::LearnTalent`: no invalid prereqs, insufficient row points, class mismatch, or invalid talent rank.
6. Each respec is processed **at most once** after a 1.2 second quiet period. It must not continually spend/rebuild points.
7. Normal player characters are unchanged; paid talent resets are unaffected.
8. With the completion setting disabled, behavior matches the existing restriction-only patch.
9. With the Playerbots expansion-limit setting disabled, completion does nothing.

## Level 60 classes and styles

| Class | Manual spec to test | Special attention |
|---|---|---|
| Warrior | Arms and Protection | Custom Rend Flurry / Improved Rend Talent.dbc |
| Paladin | Holy and Retribution | Different role identities |
| Hunter | Beast Mastery and Survival | Hunter pet talents are separate |
| Rogue | Combat and Assassination | Dual-wield builds preserved |
| Priest | Holy and Shadow | Heal and damage builds |
| Shaman | Enhancement and Restoration | Dual Wield skill handling |
| Mage | Frost and Arcane | Regression: formerly 49/51 (18 Arcane + 31 Frost); confirm 51/51 where legal |
| Warlock | Affliction and Destruction | Wrack synchronizes with Shadow Mastery rank 5 |
| Druid | Feral and Restoration | Bear/cat builds and shapeshifting spells |

### Manual template path

1. Screenshot the bot's talent distribution before changing it.
2. Whisper `talents spec list`, then one exact listed spec name.
3. Wait two seconds out of combat.
4. Check rows and total points; record any free points.
5. Repeat using an alternative named specialization.
6. Verify each run is idempotent: waiting another 10 seconds doesn't change points.

### Imported link path

1. Whisper `talents apply <link>` for a 3.3.5 compatible level 60 / level 80 build.
2. Wait two seconds out of combat.
3. Verify legal rows and that the module did not change previously learned legal choices.
4. Record whether the completion follows a matching premade spec or the deterministic fallback.
5. Repeat with a deliberately unusual valid custom build and check that the dominant tree remains dominant.

### Dual spec and interruptions

1. Configure two different legitimate talent specializations.
2. Respec active spec while leaving the other untouched; switch back and inspect both.
3. Initiate a no-cost respec followed immediately by a spec-slot switch. Pending completion must be cancelled.
4. Logout before the 1.2-second settling period; it must not run after reconnect.
5. If the bot enters combat during the waiting period, finishing must wait until combat ends.

### Expansion boundary checks

- Level 60: rows 1–6 plus the middle of row 7.
- Level 61–70: rows 1–8 plus the middle of row 9.
- Level 71+: all WotLK rows.
- Levels below 10: no completion.

### Failure handling

If any points remain unspent, check Worldserver logs for:
`Naxxramas Core: Playerbot <name> could not spend <N> remaining talent point(s)...`

Record: class, spec name, level, current talent distribution, before/after free points, whether custom DBC talents are installed, and relevant Worldserver errors.

A **passing** test means correct restrictions, no talent loss, maintained intended spec, and no unused points **when legal alternatives exist**. If no legal alternative exists, leaving points unused with a warning is preferable to inventing an illegal talent or corrupting the build.
