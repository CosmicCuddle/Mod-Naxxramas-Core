"""Pure synthetic IP Hunter owner-stage/dummy eligibility model.

No IP runtime calls, no account DB, no Pet, no SQL and no autocast writes.
Never substitute account-wide progression for a specific character's
rewarded hidden-quest evidence. The model is not authoritative runtime IP.
"""
from dataclasses import dataclass
import unittest

MOLTEN_CORE = 1
PRE_TBC = 8
TBC_TIER_5 = 13
LAST_STAGE = 18


@dataclass(frozen=True)
class IPCharacter:
    rewarded: frozenset[int] | None
    in_world: bool
    ip_enabled: bool | None
    vanilla_hunter_pets: bool | None
    progression_limit: int | None
    is_hunter: bool
    bot_account: bool | None


def character_stage(c):
    if not c.in_world or c.rewarded is None:
        return None
    return max((tier for tier in range(MOLTEN_CORE, LAST_STAGE + 1)
                if 66000 + tier in c.rewarded), default=0)


def has_passed(c, milestone):
    stage = character_stage(c)
    if stage is None or c.ip_enabled is not True:
        return None
    if not milestone or milestone < 0 or milestone > LAST_STAGE:
        return None
    if c.progression_limit is None:
        return None
    if c.progression_limit and milestone > c.progression_limit:
        return False
    return stage >= milestone


def hunter_ip_branch(c):
    """Can the pinned IP Hunter reconciliation path be evaluated at all?"""
    if (not c.in_world or c.ip_enabled is not True
            or c.vanilla_hunter_pets is not True
            or not c.is_hunter or c.bot_account is not False):
        return False
    tier5 = has_passed(c, TBC_TIER_5)
    return tier5 is False


def boar_gore_later_tbc_path(c):
    if not hunter_ip_branch(c):
        return None
    return has_passed(c, PRE_TBC)


def selected_rank(wipe_ids, ordered_dummies, known_dummies):
    """Pinned reverse-order dummy selection, not spell training permission."""
    if known_dummies is None:
        return None
    for dummy in reversed(ordered_dummies):
        if dummy in known_dummies:
            rank = dummy - 600000
            return rank if rank in wipe_ids else None
    return None


def source_rank_candidate(c, wipe_ids, ordered_dummies, known_dummies,
                          currently_known, rank):
    """Only a source-model candidate; never proves true DBC/spell legality."""
    return (hunter_ip_branch(c)
            and known_dummies is not None
            and currently_known is not None
            and rank in wipe_ids
            and selected_rank(wipe_ids, ordered_dummies, known_dummies) == rank
            and set(currently_known) & set(wipe_ids) == {rank})


def hunter(stage=0, **overrides):
    obj = dict(rewarded=frozenset({66000 + stage}) if stage else frozenset(),
               in_world=True, ip_enabled=True, vanilla_hunter_pets=True,
               progression_limit=0, is_hunter=True, bot_account=False)
    obj.update(overrides)
    return IPCharacter(**obj)


class CharacterStageSafety(unittest.TestCase):
    def test_stage_zero_no_rewarded_quests_is_pre_mc(self):
        self.assertEqual(character_stage(hunter()), 0)
        self.assertFalse(has_passed(hunter(), PRE_TBC))

    def test_rewarded_quest_stage_3_is_bwl_progression_not_account_max(self):
        player = hunter(3)
        other_on_same_account = hunter(13)
        self.assertEqual(character_stage(player), 3)
        self.assertEqual(character_stage(other_on_same_account), 13)
        self.assertTrue(hunter_ip_branch(player))
        self.assertFalse(hunter_ip_branch(other_on_same_account))

    def test_only_rewarded_hidden_quests_count_and_highest_wins(self):
        c = hunter(rewarded=frozenset({66001, 66003, 66008, 66019, 12345}))
        self.assertEqual(character_stage(c), 8)
        self.assertTrue(has_passed(c, PRE_TBC))

    def test_progression_limit_is_milestone_gate_not_faked_stage(self):
        c = hunter(13, progression_limit=7)
        self.assertEqual(character_stage(c), 13)
        # Pinned hasPassed returns FALSE when the requested milestone > cap.
        self.assertFalse(has_passed(c, TBC_TIER_5))
        self.assertTrue(hunter_ip_branch(c))
        self.assertFalse(boar_gore_later_tbc_path(c))
        self.assertTrue(has_passed(c, MOLTEN_CORE))

    def test_unknown_or_disabled_ip_config_fails_closed(self):
        for change in (dict(ip_enabled=None), dict(ip_enabled=False),
                       dict(vanilla_hunter_pets=None),
                       dict(vanilla_hunter_pets=False),
                       dict(progression_limit=None),
                       dict(bot_account=None), dict(bot_account=True),
                       dict(in_world=False), dict(is_hunter=False),
                       dict(rewarded=None)):
            with self.subTest(change=change):
                self.assertFalse(hunter_ip_branch(hunter(3, **change)))

    def test_boar_gore_conditional_uses_own_stage_and_cap(self):
        self.assertFalse(boar_gore_later_tbc_path(hunter(7)))
        self.assertTrue(boar_gore_later_tbc_path(hunter(8)))
        self.assertFalse(boar_gore_later_tbc_path(
            hunter(8, progression_limit=7)))

    def test_rank_requires_players_dummy_not_another_characters_dummy(self):
        wipe = (17260, 17261, 27050)
        dummy = (617260, 617261, 627050)
        c = hunter(3)
        self.assertTrue(source_rank_candidate(c, wipe, dummy,
            {617261}, {17261}, 17261))
        self.assertFalse(source_rank_candidate(c, wipe, dummy,
            {617260}, {17261}, 17261))
        self.assertFalse(source_rank_candidate(c, wipe, dummy,
            None, {17261}, 17261))

    def test_latest_known_dummy_supersedes_old_rank(self):
        wipe = (17260, 17261, 27050)
        dummy = (617260, 617261, 627050)
        self.assertEqual(selected_rank(wipe, dummy,
                                      {617260, 617261, 627050}), 27050)
        self.assertFalse(source_rank_candidate(
            hunter(3), wipe, dummy, {617260, 617261, 627050},
            {17261}, 17261))

    def test_unknown_or_removal_only_group_is_not_entitlement(self):
        self.assertIsNone(selected_rank((4167,), (), set()))
        self.assertFalse(source_rank_candidate(
            hunter(3), (4167,), (), set(), {4167}, 4167))
        # A rank-family test must include the COMPLETE applicable wipe
        # group. A truncated list cannot detect its disallowed older rank.
        self.assertFalse(source_rank_candidate(
            hunter(3), (17260, 17261), (617260, 617261), {617261},
            {17260, 17261}, 17261))


if __name__ == "__main__":
    unittest.main()
