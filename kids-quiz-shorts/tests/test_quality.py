"""Quality gate, hook, map, font, pacing. Network nahi — DeepSeek mock."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config as C  # noqa: E402
import quality  # noqa: E402
import seo  # noqa: E402
import tts  # noqa: E402


def _q(qid="g1", ans=1, opts=None, why="लिवर दोबारा बन जाता है।", sub="विज्ञान",
       text="कौन सा अंग दोबारा उग सकता है?"):
    opts = opts or ["दिल", "लिवर", "किडनी", "फेफड़ा"]
    return {"id": qid, "sub": sub, "q": text, "opts": opts, "ans": ans, "why": why}


def _state_q():
    return _q(
        qid="g044", sub="भारत", ans=0,
        text="कच्छ का रण किस राज्य में है?",
        opts=["गुजरात", "राजस्थान", "महाराष्ट्र", "मध्य प्रदेश"],
        why="रण गुजरात में है।",
    )


class HookTests(unittest.TestCase):
    def test_specific_hook_scores_high(self):
        q = _state_q()
        line = "बताइए: कच्छ रण राज्य"
        score, notes = quality.score_hook(line, line, question=q)
        self.assertGreaterEqual(score, 70, notes)
        self.assertNotIn("करो", line)
        self.assertNotIn("गुजरात", line)

    def test_generic_hook_penalised(self):
        q = _state_q()
        line = "क्या आप बता सकते हैं?"
        score, notes = quality.score_hook(line, line, question=q)
        self.assertLess(score, 70, notes)
        self.assertTrue(any("generic" in n for n in notes))
        stock, stock_notes = quality.score_hook("8 सेकंड में जवाब दीजिए!", "8 सेकंड में जवाब दीजिए!", question=q)
        self.assertLess(stock, 70, stock_notes)

    def test_fake_percentage_and_answer_leak_penalised(self):
        q = _state_q()
        pct, notes = quality.score_hook("90% लोग कच्छ गलत बताते हैं", "90% लोग कच्छ गलत बताते हैं", question=q)
        self.assertLess(pct, 70, notes)
        leak, leak_notes = quality.score_hook("बताइए: गुजरात", "बताइए: गुजरात", question=q)
        self.assertLess(leak, 70, leak_notes)

    def test_kid_and_tum_hooks_fail(self):
        kid, _ = quality.score_hook("बच्चों का स्कूल चैलेंज", "बच्चों का स्कूल चैलेंज")
        tum, _ = quality.score_hook("जल्दी करो!", "जल्दी करो!")
        self.assertLess(kid, 70)
        self.assertLess(tum, 70)

    def test_hook_is_question_specific_and_hides_answer(self):
        import build
        a = build.hook_seed([{"id": "g001"}], "morning", datetime(2026, 10, 1))
        b = build.hook_seed([{"id": "g044"}], "morning", datetime(2026, 10, 1))
        self.assertNotEqual(a, b)
        q = _state_q()
        line = build.hook_line([q], "noon", datetime(2026, 10, 1))
        self.assertIn("कच्छ", line)
        self.assertNotIn("गुजरात", line)
        self.assertNotIn("90%", line)
        self.assertNotIn(line, C.HOOK_LINES["quiz"])
        for tum in ("करो", "लिखो", "रुको", "बताओ", "पूछो", "खेलो"):
            self.assertNotIn(tum, line)
        score, notes = quality.score_hook(line, line, question=q)
        self.assertGreaterEqual(score, 70, notes)

    def test_hook_frame_shows_the_question(self):
        import render
        line = "बताइए: कच्छ रण राज्य"
        question = "कच्छ का रण किस राज्य में है?"
        blank = render.hook_panel(line, "")
        shown = render.hook_panel(line, question)

        def white(img):
            crop = img.crop((100, 860, 980, 1240))
            return sum(1 for p in crop.getdata() if p[0] > 240 and p[1] > 240 and p[2] > 240)

        # Question card sits in this band. The teaser-only frame does not.
        self.assertGreater(white(shown), white(blank) + 8000)

    def test_voice_matches_screen_line(self):
        line = "तैयार हैं आप?"
        self.assertEqual(tts.hook_script(line), line)
        self.assertIn("कमेंट कीजिए", tts.comment_cta_script())
        self.assertNotIn("करो", tts.comment_cta_script())


class FactTests(unittest.TestCase):
    def test_structural_duplicate_blocks_without_llm(self):
        calls = []

        def complete(system, user):
            calls.append(user)
            return "{}"

        q = _q(opts=["लिवर", "लिवर", "किडनी", "फेफड़ा"])
        got = quality.fact_check([q], complete)
        self.assertFalse(got["ok"])
        self.assertEqual(got["source"], "structural")
        self.assertEqual(calls, [])

    def test_ans_out_of_range(self):
        got = quality.fact_check([_q(ans=4)], quality.agreeing_complete)
        self.assertFalse(got["ok"])
        self.assertEqual(got["source"], "structural")

    def test_agree_passes(self):
        got = quality.fact_check([_q(), _q("g2", ans=0)], quality.agreeing_complete)
        self.assertTrue(got["ok"])
        self.assertEqual(got["score"], 100)

    def test_model_disagrees(self):
        def complete(system, user):
            return json.dumps({"items": [{
                "id": "g1", "choice": 0, "ambiguous": False,
                "explanation_ok": True, "note": "nahi",
            }]})

        got = quality.fact_check([_q(ans=1)], complete)
        self.assertFalse(got["ok"])
        self.assertEqual(got["bad_ids"], ["g1"])
        self.assertIn("model chose 0", got["notes"][0])

    def test_ambiguous_or_bad_why_fails(self):
        def amb(system, user):
            return json.dumps({"items": [{
                "id": "g1", "choice": 1, "ambiguous": True, "explanation_ok": True,
            }]})

        def bad_why(system, user):
            return json.dumps({"items": [{
                "id": "g1", "choice": 1, "ambiguous": False, "explanation_ok": False,
            }]})

        self.assertFalse(quality.fact_check([_q()], amb)["ok"])
        self.assertFalse(quality.fact_check([_q()], bad_why)["ok"])

    def test_missing_key_raises_and_does_not_echo_secret(self):
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(quality.FactCheckError) as ctx:
                quality.deepseek_complete("sys", "user")
        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))

    def test_api_error_warns_and_does_not_block(self):
        def missing(system, user):
            raise quality.FactCheckError("DEEPSEEK_API_KEY missing")

        got = quality.fact_check([_q()], missing)
        self.assertTrue(got["ok"])
        self.assertEqual(got["score"], 100)
        self.assertTrue(got["warn"])
        self.assertEqual(got["bad_ids"], [])
        self.assertTrue(got["notes"][0].startswith("WARN:"))

        def http(system, user):
            raise quality.FactCheckError("DeepSeek HTTP 500")

        got = quality.fact_check([_q()], http)
        self.assertTrue(got["ok"])
        self.assertIn("HTTP 500", got["notes"][0])

        def garbage(system, user):
            return "not json at all"

        got = quality.fact_check([_q()], garbage)
        self.assertTrue(got["ok"])
        self.assertTrue(got["warn"])
        self.assertEqual(got["bad_ids"], [])

        q = _state_q()
        hook = "बताइए: कच्छ रण राज्य"
        pre = quality.precheck([q], hook, hook, None, missing)
        self.assertNotIn("fact", pre["failures"])
        self.assertTrue(pre["pass_content"])
        self.assertTrue(pre["fact"]["warn"])

    def test_http_error_hides_key(self):
        import requests
        secret = "super-secret-key-value"
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": secret}):
            with mock.patch("requests.post", side_effect=requests.ConnectionError(secret)):
                with self.assertRaises(quality.FactCheckError) as ctx:
                    quality.deepseek_complete("sys", "user")
        self.assertNotIn(secret, str(ctx.exception))


class TrendPacingTests(unittest.TestCase):
    def test_missing_trends_are_neutral(self):
        score, notes = quality.score_trend([_q()], None)
        self.assertGreaterEqual(score, quality.THRESHOLDS["trend"], notes)
        self.assertTrue(any("absent" in n for n in notes))

    def test_absent_file(self):
        missing = C.DATA / "does-not-exist-trends.json"
        self.assertIsNone(quality.load_trends(missing))

    def test_hindi_trend_miss_fails(self):
        score, _ = quality.score_trend([_q(sub="विज्ञान")], {"topics": ["क्रिकेट विश्व कप"]})
        self.assertLess(score, quality.THRESHOLDS["trend"])

    def test_subject_alias_matches(self):
        score, notes = quality.score_trend(
            [_q(sub="भारत", text="कच्छ का रण किस राज्य में है?")],
            {"keywords": ["india gk", "bharat quiz"]},
        )
        self.assertGreaterEqual(score, quality.THRESHOLDS["trend"], notes)

    def test_pacing_window(self):
        good, _ = quality.score_pacing(36)
        near, _ = quality.score_pacing(42)
        bad, _ = quality.score_pacing(55)
        self.assertEqual(good, 100)
        self.assertGreaterEqual(near, 70)
        self.assertLess(bad, 70)


class VisualFontTests(unittest.TestCase):
    def test_hind_has_latin_and_devanagari(self):
        import render
        info = render.font_report()
        self.assertTrue(info["font_latin"], info)
        self.assertTrue(info["font_devanagari"], info)
        self.assertIn("Hind", info["font_path"])
        self.assertGreaterEqual(info["timer_radius"], 96)

    def test_noto_devanagari_rejected_for_latin(self):
        import render
        noto = Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf")
        if not noto.exists():
            self.skipTest("system Noto Devanagari not installed")
        self.assertFalse(render._font_ok(noto))

    def test_map_for_state_question_only(self):
        import indiamap
        state = _q(
            qid="g044", sub="भारत", ans=0,
            text="कच्छ का रण किस राज्य में है?",
            opts=["गुजरात", "राजस्थान", "महाराष्ट्र", "मध्य प्रदेश"],
            why="रण गुजरात में है।",
        )
        names = indiamap.for_question(state)
        self.assertEqual(names[0], "गुजरात")
        self.assertIsNone(indiamap.for_question(_q()))

    def test_reveal_highlights_state(self):
        import indiamap
        from PIL import Image
        box = (10, 10, 390, 470)
        img = Image.new("RGB", (400, 480), (0, 0, 0))
        indiamap.draw(img, box, ["गुजरात", "राजस्थान"], correct=None)
        plain = img.getpixel(indiamap.locate(box, "गुजरात"))
        img2 = Image.new("RGB", (400, 480), (0, 0, 0))
        indiamap.draw(img2, box, ["गुजरात", "राजस्थान"], correct="गुजरात")
        marked = img2.getpixel(indiamap.locate(box, "गुजरात"))
        self.assertEqual(plain, indiamap.PLAIN_FILL)
        self.assertEqual(marked, indiamap.ANSWER_FILL)
        self.assertNotEqual(plain, marked)

    def test_map_does_not_highlight_answer_before_reveal(self):
        """Timer/question frame: correct state is the same colour as every other state."""
        import indiamap
        import render
        from PIL import Image
        q = _state_q()
        opts = ["गुजरात", "राजस्थान", "महाराष्ट्र", "मध्य प्रदेश"]
        box = (10, 10, 390, 470)
        plain = Image.new("RGB", (400, 480), (0, 0, 0))
        indiamap.draw(plain, box, opts, correct=None)
        colours = {name: plain.getpixel(indiamap.locate(box, name)) for name in opts}
        colours["केरल"] = plain.getpixel(indiamap.locate(box, "केरल"))
        self.assertEqual(set(colours.values()), {indiamap.PLAIN_FILL}, colours)
        gold = (245, 197, 66)
        self.assertNotIn(gold, plain.getdata())
        self.assertNotIn(indiamap.ANSWER_FILL, plain.getdata())

        revealed = Image.new("RGB", (400, 480), (0, 0, 0))
        indiamap.draw(revealed, box, opts, correct="गुजरात")
        self.assertEqual(revealed.getpixel(indiamap.locate(box, "गुजरात")), indiamap.ANSWER_FILL)
        self.assertEqual(revealed.getpixel(indiamap.locate(box, "राजस्थान")), indiamap.PLAIN_FILL)
        self.assertEqual(revealed.getpixel(indiamap.locate(box, "महाराष्ट्र")), indiamap.PLAIN_FILL)

        panel, _ = render.question_panel(q, 1, 2, highlight=None)
        panel = panel.convert("RGB")
        self.assertEqual(sum(1 for p in panel.getdata() if p == indiamap.ANSWER_FILL), 0)
        self.assertEqual(sum(1 for p in panel.getdata() if p == gold), 0)
        rev = render.reveal_at(q, 1, 2, 1.0).convert("RGB")
        self.assertGreater(sum(1 for p in rev.getdata() if p == indiamap.ANSWER_FILL), 40)

    def test_visual_score_fails_closed_without_font(self):
        score, _ = quality.score_visual(
            {"font_latin": False, "font_devanagari": True, "timer_radius": 120,
             "option_font": 64, "why_on_reveal": True, "reveal_highlight": True,
             "comment_cta": True, "map_ids": []},
            [_q()],
        )
        self.assertLess(score, quality.THRESHOLDS["visual"])


class SeoAndPlanTests(unittest.TestCase):
    def test_description_has_comment_cta(self):
        qs = [_q(), _q("g2", ans=2, text="इंद्रधनुष में कितने रंग?", sub="विज्ञान")]
        m = seo.build(qs, "noon", datetime(2026, 9, 30))
        self.assertIn("अपना जवाब कमेंट कीजिए", m["description"])
        self.assertIn("कमेंट कीजिए", m["pinned_comment"])
        self.assertIs(m["made_for_kids"], False)
        self.assertNotIn("जवाब:", m["pinned_comment"])

    def test_plan_lands_near_thirty_to_forty(self):
        import build
        bank = json.loads((C.DATA / "questions.json").read_text(encoding="utf-8"))
        by = {q["id"]: q for q in bank}
        questions = [by["g044"], by["g012"]]

        def fake_say(text, tag=""):
            words = max(len(text.split()), 1)
            dur = max(0.8, words / 1.9)
            return Path("unused.wav"), dur, "silent"

        with mock.patch.object(tts, "say", side_effect=fake_say):
            segs = build.plan_segments(questions, "8 सेकंड में जवाब दीजिए!")
            dur = build.tighten(segs, C.LENGTH_MAX_SECONDS)
        kinds = [s["kind"] for s in segs]
        self.assertEqual(kinds[0], "hook")
        self.assertEqual(kinds[-1], "comment")
        self.assertNotIn("cta", kinds)
        self.assertGreaterEqual(dur, 28)
        self.assertLessEqual(dur, 42)
        pacing, _ = quality.score_pacing(dur)
        self.assertGreaterEqual(pacing, quality.THRESHOLDS["pacing"])

    def test_short_why_is_spoken_long_why_is_not(self):
        short = _q(why="पानी नहीं चर्बी।")
        long = _q(why="लिवर का सत्तर प्रतिशत कट जाए तो भी वो दोबारा पूरा बन जाता है।")
        self.assertIn("चर्बी", tts.answer_script(short))
        self.assertNotIn("प्रतिशत", tts.answer_script(long))
        self.assertIn("सही जवाब", tts.answer_script(long))


class ReplacementTests(unittest.TestCase):
    def test_pick_avoiding_skips_banned_ids(self):
        import pick
        bank = []
        subs = ["सामान्य ज्ञान", "विज्ञान", "भारत", "दुनिया"]
        for i, sub in enumerate(subs):
            bank.append(_q(qid=f"q{i}", ans=0, sub=sub, text=f"सवाल {i}?"))
        with tempfile.TemporaryDirectory() as d:
            used = Path(d) / "used.json"
            used.write_text('{"history":[]}', encoding="utf-8")
            with mock.patch.object(pick, "load_bank", lambda: bank), \
                 mock.patch.object(pick, "USED", used):
                got = quality.pick_avoiding(
                    2, "morning", {"q0"}, seed=1, now=datetime(2026, 10, 1))
        ids = [q["id"] for q in got]
        self.assertNotIn("q0", ids)
        self.assertEqual(len(ids), 2)


class HistoryTests(unittest.TestCase):
    def test_append_and_merge(self):
        import sync_state
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "quality_history.jsonl"
            quality.append_history({"pass": True, "hook": "तैयार हैं आप?", "scores": {}}, path)
            quality.append_history({"pass": False, "hook": "x", "scores": {}}, path)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            added = sync_state.new_quality_lines(lines[0], path.read_text(encoding="utf-8"))
            self.assertEqual(len(added), 1)
            merged = sync_state.merge_quality(lines[0] + "\n", added)
            self.assertEqual(merged.strip().splitlines(), lines)


class WorkflowTests(unittest.TestCase):
    def test_upload_workflow_gates_on_deepseek_and_does_not_force_offline(self):
        yml = (Path(__file__).resolve().parents[2] / ".github/workflows/kids-gk-shorts.yml").read_text()
        self.assertIn("DEEPSEEK_API_KEY", yml)
        self.assertIn("src/quality.py", yml)
        self.assertNotIn("QUIZ_QUALITY_OFFLINE", yml)
        sample = (Path(__file__).resolve().parents[2] / ".github/workflows/quiz-tests.yml").read_text()
        self.assertIn("quiz-sample-short", sample)
        self.assertIn("--quality-offline", sample)
        self.assertIn("g044,g012", sample)


if __name__ == "__main__":
    unittest.main()
