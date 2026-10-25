"""CS03 independent negative witnesses for Grok's frozen #135 PAK-D1 v2 model.

Read-only research (CS01 #48 6397028604, queue #143). Imports Grok's model
UNCHANGED from the file named by PAK_MODEL: in CI, `git show 50f0500:...`
of #135's tests/research/test_a02_pak_d1_protocol_v2.py. Nothing in #135,
#134 or the addon is edited.

"GAP" tests assert the frozen model's current behaviour (the gap exists).
"REF" tests run the same scenario on a minimal reference subclass that
implements the proposed fix, so each negative acceptance test is shown to
be satisfiable. Offline model only; no game, client, Lua or C++ receiver.
"""
import importlib.util
import os
import secrets
import unittest

MODEL = os.environ.get("PAK_MODEL", "")
if not MODEL or not os.path.exists(MODEL):
    raise unittest.SkipTest("PAK_MODEL not set: run via .github/workflows/a02-pak-cs03-negatives.yml")
spec = importlib.util.spec_from_file_location("pakv2", MODEL)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

GUID = 1


def fresh_store(cls):
    store = cls()
    store.enabled = True
    store.load_selfbot(0)
    store.login(GUID)
    return store


def wolf(number, bite=True):
    pet = m.make_wolf(number, bite=bite)
    pet.owner = GUID
    return pet


def ident(store):
    a = store.players[GUID].active
    return a.epoch, a.token, a.gen


def chunk(identity, pairs, seq=7):
    epoch, token, gen = identity
    return f"{m.PREFIX}v2|{epoch}|{token}|{gen}|{seq}|1/1|{pairs}"


# --- Reference fixes (model level only) -----------------------------------

class RefStore(m.V2Store):
    """(1) boot-fresh unpredictable tokens, (2) send-time revalidated,
    coalesced outbound HELLO, (3) stable membership from an independent
    authoritative oracle, never from observe()."""

    def __init__(self, stable_oracle=None):
        super().__init__()
        try:
            self.boot_nonce = secrets.token_hex(8)  # stands in for RAND_bytes
        except Exception:  # entropy failure -> feature closed, no fallback
            self.boot_nonce = None
            self.enabled = False
        self.stable_oracle = stable_oracle or (lambda guid, number: False)
        self.sent = []

    def issue(self, player, pet_number, instance_id):
        if self.boot_nonce is None:
            player.active = None
            return
        if player.next_gen >= m.MAX_SEQ:
            player.active = None
            player.assembler = m.Assembler()
            return
        player.next_gen += 1
        token = secrets.token_hex(8)  # 64 random bits per issue, 16 hex chars
        hello = f"v2|hello|{player.epoch}|{token}|{player.next_gen}|{pet_number}"
        player.outbound[:] = [hello]  # coalesce: only the newest can be valid
        player.active = m.Active(pet_number, token, player.next_gen,
                                 player.epoch, hello, instance_id)
        player.assembler = m.Assembler()

    def observe(self, guid, pet):
        player = self.player(guid)
        if pet is not None and pet.number and not self.stable_oracle(guid, pet.number):
            player.active = None
            player.assembler = m.Assembler()
            return
        before = set(player.stable)
        super().observe(guid, pet)
        player.stable = before  # never self-populate membership

    def drain(self, guid, pet):
        player = self.player(guid)
        if pet is not None and pet.number and self.stable_oracle(guid, pet.number):
            player.stable.add(pet.number)  # oracle-confirmed only
        super().drain(guid, pet)

    def logout(self, guid):
        super().logout(guid)
        self.player(guid).outbound.clear()

    def send_pending(self, guid):
        """World-thread send: revalidate each queued HELLO at send time."""
        player = self.player(guid)
        for hello in player.outbound:
            _, _, epoch, token, gen, pet = hello.split("|")
            a = player.active
            if (player.logged_in and a is not None and a.epoch == int(epoch)
                    and a.token == token and a.gen == int(gen)
                    and a.pet_number == int(pet)):
                self.sent.append(hello)
        player.outbound.clear()


def oracle_all(guid, number):
    return True


# --- PAK-RESTART-01 ----------------------------------------------------------

