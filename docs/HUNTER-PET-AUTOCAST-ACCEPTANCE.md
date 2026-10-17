# Hunter pet autocast persistence — acceptance plan

**Research-only. No tests have been run, no config/SQL has been installed, and no runtime fix has been implemented.**

This is a focused companion to [the feasibility audit](HUNTER-PET-AUTOCAST-FEASIBILITY.md), not proof of an implementation. Prepare disposable/staging Hunter pets only after separately approved setup and verified characters DB backup.

| ID | Setup/action | Required result |
|---|---|---|
| AC-00 | New module config off | Identical core/IP pet spells, packets, autocast and persistence; zero module DB writes |
| AC-01 | Meshana-style Wind Serpent at Molten Core stage, legally knows Lightning Breath R5 25011, explicitly chooses ON | After IP re-learns legal R5, autocast returns ON without module teaching any rank |
| AC-02 | Same pet with R5 explicitly chosen OFF | After dismiss/revive/stable/relog, autocast remains OFF; no silent enabling |
| AC-03 | At MC stage, without ZG unlock/dummy, attempt resummon and revive | Rank 6 25012 is never granted by module or enabled; any existing core/IP issue is logged separately, not disguised |
| AC-04 | Wind Serpent after legitimately unlocking ZG R6 | Preference follows *legal ability family* from R5 to R6 if policy approved; no invented ranks; confirm native IP behaviour |
| AC-05 | Bite R8 and Dive (ON/OFF separately) | Both retain intended state; Lightning Breath restoration cannot affect other ranks |
| AC-06 | Normal Hunter voluntarily toggles R5 ON then OFF using standard pet spell toggle packet | Persist **two different confirmed user intents**; last validated state wins |
| AC-07 | Normal Hunter changes existing pet actionbar spell autocast using single-slot `CMSG_PET_SET_ACTION` | Read-only audit confirms eligible same-slot ON/OFF and matching native/bar state; ignores two-slot move/reject; no persistence yet |
| AC-08 | Crafted invalid packet, foreign pet GUID, unknown spell or unlearned spell | Reject as preference evidence; never touch pet or DB |
| AC-09 | IP removes and relearns an ability; automatic re-learn leaves native autocast OFF | **Do not misclassify automatic OFF as explicit user OFF**; restore explicit stored ON only after IP settled |
| AC-10 | IP reconcile delayed while native pet loading / callback reordered | Restoration never wins a race or toggles the wrong rank; bounded skip on uncertainty |
| AC-11 | Dismiss, summon, death/revive, logout/login | Explicit ON and OFF restored per *same pet identity*; native ability set unchanged |
| AC-12 | Stable pet A, use pet B (same family allowed), swap A↔B | Each pet keeps its **own** preference; no cross-contamination |
| AC-13 | Delete/replace pet, native PetNumber reused, same creature entry possible | Old pet's preference is not inherited by new pet; fail closed if identity ambiguous |
| AC-14 | Server process restart, read approved module-owned persistent store | ON and OFF survive; no duplicate/stale rows or unsafe native pet_spell edits |
| AC-15 | Ordinary Hunter stage Vanilla 0–7 and late Vanilla raid tiers | Works under intended Vanilla stages, stage derived from **that Hunter** |
| AC-16 | TBC/WotLK or IP disabled; unknown progression | No forced Vanilla autocast restoration; no rank edits |
| AC-17 | Altbot Hunter with own pet and effective stage | Separately opt-in; prove packet/direct AI pathway and ownership; no controller-era shortcut |
| AC-18 | Non-Hunter/Warlock/DK pet | Entirely untouched |
| AC-19 | Client 3.3.5a pet actionbar vs server `m_autospells`/spell active | Server and client ON/OFF presentation agree after legitimate restore; no duplicate learned-spell message attributable to module |
| AC-20 | Playerbot AI routine invokes direct `ToggleAutocast` without packet | Do not invent explicit user intent; either prove safe alternate capture or mark bot path unsupported |
| AC-21 | Disable feature after test | Existing spells, stable rows and player choices remain intact; no forced reversal or lingering event |
| AC-22 | No user selection recorded | Do **nothing**; never default Lightning Breath to ON |
| AC-23 | Pet's legal ability rank changes through legitimate IP unlock | Map to validated first-rank spell family; never restore on obsolete/illegal rank |
| AC-24 | Session disconnect or pet replaced while deferred work queued | Deferred operation cancels without dereferencing dead pet or touching replacement |
| AC-25 | Multi-character concurrent summon/respawn | Scoped event data cannot leak across players or pet instances; no global scanning |
| AC-26 | Database unavailable or migration not installed | Fail closed; preserve native behaviour and player pets; do not repeatedly spam logs or DB |
| AC-27 | Config Debug=0 | No new player chat or repetitive log noise; no DB writes except approved confirmed preference changes |
| AC-28 | Repeated unchanged state | Zero redundant `ToggleAutocast`, client refresh packets, database writes or continuous updates |
| AC-29 | Highest retired native PetNumber is reused after deletion + restart | Old record is never treated as a verified incarnation; do not restore on merely equal owner/pet number/family |
| AC-30 | Module absent during abandon/retame, then enabled again | New pet with same owner/number/entry cannot inherit a stale choice; unsupported identification must fail closed |
| AC-31 | Read-only pet event-clock sample at +2500ms | Observe actual queue order after native loading, without declaring IP completion, teaching a spell or toggling autocast |
| AC-32 | Event queue delayed/retry rescheduled after large tick | Marker alone never authorizes restoration; absence of post-IP proof means skip |
| AC-33 | Hunter pet knows Bite, Growl, Dash, Lightning Breath or other autocast-capable abilities | Every ability's ON/OFF is independent, not Lightning Breath-only |
| AC-34 | Different Hunter pets know the same autocast-capable ability | Per-pet preferences never bleed across individuals |
| AC-35 | Passive or non-autocastable ability exists | Never attempt to store or restore an autocast state for it |
| AC-36 | Enable the audit on an ordinary Hunter whose pet knows non-Lightning Breath spells | Generic bounded snapshot observes all eligible learned abilities and bar entries; no gameplay changes |
| AC-37 | Pet legitimately upgrades an ability through IP | The remembered rank-family choice may apply only to the current known IP-legal rank, never to unknown/locked ranks |
| AC-38 | IP or another legal system relearns several autocast-capable Hunter abilities before next Player update | Bounded read-only learned-spell audit preserves up to 32 distinct pending IDs, never changes packets, abilities or actionbar |
| AC-39 | Hunter pet dies and is revived in-world without another OnPetAddToWorld callback | Bounded read-only Player-update transition probe logs before/after generic autocast; no implied IP readiness or change |
| AC-40 | Pet dies again, is dismissed or replaced before delayed revival snapshot | Old per-pet event cannot apply to another pet or report obsolete revival sequence, including after the four-sample cap; no gameplay writes |
| AC-41 | Revive happens entirely between two Player updates | Document and verify the limitation: missed transition must NOT be treated as proof that IP reconciliation was bypassed or completed |
| AC-42 | Offline candidate planner handles multiple abilities and rank upgrades | Confirm independent explicit ON/OFF, stage legality, no unknown/duplicate ranks, no pet inheritance and no bot default; model-only tests never treated as runtime proof |
| AC-43 | Enable read-only audit when active Hunter pet is already dead, then revive it | Initial dead state is retained and next observed revival is logged; no user-intent or IP-ready inference |
| AC-44 | Hunter pet killed and revived between two player-update callbacks | UnitScript::OnUnitDeath captures the normal lethal death and bounded observer sees later revival; no rank or autocast change |
| AC-45 | Same death observed by both unit-death hook and player fallback | Single death record and revival sequence; no duplicated generation bump or stale deferred observation |
| AC-46 | Source-pinned PetNumber allocator, pet SQL schema and normal save | CI demonstrates no proven durable incarnation token, possible number reuse and save delete/replace, blocking any preference table pending new proof |
| AC-47 | Exact pinned IP pet delayed check, core Pet::Update and PetScript source | Verify private pending flag resets BEFORE checkHunterPetSpells, native load flag is separate, and no verified public post-IP completion signal exists; no restore |
| AC-48 | Pinned IP family/rank reconciliation source inventory | Verify 26 family branches and 89 active calls: 52 with dummy candidates and 37 removal-only, excluding commented-out calls; no rank/autocast permission inferred |
| AC-49 | Hunter toggles two different autocast-capable abilities before the next player update | Bounded read-only queue preserves each distinct candidate (up to 32), verifies its own native state and never applies any spell or SQL change |
| AC-50 | Repeated same-spell toggle packets or more than 32 rapid candidates | Exact duplicates coalesce, opposite ON/OFF remains distinct, overflow is logged once on the next update, and no candidate becomes a stored preference |
| AC-51 | Pinned core add/remove/native-save and IP rank reconcile loss path | Prove fresh autocastable spells default OFF, native saves active state, normal high-rank inheritance is distinct from IP unlearn/relearn, and OFF alone is never human intent |
| AC-52 | Standalone pure C++ decision gate evaluates hypothetical ON/OFF candidate | Reject unverified user intent, native load / clock / packet as IP completion, ambiguous rank, illegal or unknown spells, non-Hunter, and bots; no runtime integration or spell writes |
| AC-53 | Same active Pet runtime object versus another Pet object after summon, stable or restart | Runtime identity allowed only for same-object hypothetical evaluation; after object replacement require independently verified never-reused incarnation, which is presently unavailable |
| AC-54 | Native existing Hunter pet load reaches pre-create PlayerScript callback | Audit logs read-only attempted load arguments without modifying refs; abort after hook remains possible and does not imply IP completion or incarnation identity |
| AC-55 | Fresh tame, or no native load-attempt log observed | Do not treat absence of the pre-create hook as proof of successful new tame; audit disabled/early failure/alternate paths remain ambiguous |

