# Mail sender-route composition milestone

For CosmicCuddle's attachment-only same-account mail delay. Test-only child of
PR348 8812de18813e845a39d9574c46c240fa6a0dad2a, preserving Naxx337's established
production correction. Core dependency remains PR34
9edf437e62218be610dfc4b3d797563217644ad1. No new production change is needed.

## Actual-source route now executed

Compile the complete unchanged Core34 `Mail.h`, `CanOpenMailBox`,
`WorldSession::HandleSendMail`, `MailSender(Player*)`, `MailDraft::AddItem`,
`SendMailTo` and `deleteIncludedItems` together with the existing Naxx hook.
The handler performs its real admission branches, item-map population,
money/COD assignment, native cross-account delay choice, send call and transaction
commit call. The fixture's script bridge observes populated draft state at the
actual send-path callback and invokes the Naxx implementation.

Real integration names remain `AddAltMailDelayScripts` called by
`src/NaxxramasCore_loader.cpp`, registration of
`MAILHOOK_ON_BEFORE_MAIL_DRAFT_SEND_MAIL_TO`, and Core ScriptMgr's
`OnBeforeMailDraftSendMailTo`. Registry/module-loader execution is still a seam.

The new fixture passes 797 cases / 7376 assertions locally under Clang20.1.2
through Zig0.15.2, C++17 with warnings as errors. It covers online/offline,
native versus custom delay, receiver/cache identity absence, 0/1/3/12 items,
money/body combinations, delay zero, COD removal without attachments, GM sender,
postage and captured queue fields. Twenty-three rejection cases preserve funds,
inventory and queue: mailbox/type/permission, trial/level/receiver/self, money+COD,
postage overflow, funds/cap/faction, invalid/missing/bag/bound/conjured/temporary/
wrapped items and script veto. Positive self-mailbox, NPC-mailbox and cross-faction
permission routes remain accepted. Parent real-header24 and send/return59 fixtures
remain reused in the focused GCC/Clang workflow.

## Evidence limits and release gates

Packet extraction uses typed synthetic fields, not native bytes/opcodes/network
parsing. Inventory/item persistence, permissions, player/cache/account lookup,
clock, script registry and database are explicit doubles. Actual handler branches
execute, but this does not establish real RBAC/security, database durability or
rollback, actual item serialization, ScriptMgr/module ABI or full Worldserver
link/startup. No client, owner account, mail history or live files are used.

This extends the earlier 22 Nov source candidate evidence; its native full-link,
required custom module/DBC compatibility, disposable-DB and owner client acceptance
gates remain open. COD payment/return/system exclusions are also exercised by the
existing send/return suite; actual purchase/settlement/AH handlers remain separate
runtime acceptance. Template generation remains deliberately outside this fixture.

## Register delta and rollback

Feature: existing same-account attachment-only mail delay. Owner: CosmicCuddle.
Affected additions: handler runner, explicit doubles/check matrix, focused
workflow and this record. Dependency: exact Core34 + Naxx337/348 lineage. Test
code only; no config/default/schema/SQL/DBC/client or mail queue migration.
Risks are overinterpreting synthetic permission/DB seams as installed behavior.
Live status: unchanged/uninstalled candidate. Rollback removes this test child;
preserve Core/Naxx source dependencies, queued mail rows and item ownership.
The prior release-candidate acceptance and binary/config backup plan still apply.
