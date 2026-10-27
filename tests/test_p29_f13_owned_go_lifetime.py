"""F13 Part29 native GO lifetime proof (PUBLIC pinned core; NO owner host).

This verifies only source-shaped control flow; it does NOT inject a real GO,
launch Worldserver, establish owner-installed semantics or claim gameplay pass.
"""
from pathlib import Path
import os
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = Path(os.environ.get("F13_CORE_PIN_ROOT", "acore"))
PATHS = {
    "player": "src/server/game/Entities/Player/Player.cpp",
    "map": "src/server/game/Maps/Map.cpp",
    "unit": "src/server/game/Entities/Unit/Unit.cpp",
    "go": "src/server/game/Entities/GameObject/GameObject.cpp",
}
OURS = (ROOT / "src/Systems/AtieshKarazhanPortal.cpp").read_text(encoding="utf-8")


def load(name):
    file = CORE / PATHS[name]
    if not file.is_file():
        raise AssertionError("Missing pinned PUBLIC core file: " + str(file))
    return file.read_text(encoding="utf-8")


def body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:i + 1]
    raise AssertionError("unbalanced source function: " + signature)


class Lifetime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = {k: load(k) for k in PATHS}
        cls.hook = body(OURS,
                        "bool CanGameObjectGossipHello(Player* player, GameObject* go) override")

    def test_teleport_can_remove_player_synchronously(self):
        t = body(self.p["player"], "bool Player::TeleportTo(")
        self.assertIn("oldmap->RemovePlayerFromMap(this, false);", t)
        self.assertIn("if (GetMapId() == mapid && !newInstance)", t)
        # TeleportTo has earlier short-circuit true returns in its
        # *near* and delayed-teleport branches. The far-transfer block
        # removes the player before the method's FINAL successful return.
        far = t[t.index("// far teleport to another map"):]
        self.assertLess(far.index("oldmap->RemovePlayerFromMap(this, false);"),
                        far.rindex("return true;"))

    def test_native_map_and_player_world_exit_chain(self):
        map_exit = body(self.p["map"], "void Map::RemovePlayerFromMap(Player* player, bool remove)")
        player_exit = body(self.p["player"], "void Player::RemoveFromWorld()")
        self.assertIn("player->RemoveFromWorld();", map_exit)
        self.assertIn("Unit::RemoveFromWorld();", player_exit)
        self.assertLess(map_exit.index("player->RemoveFromWorld();"),
                        map_exit.index("if (remove)"))

    def test_native_unit_removes_owned_go_and_schedules_deletion(self):
        unit_exit = body(self.p["unit"], "void Unit::RemoveFromWorld()")
        all_go = body(self.p["unit"], "void Unit::RemoveAllGameObjects()")
        del_go = body(self.p["go"], "void GameObject::Delete()")
        self.assertIn("RemoveAllGameObjects();", unit_exit)
        self.assertIn("go->SetOwnerGUID(ObjectGuid::Empty);", all_go)
        self.assertIn("go->Delete();", all_go)
        self.assertIn("AddObjectToRemoveList();", del_go)
        # 'Delete' schedules removal; physical memory free at this exact
        # call site is not established. Access after removal is unsound.

    def test_ownership_is_snapshotted_before_teleport(self):
        check = "bool const clickerOwnsPortal = go->GetOwnerGUID() == player->GetGUID();"
        t = self.hook
        self.assertIn(check, t)
        self.assertLess(t.index(check), t.index("player->TeleportTo("))
        # Cached flag remains valid if owner GUID is cleared on removal.
        self.assertEqual(t.count("go->GetOwnerGUID()"), 1)

    def test_unowned_or_other_owner_success_only_keeps_add_use(self):
        hook = self.hook
        after = hook[hook.index("player->TeleportTo("):]
        self.assertRegex(after,
                         r"if \(!clickerOwnsPortal\)\s+go->AddUse\(\);")
        self.assertLess(after.index("go->AddUse();"),
                        after.index("else\n            Tell(player);"))
        self.assertEqual(after.count("go->"), 1)
        self.assertEqual(OURS.count("AddUse()"), 1)
        # A rejected teleport cannot enter the true branch and count use.

    def test_owned_portal_never_dereferenced_after_possible_removal(self):
        after = self.hook[self.hook.index("player->TeleportTo("):]
        self.assertNotIn("go->GetOwnerGUID()", after)
        self.assertNotIn("go->GetGOInfo()", after)
        self.assertNotIn("go->GetMap()", after)
        self.assertIn("if (!clickerOwnsPortal)", after)
        # Conservative tradeoff: a clicker-owned portal has no AddUse
        # after success, even if a same-map move happened to leave it live.
        # Require future private gameplay review for exact owned GO lifespan.


if __name__ == "__main__":
    unittest.main(verbosity=2)
