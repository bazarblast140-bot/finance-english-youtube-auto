"""python -m unittest discover -s tests   (kids-quiz-shorts/ se). Network nahi."""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pick  # noqa: E402
import propose_questions as pq  # noqa: E402
import trend_research as tr  # noqa: E402

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
KID_BITS = ("कक्षा", "बच्चों", "kids", "school", "स्कूल", "होमवर्क")


class _QuotaError(Exception):
    def __init__(self):
        super().__init__("https://example.invalid/search?key=SUPERSECRET")
        self.resp = type("R", (), {"status": 403})()
        self.content = b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}'


def _cfg(**over):
    cfg = {
        "queries": ["a", "b", "c", "d"],
        "max_search_calls": 4,
        "lookback_days": 7,
        "max_results": 15,
        "region_code": "IN",
        "relevance_language": "hi",
        "budget_config": 800,
        "rss_urls": [],
        "enabled": True,
        "stale_days": 8,
    }
    cfg.update(over)
    return cfg


def _api(vid, views=1000, duration="PT30S", channel="UCzz", title="hindi paheli?",
         hours_ago=24, kids=False, description="pehli line\ndoosri"):
    published = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": vid,
        "snippet": {
            "publishedAt": published,
            "channelId": channel,
            "channelTitle": "Chan",
            "title": title,
            "description": description,
            "thumbnails": {"high": {"url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}},
            "liveBroadcastContent": "none",
        },
        "statistics": {"viewCount": str(views), "likeCount": "3"},
        "contentDetails": {"duration": duration, "definition": "hd"},
        "status": {"madeForKids": kids},
    }


class RankParseTests(unittest.TestCase):
    def test_velocity_floors_brand_new_videos(self):
        self.assertEqual(tr.views_per_day(100, 48), 50)
        self.assertEqual(tr.views_per_day(100, 1), 400)

    def test_rank_by_velocity_then_views(self):
        slow = {"id": "s", "views_per_day": 10, "views": 9999}
        fast = {"id": "f", "views_per_day": 50, "views": 100}
        tied_hi = {"id": "b", "views_per_day": 50, "views": 200}
        tied_lo = {"id": "a", "views_per_day": 50, "views": 200}
        ranked = tr.rank_videos([slow, fast, tied_hi, tied_lo])
        self.assertEqual([v["id"] for v in ranked], ["a", "b", "f", "s"])

    def test_parse_video_and_drop_old(self):
        v = tr.parse_video_item(_api("abc", views=240, hours_ago=24), NOW)
        self.assertEqual(v["duration_s"], 30)
        self.assertEqual(v["views"], 240)
        self.assertAlmostEqual(v["views_per_day"], 240, places=3)
        self.assertEqual(v["description_first"], "pehli line")
        self.assertTrue(v["thumbnail_url"].endswith("/hqdefault.jpg"))
        old = tr.parse_video_item(
            _api("old", hours_ago=24 * 30), NOW,
            not_before=NOW - timedelta(days=8))
        self.assertIsNone(old)

    def test_iso_duration_used_for_long_filter(self):
        self.assertEqual(tr.iso_duration_seconds("PT45S"), 45)
        self.assertEqual(tr.iso_duration_seconds("PT1M30S"), 90)
        self.assertEqual(tr.iso_duration_seconds("nope"), 0)


class QuotaTests(unittest.TestCase):
    def test_budget_math_stays_under_1500(self):
        self.assertEqual(tr.effective_budget(5000), 1200)
        self.assertEqual(tr.plan_search_count(20, 1200, 20), 11)
        self.assertLessEqual(11 * tr.SEARCH_COST + tr.RESERVE_LIST_UNITS, 1500)
        self.assertEqual(tr.plan_search_count(4, 250, 4), 2)
        self.assertEqual(tr.plan_search_count(4, 90, 4), 0)
        cfg = tr.load_trends_cfg()
        self.assertLessEqual(cfg["max_search_calls"], 6)
        self.assertLessEqual(cfg["budget_config"], 1200)
        self.assertEqual(tr.plan_search_count(len(cfg["queries"]), tr.effective_budget(cfg["budget_config"]),
                                              cfg["max_search_calls"]), 4)

    def test_search_kwargs_are_india_hindi_shorts(self):
        kw = tr.search_kwargs("gk quiz in hindi", "2026-09-24T00:00:00Z", _cfg())
        self.assertEqual(kw["type"], "video")
        self.assertEqual(kw["order"], "viewCount")
        self.assertEqual(kw["videoDuration"], "short")
        self.assertEqual(kw["regionCode"], "IN")
        self.assertEqual(kw["relevanceLanguage"], "hi")
        self.assertEqual(kw["publishedAfter"], "2026-09-24T00:00:00Z")

    def test_quota_error_stops_and_hides_key(self):
        calls = []

        def search(q):
            calls.append(q)
            if q == "b":
                raise _QuotaError()
            return ["v" + q]

        def videos(_ids):
            raise AssertionError("list after quota")

        quota = tr.Quota(800)
        got, ran, errors, _filtered = tr.collect_videos(_cfg(), NOW, quota, search, videos, "")
        self.assertEqual(calls, ["a", "b"])
        self.assertEqual(ran, ["a"])
        self.assertEqual(got, [])
        self.assertTrue(quota.api_dead)
        self.assertNotIn("SUPERSECRET", " ".join(errors))
        self.assertIn("quotaExceeded", tr.safe_api_error(_QuotaError()))
        self.assertNotIn("SUPERSECRET", tr.safe_api_error(_QuotaError()))

    def test_local_budget_limits_searches_but_lists_what_it_has(self):
        calls = []

        def search(q):
            calls.append(q)
            return ["v" + q]

        def videos(ids):
            return [_api(i, title="चंद्रयान मिशन विज्ञान") for i in ids]

        quota = tr.Quota(250)
        got, ran, errors, _f = tr.collect_videos(_cfg(), NOW, quota, search, videos, "")
        self.assertEqual(calls, ["a", "b"])
        self.assertEqual(ran, ["a", "b"])
        self.assertLessEqual(quota.spent, 250)
        self.assertEqual(len(got), 2)
        self.assertEqual(errors, [])

    def test_drops_long_and_own_channel(self):
        def search(_q):
            return ["short", "long", "own"]

        def videos(_ids):
            return [
                _api("short", duration="PT20S", title="paheli?"),
                _api("long", duration="PT10M", title="long"),
                _api("own", channel="UCOWN", title="ours"),
            ]

        quota = tr.Quota(800)
        got, _ran, _err, filtered = tr.collect_videos(
            _cfg(queries=["only"], max_search_calls=1), NOW, quota, search, videos, "UCOWN")
        self.assertEqual([v["id"] for v in got], ["short"])
        self.assertGreaterEqual(filtered, 2)

    def test_keyinvalid_is_not_quota(self):
        class E(Exception):
            def __init__(self):
                self.resp = type("R", (), {"status": 403})()
                self.content = b'{"error":{"errors":[{"reason":"keyInvalid"}]}}'
        self.assertFalse(tr.is_quota_error(E()))


class RssTopicTests(unittest.TestCase):
    RSS = """<?xml version="1.0"?>
    <rss xmlns:ht="https://trends.google.com/trending/rss"><channel>
      <item><title>ISRO mission</title><ht:approx_traffic>50,000+</ht:approx_traffic></item>
      <item><title>Bollywood trailer song</title><ht:approx_traffic>500,000+</ht:approx_traffic></item>
      <item><title>Random celebrity</title></item>
    </channel></rss>"""

    def test_parse_and_filter(self):
        items = tr.parse_rss(self.RSS)
        self.assertEqual(items[0]["title"], "ISRO mission")
        self.assertEqual(items[0]["traffic"], 50000)
        kept = [it for it in items if tr.gk_relevant(it["title"])]
        self.assertEqual([it["title"] for it in kept], ["ISRO mission"])
        self.assertFalse(tr.gk_relevant("Bollywood trailer song"))
        self.assertFalse(tr.gk_relevant("Random celebrity"))

    def test_bad_xml_and_topics_from_titles(self):
        with self.assertRaises(Exception):
            tr.parse_rss("<nope")
        videos = [
            tr.parse_video_item(_api("1", views=5000, title="चंद्रयान मिशन विज्ञान", hours_ago=24), NOW),
            tr.parse_video_item(_api("2", views=4000, title="चंद्रयान और इसरो", channel="UC2", hours_ago=48), NOW),
        ]
        topics = tr.extract_topics(videos, [{"title": "ISRO mission", "traffic": 1000, "origin": "google_trends"}])
        kinds = {(t["kind"], t["topic"]) for t in topics}
        self.assertIn(("subject", "विज्ञान"), kinds)
        self.assertTrue(any(t["kind"] == "keyword" and "चंद्रयान" in t["topic"] for t in topics))
        self.assertTrue(any(t["topic"] == "ISRO mission" for t in topics))
        merged = tr.merge_topic_history(
            {"topics": [{"kind": "subject", "topic": "विज्ञान", "first_seen": "2026-09-01",
                         "dates": ["2026-09-01", "2020-01-01"]}]},
            [t for t in topics if t["topic"] == "विज्ञान"], NOW)
        self.assertEqual(merged[0]["first_seen"], "2026-09-01")
        self.assertIn("2026-10-01", merged[0]["dates"])
        self.assertNotIn("2020-01-01", merged[0]["dates"])


class WeightTests(unittest.TestCase):
    def test_score_does_not_let_subject_drown_keyword(self):
        trends = {"topics": [
            {"kind": "subject", "topic": "भारत", "score": 99999},
            {"kind": "keyword", "topic": "चंद्रयान", "score": 3},
        ]}
        self.assertAlmostEqual(tr.question_trend_score(
            {"sub": "भारत", "q": "राजधानी क्या है?", "topic": ""}, trends), 0.35)
        self.assertAlmostEqual(tr.question_trend_score(
            {"sub": "विज्ञान", "q": "चंद्रयान कहाँ उतरा?", "topic": ""}, trends), 0.65)
        self.assertAlmostEqual(tr.question_trend_score(
            {"sub": "भारत", "q": "चंद्रयान कहाँ उतरा?", "topic": ""}, trends), 1.0)
        self.assertEqual(tr.question_trend_score(
            {"sub": "पहेली", "q": "आँख है पर देख नहीं सकती", "topic": ""}, trends), 0.0)
        self.assertEqual(tr.question_trend_score({"sub": "भारत", "q": "x", "topic": ""}, None), 0.0)
        # subject sirf exact sub match — sawaal ke text mein 'भारत' kaafi nahi
        only_sub = {"topics": [{"kind": "subject", "topic": "भारत", "score": 10}]}
        self.assertEqual(tr.question_trend_score(
            {"sub": "विज्ञान", "q": "भारत का उपग्रह", "topic": ""}, only_sub), 0.0)

    def test_ascii_keyword_needs_a_boundary(self):
        trends = {"topics": [{"kind": "keyword", "topic": "rbi", "score": 5}]}
        self.assertEqual(tr.question_trend_score(
            {"sub": "भारत", "q": "arbitration study kya hai?", "topic": ""}, trends), 0.0)
        self.assertAlmostEqual(tr.question_trend_score(
            {"sub": "भारत", "q": "RBI ki sthapna kab hui?", "topic": ""}, trends), 0.65)

    def test_weighted_shuffle_prefers_heavier_item(self):
        rng = random.Random(0)
        first = 0
        for _ in range(400):
            out = tr.weighted_shuffle(["a", "b"], [1.0, 4.0], rng)
            self.assertEqual(sorted(out), ["a", "b"])
            if out[0] == "b":
                first += 1
        self.assertGreater(first, 280)

    def test_missing_stale_and_bad_trends(self):
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "nope.json"
            self.assertIsNone(tr.load_active_trends(NOW, missing))
            bad = Path(d) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            self.assertIsNone(tr.load_active_trends(NOW, bad))
            stale = Path(d) / "old.json"
            old = (NOW - timedelta(days=30)).isoformat()
            stale.write_text(json.dumps({"generated_at": old, "topics": [{"topic": "भारत"}]}), encoding="utf-8")
            self.assertIsNone(tr.load_active_trends(NOW, stale))
            fresh = Path(d) / "new.json"
            fresh.write_text(json.dumps({"generated_at": NOW.isoformat(), "topics": []}), encoding="utf-8")
            self.assertIsNotNone(tr.load_active_trends(NOW, fresh))

    def test_picker_does_not_resurrect_hot_question(self):
        bank = [
            {"id": "hot1", "sub": "पहेली", "q": "चंद्रयान वाली पहेली क्या है?",
             "opts": ["a", "b", "c", "d"], "ans": 0, "why": "x"},
            {"id": "f1", "sub": "पहेली", "q": "pehli taza paheli kya hai?",
             "opts": ["a", "b", "c", "d"], "ans": 0, "why": "x"},
            {"id": "f2", "sub": "पहेली", "q": "doosri taza paheli kya hai?",
             "opts": ["a", "b", "c", "d"], "ans": 0, "why": "x"},
        ]
        trends = {
            "generated_at": NOW.isoformat(),
            "topics": [{"kind": "keyword", "topic": "चंद्रयान", "score": 50}],
        }
        with tempfile.TemporaryDirectory() as d:
            used = Path(d) / "used.json"
            used.write_text(json.dumps({"history": [{"id": "hot1", "at": "2026-09-30T12:00:00"}]}), encoding="utf-8")
            path = Path(d) / "trends.json"
            path.write_text(json.dumps(trends), encoding="utf-8")
            with mock.patch.object(pick, "load_bank", lambda: bank), \
                 mock.patch.object(pick, "USED", used), \
                 mock.patch.object(tr, "TRENDS_PATH", path):
                chosen = [q["id"] for q in pick.pick(2, dry_run=True, seed=1, slot="paheli", now=NOW.replace(tzinfo=None))]
        self.assertNotIn("hot1", chosen)
        self.assertEqual(sorted(chosen), ["f1", "f2"])

    def test_stale_trends_file_leaves_cooldown_alone(self):
        bank = [
            {"id": "old", "sub": "पहेली", "q": "purani", "opts": ["a", "b", "c", "d"], "ans": 0, "why": "x"},
            {"id": "mid", "sub": "पहेली", "q": "beech", "opts": ["a", "b", "c", "d"], "ans": 0, "why": "x"},
        ]
        with tempfile.TemporaryDirectory() as d:
            used = Path(d) / "used.json"
            used.write_text(json.dumps({"history": [
                {"id": "old", "at": "2026-08-01T00:00:00"},
                {"id": "mid", "at": "2026-08-20T00:00:00"},
            ]}), encoding="utf-8")
            path = Path(d) / "trends.json"
            path.write_text(json.dumps({
                "generated_at": "2026-01-01T00:00:00+00:00",
                "topics": [{"kind": "keyword", "topic": "beech", "score": 99}],
            }), encoding="utf-8")
            with mock.patch.object(pick, "load_bank", lambda: bank), \
                 mock.patch.object(pick, "USED", used), \
                 mock.patch.object(tr, "TRENDS_PATH", path):
                chosen = [q["id"] for q in pick.pick(1, dry_run=True, seed=1, slot="paheli", now=NOW.replace(tzinfo=None))]
        self.assertEqual(chosen, ["old"])


class ReportTests(unittest.TestCase):
    def test_week_filename_and_hinglish_report(self):
        self.assertEqual(tr.report_path(datetime(2026, 1, 1, tzinfo=timezone.utc)).name, "trends-2026-01.md")
        self.assertEqual(tr.report_path(NOW).name, "trends-2026-40.md")
        doc = tr.build_document(
            [tr.parse_video_item(_api("v", views=800, title="8 सेकंड में पहेली?", description="जवाब अंत में"), NOW)],
            [], _cfg(), NOW, tr.Quota(800), ["gk quiz in hindi"], [], 0,
            {"channel_id": "UCx", "window_days": 7, "videos": 4, "median_views": 15,
             "median_views_per_day": 2.0},
            {}, None, "")
        text = tr.render_report(doc, NOW)
        self.assertIn("hafte 2026-W40", text)
        self.assertIn("frames nahi dikhte", text)
        self.assertIn("Hamara channel", text)
        self.assertIn(tr.POLICY, text)
        low = text.lower()
        for bad in KID_BITS:
            self.assertNotIn(bad, low)
        self.assertIn(8, doc["timer_and_reveal"]["seconds_mentioned"])
        self.assertTrue(doc["visual_notes"]["thumbnail_sample"])
        self.assertFalse(doc["quota"]["exhausted"])
        self.assertLess(doc["quota"]["typical_day_units"], 1500)

    def test_exhausted_empty_does_not_wipe_previous(self):
        quota = tr.Quota(800)
        quota.mark_api_quota("search")
        doc = tr.build_document([], [], _cfg(), NOW, quota, [], ["HTTP 403 quotaExceeded"], 0,
                                {"videos": 0}, {}, {"topics": [{"topic": "purana"}]}, "")
        self.assertFalse(tr.useful(doc))
        self.assertFalse(tr.should_replace(doc, {"topics": [{"topic": "purana"}]}))
        self.assertTrue(tr.should_replace(doc, None))


class ProposeTests(unittest.TestCase):
    def setUp(self):
        self.bank = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))

    def test_catalog_shape_and_not_already_in_bank(self):
        subs = {"सामान्य ज्ञान", "विज्ञान", "भारत", "दुनिया", "पहेली"}
        for entry in pq.CATALOG:
            self.assertEqual(len(entry["opts"]), 4, entry["catalog_id"])
            self.assertEqual(len(set(entry["opts"])), 4, entry["catalog_id"])
            self.assertIn(entry["ans"], range(4), entry["catalog_id"])
            self.assertIn(entry["sub"], subs)
            blob = (entry["q"] + entry["why"] + " ".join(entry["opts"])).lower()
            for bad in KID_BITS:
                self.assertNotIn(bad, blob, entry["catalog_id"])
            self.assertFalse(pq.overlaps_bank(entry, self.bank), entry["catalog_id"])

    def test_keyword_proposes_rbi_and_gap_without_inventing(self):
        trends = {"topics": [
            {"kind": "keyword", "topic": "rbi monetary policy", "score": 12},
            {"kind": "keyword", "topic": "क्वांटम कंप्यूटर", "score": 4},
            {"kind": "keyword", "topic": "चंद्रयान", "score": 9},
            {"kind": "subject", "topic": "भारत", "score": 100},
        ]}
        cands, gaps = pq.select_proposals(trends, self.bank, NOW)
        ids = [c["catalog_id"] for c in cands]
        self.assertIn("rbi-1935", ids)
        self.assertNotIn("paheli-nayan", ids)
        self.assertTrue(all(c["sub"] != "पहेली" for c in cands))
        for c in cands:
            self.assertFalse(c["add_to_bank"])
            self.assertEqual(c["status"], "needs_review")
        self.assertTrue(any(g["topic"] == "क्वांटम कंप्यूटर" and "opts" not in g for g in gaps))
        self.assertFalse(any(g["topic"] == "चंद्रयान" for g in gaps))
        # sirf subject 'भारत' catalog ko nahi kholta
        only = {"topics": [{"kind": "subject", "topic": "भारत", "score": 100}]}
        c2, g2 = pq.select_proposals(only, self.bank, NOW)
        self.assertEqual(c2, [])
        self.assertEqual(g2, [])

    def test_paheli_subject_can_propose_riddle(self):
        trends = {"topics": [{"kind": "subject", "topic": "पहेली", "score": 20}]}
        cands, _gaps = pq.select_proposals(trends, self.bank, NOW)
        self.assertTrue(cands)
        self.assertTrue(all(c["sub"] == "पहेली" for c in cands))

    def test_rejected_row_is_kept(self):
        new = pq.make_candidate(pq.CATALOG[0], {"topic": "rbi", "score": 1}, NOW)
        prev = {"candidates": [{"catalog_id": "rbi-1935", "status": "rejected", "q": "mat daalna"}], "gaps": []}
        merged = pq.merge_proposals(prev, [new], [], NOW)
        self.assertEqual(merged["candidates"][0]["status"], "rejected")
        self.assertEqual(merged["candidates"][0]["q"], "mat daalna")
        prev2 = {"candidates": [{"catalog_id": "rbi-1935", "status": "needs_review", "q": "old"}]}
        merged2 = pq.merge_proposals(prev2, [new], [], NOW)
        self.assertEqual(merged2["candidates"][0]["q"], new["q"])

    def test_term_must_sit_inside_topic(self):
        self.assertFalse(pq.topic_matches_term("संविधान", "संविधान सभा"))
        self.assertTrue(pq.topic_matches_term("संविधान सभा की बैठक", "संविधान सभा"))
        self.assertFalse(pq.topic_matches_term("arbitration", "rbi"))
        self.assertTrue(pq.topic_matches_term("rbi policy", "rbi"))

    def test_main_does_not_touch_live_bank(self):
        bank_path = ROOT / "data" / "questions.json"
        before = bank_path.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            trends = d / "trends.json"
            trends.write_text(json.dumps({
                "generated_at": NOW.isoformat(),
                "topics": [{"kind": "keyword", "topic": "rbi policy", "score": 5}],
            }), encoding="utf-8")
            cand = d / "question_candidates.json"
            manifest = d / "trend_manifest.txt"
            with mock.patch.object(tr, "TRENDS_PATH", trends), \
                 mock.patch.object(pq, "CANDIDATES_PATH", cand), \
                 mock.patch.object(tr, "MANIFEST", manifest), \
                 mock.patch.object(pq, "BANK_PATH", bank_path):
                self.assertEqual(pq.main([]), 0)
            saved = json.loads(cand.read_text(encoding="utf-8"))
            self.assertTrue(any(c["catalog_id"] == "rbi-1935" for c in saved["candidates"]))
            self.assertIn("auto-add nahi", saved["policy"])
            self.assertIn("data/question_candidates.json", manifest.read_text(encoding="utf-8"))
        self.assertEqual(bank_path.read_bytes(), before)


