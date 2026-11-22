# Attachment-only mail delay composition

Owner: CosmicCuddle. Source-test child of Naxx draft337 c5e97acde24da8944df152749a214c20f1b4f4c4.
Core draft34 accessor pinned at9edf437e62218be610dfc4b3d797563217644ad1.

The runner extracts the real MailDraft::HasItems body from the pinned Core header
and compiles the complete existing AltMailDelay module source with explicit engine
doubles. Includes are removed and override keywords suppressed: this is executable
hook logic evidence, not native engine ABI/build proof. Fixture attachment storage,
cache/world, sender/receiver and registration are doubles. Gold/body independence
is checked as empty-draft hook cases, not actual MailHandler serialization.

Matrix covers empty attachment drafts, one/two/twelve items, null draft, returned,
COD-payment/combined flags, system type, GM stationery, self/invalid GUIDs, missing
account identities, cross-account mail, existing nonzero delay preservation and
configured zero delay. Ordinary item+COD request remains in the normal attachment
path; COD-payment notification is excluded. Full Core send/return/COD/AH lifecycle
and actual attachment persistence/gameplay still require native integration tests.

No production logic, delay configuration, SQL/data or live state is changed.
Run tests/run_mail_composition.py --core PATH --compiler CXX. Zig driver is supported.
Exact execution outcomes are recorded in draft PR/review queue. Existing source
contract suite passes6/6 locally. Existing pinned full-Worldserver workflow is
preserved; no expensive full build was requested by this test increment.
Rollback: abandon/revert test-only child; preserve existing Core/Naxx drafts.
