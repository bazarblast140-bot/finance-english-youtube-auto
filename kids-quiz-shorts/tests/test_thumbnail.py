import re
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

_PUNCT = T._PUNCT


def _bare(token):
    return str(token).strip(_PUNCT)


def _answer_phrase_in_question(q):
    ans = str(q["opts"][q["ans"]])
    toks = [_bare(t) for t in ans.split() if _bare(t)]
    if not toks or len(_bare(ans)) <= 1:
        return False
    bare = [_bare(w) for w in q["q"].split()]
    n = len(toks)
    return any(bare[i:i + n] == toks for i in range(len(bare) - n + 1))


def _shared_numbers(q):
    qnums = set(re.findall(r"[0-9]+", q["q"]))
    onums = set()
    for o in q["opts"]:
        onums |= set(re.findall(r"[0-9]+", str(o)))
    return qnums & onums


def _unchanged(q):
    """Questions whose cover text must be the full question, word for word."""
    if re.search(r"[\(\[]\s*[0-9]{3,4}", q["q"]):
        return False
    if _shared_numbers(q):
        return False
    if _answer_phrase_in_question(q):
        return False
    return True


def _inside_frame(box, pad=0):
    l, t, r, b = box
    return l >= pad and t >= pad and r <= C.W - pad and b <= C.H - pad


def _inside_safe(box):
    l, t, r, b = box
    return (l >= 0 and r <= C.W and t >= T.SAFE_TOP - 0.5 and b <= T.SAFE_BOTTOM + 0.5
            and r > l and b > t)