class MainSkipTests(unittest.TestCase):
    def test_skips_without_api_key(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("YT_DATA_API_KEY", "RESEARCH_ALLOW_OAUTH")}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "trends.json"
            with mock.patch.dict(os.environ, env, clear=True), \
                 mock.patch.object(tr, "TRENDS_PATH", path):
                self.assertEqual(tr.main(["--force"]), 0)
            self.assertFalse(path.exists())

    def test_refuses_oauth_even_if_client_exists(self):
        with mock.patch.object(tr, "get_client", return_value=(object(), "oauth")):
            self.assertEqual(tr.main(["--force"]), 0)


class WorkflowTests(unittest.TestCase):
    def test_workflow_is_scheduled_and_quota_safe(self):
        text = (REPO / ".github" / "workflows" / "quiz-trends.yml").read_text(encoding="utf-8")
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("YT_DATA_API_KEY", text)
        self.assertIn("sync_state.py", text)
        self.assertIn("--text-files false", text)
        self.assertNotIn("YOUTUBE_REFRESH_TOKEN", text)
        self.assertNotIn("YOUTUBE_CLIENT", text)
        self.assertNotIn("RESEARCH_ALLOW_OAUTH", text)
        tests = (REPO / ".github" / "workflows" / "quiz-tests.yml").read_text(encoding="utf-8")
        self.assertIn("quiz-trends.yml", tests)
        self.assertIn("unittest discover", tests)


