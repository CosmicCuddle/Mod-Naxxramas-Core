# Custom Modifications Register

This register tracks CosmicCuddle-specific behavior in this repository. A register entry does not imply merge, deployment, or live activation.

## MAIL-01 — Same-account mail delay only for item attachments

- **Intended behavior:** Preserve the configured same-account alt-mail delivery delay only when the mail contains one or more item attachments. Gold-only, text-only, and text+gold mail remain instant. Existing returned-mail, COD-payment, GM/support, invalid/self and non-same-account exclusions remain unchanged.
- **Owning component:** Mod-Naxxramas-Core mail hook, with a minimal AzerothCore MailDraft read-only API dependency.
- **Affected files:** `src/Systems/AltMailDelay.cpp`; tests/workflows on the development branch.
- **Source refs:** Naxx base `80e9de1c39a6dc995188a80c31a5e785d0f2a6f9`; development PR #337. Companion Core DRAFT #34 head `f97fef89ff07f29ecea563edbc729706badcf6ff`.
- **Config/SQL/DBC/client dependencies:** Existing Core `MailDeliveryDelay`; no new config, SQL, DBC or client patch.
- **Known risks:** Requires Core `MailDraft::HasItems()`; a mismatched Core/module deployment will not compile. Must verify item+gold/COD/returned/system mail behavior in-game before release.
- **Tests:** Source contract 6/6 PASS on Ubuntu 24.04. Pinned combined Worldserver link is a required release gate and may still be running. In-game mail matrix remains required.
- **Live status:** NOT merged or deployed. Live server remains on Naxx main.
- **Owner decisions:** CosmicCuddle requested delay only when items are sent; gold-only and note-only mail must be instant.
- **Rollback:** Revert the Naxx mail PR and companion Core accessor PR together; no data migration is involved.
