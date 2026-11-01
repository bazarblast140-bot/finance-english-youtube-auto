import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config as C  # noqa: E402
import thumbnail as T  # noqa: E402
from pick import load_bank  # noqa: E402


class ThumbTests(unittest.TestCase):
    def test_hook_short_and_no_answer_whole_bank(self):
        for q in load_bank():
            t = T.hook_text(q)
            self.assertTrue(2 <= len(t.split()) <= T.MAX_WORDS, (q["id"], t))
            self.assertFalse(T.leaks_answer(t, q), (q["id"], t))

    def test_answer_word_removed(self):
        q = {"q": "पेरू की राजधानी लीमा किस देश में है?", "opts": ["लीमा", "b", "c", "d"], "ans": 0}
        self.assertNotIn("लीमा", T.hook_text(q))

    def test_render_fits(self):
        q = load_bank()[0]
        with tempfile.TemporaryDirectory() as d:
            info = T.make(q, Path(d) / "thumbnail.jpg")
            from PIL import Image, ImageDraw
            im = Image.open(info["path"])
            self.assertEqual(im.size, (1080, 1920))
            self.assertLessEqual(Path(info["path"]).stat().st_size, 2_000_000)
            self.assertLessEqual(len(info["lines"]), 3)
            self.assertGreaterEqual(info["font_size"], 90)
            import render
            dr = ImageDraw.Draw(im)
            for l in info["lines"]:
                self.assertLessEqual(render.text_w(dr, l, render.F(info["font_size"])), C.W - 140)

    def test_set_thumbnail_failure_is_warning(self):
        yt = mock.Mock()
        yt.thumbnails.return_value.set.return_value.execute.side_effect = Exception("403")
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            self.assertFalse(T.set_thumbnail(yt, "vid", f.name))

    def test_scheduled_private_filter(self):
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        rows = [{"video_id": "a", "publish_at": "2026-11-02T12:00:00Z"},
                {"video_id": "b", "publish_at": "2026-10-30T12:00:00Z"},
                {"video_id": "c", "publish_at": None}]
        self.assertEqual([r["video_id"] for r in T.scheduled_private(rows, now)], ["a"])
