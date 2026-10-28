"""A04 Part29: PUBLIC synthetic/enum-only H1 vs H2 incident triage.

No network, filesystem I/O, GitHub data submission, IDs or runtime core APIs.
This is an evidence-gating helper, NOT a gameplay fix or an authority for
claiming a bug, approving a deployment, or activating default-OFF switches.
"""
from dataclasses import dataclass
from typing import Tuple

UNKNOWN = "unknown"
BOOL3 = frozenset(("yes", "no", UNKNOWN))
KIND = frozenset(("H1", "H2"))
BUCKET = frozenset(("quest", "ordinary", UNKNOWN))
SOURCE = frozenset(("creature", "gameobject", "item", UNKNOWN))
METHOD = frozenset(("group", "round_robin", "need_before_greed",
                    "master", "free_for_all", UNKNOWN))
TURN = frozenset(("friend", "reporter", "released", UNKNOWN))
SLOT = frozenset(("allow", "locked", "roll_ongoing", "hidden", UNKNOWN))
NEED = frozenset(("short", "met", UNKNOWN))
GUARD = frozenset(("on", "off", UNKNOWN))


@dataclass(frozen=True)
class Incident:
    """Only generic observations; NEVER put private IDs or logs in this model."""
    kind: str
    source: str = UNKNOWN
    bucket: str = UNKNOWN
    method: str = UNKNOWN
    turn: str = UNKNOWN
    friend_eligible: str = UNKNOWN
    award_to_friend: str = UNKNOWN
    sparkle: str = UNKNOWN
    denied: str = UNKNOWN
    slot: str = UNKNOWN
    objective: str = UNKNOWN
    inventory: str = UNKNOWN
    shared_one_copy: str = UNKNOWN
    legacy_quest_guard: str = UNKNOWN
    hidden_ordinary_guard: str = UNKNOWN

    def __post_init__(self):
        allowed = {
            "kind": KIND, "source": SOURCE, "bucket": BUCKET,
            "method": METHOD, "turn": TURN,
            "friend_eligible": BOOL3, "award_to_friend": BOOL3,
            "sparkle": BOOL3, "denied": BOOL3, "slot": SLOT,
            "objective": NEED, "inventory": NEED,
            "shared_one_copy": BOOL3,
            "legacy_quest_guard": GUARD, "hidden_ordinary_guard": GUARD,
        }
        for name, options in allowed.items():
            value = getattr(self, name)
            if type(value) is not str or value not in options:
                raise ValueError("Invalid generic " + name + " category")


@dataclass(frozen=True)
class Assessment:
    """Possibilities/questions, never bug proof, approval or entitlement."""
    case: str
    hypothesis_codes: Tuple[str, ...]
    needed_categories: Tuple[str, ...]
    accepted: bool = False
    bug_proven: bool = False
    can_enable_a04: bool = False
    can_change_shared_loot: bool = False
    write_policy: str = "NO_WRITE"

    def __post_init__(self):
        if self.accepted or self.bug_proven or self.can_enable_a04:
            raise ValueError("Evidence-only tool cannot authorize outcome")
        if self.can_change_shared_loot or self.write_policy != "NO_WRITE":
            raise ValueError("Evidence-only tool cannot change loot policy")


