# Hunter Playerbot — Master command ingress and acceptance boundary

**Pinned source research only.** No chat observer or preference writer has been added to Worldserver.

## Proven ingress and deferral sequence

The pinned [Playerbots chat script](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Script/Playerbots.cpp) receives sender `Player*`, type and message through `OnPlayerCanUseChat`; whispers and group/guild routes can call `PlayerbotAI::HandleCommand`. The [AI command processor](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Bot/PlayerbotAI.cpp) can reject commands based on Playerbot security, chat type, configured prefix or filter; many commands are then **queued** in `ChatCommandHolder` before `ExternalEventHelper::ParseChatCommand` dispatches a trigger. Trigger acceptance and subsequent action execution are different steps, neither exposed as a proof by Naxx's chat or pet-packet observer.

An apparent command from a Player* is not necessarily a fresh human decision: other bot actions can call `botAI->HandleCommand` internally, including [CastCustomSpellAction.cpp](https://github.com/mod-playerbots/mod-playerbots/blob/037c01418b5d01506917a3db9b44fd56ac5f965c/src/Ai/Base/Actions/CastCustomSpellAction.cpp) passing the bot itself as the command sender. Observing a real chat message with a plausible spell name is also not proof it was accepted or applied, especially with deferred commands.

## Hypothetical end-to-end proof (not available)

Any future consumer must verify: human-origin sender and current master for the exact bot; Playerbots security acceptance; precise parsed command and later executed AI action; native applied ON/OFF for that same pet instance/ability and no subsequent overwrite; independently verified IP-legal learned rank and post-IP reconciliation; and coordinated Playerbot policy if the chosen state conflicts with its defaults.

The [source guard](../scripts/check_hunter_pet_bot_master_ingress_pinned.py) freezes the observed routing and queued-command contracts against the pinned Playerbots repository. The [offline counterexamples](../tests/test_hunter_pet_autocast_bot_master_ingress_model.py) show why earlier partial observations cannot safely become stored preference evidence. Even synthetic end-to-end success yields only `CANDIDATE_ONLY` for human review, **not a native ToggleAutocast operation or preference storage authorisation**.

## Next integration decision

No public post-Playerbot-command-applied signal has been demonstrated on the existing module-only script surface, and no IP post-reconcile callback or durable pet incarnation guarantee exists. An authoritative bot-master override could require separately approved changes inside Playerbots and a coordinated policy exemption or priority rule. Do not implement a Naxx side re-toggle timer; it could fight AI indefinitely.

**Safety:** source/tests/docs/CI only; no core/IP/Playerbots code changed, no server restart, SQL, manual bot commands, feature enable or release.