class ThumbTests(unittest.TestCase):
    def test_full_question_not_truncated_whole_bank(self):
        clean = 0
        for q in load_bank():
            text = T.cover_text(q)
            self.assertNotIn("…", text, q["id"])
            self.assertNotIn("...", text, q["id"])
            self.assertIn("?", text, q["id"])
            self.assertFalse(T.leaks_answer(text, q), (q["id"], text))
            if _unchanged(q):
                clean += 1
                self.assertEqual(text.split(), q["q"].split(), q["id"])
            layout = T.layout_cover(q)
            self.assertEqual(layout["text"].split(), text.split(), q["id"])
            self.assertEqual(" ".join(layout["lines"]).split(), text.split(), q["id"])
            self.assertGreaterEqual(len(layout["lines"]), T.MIN_LINES, (q["id"], layout["lines"]))
            self.assertLessEqual(len(layout["lines"]), T.MAX_LINES, (q["id"], layout["lines"]))
            self.assertIsNotNone(layout["qmark_bbox"], q["id"])
            self.assertTrue(_inside_frame(layout["qmark_bbox"]), (q["id"], layout["qmark_bbox"]))
            self.assertTrue(_inside_safe(layout["qmark_bbox"]), (q["id"], layout["qmark_bbox"]))
            for bound in layout["text_bounds"]:
                self.assertTrue(_inside_safe(bound), (q["id"], bound))
                self.assertGreaterEqual(bound[0], 24, q["id"])
                self.assertLessEqual(bound[2], C.W - 24, q["id"])
        self.assertGreater(clean, 400)

    def test_answer_word_removed_without_truncating_the_question(self):
        q = {"id": "lima", "sub": "दुनिया",
             "q": "पेरू की राजधानी लीमा किस देश में है?",
             "opts": ["लीमा", "बोगोटा", "क्विटो", "ला पाज़"], "ans": 0}
        text = T.cover_text(q)
        self.assertNotIn("लीमा", text)
        self.assertEqual(text.split(), "पेरू की राजधानी किस देश में है?".split())
        self.assertFalse(T.leaks_answer(text, q))

    def test_panipat_year_does_not_leak(self):
        bank = {q["id"]: q for q in load_bank()}
        real = bank["g206"]
        text = T.cover_text(real)
        self.assertEqual(text, "पानीपत का पहला युद्ध किनके बीच हुआ था?")
        self.assertNotIn("1526", text)
        for leaked in ("बाबर", "इब्राहिम", "लोदी", "हेमू", "सांगा", "अब्दाली"):
            self.assertNotIn(leaked, text)
        self.assertFalse(T.leaks_answer(text, real))

        # Year is the answer itself, and it is also written in the question.
        like = {
            "id": "panipat-like",
            "sub": "भारत",
            "q": "पानीपत का पहला युद्ध (1526) किस वर्ष हुआ था?",
            "opts": ["1526", "1556", "1761", "1857"],
            "ans": 0,
        }
        covered = T.cover_text(like)
        for year in ("1526", "1556", "1761", "1857"):
            self.assertNotIn(year, covered)
        self.assertIn("पानीपत", covered)
        self.assertIn("वर्ष", covered)
        self.assertTrue(covered.endswith("?"))
        self.assertFalse(T.leaks_answer(covered, like))
        layout = T.layout_cover(like)
        blob = " ".join(layout["lines"])
        self.assertNotIn("1526", blob)
        self.assertTrue(_inside_frame(layout["qmark_bbox"]))
        self.assertTrue(_inside_safe(layout["qmark_bbox"]))

    def test_contextual_year_that_is_not_an_answer_stays(self):
        # 1947 is in the question and not in the options — it is not a spoiler year.
        q = next(item for item in load_bank() if item["id"] == "g338")
        text = T.cover_text(q)
        self.assertIn("1947", text)
        self.assertIn("पतंगा", q["opts"])
        self.assertNotIn("पतंगा", text)

    def test_option_numbers_stripped_from_question(self):
        q = next(item for item in load_bank() if item["id"] == "ph121")
        text = T.cover_text(q)
        for n in ("0", "8", "9", "17"):
            self.assertNotIn(n, text)
        self.assertIn("किसान", text)
        self.assertIn("भेड़ें", text)
        self.assertTrue(text.endswith("?"))
        self.assertFalse(T.leaks_answer(text, q))

    def test_question_mark_inside_frame_when_rendered(self):
        from PIL import Image
        bank = {q["id"]: q for q in load_bank()}
        samples = [bank["g206"], bank["ph93"], bank["g173"], bank[max(bank, key=lambda i: len(bank[i]["q"]))]]
        with tempfile.TemporaryDirectory() as d:
            for q in samples:
                info = T.make(q, Path(d) / f"{q['id']}.jpg")
                im = Image.open(info["path"])
                self.assertEqual(im.size, (C.W, C.H))
                self.assertLessEqual(Path(info["path"]).stat().st_size, 2_000_000)
                self.assertTrue(_inside_frame(info["qmark_bbox"]), info["qmark_bbox"])
                self.assertTrue(_inside_safe(info["qmark_bbox"]), info["qmark_bbox"])
                for bound in info["text_bounds"]:
                    self.assertTrue(_inside_safe(bound), bound)
                # The old cover drew a giant "?" that fell out of the centre crop.
                self.assertEqual(_bright_count(im, (0, 0, C.W, T.SAFE_TOP)), 0, q["id"])
                self.assertEqual(_bright_count(im, (0, T.SAFE_BOTTOM, C.W, C.H)), 0, q["id"])
                self.assertNotIn("1526", info["text"])

    def test_background_colour_varies_and_is_deterministic(self):
        bank = load_bank()
        colors = {T.background_color(q) for q in bank}
        self.assertGreaterEqual(len(colors), 8)
        self.assertTrue(colors <= set(T.PALETTE))
        q = next(item for item in bank if item["id"] == "g206")
        self.assertEqual(T.background_color(q), T.background_color(dict(q)))
        with tempfile.TemporaryDirectory() as d:
            info = T.make(q, Path(d) / "thumbnail.jpg")
            from PIL import Image
            im = Image.open(info["path"])
            pixel = im.getpixel((6, 6))
            self.assertTrue(all(abs(a - b) <= 3 for a, b in zip(pixel, info["bg"])), pixel)
            # Not the old single purple blur.
            self.assertNotEqual(pixel, (124, 58, 237))

    def test_cover_does_not_paint_the_question_panel(self):
        q = load_bank()[0]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("render.question_panel", side_effect=AssertionError("options would leak")):
            info = T.make(q, Path(d) / "thumbnail.jpg")
        self.assertTrue(info["icon"])
        self.assertIn(info["bg"], T.PALETTE)

    def test_latin_words_use_a_real_font(self):
        # Noto Sans Devanagari draws A–Z as empty boxes. The cover must not.
        from PIL import Image, ImageDraw
        font = T.latin_font(72)
        im = Image.new("L", (640, 120), 0)
        ImageDraw.Draw(im).text((8, 8), "radioactivity", font=font, fill=255)
        lit = sum(1 for p in im.getdata() if p > 128)
        self.assertGreater(lit, 2000, "Latin face is drawing .notdef boxes")
        q = next(item for item in load_bank() if item["id"] == "g230")
        self.assertIn("radioactivity", T.cover_text(q))

    def test_icons_follow_the_topic(self):
        bank = {q["id"]: q for q in load_bank()}
        self.assertEqual(T.topic_icon(bank["g206"]), "swords")
        self.assertEqual(T.topic_icon(bank["g173"]), "music")
        self.assertEqual(T.topic_icon(bank["ph93"]), "puzzle")
        icons = {T.topic_icon(q) for q in bank.values()}
        self.assertGreaterEqual(len(icons), 8)

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


def _bright_count(im, box, thresh=220):
    crop = im.crop(box)
    n = 0
    for p in crop.getdata():
        if p[0] >= thresh and p[1] >= thresh and p[2] >= thresh:
            n += 1
    return n


if __name__ == "__main__":
    unittest.main()