class SyncExtraTests(unittest.TestCase):
    def test_rejects_parent_path(self):
        with self.assertRaises(SystemExit):
            import sync_state as ss
            ss.normalize_extra("../.env")
        import sync_state as ss
        self.assertEqual(ss.normalize_extra("data/trends.json"), "data/trends.json")

    def test_extra_pushes_without_clobbering_last_run(self):
        import sync_state as ss
        if not shutil.which("git"):
            self.skipTest("git nahi")
        src = ROOT / "src"

        def g(cwd, *a):
            return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            g(d, "init", "-q", "--bare", "-b", "main", "remote.git")
            g(d, "clone", "-q", str(d / "remote.git"), "seed")
            seed = d / "seed"
            q = seed / "kq"
            (q / "data").mkdir(parents=True)
            (q / "data" / "used.json").write_text("{}\n", encoding="utf-8")
            (q / "data" / "uploads.json").write_text("[]\n", encoding="utf-8")
            (q / "LAST_RUN.md").write_text("remote-run\n", encoding="utf-8")
            g(seed, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
            g(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")
            g(seed, "push", "-q", "origin", "HEAD:main")
            g(d, "clone", "-q", str(d / "remote.git"), "a")
            a = d / "a" / "kq"
            (a / "LAST_RUN.md").write_text("LOCAL\n", encoding="utf-8")
            (a / "reports").mkdir()
            (a / "reports" / "trends-2026-40.md").write_text("report-body\n", encoding="utf-8")
            env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
            code = subprocess.run(
                [sys.executable, "-c",
                 "import sys, pathlib; sys.path.insert(0, sys.argv[1]); import sync_state as s; "
                 "s.HERE = pathlib.Path(sys.argv[2]); "
                 "sys.exit(s.main(['--message','m','--include-used','false','--text-files','false',"
                 "'--extra','reports/trends-2026-40.md','--attempts','2']))",
                 str(src), str(a)],
                cwd=a, env=env, capture_output=True, text=True)
            self.assertEqual(code.returncode, 0, code.stdout + code.stderr)
            g(d, "clone", "-q", str(d / "remote.git"), "b")
            self.assertEqual((d / "b" / "kq" / "LAST_RUN.md").read_text(encoding="utf-8"), "remote-run\n")
            self.assertEqual((d / "b" / "kq" / "reports" / "trends-2026-40.md").read_text(encoding="utf-8"),
                             "report-body\n")
            self.assertEqual(ss.TEXT_FILES[0], "LAST_RUN.md")


if __name__ == "__main__":
    unittest.main()
