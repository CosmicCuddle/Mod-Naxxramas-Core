# A04 — pinned Playerbots normal loot packet and core hook safety contract

**19 October 2026 · research draft · no game mutation or deployment.**

Existing [Quest Loot PR #25](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/25) adds an OFF-by-default \`CMSG_AUTOSTORE_LOOT_ITEM\` pre-dispatch receive script. This isolated stacked draft checks whether the exact pinned **normal Playerbots loot action** still reaches that native receive hook, instead of assuming all bot loot automatically passes through it.

## Explicit verified source chain to test

1. Pinned \`mod-playerbots/mod-playerbots@037c01418b5d01506917a3db9b44fd56ac5f965c\`: \`StoreLootAction::Execute\` builds an autostore packet, writes the viewer's item slot, and enqueues it with \`bot->GetSession()->QueuePacket(packet)\`. An obsolete direct handler call is commented out and must not count as an active bypass.
2. Pinned \`Grimfeather/azerothcore-wotlk@a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7\`: \`WorldSession::QueuePacket\` adds packets to \`_recvQueue\`. In the logged-in/in-world branch, \`CanPacketReceive\` must veto **before** normal opcode handler dispatch.
3. The same core \`Opcodes.cpp\` maps \`CMSG_AUTOSTORE_LOOT_ITEM\` to \`STATUS_LOGGEDIN\` / \`HandleAutostoreLootItemOpcode\`.
4. Current module \`QuestLootProtection.cpp\`: the receive script still uses the correct opcode, copies the packet cursor, checks \`PermitPickup\` and issues a native locked-loot error before returning false.

The GitHub job uses sparse checkouts with exact SHA checks. Eight synthetic tests intentionally break the packet queue, client item index, queue order, receive-hook order, opcode dispatch, and module hook to demonstrate fail-closed behavior. It then checks the **real pinned** source files with the identical verifier. No Worldserver compilation, SQL query, gameplay, item awards or owner live machine involved.

## Deliberate limitations

This only proves the **ordinary Playerbots StoreLootAction** route in those exact revisions. It does **not** inspect every encounter-specific bot looter, arbitrary direct \`StoreLootItem\` callers, runtime module script registration, versions actually installed on the owner's server, real human/bot inventories or the actual in-game loot turn.

All QL-01 to QL-15 staged human/Altbot owner, entitlement, release, group-loot and round-robin cases remain **unexecuted**. Do not enable, merge, install or restart from this CI proof. First obtain owner permission, verify matching installed source and a restorable character/Worldserver backup, and test in a controlled environment.

[Initial pinned source review](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/pull/25#issuecomment-6271531047) · [Authoritative master checklist](https://github.com/CosmicCuddle/Mod-Naxxramas-Core/issues/28).