def assess(x: Incident) -> Assessment:
    """Safe, total, conservative classifier of *questions*, not fixes.

    Source backing: pinned public Grimfeather core 8daffdabe...
    H1: Player::StoreLootItem, loot turn/release, per-viewer quest slots.
    H2: Player::isAllowedToLoot, LootView, HasQuestForItem.
    Real owner-installed code, effective flags, item/quest rows and timing
    remain unknown unless observed privately with separate permission.
    """
    if not isinstance(x, Incident):
        raise TypeError("Expected generic Incident")
    h = []
    missing = []

    if x.source == UNKNOWN:
        missing.append("loot source: creature/gameobject/item")
    if x.bucket == UNKNOWN:
        missing.append("loot bucket: quest/ordinary")
    if x.method == UNKNOWN:
        missing.append("group loot method")
    # These two default-OFF guards are INDEPENDENT. A quest-bucket row is
    # not an ordinary hidden slot, so do not classify the wrong switch as
    # a possible cause of this particular H2 item.
    if x.bucket == "quest":
        if x.legacy_quest_guard == UNKNOWN:
            missing.append("effective legacy quest-turn guard and installed binary (privately)")
    elif x.bucket == "ordinary":
        if x.hidden_ordinary_guard == UNKNOWN:
            missing.append("effective hidden-ordinary-slot guard and installed binary (privately)")
    else:
        missing.append("both independent effective A04 flags and installed binary (privately)")
    if x.kind == "H1":
        if x.award_to_friend == UNKNOWN:
            missing.append("verified friend inventory/mail award (not merely click/window)")
        if x.friend_eligible == UNKNOWN:
            missing.append("friend's quest/item eligibility at award time")
        if x.turn == UNKNOWN:
            missing.append("turn holder and whether holder released corpse")
        if x.shared_one_copy == UNKNOWN:
            missing.append("shared-one-copy versus FFA/MULTI_DROP classification")

        if x.award_to_friend != "yes":
            h.append("H1_AWARD_NOT_VERIFIED")
        elif x.friend_eligible == "no":
            # A missing quest objective does not itself prohibit an
            # ordinary-bucket award. Native conditions, faction, loot
            # method/turn and custom hooks may still make it legal.
            # Similarly, an unknown bucket cannot justify a quest-specific
            # unexpected-award label. Require bucket classification first.
            if x.bucket == "quest":
                h.append("H1_UNEXPECTED_AWARD_REQUIRES_PRIVATE_NATIVE_AUDIT")
            elif x.bucket == "ordinary":
                h.append("H1_ORDINARY_ENTITLEMENT_UNDETERMINED")
                missing.append("friend's native ordinary-loot entitlement, not quest status alone")
            else:
                h.append("H1_BUCKET_REQUIRED_BEFORE_ELIGIBILITY_JUDGMENT")
        elif x.friend_eligible == "yes" and x.shared_one_copy == "yes":
            h.append("H1_POSSIBLE_LEGITIMATE_SHARED_AWARD")
            # This includes friend and reporter loot turns: quest-specific
            # visibility need not always match the ordinary turn holder.
            # A turn/release *explanation* is grounded only for the
            # stock creature-loot group path traced in the pinned core.
            # FREE_FOR_ALL bypasses Group::UpdateLooterGuid, and unknown
            # sources/methods must not be diagnosed as stock turn behavior.
            # Quest-item eligibility is separate: this remains only a
            # possible explanation, never a verified award or permission.
            turn_explanation_supported = (
                x.source == "creature"
                and x.method in ("group", "round_robin",
                                 "need_before_greed", "master")
            )
            if turn_explanation_supported and x.turn in ("friend", "released"):
                h.append("H1_TURN_RELEASE_STOCK_CONSISTENT_CANDIDATE")
        else:
            h.append("H1_AWARD_OR_ENTITLEMENT_UNDETERMINED")
        if x.bucket == "ordinary":
            h.append("H1_ORDINARY_ITEM_IS_NOT_AUTOMATICALLY_PERSONAL")
        if x.method in ("group", "need_before_greed") and x.bucket == "quest":
            h.append("H1_CONFIRM_ROLL_FOLLOW_RULES_AND_AWARD_TIMING")
    else:
        if x.sparkle == UNKNOWN:
            missing.append("corpse sparkle at time of attempted loot")
        if x.denied == UNKNOWN:
            missing.append("actual native denial/error versus unavailable row")
        if x.slot == UNKNOWN:
            missing.append("viewer-specific row: locked/hidden/allow/roll ongoing")
        if x.objective == UNKNOWN:
            missing.append("objective counter short/met at H2")
        if x.inventory == UNKNOWN:
            missing.append("inventory amount short/met at H2")
        if x.shared_one_copy == UNKNOWN:
            missing.append("shared non-FFA one-copy quest item?")
        if x.sparkle == "yes" and x.slot == "locked":
            h.append("H2_CACHED_SPARKLE_LOCKED_ROW_STOCK_POSSIBLE")
        if x.sparkle == "yes" and x.denied == "yes" and x.slot != "locked":
            h.append("H2_SPARKLE_AND_DENIAL_NEED_NATIVE_ERROR_CAUSE")
        # H2 is the corpse-sparkle incident. A generic item container or
        # GO must not inherit this *creature-corpse* shared-window cause.
        # Even for a creature this remains a source hypothesis, not a
        # demonstrated persisted counter/bag mismatch or gameplay proof.
        if (x.source == "creature" and x.bucket == "quest"
                and x.shared_one_copy == "yes"
                and x.objective == "short" and x.inventory == "met"):
            h.append("H2_SHARED_WINDOW_COUNTER_DRIFT_SOURCE_CANDIDATE")
            missing.append("confirm mismatch existed BEFORE first loot window; other eligible viewer and count")
        # A guard merely being ON is not a denial. Pinned module's
        # PermitPickup only checks creature corpses under these three group
        # loot methods; all other sources/methods pass native handling.
        guard_path_possible = (
            x.source == "creature" and
            x.method in ("group", "round_robin", "need_before_greed") and
            x.denied == "yes"
        )
        if (guard_path_possible and x.bucket == "quest"
                and x.legacy_quest_guard == "on"):
            h.append("H2_LEGACY_QUEST_TURN_GUARD_CANDIDATE")
        # The ordinary guard rejects ONLY genuinely hidden ordinary rows.
        # A visible, locked, rolling or unknown row cannot implicate it.
        if (guard_path_possible and x.bucket == "ordinary"
                and x.slot == "hidden"
                and x.hidden_ordinary_guard == "on"):
            h.append("H2_HIDDEN_ORDINARY_SLOT_GUARD_CANDIDATE")
        if not h:
            h.append("H2_SOURCE_PATH_UNDETERMINED")
    return Assessment(x.kind, tuple(h), tuple(dict.fromkeys(missing)))


def blank_checklist() -> str:
    """Public safe guidance, not actual owner observation or data export."""
    return (
        "H1: Was an item really in friend's bag/mail? Was friend eligible? "
        "Which bucket/method/turn and who released? Was it shared or personal?\n"
        "H2: Was corpse sparkling? Was row locked/hidden/allow/rolling? "
        "What exact client denial? Were objective counter and held count each "
        "short/met *before* loot window? Shared non-FFA? Effective legacy quest-turn and hidden-ordinary guard switches separately?\n"
        "For both: privately confirm installed pinned versions/source, "
        "never put actual account, quest, item, creature or log identifiers in "
        "the PUBLIC repository. Maintain separate written owner staging/backup approval."
    )
