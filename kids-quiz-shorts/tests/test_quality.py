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
        line = "नमक का सफ़ेद रेगिस्तान — किस राज्य में?"
        score, notes = quality.score_hook(line, line, question=q)
        self.assertGreaterEqual(score, 70, notes)
        self.assertFalse(quality.hook_is_keyword_list(line))
        self.assertNotIn("करो", line)
        self.assertNotIn("गुजरात", line)

    def test_keyword_list_hook_penalised(self):
        q = _state_q()
        line = "सोचिए — कच्छ रण राज्य"
        score, notes = quality.score_hook(line, line, question=q)
        self.assertLess(score, 70, notes)
        self.assertTrue(any("keyword-list" in n for n in notes))

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
        self.assertIn("कच्छ का रण", line)
        self.assertIn("किस राज्य", line)
        self.assertNotIn("रण राज्य", line.split("—")[-1])
        self.assertNotIn("गुजरात", line)
        self.assertNotIn("कच्छ रण राज्य", line)
        self.assertNotIn("90%", line)
        self.assertNotIn(line, C.HOOK_LINES["quiz"])
        self.assertFalse(quality.hook_is_keyword_list(line))
        for tum in ("करो", "लिखो", "रुको", "बताओ", "पूछो", "खेलो"):
            self.assertNotIn(tum, line)
        score, notes = quality.score_hook(line, line, question=q)
        self.assertGreaterEqual(score, 70, notes)

    def test_why_lead_in_becomes_a_natural_hook(self):
        q = _state_q()
        q["why"] = "नमक का ये विशाल सफ़ेद रेगिस्तान गुजरात के कच्छ ज़िले में है, जहाँ हर साल रण उत्सव होता है।"
        line = quality.offline_hook(q)
        self.assertEqual(line, "नमक का सफ़ेद रेगिस्तान — किस राज्य में?")
        self.assertNotIn("गुजरात", line)
        score, notes = quality.score_hook(line, line, question=q)
        self.assertGreaterEqual(score, 70, notes)

    def test_offline_hook_falls_back_for_science_question(self):
        import build
        q = _q(text="दुनिया की सबसे तेज़ चीज़ कौन सी है?", opts=["आवाज़", "प्रकाश", "रॉकेट", "हवा"], ans=1,
               why="प्रकाश एक सेकंड में धरती के 7 चक्कर लगा सकता है।")
        line = build.hook_line([q], "morning", datetime(2026, 10, 1))
        self.assertNotIn("प्रकाश", line)
        self.assertIn("तेज़", line)
        self.assertFalse(quality.hook_is_keyword_list(line))
        score, notes = quality.score_hook(line, line, question=q)
        self.assertGreaterEqual(score, 70, notes)

    def test_deepseek_hook_used_and_bad_reply_falls_back(self):
        import build
        q = _state_q()

        def good(system, user):
            self.assertIn("forbidden", user)
            self.assertNotIn("DEEPSEEK", system)
            return json.dumps({"hook": "नमक का सफ़ेद रेगिस्तान — किस राज्य में?"})

        line = build.hook_line([q], "noon", datetime(2026, 10, 1), complete=good)
        self.assertIn("रेगिस्तान", line)

        def leaks(system, user):
            return json.dumps({"hook": "जवाब गुजरात है, बताइए"})

        line = build.hook_line([q], "noon", datetime(2026, 10, 1), complete=leaks)
        self.assertNotIn("गुजरात", line)
        self.assertIn("कच्छ का रण", line)

        def boom(system, user):
            raise quality.FactCheckError("DeepSeek HTTP 500")

        line = build.hook_line([q], "noon", datetime(2026, 10, 1), complete=boom)
        self.assertNotIn("गुजरात", line)
        self.assertGreaterEqual(quality.score_hook(line, line, question=q)[0], 70)

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

    def test_grapheme_safe_typing_order(self):
        import unicodedata
        import hooktype
        self.assertEqual(hooktype.grapheme_clusters("कि"), ["कि"])
        self.assertEqual(hooktype.grapheme_clusters("क्ष"), ["क्ष"])
        self.assertEqual(hooktype.grapheme_clusters("कच्छ"), ["क", "च्छ"])
        fed = hooktype.grapheme_clusters("सफ़ेद")
        self.assertEqual(fed, ["स", "फ़े", "द"])
        self.assertEqual("".join(fed), "सफ़ेद")
        line = "नमक का सफ़ेद रेगिस्तान — किस राज्य में?"
        clusters = hooktype.grapheme_clusters(line)
        self.assertEqual("".join(clusters), line)
        self.assertGreater(len(clusters), 8)
        for cluster in clusters:
            self.assertNotEqual(cluster, "\u094d")
            if len(cluster) == 1:
                self.assertNotIn(unicodedata.category(cluster), ("Mn", "Mc", "Me"))
        self.assertEqual(hooktype.visible_text(line, 0.0), "")
        self.assertEqual(hooktype.visible_text(line, hooktype.TYPE_SECONDS), line)
        self.assertEqual(hooktype.visible_text(line, 2.5), line)
        n = len(clusters)
        last = hooktype.cluster_time(n - 1, n)
        self.assertGreaterEqual(last, 1.2)
        self.assertLessEqual(last, 1.5)
        self.assertAlmostEqual(last, hooktype.TYPE_SECONDS)
        prev = ""
        for i, cluster in enumerate(clusters):
            got = hooktype.visible_text(line, hooktype.cluster_time(i, n))
            self.assertEqual(got, "".join(clusters[: i + 1]))
            self.assertTrue(got.startswith(prev))
            self.assertFalse(got.endswith("\u094d"))
            self.assertTrue(got.endswith(cluster))
            prev = got
        before = hooktype.cluster_time(0, n) - 0.02
        self.assertEqual(hooktype.visible_text(line, before), "")

    def test_final_hook_frame_is_fully_opaque(self):
        import numpy as np
        import render
        line = "नमक का सफ़ेद रेगिस्तान — किस राज्य में?"
        question = "कच्छ का रण किस राज्य में है?"
        box = (80, 250, 1000, 690)

        def ink_count(t):
            img = render.hook_frame(line, question, t)
            self.assertEqual(img.mode, "RGB")
            crop = np.asarray(img.crop(box))
            exact = int(np.all(crop == np.array(render.HOOK_INK), axis=2).sum())
            return exact, crop

        import hooktype
        early, _ = ink_count(0.0)
        mid, _ = ink_count(0.45)
        full, full_px = ink_count(1.5)
        later, later_px = ink_count(2.0)
        end, end_px = ink_count(2.5)
        panel, panel_px = ink_count(hooktype.TYPE_SECONDS)
        self.assertEqual(early, 0)
        self.assertGreater(mid, 200)
        self.assertGreater(full, mid + 400)
        self.assertEqual(full, later)
        self.assertEqual(later, end)
        self.assertEqual(end, panel)
        self.assertTrue(np.array_equal(full_px, later_px))
        self.assertTrue(np.array_equal(later_px, end_px))
        self.assertTrue(np.array_equal(end_px, panel_px))

    def test_hook_audio_contains_click_layer(self):
        import numpy as np
        import build
        import hooktype
        import sfx
        line = "नमक का सफ़ेद रेगिस्तान — किस राज्य में?"
        bed = sfx.keyclick_bed(line, 2.0)
        sr = C.SAMPLE_RATE
        head = bed[: int(1.5 * sr)]
        tail = bed[int(1.55 * sr):]
        self.assertGreater(float(np.max(np.abs(head))), 0.3)
        self.assertLess(float(np.max(np.abs(tail))), 0.05)
        # Voice in this fixture is a steady 0.55. Clicks must sit under it.
        self.assertLess(float(np.max(np.abs(bed))) * C.KEYCLICK_VOLUME, 0.55)
        clusters = hooktype.grapheme_clusters(line)
        click = sfx.key_click()
        self.assertGreater(len(click), 100)
        for i, cluster in enumerate(clusters):
            if cluster.isspace():
                continue
            start = int(hooktype.cluster_time(i, len(clusters)) * sr)
            window = bed[start:start + min(len(click), 200)]
            self.assertGreater(float(np.max(np.abs(window))), 0.2, cluster)
        voice = np.full(int(2.2 * sr), 0.55, dtype=np.float32)
        folder = Path(tempfile.mkdtemp())
        path = folder / "voice.wav"
        sfx.write_wav(path, voice)
        frames = round(2.0 * C.FPS)

        def seg(audio):
            return {"kind": "hook", "frames": frames, "audio": audio, "hook": line,
                    "payload": ({}, 1, 1)}

        with_clicks = build.render_audio([seg([
            (0.0, str(path), C.VOICE_VOLUME),
            (0.0, "KEYCLICKS", C.KEYCLICK_VOLUME),
        ])], frames)
        voice_only = build.render_audio([seg([
            (0.0, str(path), C.VOICE_VOLUME),
        ])], frames)
        self.assertGreater(float(np.max(np.abs(with_clicks - voice_only))), 0.01)


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
        hook = "कच्छ का रण — किस राज्य में?"
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
        lic = (C.ASSETS / "maps" / "LICENSE.txt").read_text(encoding="utf-8")
        self.assertIn("public domain", lic.lower())
        self.assertIn("Natural Earth", lic)
        geo = C.ASSETS / "maps" / "india_states.geojson"
        self.assertLess(geo.stat().st_size, 80_000)
        self.assertIn("गुजरात", geo.read_text(encoding="utf-8"))

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

        wide = (20, 20, 560, 540)
        sheet = Image.new("RGB", (580, 560), (0, 0, 0))
        indiamap.draw(sheet, wide, opts, correct=None)
        self.assertGreaterEqual(indiamap.ink_width(wide), 400)
        panel, opt_end = render.question_panel(q, 1, 2, highlight=None)
        panel = panel.convert("RGB")
        self.assertGreaterEqual(render.map_ink_width(panel), 400)
        self.assertGreater(opt_end, 1300)
        self.assertLess(opt_end, render.SAFE_BOTTOM - 60)
        self.assertEqual(sum(1 for p in panel.getdata() if p == indiamap.ANSWER_FILL), 0)
        self.assertEqual(sum(1 for p in panel.getdata() if p == gold), 0)
        self.assertLess(render.visual_slot(400)["bottom"], 1200)
        rev = render.reveal_at(q, 1, 2, 1.0).convert("RGB")
        box = indiamap.LAST_LAYOUT["box"]
        x0, y0, x1, y1 = [int(v) for v in box]
        greens = [(x, y) for y in range(y0, y1, 2) for x in range(x0, x1, 2)
                  if rev.getpixel((x, y)) == indiamap.ANSWER_FILL]
        self.assertGreater(len(greens), 80)
        outside = [p for p in greens if not indiamap.covers("गुजरात", p[0], p[1])]
        self.assertLess(len(outside) / len(greens), 0.04, "green fill left the state outline")
        gx, gy = indiamap.locate(box, "गुजरात")
        self.assertEqual(rev.getpixel((gx, gy)), indiamap.ANSWER_FILL)

    def test_science_question_gets_an_icon_card(self):
        import render
        q = _q()
        panel, opt_end = render.question_panel(q, 1, 2)
        panel = panel.convert("RGB")
        self.assertIsNone(__import__("indiamap").for_question(q))
        ink = sum(1 for p in panel.getdata() if p == render.ICON_INK)
        self.assertGreater(ink, 80, "science frame should draw an icon, not a blank card")
        self.assertEqual(render.map_ink_width(panel), 0)
        self.assertLess(opt_end, render.SAFE_BOTTOM)
        # Options sit in the lower half, still above the Shorts overlay.
        self.assertGreater(opt_end, 1200)

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
        self.assertIn("KEYCLICKS", [src for _, src, _ in segs[0]["audio"]])
        self.assertGreaterEqual(segs[0]["dur"], C.HOOK_SECONDS)
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
