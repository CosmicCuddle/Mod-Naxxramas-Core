# Quest loot: three choices (not a decision)

For the server owner. A human friend can click a quest item and take the only copy, because the corpse shows it as available. Nothing here is switched on. No items or server files change.

Today many quest drops are **one shared copy**, and the group has a rotating **turn**. The current protection refuses another player's click only while the turn holder still needs that quest item. A manual click and autoloot are the same click. Gold and dice rolls are separate. The last line is for review. **It is not chosen.**

## A — Keep one copy

Only the player the item is for, or the current turn holder, may take a one-copy quest item. Other people can still open the corpse. Their click on that one slot is refused. The item stays one item.

**Does the friend still take it?** On the friend's own turn, yes. The turn holder is allowed, so they can still pick up the only copy when the turn reaches them. Off their turn, if the item is for you, their click can be refused. After the turn is cleared, someone who is neither the turn holder nor the person the item is for is no longer waved through.

**Vanilla and the economy.** The number of items stays the same as the original game.

**Ordinary quest drops.** Some quests collect items that drop as normal treasure, not as quest-only drops. This option covers the one-copy quest item. It does not automatically cover those normal drops. Whether it should is unresolved.

**Items everyone is already meant to receive.** Free-for-all and multi-drop items already give each eligible player their own copy. This option leaves those alone.

**Who may receive it.** The friend still has to be on the quest. This does not give the item to someone who does not need it.

**Gold and dice.** Gold still splits as it does now. A rolled item, or one assigned by master loot, is not decided by this click. Refusing one slot does not hide coins or the rest of the window.

**How.** The module already checks a human click before it is accepted. It can refuse that single slot and does not rewrite the shared item. Refusing more cases is a policy in that existing check. There is no switch inside the function that places the item in the bag. Bots, rolls, and master loot do not use this click check.

**Proven in the source.** A human click can be refused one slot at a time, and the window stays up. The friend succeeds today where that check deliberately says yes. **Unresolved:** who "the player the item is for" is when two people have the quest.

## B — A real personal copy

Every member who still needs the quest gets their own copy. The friend's copy is not yours.

**Does the friend still take it?** They take their own. Yours remains.

**Vanilla and the economy.** This creates more items than the original game. One drop becomes one item per eligible player.

**Ordinary quest drops.** Include them, and collection quests finish faster than on an original server. Leave them shared, and the friend can still take that single normal item. How far this extends is unresolved.

**Items everyone is already meant to receive.** Free-for-all and multi-drop items are already one per player. This option should not mint a second copy of those.

**Who may receive it.** Only people who still need the quest.

**Gold and dice.** Coins stay shared. Rolled items stay on the roll.

**How.** No existing check can create that second copy without changing the shared drop. The click check can only refuse a click. The loot-generation points that could mark a drop as one-per-player would edit the shared drop, which this note does not allow.

**Proven in the source.** A one-copy quest line is counted once. A multi-drop line is counted per player. **Unresolved:** whether the extra items are wanted. Not tried on a running server.

## C — Name one owner

The one copy is reserved for a named player, such as the person who still has the quest, rather than for whoever's turn it is. The friend cannot take it while that person still needs it, including on the friend's turn.

**Does the friend still take it?** Not while the named owner still needs it and the friend uses a normal click or autoloot. If that owner finishes the quest, goes offline, or leaves, the fallback is not decided.

**Vanilla and the economy.** Still one item. The original game gives the turn to the rotating looter. This option gives the item to a named person. That is a rules change, not extra loot.

**Ordinary quest drops.** Same open question as A. Normal collection drops stay on today's rules unless you later include them.

**Items everyone is already meant to receive.** Free-for-all and multi-drop items stay as they are. Naming one owner there would take copies away from other people.

**Who may receive it.** The named owner should be someone who still needs the item. A friend who is not on the quest already cannot take a true quest-only row.

**Gold and dice.** Unchanged. Rolls and master loot still bypass the click.

**How.** The same human click check can refuse the friend's slot and does not rewrite the shared item, once a rule says who the name is. The game stores whose turn it is. It does not store a quest-item owner. Bots, rolls, and master loot stay outside the check.

**Proven in the source.** The turn is not a named quest owner. If the click is allowed, the item goes into that player's bags. **Unresolved:** how the name is chosen, and what happens when that player no longer needs the item.

## Note for CS03 to review — not chosen

If the owner wants the friend's human click stopped without creating extra items, A or C can use the existing single-slot click check, and B cannot, because a personal copy changes the shared drop.
