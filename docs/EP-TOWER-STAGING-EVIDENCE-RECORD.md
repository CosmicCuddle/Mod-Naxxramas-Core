# Eastern Plaguelands tower locks — isolated staging evidence record

**Status:** BLANK TEST RECORD. This document grants **no staging, database, restart, or production permission**. Fill only after explicit owner approval, verified isolated backups and the preflight in [the acceptance checklist](EP-TOWER-STAGING-ACCEPTANCE-CHECKLIST.md).

## A. Environment and release candidate

| Field | Record actual value before test |
|---|---|
| Staging realm identifier (not production) | NOT RECORDED |
| Test operator and approval reference | NOT RECORDED |
| Staging test date/time and timezone | NOT RECORDED |
| AzerothCore fork + exact commit | NOT RECORDED |
| Playerbots + exact commit | NOT RECORDED |
| Individual Progression + exact commit | NOT RECORDED |
| Mod-Naxxramas-Core draft PR #21 candidate SHA | NOT RECORDED |
| Pinned source-test workflow URL + outcome for this SHA | NOT RECORDED |
| Full linked Worldserver workflow URL + outcome for this SHA | NOT RECORDED |
| Exact staging Worldserver binary identifier/hash | NOT RECORDED |
| Ordinary realm / cross-realm ruled out | NOT VERIFIED |
| Staging DB isolation from production | NOT VERIFIED |

**STOP:** Any unknown fork/API/schema compatibility, cross-realm mode, missing current-commit full link, or unclear DB isolation blocks installation.

## B. Backup, read-only preflight and manual opt-in

| Gate | Actual evidence/reference | Outcome |
|---|---|---|
| Full `acore_world` backup and separate restore proof | NOT RECORDED | NOT TESTED |
| Full `acore_characters` backup and separate restore proof | NOT RECORDED | NOT TESTED |
| Known-good binary, module, config and source snapshot | NOT RECORDED | NOT TESTED |
| `outdoorpvp_template.TypeId=6` has precisely one stock `outdoorpvp_ep` row | NOT RECORDED | NOT TESTED |
| Character worldstate keys 93420020–93420023 are absent/unclaimed | NOT RECORDED | NOT TESTED |
| Installed new module **without** manual SQL: script stays stock | NOT RECORDED | NOT TESTED |
| Explicitly owner-authorised `docs/install/` world SQL applied to **staging** only | NOT RECORDED | NOT TESTED |
| Exact module handler selected, no duplicate PvP controller | NOT RECORDED | NOT TESTED |

Never run the forward SQL from `data/sql/db-world`; the optional binding is intentionally in `docs/install/`. Do not perform any of these operations against production.

## C. Per-tower capture and lock tests

Each tower needs both Alliance and Horde evidence. Timestamps must come from staging observations, not invented estimates. The end time is the **same absolute expiry** after clean restarts.

| Tower | Faction | Below full capture: unlocked? | Exact 100% reached (local/UTC) | Expected expiry (UTC) | Other faction blocked until expiry? | Neutral reset observed (UTC) | Result |
|---|---|---|---|---|---|---|---|
| Eastwall | Alliance | NOT TESTED | — | — | NOT TESTED | — | PENDING |
| Eastwall | Horde | NOT TESTED | — | — | NOT TESTED | — | PENDING |
| Northpass | Alliance | NOT TESTED | — | — | NOT TESTED | — | PENDING |
| Northpass | Horde | NOT TESTED | — | — | NOT TESTED | — | PENDING |
| Plaguewood | Alliance | NOT TESTED | — | — | NOT TESTED | — | PENDING |
| Plaguewood | Horde | NOT TESTED | — | — | NOT TESTED | — | PENDING |
| Crown Guard | Alliance | NOT TESTED | — | — | NOT TESTED | — | PENDING |
| Crown Guard | Horde | NOT TESTED | — | — | NOT TESTED | — | PENDING |

Include two or more staggered captures in the same session to demonstrate **independent 90-minute clocks**. The expiry may become visible on the next normal OutdoorPvP update tick; record that observation rather than assuming an instant screen refresh.

## D. Restoration, NPCs and compatibility

| Scenario | Actual observation / timestamp | Result |
|---|---|---|
| No players nearby or no grid loaded at expiry | — | NOT TESTED |
| Clean restart about 10 minutes after full capture (remaining ~80 min) | — | NOT TESTED |
| Clean restart about 89 minutes after capture (remaining ~1 min) | — | NOT TESTED |
| Worldserver offline through the deadline: neutral on re-entry | — | NOT TESTED |
| Loaded-after-restart tower capture point + flag correct, then neutral at expiry | — | NOT TESTED |
| Northpass shrine Alliance faction 84, Horde faction 83, neutral cleanup | — | NOT TESTED |
| Eastwall support units removed at neutral | — | NOT TESTED |
| Plaguewood flight master removed at neutral | — | NOT TESTED |
| Crown Guard graveyard returns to neutral link | — | NOT TESTED |
| Counts, buffs, slider UI and existing quest credit remain correct | — | NOT TESTED |
| Playerbots and Individual Progression coexist without regression | — | NOT TESTED |
| Terokkar towers and other PvP scripts unaffected | — | NOT TESTED |
| No extra announcements, countdown, or config option | — | NOT TESTED |

A clean restart test **does not** demonstrate hard-crash durability. Deliberate fault injection is outside this plan without further specific consent and a disposable environment.

## E. Rollback and sign-off

| Gate | Evidence/reference | Outcome |
|---|---|---|
| Stop isolated staging, preserve test snapshot | — | NOT TESTED |
| Apply exact-match `docs/rollback/` SQL on staging world DB only | — | NOT TESTED |
| Verify TypeId 6 restored to stock `outdoorpvp_ep` | — | NOT TESTED |
| Restore known-good staging binary/module and verify stock captures | — | NOT TESTED |
| Confirm module worldstate keys not deleted or overwritten by rollback | — | NOT TESTED |
| Capture failed checks and agreed remediation/restore evidence | — | NOT TESTED |
| Independent owner review and separate merge/release authorisation | — | **NOT GRANTED** |

**No pass by inference:** A blank evidence record or successful CI is not an in-game acceptance. Keep PR #21 draft until the owner explicitly approves the later step.
