# Attachment-only mail source integration candidate

Owner: CosmicCuddle. Proposed source candidate only; no release or deployment.

## Dependency matrix

| Component | Exact source |
| --- | --- |
| Core draft34 | 9edf437e62218be610dfc4b3d797563217644ad1 |
| Naxx draft337 | c5e97acde24da8944df152749a214c20f1b4f4c4 |
| Hook test parent draft348 | f10ff7d830d1e75d521233728b4f1f4d5e2c5101 |
| Historical module baseline | 80e9de1c39a6dc995188a80c31a5e785d0f2a6f9 |

## Real route and failure model

WorldSession::HandleSendMail moves valid items from inventory and calls
MailDraft::AddItem before AddMoney/AddCOD/SendMailTo. Its native cross-account item
delay remains separate. MailDraft::SendMailTo calls ScriptMgr's
OnBeforeMailDraftSendMailTo before computing deliver_time or appending CHAR_INS_MAIL
and CHAR_INS_MAIL_ITEM. NaxxramasCoreAltMailDelay registers
MAILHOOK_ON_BEFORE_MAIL_DRAFT_SEND_MAIL_TO and consults the populated draft.
Core draft34 exposes m_items.empty through a const accessor; it does not itself
alter delay or SQL. The module only restores configured delay for same-account
normal non-GM mail with real attachments, excluding returned/COD-payment flags.

The historical module did not inspect attachments: the same-account customization
could delay pure gold/text. The executable matrix using that actual historical
module fails delivery-field assertions, while draft337 passes the same assertions.
No new production correction is needed; the existing drafts implement this rule.

SendReturnToSender passes RETURNED and zero delay; real return source is exercised.
COD-payment notification uses COD_PAYMENT and no new custom delay. Actual COD
purchase/settlement handler validation remains outside the executable adapter.
Auction/system sender types are excluded. Mail-template generation occurs AFTER
the hook; the adapter deliberately rejects template generation rather than claiming
it is tested. Do not broaden this custom player-mail rule into template mail.

## Executable evidence and limits

- run_mail_real_header.py:24 PASS using the complete unmodified Core Mail.h,
  actual AddItem definition, actual draft money/body/map and existing Naxx hook.
- run_mail_send_path.py:59 PASS using the complete Core Mail.h and actual
  AddItem, SendMailTo, SendReturnToSender and deleteIncludedItems definitions.
  Covers online/offline handoff, baseline vs custom delay,0/1/2 items, real body
  and money, attachment cleanup/ownership transfer, transaction fields, returned
  mail, COD-payment flags and system sender exclusions.
- --verify-old-baseline-fails: actual historical hook compiles and fails the
  delivery-field matrix as expected; this is not an intentionally broken fixture.
- Existing isolated executable hook20 PASS and source contracts6 PASS remain.

All executable runs use Clang20.1.2/C++17 via workspace Zig0.15.2. Dependency
headers, DB transaction/statement capture, player/session/cache/manager/clock and
registration are explicit doubles; override is suppressed in the module adapter.
No MySQL, actual ScriptMgr ABI/module loading, full HandleSendMail packet/security
validation, template generation, DBC or client gameplay is proven. Transaction
capture proves requested fields/attachments, not durable DB commit or rollback.
No owner database, account mail history or production files were opened.

## Highest native gate and remaining acceptance

The Windows developer environment has no working Linux runtime or demonstrated
full Core dependency/DBC/disposable-DB stack. Standalone actual-source compilation
is the completed gate. Existing full-link workflow is preserved, not reinterpreted
as a run of this new candidate. A native Core34/Naxx tuple full build/link with
required modules, recorded fingerprints, owner-approved isolated startup and
actual mail send/receive/return/COD/AH acceptance remain required before release.

Owner client matrix: gold/text/mixed instant custom path; item1/many/item+gold
retain configured custom delay; normal cross-account native delay; returned mail
instant; COD receipt/settlement unchanged; AH/system/GM unchanged; online recipient
notification/inbox; offline relog; cancel/error transaction rollback; old queued
mail stays unchanged. Verify no lost/duplicate items or altered account ownership.

## Register delta, defaults and rollback

Custom feature: same-account attachment-only delay; component AltMailDelay plus
Core read-only accessor. No new config flag: existing MailDeliveryDelay value
applies only on qualifying attached-item mail. Configuration zero remains zero.
Migration:none. No queue rewrite, SQL/schema/data migration, DBC/client dependency
or removal of existing custom behavior. Tests only are added in this increment.

Source rollback abandons/reverts the test child while preserving Core34/Naxx337.
Future owner-approved production rollback requires backup of exact binaries/modules
and config; restore the prior compatible tuple without deleting/rescheduling mail
rows. Preserve existing mail and item ownership records. No live change is
performed or approved by this document.
