"""A04 research: a small transcription of native group-roll loot at core 8daffda.

Research only. This is NOT module code, NOT a loot policy and NOT a fix.
It copies, in Python, just the decisions the pinned Grimfeather AzerothCore
source makes when a group rolls on one loot slot and when a player picks a
slot up, so tests can show what the stock code does when eligibility
changes while a roll is pending.

Pinned source (core 8daffdabe9202c228e45d833c9a1d399597a15cd):
  Groups/Group.cpp
    CanRollOnItem                     L1106-L1121  roll admission
    Group::GroupLoot                  L1123-L1286  which slots roll, auto-pass
    Group::SendLootStartRoll          L928-L950    roll window only to NOT_EMITED_YET
    Group::CountRollVote              L1497-L1546  vote counting
    Group::CountTheRoll               L1604-L1826  award (Need, then Greed)
    SendRollWonItemViaMail            L67          mail award on full bags
  Entities/Player/Player.cpp
    Player::StoreLootItem             L13861-L13962 direct pickup gates
  Entities/Player/PlayerQuest.cpp
    Player::HasQuestForItem           L2338-L2385  quest still needs the item
  Loot/LootMgr.cpp
    LootItem::AllowedForPlayer        L417-L470    eligibility
    Loot::LootItemInSlot              L821-L880    quest-slot lookup
    LootView (roll winner / quest)    L1033-L1037, L1130-L1149  visibility

scripts/check_a04_roll_fingerprint.py hashes those functions so a core pin
change forces this transcription to be re-reviewed.

Simplifications, all stated: one loot source, one slot per roll, no
conditions/faction/recipe/disable rules (they are fixed during a roll), no
achievements or packets, and roll numbers are injected instead of urand.
"""
from dataclasses import dataclass, field

# RollVote values (Group.h). Only identity matters here.
PASS, NEED, GREED, DISENCHANT, NOT_EMITED_YET, NOT_VALID = (
    "PASS", "NEED", "GREED", "DISENCHANT", "NOT_EMITED_YET", "NOT_VALID")

# InventoryResult values used by CountTheRoll / StoreLootItem.
EQUIP_ERR_OK = "OK"
EQUIP_ERR_INVENTORY_FULL = "INVENTORY_FULL"
EQUIP_ERR_CANT_CARRY_MORE_OF_THIS = "CANT_CARRY_MORE_OF_THIS"

# LFG.MailItemOnFullInventory (WorldConfig.cpp L523, default 0).
MAIL_DISABLED, MAIL_LFG_ONLY, MAIL_EVERYWHERE = 0, 1, 2

# LootView slot types sent to a viewer (only the ones the tests use).
SLOT_ALLOW_LOOT, SLOT_ROLL_ONGOING, SLOT_OWNER, SLOT_HIDDEN = (
    "ALLOW_LOOT", "ROLL_ONGOING", "OWNER", "HIDDEN")


@dataclass(frozen=True)
class ItemTemplate:
    entry: int
    max_count: int = 0                 # item_template.maxcount, 0 = unlimited
    follow_loot_rules: bool = False    # flagsCustom 0x4 (ITEM_FLAGS_CU_FOLLOW_LOOT_RULES)
    ignore_quest_status: bool = False  # flagsCustom 0x2 (ITEM_FLAGS_CU_IGNORE_QUEST_STATUS)


QUEST_STATUS_INCOMPLETE, QUEST_STATUS_COMPLETE = "INCOMPLETE", "COMPLETE"


@dataclass
class Quest:
    """One quest-log entry with deliver objectives (QUEST_SPECIAL_FLAGS_DELIVER).

    `counts` is QuestStatusData.ItemCount, kept separately from inventory,
    exactly as core does: it only moves through AdjustQuestReqItemCount
    (accept), ItemAddedQuestCheck and ItemRemovedQuestCheck.
    """
    required: dict                      # RequiredItemId -> RequiredItemCount
    counts: dict = field(default_factory=dict)
    status: str = QUEST_STATUS_INCOMPLETE

    def all_objectives_met(self):
        return all(self.counts.get(i, 0) >= n for i, n in self.required.items())

    @property
    def incomplete(self):
        return self.status == QUEST_STATUS_INCOMPLETE

    @incomplete.setter
    def incomplete(self, value):
        # Fixtures use this to mark a quest finished (completed or turned in).
        self.status = QUEST_STATUS_INCOMPLETE if value else QUEST_STATUS_COMPLETE


def QuestObjective(item, required):
    """A single-objective deliver quest (the common fixture)."""
    return Quest({item: required})


