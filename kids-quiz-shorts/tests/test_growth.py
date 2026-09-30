"""python -m unittest discover -s tests   (kids-quiz-shorts/ se)"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config as C  # noqa: E402
import pick  # noqa: E402
import seo  # noqa: E402


def _bank():
    b = [{"id": f"ph{i:02d}", "sub": C.PAHELI_SUB, "q": f"पहेली नंबर {i} क्या है?",
          "opts": [f"क{i}", f"ख{i}", f"ग{i}", f"घ{i}"], "ans": 0, "why": "x"} for i in range(6)]
    subs = ["सामान्य ज्ञान", "विज्ञान", "भारत", "दुनिया"]
    b += [{"id": f"g{i:03d}", "sub": subs[i % 4], "q": f"सवाल {i} का जवाब {i} क्या?",
           "opts": [f"अ{i}", f"ब{i}", f"स{i}", f"द{i}"], "ans": 1, "why": "y"} for i in range(16)]
    return b


class PickTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.used_path = Path(self.tmp.name) / "used.json"
        self.now = datetime(2026, 9, 30, 12, 0, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, history, slot, n=2):
        self.used_path.write_text(json.dumps({"history": history}), encoding="utf-8")
        with mock.patch.object(pick, "load_bank", _bank), \
             mock.patch.object(pick, "USED", self.used_path):
            return pick.pick(n, dry_run=True, seed=1, slot=slot, now=self.now)

    def _at(self, days_ago):
        return (self.now - timedelta(days=days_ago)).isoformat(timespec="seconds")

    def test_paheli_exhausted_picks_least_recently_used(self):
        # saari paheli use ho chuki: ph00 sabse purani (40 din), ph05 kal
        hist = [{"id": f"ph{i:02d}", "at": self._at(40 - i * 7)} for i in range(6)]
        got = [q["id"] for q in self._run(hist, "paheli")]
        self.assertEqual(got, ["ph00", "ph01"])

    def test_fresh_before_reused(self):
        hist = [{"id": "ph00", "at": self._at(60)}]
        got = [q["id"] for q in self._run(hist, "paheli")]
        self.assertNotIn("ph00", got)

    def test_quiz_never_takes_recent_when_cooled_exists(self):
        # 12 quiz sawaal kal use hue, 4 (g012..g015) 45 din pehle
        hist = [{"id": f"g{i:03d}", "at": self._at(1)} for i in range(12)]
        hist += [{"id": f"g{i:03d}", "at": self._at(45)} for i in range(12, 16)]
        got = {q["id"] for q in self._run(hist, "morning")}
        self.assertTrue(got <= {"g012", "g013", "g014", "g015"}, got)

    def test_quiz_subjects_differ(self):
        got = self._run([], "noon")
        self.assertEqual(len({q["sub"] for q in got}), 2)

    def test_stock_warning(self):
        last = {f"g{i:03d}": self._at(1) for i in range(15)}
        lines = pick.stock_report(_bank(), last, 2)
        self.assertTrue(any("WARNING" in line and "quiz" in line for line in lines))

    def test_real_bank_has_no_duplicate_ids(self):
        bank = json.loads((C.DATA / "questions.json").read_text(encoding="utf-8"))
        ids = [q["id"] for q in bank]
        self.assertEqual(len(ids), len(set(ids)))
        for q in bank:
            self.assertEqual(len(q["opts"]), 4, q["id"])
            self.assertIn(q["ans"], range(4), q["id"])
            self.assertTrue(q.get("why"), q["id"])


class SeoTests(unittest.TestCase):
    def _qs(self, sub="दुनिया"):
        return [{"id": "g1", "sub": sub, "q": "माचू पिच्चू किस देश में है?",
                 "opts": ["मेक्सिको", "पेरू", "चिली", "ब्राज़ील"], "ans": 1, "why": "इंका शहर"},
                {"id": "g2", "sub": "विज्ञान", "q": "इंद्रधनुष में कितने रंग होते हैं?",
                 "opts": ["5", "6", "7", "8"], "ans": 2, "why": "सात"}]

    def test_title_has_search_keyword_and_fits(self):
        m = seo.build(self._qs(), "morning", datetime(2026, 9, 30))
        self.assertTrue(m["title"].startswith("माचू पिच्चू"))
        self.assertIn("World GK Quiz", m["title"])
        self.assertLessEqual(len(m["title"]), 100)

    def test_no_kids_targeting_metadata(self):
        for slot in C.SLOT_ORDER:
            sub = C.PAHELI_SUB if slot == "paheli" else "भारत"
            m = seo.build(self._qs(sub), slot, datetime(2026, 9, 30))
            blob = (m["description"] + " ".join(m["tags"])).lower()
            for bad in ("class 1", "बच्चे", "स्कूल", "होमवर्क", "90%", "80%"):
                self.assertNotIn(bad, blob, (slot, bad))

    def test_pinned_comment_asks_does_not_spoil(self):
        m = seo.build(self._qs(), "night", datetime(2026, 9, 30))
        if C.MADE_FOR_KIDS:
            self.assertIsNone(m["pinned_comment"])
        else:
            self.assertNotIn("जवाब:", m["pinned_comment"])
            self.assertIn("कमेंट", m["pinned_comment"])

    def test_description_mentions_bonus_question(self):
        m = seo.build(self._qs(), "noon", datetime(2026, 9, 30))
        self.assertIn("इंद्रधनुष", m["description"].split("\n")[0])


class UploadTests(unittest.TestCase):
    def test_force_ssl_scope_requested(self):
        import upload
        self.assertIn("https://www.googleapis.com/auth/youtube.force-ssl", upload.SCOPES)

    def test_comment_body_has_channel_id(self):
        import upload
        yt = mock.MagicMock()
        upload.post_comment(yt, "VID", "UCabc", "hello")
        body = yt.commentThreads.return_value.insert.call_args.kwargs["body"]
        self.assertEqual(body["snippet"]["channelId"], "UCabc")
        self.assertEqual(body["snippet"]["videoId"], "VID")

    def test_pending_comments_skip_without_scope(self):
        import upload
        with tempfile.TemporaryDirectory() as d:
            led = Path(d) / "uploads.json"
            led.write_text(json.dumps([{"video_id": "V", "pinned_comment": "x",
                                        "publish_at": "2026-01-01T00:00:00Z"}]), encoding="utf-8")
            with mock.patch.object(upload, "LEDGER", led), \
                 mock.patch.object(upload, "_creds", return_value=mock.MagicMock(token="t")), \
                 mock.patch.object(upload, "granted_scopes", return_value={upload.SCOPES[0]}), \
                 mock.patch.object(upload, "post_comment") as pc:
                self.assertEqual(upload.post_pending_comments(), 0)
                pc.assert_not_called()


class ResearchTests(unittest.TestCase):
    def test_skip_without_credentials(self):
        import competitor_research as cr
        env = {k: v for k, v in os.environ.items()
               if k not in ("YT_DATA_API_KEY", "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(sys, "argv", ["x", "--dry-run"]):
            self.assertEqual(cr.main(), 0)

    def test_insight_tags_allowlist_and_no_channel_names(self):
        import competitor_research as cr
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ins.json"
            p.write_text(json.dumps({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "channels": [{"title": "Rival GK"}],
                "analysis": {"top_tags": ["rival gk", "gk quiz hindi 2026", "funny cat", "hindi paheli"]}}),
                encoding="utf-8")
            with mock.patch.object(cr, "INSIGHTS", p):
                self.assertEqual(cr.insight_tags(max_n=3), ["gk quiz hindi 2026", "hindi paheli"])

    def test_title_labels(self):
        import competitor_research as cr
        self.assertIn("paheli", cr.title_labels("आज की पहेली?"))
        self.assertIn("exam", cr.title_labels("SSC GK question"))


class RenderTextTests(unittest.TestCase):
    def test_reveal_banner(self):
        try:
            import render
        except Exception as e:  # font na ho to skip
            self.skipTest(f"render import: {e}")
        self.assertIn("अगला सवाल", render.reveal_banner_text(1, 2))
        if C.SUBSCRIBE_CTA == "end":
            self.assertIn("सब्सक्राइब", render.reveal_banner_text(2, 2))


if __name__ == "__main__":
    unittest.main()