class PakRestart01(unittest.TestCase):
    def scenario(self, cls, **kw):
        a = wolf(17)
        old = fresh_store(cls) if not kw else cls(**kw)
        if kw:
            old.enabled = True
            old.load_selfbot(0)
            old.login(GUID)
        old.observe(GUID, a)
        stale = chunk(ident(old), "17259=0")  # complete OFF packet, delayed
        # Worldserver restart: brand-new store, same saved pet number.
        new = cls(**kw) if kw else cls()
        new.enabled = True
        new.load_selfbot(0)
        new.login(GUID)
        a2 = wolf(17)
        new.observe(GUID, a2)
        same_identity = ident(new) == ident(old)
        self.assertEqual(new.world_accept(GUID, stale, 0, "x"), "Queued")
        new.drain(GUID, a2)
        return same_identity, new.choices_for(GUID, a2)

    def test_gap_frozen_model_replays_old_process_packet(self):
        same, choices = self.scenario(m.V2Store)
        self.assertTrue(same, "fresh process re-mints (1, 0000000000000001, 1)")
        self.assertEqual(choices, {17253: False},
                         "old-process OFF choice is applied after restart")

    def test_ref_boot_fresh_token_rejects_old_process_packet(self):
        same, choices = self.scenario(RefStore, stable_oracle=oracle_all)
        self.assertFalse(same)
        self.assertIsNone(choices)


# --- PAK-HELLO-STALE-01 -------------------------------------------------------

class PakHelloStale01(unittest.TestCase):
    def test_gap_stale_A_hello_remains_queued_after_swap_and_logout(self):
        s = fresh_store(m.V2Store)
        a, b = wolf(17), wolf(18)
        s.observe(GUID, a)
        hello_a = s.players[GUID].outbound[-1]
        s.observe(GUID, b)  # A -> B before any world-thread send
        self.assertIn(hello_a, s.players[GUID].outbound)
        s.logout(GUID)
        self.assertIn(hello_a, s.players[GUID].outbound,
                      "logout does not revoke queued HELLOs")
        s.login(GUID)
        alive = [wolf(19) for _ in range(50)]  # distinct summons
        for pet in alive:  # repeated summons build an unbounded backlog
            s.observe(GUID, pet)
        self.assertGreater(len(s.players[GUID].outbound), 50)

    def test_ref_send_time_revalidation_drops_A_after_swap(self):
        s = RefStore(stable_oracle=oracle_all)
        s.enabled = True
        s.load_selfbot(0)
        s.login(GUID)
        a, b = wolf(17), wolf(18)
        s.observe(GUID, a)
        hello_a = s.players[GUID].outbound[-1]
        s.observe(GUID, b)
        s.send_pending(GUID)
        self.assertNotIn(hello_a, s.sent)
        self.assertEqual(len(s.sent), 1)
        self.assertTrue(s.sent[0].endswith("|18"))

    def test_ref_logout_and_backlog(self):
        s = RefStore(stable_oracle=oracle_all)
        s.enabled = True
        s.load_selfbot(0)
        s.login(GUID)
        s.observe(GUID, wolf(17))
        s.logout(GUID)
        s.send_pending(GUID)
        self.assertEqual(s.sent, [])
        s.login(GUID)
        alive = [wolf(19) for _ in range(50)]
        for pet in alive:
            s.observe(GUID, pet)
        self.assertLessEqual(len(s.players[GUID].outbound), 1)


class IncarnationIdentity(unittest.TestCase):
    def test_gap_reused_object_identity_keeps_old_generation(self):
        # The model keys an incarnation on id(pet). A dismissed pet's storage
        # reused by the next summon (CPython ids, or a C++ allocator handing
        # back the same Pet* address) keeps the old token valid for the new
        # incarnation. A per-summon counter or the per-summon Pet GUID avoids it.
        s = fresh_store(m.V2Store)
        first = wolf(17)
        s.observe(GUID, first)
        before = ident(s)
        reused = first  # same object identity, new summon
        reused.spells = dict(wolf(17, bite=False).spells)
        s.observe(GUID, reused)
        self.assertEqual(ident(s), before)


# --- PAK-STABLE-MEMBER-01 -----------------------------------------------------

class PakStableMember01(unittest.TestCase):
    def test_gap_observe_self_populates_membership(self):
        s = fresh_store(m.V2Store)
        ghost = wolf(4242)  # never in the owner's stable; never retired
        s.observe(GUID, ghost)
        self.assertIn(4242, s.players[GUID].stable)
        s.world_accept(GUID, chunk(ident(s), "17259=0"), 0, "x")
        s.drain(GUID, ghost)
        self.assertEqual(s.choices_for(GUID, ghost), {17253: False})

    def test_ref_unconfirmed_pet_fails_closed(self):
        s = RefStore(stable_oracle=lambda guid, number: number == 17)
        s.enabled = True
        s.load_selfbot(0)
        s.login(GUID)
        ghost = wolf(4242)
        s.observe(GUID, ghost)
        self.assertIsNone(s.players[GUID].active)
        self.assertNotIn(4242, s.players[GUID].stable)
        self.assertIsNone(s.choices_for(GUID, ghost))
        good = wolf(17)
        s.observe(GUID, good)
        s.world_accept(GUID, chunk(ident(s), "17259=0"), 0, "x")
        s.drain(GUID, good)
        self.assertEqual(s.choices_for(GUID, good), {17253: False})


if __name__ == "__main__":
    unittest.main(verbosity=2)
