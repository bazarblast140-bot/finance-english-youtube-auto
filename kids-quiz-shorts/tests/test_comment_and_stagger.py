"""403 comment root cause (private/scheduled video) + catch-up stagger."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import upload  # noqa: E402
import slot_planner  # noqa: E402


class CommentTiming(unittest.TestCase):
    def test_no_comment_on_scheduled_or_private(self):
        self.assertFalse(upload.comment_now_ok("public", "2026-10-22T12:00:00Z"))
        self.assertFalse(upload.comment_now_ok("private", None))
        self.assertFalse(upload.comment_now_ok("unlisted", None))
        self.assertTrue(upload.comment_now_ok("public", None))

    def test_detects_insufficient_permissions(self):
        e = Exception('<HttpError 403 ... "reason": "insufficientPermissions">')
        self.assertTrue(upload.is_insufficient_permissions(e))
        self.assertFalse(upload.is_insufficient_permissions(Exception("quotaExceeded")))


class Stagger(unittest.TestCase):
    def test_bounds_and_default(self):
        self.assertEqual(slot_planner.dispatch_stagger_seconds("150"), 150)
        self.assertEqual(slot_planner.dispatch_stagger_seconds("bad"), 150)
        self.assertEqual(slot_planner.dispatch_stagger_seconds("-5"), 0)
        self.assertEqual(slot_planner.dispatch_stagger_seconds("9999"), 600)


if __name__ == "__main__":
    unittest.main()
