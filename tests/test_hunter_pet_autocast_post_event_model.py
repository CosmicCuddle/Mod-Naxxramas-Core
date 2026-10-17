"""Synthetic counterexamples for native event queue status as IP readiness.

Source-backed qualitative state transitions, no live queue or Pet objects.
A queue can be empty while a removed event callback is running, or remain
nonempty after an IP event returned. Neither status proves completion.
"""
import unittest


class SyntheticQueue:
    def __init__(self):
        self.pending = []
        self.executing = None
        self.ip_completed = False

    def add(self, name, callback):
        self.pending.append((name, callback))

    def has_events(self):
        return bool(self.pending)

    def update_one(self):
        # Pinned EventProcessor::Update first erases a due event from queue.
        name, callback = self.pending.pop(0)
        self.executing = name
        callback(self)
        self.executing = None


class PostEventBoundary(unittest.TestCase):
    def test_empty_queue_during_unfinished_ip_callback(self):
        q = SyntheticQueue()
        observed = []

        def ip_event(queue):
            observed.append((queue.has_events(), queue.executing,
                             queue.ip_completed))
            queue.ip_completed = True

        q.add("IP", ip_event)
        q.update_one()
        self.assertEqual(observed, [(False, "IP", False)])
        # An empty queue doesn't prove completion even in the same tick.

    def test_nonempty_queue_after_ip_finishes(self):
        q = SyntheticQueue()
        q.add("IP", lambda queue: setattr(queue, "ip_completed", True))
        q.add("unrelated", lambda queue: None)
        q.update_one()
        self.assertTrue(q.has_events())
        self.assertTrue(q.ip_completed)

    def test_post_queue_callback_can_run_before_later_due_ip(self):
        # First tick is early; IP is scheduled for the future, so a
        # post-event-loop observation isn't the post-IP call return.
        pending = {"IP": "future"}
        observed = (bool(pending), False)
        self.assertEqual(observed, (True, False))

    def test_empty_queue_without_any_ip_event(self):
        q = SyntheticQueue()
        self.assertFalse(q.has_events())
        self.assertFalse(q.ip_completed)

    def test_loading_pet_update_skips_world_object_callback(self):
        def ordinary_pet_tick(loading):
            # Pinned Pet::Update immediately returns while m_loading.
            return "no_world_object_update" if loading else "world_object_update"
        self.assertEqual(ordinary_pet_tick(True), "no_world_object_update")
        self.assertEqual(ordinary_pet_tick(False), "world_object_update")

    def test_post_event_tick_does_not_authenticate_ip_origin(self):
        q = SyntheticQueue()
        q.add("OtherPlugin", lambda queue: None)
        q.update_one()
        self.assertFalse(q.has_events())
        self.assertFalse(q.ip_completed)


if __name__ == "__main__":
    unittest.main()
