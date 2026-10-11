# NT1 Alt Bot Recovery Checkpoint — Offline Backup and Gear Safety

**Status: READ-ONLY DEVELOPMENT ONLY.** Stacked on draft [PR #9](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/9) and, transitively, draft [PR #7](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/7). No Alt Bot reset-and-repair command, no config activation, no schema migration, no production merge. The separate level-projection draft [PR #8](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/8) is not part of this branch.

## 1. What is now implemented in this draft

The previously proposed read-only `.naxxbot talents repairpreview <bot> <NT1-code>` (PR #9) additionally reports:

- The currently active spec slot and the number of available spec slots.
- Whether the target has **any item equipped in the offhand slot**, determined read-only with `Player::GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND)`.
- A warning that ordinary `Player::resetTalents(true)` **can dismiss a pet and may move or mail an offhand item**. Presence of an offhand is a *risk indicator*, not a proof of incompatibility; absence is **not** proof of complete repair safety.
- An explicit warning that the command **cannot verify database backups or that a backup can be restored**.

The command still checks the real issuing human, existing `AccessMode`, the human's current Individual Progression, Playerbot ownership/master checks, a non-Random Alt Bot target, and `AltBotAllowedPlayers` (including for GM). It never resets talents or touches inventory.

**Critical upstream source evidence:** AzerothCore `Player.cpp::resetTalents` calls `RemovePet` and `AutoUnequipOffhandIfNeed`. The latter may move an item into bags, or create an **in-game mail with the item attached when no bag slot can hold it**. This is strictly incompatible with “Alt Bot gear and bags never touched.” An ordinary Apply may share that risk; this PR does not claim to fix it by merely warning. **Do not run destructive Apply/repair on affected Alt Bots until a separately tested no-item-change guard is installed.**

## 2. Offline structural audit utility (does not create or restore a backup)

- `scripts/audit_nt1_altbot_recovery_backup.py` accepts an already-created `.sql` or `.sql.gz` full characters database export and optionally generates a **new, owner-only (0600), non-overwriting JSON checksum manifest**.
- It streams the whole compressed file to verify gzip CRC, computes **SHA-256 of the original backup bytes**, and verifies table definitions for **12 core character-state tables**: `characters`, `character_talent`, `character_spell`, `character_glyphs`, `character_action`, `character_aura`, `character_inventory`, `character_stats`, `item_instance`, `character_pet`, `pet_spell`, and `pet_aura`. It reports the presence of the optional module-owned `mod_naxxramas_bot_talent_import` table.
- It fails if the file is absent, empty, corrupt/truncated, not SQL/gzip, or lacks a required table. It never opens a MySQL connection, saves/modifies character rows, executes SQL or prints data from dump rows.
- Passing means only **structural coverage, file readability/CRC and checksum recorded**. It is emphatically **NOT proof** that the SQL came from a quiescent database, contains every row, can be loaded, or will successfully restore all Alt Bot state.
- Tests in `tests/test_nt1_altbot_backup_audit.py` use synthetic SQL fixtures. They do NOT contain or expose any real character, account or database records.

### Example: audit an existing PRIVATE offline backup

**Do not run this until you have an actual full backup from a stopped Worldserver.** Run from the module repository root:

```bash
python3 scripts/audit_nt1_altbot_recovery_backup.py \
  --dump /root/naxxramas-backups/nt1/acore_characters_TIMESTAMP.sql.gz \
  --manifest /root/naxxramas-backups/nt1/acore_characters_TIMESTAMP.manifest.json
```

The supplied paths are examples: use the actual backup path. The tool refuses to overwrite a pre-existing manifest. The manifest must stay private and must never be committed to GitHub.

## 3. Required operator backup checkpoint (manual, not executed by module)

**Before any experimental destructive Alt Bot talent repair:**

1. Confirm the Worldserver is cleanly **stopped** (not merely the bot logged out). Run `pgrep -a -x worldserver`; there must be **no active worldserver process**. Ensure other background tools are not writing to the characters DB. Also capture exact module/core Git revisions and database version.
2. Create a private backup directory and a fresh, **complete** characters DB dump. In a Linux shell with the necessary local DB authentication, an example is:

```bash
set -o pipefail
umask 077
BACKUP_DIR=/root/naxxramas-backups/nt1
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/acore_characters_$(date +%Y%m%d_%H%M%S).sql.gz"
mariadb-dump --single-transaction --quick --hex-blob --triggers acore_characters |
  gzip -c > "$BACKUP_FILE"
```

If your database client is named `mysqldump`, use that instead of `mariadb-dump`. Use your existing **secure** MySQL credentials file/Unix-socket authentication; never place a password directly on the command line or in GitHub. This command is an **example**, not a production run performed by ChatGPT.

3. If the dump command fails, the resulting file is **NOT** a usable backup, even if gzip created a non-empty file. Do not use it for repair. Do not restart writes until you know the backup completed correctly. Run the structural audit above and independently `sha256sum "$BACKUP_FILE"`. Store a second copy in a protected location outside the live server.
4. Restore a copy into a **separate isolated test MySQL/MariaDB instance**, with **no Worldserver pointed at it**. Verify character GUID and the active/inactive `character_talent.specMask`, `character_spell.specMask`, `character_glyphs.talentGroup`, action bars, pet state, item GUID ownership and `character_inventory` bag/slot mappings. Compare rows and item GUIDs to a consistent pre-change baseline for the specific Alt Bot. A restore performed into an isolated instance should not overwrite production.
5. If an emergency recovery is needed after a future authorised test, **stop the Worldserver**, secure its state and use the rehearsed offline restoration process. Do not overwrite a character's SQL while the bot is logged in; the live character state may overwrite the restoration. A full DB restore rolls back **every character's changes since backup**, so targeted restoration is a separate, carefully reviewed recovery procedure.

**No backup or successful restore rehearsal can be verified by the game command.** No in-game Apply should be enabled merely because a Python manifest has been generated.

## 4. Follow-up safety acceptance before any destructive repair

| Required proof | Current status |
| --- | --- |
| 51/51 replacement NT1 passes DBC/era and real human/Alt Bot allowlist | Prior source logic exists; live field testing still needed |
| Full database backup, SHA, table coverage | Tool implemented; operator checkpoint NOT performed |
| Full isolated restore rehearsal, data/GUID comparison | NOT performed |
| Both talent specs and glyphs preserved except selected repair spec | No destructive repair implemented |
| Talent-derived spells, pets and auras handled consistently | Pending live code design/test |
| No equipped item/bag move; **no offhand mail fallback** | NOT proven, must fail closed |
| Failed LearnTalent recovery without invalid old-talent replay | NOT implemented |
| Conflict with Playerbots AltMaintenanceTalentTree resolved or blocked | Pending |
| Default-off independent Alt Bot repair flag and explicit confirmation | Proposed only; NOT added |

## 5. Tests and limitations

The draft regression workflow runs `python -m unittest discover -s tests -p 'test_nt1_altbot_*.py' -v`, covering the inherited PR #9 source-contract tests, the backup verifier's synthetic valid/missing/corrupt cases, and new recovery-risk read-only checks.

**Python test success is not C++ compilation or in-game validation.** No actual database dump has been audited, no database has been restored, no SQL migrations have been applied, and no character's talents, spells, equipment or inventory have been changed.

The existing normal NT1 Apply path remains experimental and should **not** be used to repair the illegal Priest Alt Bot builds. A separate confirmed reset-and-rebuild operation with proven recovery would be a future, separately reviewed default-off PR.