@dataclass
class Player:
    guid: str
    bag_slots_free: int = 16
    inventory: dict = field(default_factory=dict)
    quests: list = field(default_factory=list)
    mailbox: list = field(default_factory=list)

    def __post_init__(self):
        for q in self.quests:
            self.adjust_quest_req_item_count(q)

    def item_count(self, entry):
        return self.inventory.get(entry, 0)

    def adjust_quest_req_item_count(self, quest):
        # PlayerQuest.cpp L1838-L1855 (on accept): counter = min(held, required).
        for item, needed in quest.required.items():
            quest.counts[item] = min(self.item_count(item), needed)
        if quest.incomplete and quest.all_objectives_met():
            quest.status = QUEST_STATUS_COMPLETE

    def accept_quest(self, quest):
        self.quests.append(quest)
        self.adjust_quest_req_item_count(quest)

    def load_quest(self, quest):
        # Player::_LoadQuestStatus (PlayerStorage.cpp ~L6453): the counter
        # is read from character_queststatus as stored, with NO re-adjust to
        # current inventory (AdjustQuestReqItemCount runs only in AddQuest,
        # PlayerQuest.cpp L552). After login the two can differ.
        self.quests.append(quest)

    def has_quest_for_item(self, entry):
        # PlayerQuest.cpp L2338-L2385, as called by AllowedForPlayer (no
        # showInLoot, no turnIn): an INCOMPLETE quest whose objective
        # COUNTER (QuestStatusData.ItemCount), not inventory, is below the
        # required count.
        for q in self.quests:
            if (q.incomplete and entry in q.required and
                    q.counts.get(entry, 0) < q.required[entry]):
                return True
        return False

    def can_store_new_item(self, template, count):
        # Only the two results CountTheRoll distinguishes.
        if template.max_count and self.item_count(template.entry) + count > template.max_count:
            return EQUIP_ERR_CANT_CARRY_MORE_OF_THIS
        if self.bag_slots_free <= 0:
            return EQUIP_ERR_INVENTORY_FULL
        return EQUIP_ERR_OK

    def store_new_item(self, entry, count):
        self.inventory[entry] = self.item_count(entry) + count
        self.bag_slots_free -= 1
        # ItemAddedQuestCheck L1909-L1946: only INCOMPLETE quests count up,
        # capped at the required count; complete when every objective is met.
        for q in self.quests:
            if not q.incomplete or entry not in q.required:
                continue
            if q.counts.get(entry, 0) < q.required[entry]:
                q.counts[entry] = min(q.counts.get(entry, 0) + count, q.required[entry])
            if q.all_objectives_met():
                q.status = QUEST_STATUS_COMPLETE

    def remove_item(self, entry, count):
        # ItemRemovedQuestCheck L1948-L1985, called before the item leaves:
        # a met counter is re-read from inventory, reduced, capped, and the
        # quest becomes INCOMPLETE again.
        for q in self.quests:
            if entry not in q.required:
                continue
            needed = q.required[entry]
            current = q.counts.get(entry, 0)
            if current >= needed:
                current = self.item_count(entry)
            new = 0 if count > current else current - count
            new = min(new, needed)
            if new != q.counts.get(entry, 0):
                q.counts[entry] = new
                q.status = QUEST_STATUS_INCOMPLETE
        self.inventory[entry] = max(0, self.item_count(entry) - count)
        self.bag_slots_free += 1


@dataclass
class LootItem:
    template: ItemTemplate
    needs_quest: bool                  # loot row QuestRequired=1 -> quest_items bucket
    count: int = 1
    is_blocked: bool = False
    is_looted: bool = False
    roll_winner: str = ""
    quest_slot_looted: dict = field(default_factory=dict)  # QuestItem::is_looted per player

    def allowed_for_player(self, player):
        # LootMgr.cpp L417-L470, quest part only (other rules cannot change
        # while a roll is pending in these fixtures).
        if not self.template.ignore_quest_status:
            if self.needs_quest and not player.has_quest_for_item(self.template.entry):
                return False
        return True


def can_roll_on_item(item, player):
    # Group.cpp L1106-L1121.
    t = item.template
    if t.max_count > 0 and player.item_count(t.entry) >= t.max_count:
        return False
    return item.allowed_for_player(player)


def slot_rolls(item, over_threshold=True):
    # Group::GroupLoot L1129-L1218 (items bucket rolls when over threshold)
    # and L1220-L1224 (quest bucket rolls ONLY with follow_loot_rules).
    if item.needs_quest:
        return item.template.follow_loot_rules
    return over_threshold


@dataclass
class Roll:
    item: LootItem
    votes: dict = field(default_factory=dict)
    total_need: int = 0
    total_greed: int = 0
    total_pass: int = 0
    total_rolling: int = 0
    finished: bool = False


