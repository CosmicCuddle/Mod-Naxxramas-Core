"""A04 research: group loot turns, release and the module's quest-loot guard.

Research only, like a04_roll_model.py. Copies the decisions that decide
who may take a one-copy quest drop from a group kill at core 8daffda, plus
the module's existing QuestLootProtection guard on main (blob 48729dc):

  Entities/Unit/Unit.cpp            L13654-L13701  kill: keep or advance the looter
  Groups/Group.cpp                  Group::UpdateLooterGuid L2081-L2140
  Loot/LootMgr.cpp                  Loot::FillLoot L569 roundRobinPlayer = loot owner
                                    Loot::hasItemFor L907 (quest slot left for viewer)
  Entities/Player/PlayerStorage.cpp Player::isAllowedToLoot L5746 (corpse sparkle)
  Handlers/LootHandler.cpp          WorldSession::DoLootRelease L459-L461 (turn ends)
  src/Systems/QuestLootProtection.cpp  PermitPickup (module, main)

Group loot without rolls (items under threshold) and a one-copy quest-bucket
drop (QuestRequired=1, no MULTI_DROP, no flag 0x4) only.
"""
from dataclasses import dataclass, field

from a04_roll_model import store_loot_item


@dataclass
class GroupTurns:
    """Group::UpdateLooterGuid for a group whose members are all in range."""
    order: list                       # member slot order (guids)
    looter: str = ""

    def on_kill(self):
        # Unit.cpp L13654: UpdateLooterGuid(creature, true) keeps an
        # in-range looter; with no looter yet it picks the first member.
        if not self.looter:
            self.looter = self.order[0]
        owner = self.looter
        # L13701: after the loot is filled the turn advances for next kill.
        i = self.order.index(self.looter)
        self.looter = self.order[(i + 1) % len(self.order)]
        return owner


@dataclass
class Corpse:
    item: object                      # LootItem, one-copy quest bucket
    round_robin_player: str           # Loot::FillLoot L569
    slots: dict = field(default_factory=dict)  # guid -> has a quest slot (FillQuestLoot)

    def open_for(self, player):
        # FillNotNormalLootFor -> FillQuestLoot: a slot only if allowed now.
        if player.guid not in self.slots:
            self.slots[player.guid] = self.item.allowed_for_player(player)

    def has_item_for(self, player):
        # Loot::hasItemFor L907: an unlooted quest slot for this viewer.
        return (self.slots.get(player.guid, False) and
                not self.item.is_looted and
                not self.item.quest_slot_looted.get(player.guid))

    def sparkles_for(self, player):
        # Player::isAllowedToLoot L5746, GROUP_LOOT, nothing over threshold.
        if not self.round_robin_player or self.round_robin_player == player.guid:
            return True
        return self.has_item_for(player)

    def release(self, player):
        # DoLootRelease L459-L461: the turn owner closing the window ends
        # the turn; the corpse stays lootable while items remain.
        if player.guid == self.round_robin_player:
            self.round_robin_player = ""


def module_permits(enabled, looter, corpse, owner):
    """QuestLootProtection::PermitPickup on main, quest-slot path only.

    Same-group, same-map and same-instance checks are assumed true in these
    fixtures; the module fails open whenever any of them is false.
    """
    if not enabled:
        return True
    if not corpse.round_robin_player or corpse.round_robin_player == looter.guid:
        return True
    item = corpse.item
    if (not item.needs_quest or item.count != 1 or item.is_looted or
            item.template.follow_loot_rules or item.is_blocked or item.roll_winner):
        return True
    if not corpse.slots.get(owner.guid) or item.quest_slot_looted.get(owner.guid):
        return True
    if not owner.has_quest_for_item(item.template.entry) or not item.allowed_for_player(owner):
        return True
    return False                      # LOOT_ERROR_LOCKED


def try_pickup(enabled, looter, corpse, owner):
    """CMSG_AUTOSTORE_LOOT_ITEM: module hook first, then StoreLootItem."""
    corpse.open_for(looter)
    if not corpse.slots.get(looter.guid):
        return "no slot"
    if not module_permits(enabled, looter, corpse, owner):
        return "denied by module"
    return "stored" if store_loot_item(looter, corpse.item, via_quest_slot=True) else "refused by core"
