import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config as C  # noqa: E402
import build  # noqa: E402
import slot_planner  # noqa: E402


def _qs(n=10):
    return [{"id": f"g{i}", "sub": "भारत", "q": f"सवाल {i}?", "opts": ["a", "b", "c", "d"],
             "ans": 1, "why": "x"} for i in range(n)]


class ChallengeTests(unittest.TestCase):
    def test_default_off(self):
        self.assertFalse(C.CHALLENGE_MODE)
        self.assertFalse(C.EVENING_HEAVY)

    def test_plan_structure_and_length(self):
        with mock.patch.object(build.tts, "say", return_value=("x.wav", 3.0, "edge")):
            segs = build.plan_challenge(_qs())
        kinds = [s["kind"] for s in segs]
        self.assertEqual(kinds.count("timer"), 10)
        self.assertEqual(kinds.count("reveal"), 10)
        self.assertEqual(kinds[-1], "score")
        self.assertNotIn("cta", kinds)
        total = sum(s["frames"] for s in segs) / C.FPS
        self.assertTrue(120 <= total <= C.HARD_LIMIT_SECONDS, total)

    def test_meta_title(self):
        m = build.challenge_meta(_qs(), "evening", datetime(2026, 10, 31))
        self.assertEqual(m["title"], "GK Quiz in Hindi | 10 सवाल – कितने सही? 🧠")
        self.assertLessEqual(len(m["title"]), 100)
        self.assertEqual(m["mode"], "challenge10")

    def test_cli_refuses_when_flag_off(self):
        with mock.patch.object(sys, "argv", ["build.py", "--challenge"]), \
             mock.patch.object(build, "pick") as p:
            self.assertEqual(build.main(), 2)
            p.assert_not_called()

    def test_evening_proposal(self):
        self.assertEqual(slot_planner.proposed_slots(), C.SLOTS)
        prop = slot_planner.proposed_slots(True)
        evening = [v for v in prop.values() if "18:00" <= v[:5] <= "21:00"]
        self.assertGreaterEqual(len(evening), 3)
        self.assertEqual(C.SLOTS["night"], "20:30 IST")   # live untouched