## Evidence required before any rollout

For each case, keep a staging record with:
`test ID`, exact AzerothCore/IP/Playerbots/Naxx Core commit hashes, module flags, human vs bot account classification, effective character IP stage, pet number+verified generation, family/creature entry, spell IDs/dummy evidence, explicit last preference, event/packet order, actual spellbook+actionbar before/after, observed DB writes, result (PASS / FAIL / BLOCKED).

**Do not** claim any case passed from source reading alone. For a real install, verify restoration of the **characters database** and native pet tables on a nonproduction copy before enabling the feature. An existing general backup is welcome but does not automatically prove a restorable pet/characters DB snapshot.

## Recommended incremental review gates

- **HPA-G1 (source + model):** Confirm hook/API signatures, native accepted-intent capture, first-rank chain and missing-hook limitations. No code in other repositories.
- **HPA-G2 (read-only prototype):** Feature code only in Mod-Naxxramas-Core, all config OFF, no SQL, compile against pinned Grimfeather + IP + Playerbots; instrumentation proves timing with no mutation.
- **HPA-G3 (durable preference state):** Pet identity lifecycle verified, approve module-owned persistence schema and rollback, staging character DB backup/restoration.
- **HPA-G4 (functional staging):** Execute AC-00…AC-55 and independently verify IP progression, original spell-learning messages and Altbot paths.
- **HPA-G5 (production):** Separate explicit owner approval to merge/install/enable; staged opt-in; rollback ready.
