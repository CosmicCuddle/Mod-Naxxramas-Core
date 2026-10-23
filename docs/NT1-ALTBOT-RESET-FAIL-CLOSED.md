# NT1 Altbot Apply: interim fail-closed protection

**DRAFT / not merged, deployed or runtime-tested.** Tracked in issue #17 and master #28.
Based on current main at \`80e9de1\`, not the diverged old PR #18.

Main's existing offhand/pet checks protect against two known reset hazards,
but a controlled Altbot with neither could still reach \`resetTalents(true)\`.
This cannot guarantee the owner's requirement that NT1 never moves, deletes,
mails or replaces an Altbot's earned equipment. Native reset hooks and a
partially failed multi-rank \`LearnTalent\` are not transactional.

This isolated proposal adds a second guard in \`ApplyValidated\` after shared
readiness checks and before \`ImportScope\`, talent reset, learning, profile or
character DB writes. It returns an explicit refusal for ALL Altbots (even
ones without an offhand/pet); Random Bot Apply is unchanged. It does NOT
backport the historical PR #18 exact-build NO-OP, so even an already matching
Altbot build cannot use Apply under this interim policy. Preview remains
available under its existing permission rules.

The new test checks production source ordering and compiles the actual
extracted guard with mutation-counting stand-ins. This is **not** a real
Worldserver/character/item test. No configuration keys, SQL/DBC changes or
upstream edits. The trade-off is significant: this draft temporarily
disables formerly permitted changed-build Altbot imports. It must undergo
independent reviews and separate owner approval before any merge or install.

Follow-on research: port an independently checked exact-match no-op to a
fresh current-main branch, then design transactional/rollback-safe
changed-build support. If zero equipment changes cannot be proven, retain
the refusal rather than using offhand/gear relocation or unverified SQL.
