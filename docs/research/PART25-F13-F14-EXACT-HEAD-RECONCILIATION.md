# CS01 Part25 F14-on-F13 clean-source reconciliation — review ONLY

**Status:** isolated DRAFT integration *candidate*, no merge, no enable, no install. This is **not** a new implementation or evidence that the owner’s Worldserver runs any of these features.

## Exact lineage

- Base: individually verified F13 Atiesh draft [#127](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/127) at `31f312b5fe1678ea7aaf3fa935b9b00802a320c1`. Its own [16/16 hosted workflows](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/actions/runs/40204660757) include a pinned **full linked** Worldserver.
- Feature transfer: existing older-stacked F14 who-listing draft [#145](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/145) `e07a1e18f7525f8b2c0d1bb6215e31c985717540`. Its standalone 16/16 hosted workflows passed, but on an *older* parent F13 ancestry.
- Ten F14 feature-only files copied **without byte changes**. Shared `src/NaxxramasCore_loader.cpp` differs from exact F13 only by the two F14 `AddWhoListingScripts` declaration/call lines, matching existing reviewed F14 blob **exactly**. Shared `conf/mod_naxxramas_core.conf.dist` is exact F13 original prefix plus the 946-byte reviewed F14 appended configuration, matching existing reviewed F14 blob **exactly**.
- Original F13 implementation, policy, IP-header fallback and operator doc retained **byte-for-byte**.
- `tests/test_f13_f14_exact_lineage.py` independently asserts Git blob SHA1 for all twelve exact reviewed F14 files and four critical newer F13 files, exact registration once each and default-off config lines. This is source integrity, not semantic proof of normal who lists or correct portals.

## Strict limits and next gates

- Run F14 native WHO packet serialization/source/handler-fingerprint CI **at this exact new head**; run F13 native policy and pinned full Worldserver link where path triggers require it. A **new combined exact-head** full build must be verified; inherited individual 16/16 jobs **do not** automatically prove this joint candidate.
- Keep the two paths and all options disabled by default. In the later *five-fix* assembly, still preserve distinct GFPP 120s, Hunter A02, human-human quest loot, physical Scarlet entry/exit, Atiesh outside Karazhan, Golemagg registration and no change to `MapUpdate.Threads=8`.
- This draft contains F13 + F14 **only**. It does **not** integrate F12, #120, Hunter A02, loot A04 or true F15 crash AND error reporting. Do not present it as that combined build. It intentionally does not touch current #127 or #145 reviewed branches.
- No host discovery, real server process, root/service, core, DB, SQL, DBC, IP, Playerbots, N-Core, config editing, release or deployment. Later staging requires explicit owner approval and restorable backups/rollback.
- Independent Claude/CS03 peer review required for clean ancestry, F13 configuration/event timing, F14 stock packet parity, IP header/no-header fallback and all native/hosted evidence before considering integration.

**Coordination:** master issue #28, CS01/CS02 #48, Claude continuous queue #143.