class Group:
    def __init__(self, members, mail_on_full=MAIL_DISABLED, lfg=False):
        self.members = {p.guid: p for p in members}
        self.mail_on_full = mail_on_full
        self.lfg = lfg
        self.start_roll_sent = []          # (guid, roll) pairs for SendLootStartRoll

    def start_roll(self, item, near=None):
        """GroupLoot for one rolled slot: admission and auto-pass."""
        roll = Roll(item)
        for guid, member in self.members.items():
            if near is not None and guid not in near:
                continue
            roll.total_rolling += 1
            vote = NOT_EMITED_YET
            if not can_roll_on_item(item, member):
                vote = PASS
                roll.total_pass += 1
            roll.votes[guid] = vote
        item.is_blocked = True             # L1179 / L1266
        # SendLootStartRoll L941-L949: only voters still NOT_EMITED_YET.
        for guid, vote in roll.votes.items():
            if vote == NOT_EMITED_YET:
                self.start_roll_sent.append((guid, roll))
        return roll

    def count_roll_vote(self, roll, guid, choice, rolls=None):
        """CountRollVote L1497-L1546. Note: no check that the previous vote
        was NOT_EMITED_YET; a later packet overwrites an auto-pass."""
        if roll.finished:                  # CountTheRoll erased it from RollId
            return False
        if guid not in roll.votes:
            return False
        if choice == PASS:
            roll.total_pass += 1
        elif choice == NEED:
            roll.total_need += 1
        elif choice in (GREED, DISENCHANT):
            roll.total_greed += 1
        roll.votes[guid] = choice
        if roll.total_pass + roll.total_need + roll.total_greed >= roll.total_rolling:
            self.count_the_roll(roll, rolls or {})
            return True
        return False

    def count_the_roll(self, roll, rolls):
        """CountTheRoll L1604-L1826. `rolls` maps guid -> injected urand(1,100)."""
        item = roll.item
        t = item.template
        for bucket, total_attr in ((NEED, "total_need"), (GREED, "total_greed")):
            if getattr(roll, total_attr) <= 0:
                continue
            if bucket == GREED and roll.total_need > 0:
                break
            voters = [g for g, v in roll.votes.items()
                      if (v == NEED if bucket == NEED else v in (GREED, DISENCHANT))]
            best, best_n = None, 0
            for g in voters:
                n = rolls.get(g, 1)
                if best_n < n:
                    best, best_n = g, n
            if best is None:
                setattr(roll, total_attr, 0)
                continue
            winner = self.members[best]
            if roll.votes[best] == DISENCHANT:
                # L1772-L1803: the slot is consumed; the winner gets
                # disenchant materials, not this item.
                item.is_looted = True
                roll.finished = True
                return
            # No AllowedForPlayer here (L1655-L1689, L1739-L1771).
            msg = winner.can_store_new_item(t, item.count)
            if msg == EQUIP_ERR_OK:
                item.is_looted = True
                winner.store_new_item(t.entry, item.count)      # L1662 / L1746
            elif msg == EQUIP_ERR_INVENTORY_FULL and (
                    self.mail_on_full == MAIL_EVERYWHERE or
                    (self.mail_on_full == MAIL_LFG_ONLY and self.lfg)):
                item.is_looted = True
                winner.mailbox.append(t.entry)                  # L1678 / L1762
            else:
                item.is_blocked = False                         # L1682 / L1766
                item.roll_winner = winner.guid                  # L1683 / L1767
            roll.finished = True
            return
        # All passed (L1810-L1816): unblock so anyone allowed can loot.
        item.is_blocked = False
        roll.finished = True


def store_loot_item(player, item, via_quest_slot):
    """Player::StoreLootItem L13861-L13962. Returns True when stored.

    via_quest_slot is True when LootItemInSlot resolves a per-player
    QuestItem (quest bucket), which skips the is_blocked check (L13897).
    """
    if item.is_looted:                                          # L13870
        return False
    if via_quest_slot and item.quest_slot_looted.get(player.guid):
        return False                                            # LootItemInSlot L878
    if not item.allowed_for_player(player):                     # L13889
        return False
    if not via_quest_slot and item.is_blocked:                  # L13895
        return False
    if item.roll_winner and item.roll_winner != player.guid:    # L13902
        return False
    if player.can_store_new_item(item.template, item.count) != EQUIP_ERR_OK:
        return False
    player.store_new_item(item.template.entry, item.count)
    if via_quest_slot:
        item.quest_slot_looted[player.guid] = True
    item.is_looted = True                                       # L13942 (not freeforall)
    return True


def loot_view_slot(viewer, item, via_quest_slot):
    """What a viewer's loot window shows for this slot (LootMgr.cpp)."""
    if item.is_looted and not via_quest_slot:
        return SLOT_HIDDEN
    if via_quest_slot:
        if not viewer.has_quest_for_item(item.template.entry):
            return SLOT_HIDDEN
        if item.template.follow_loot_rules:                     # L1130-L1149, group permission
            return SLOT_ROLL_ONGOING if item.is_blocked else SLOT_ALLOW_LOOT
        return SLOT_ALLOW_LOOT
    if item.roll_winner:                                        # L1033-L1037
        return SLOT_OWNER if item.roll_winner == viewer.guid else SLOT_HIDDEN
    return SLOT_ROLL_ONGOING if item.is_blocked else SLOT_ALLOW_LOOT
