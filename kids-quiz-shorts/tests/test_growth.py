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


# 01-Oct-2026: channel general audience ka hai — ye shabd metadata, hooks,
# CTA ya on-screen text me kabhi nahi aane chahiye.
KID_SIGNALS = ("class 1", "class 5", "class 1-5", "कक्षा", "बच्चे", "बच्चों", "kids",
               "kid ", "school", "homework", "स्कूल", "होमवर्क", "घर वालों", "घर में सबको")


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
            blob += " " + m["title"].lower() + " " + (m["pinned_comment"] or "")
            for bad in KID_SIGNALS + ("90%", "80%"):
                self.assertNotIn(bad.lower(), blob, (slot, bad))
            self.assertIs(m["made_for_kids"], False)

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


class AudienceTests(unittest.TestCase):
    def test_made_for_kids_false(self):
        self.assertIs(C.MADE_FOR_KIDS, False)

    def test_hooks_cta_have_no_kid_signals(self):
        texts = [C.CTA_TEXT] + [t for v in C.HOOK_LINES.values() for t in v] \
            + [t for v in seo.HOOKS.values() for t in v]
        for t in texts:
            for bad in KID_SIGNALS:
                self.assertNotIn(bad.lower(), t.lower(), (t, bad))
            # "आप" register: "करो/लिखो/रुको" jaisa tum-imperative nahi
            for tum in ("करो", "लिखो", "रुको", "बताओ", "पूछो", "खेलो"):
                self.assertNotIn(tum, t, (t, tum))

    def test_upload_status_falls_back_to_not_for_kids(self):
        import upload
        self.assertIs(upload.video_status({}, "public")["selfDeclaredMadeForKids"], False)
        self.assertIs(upload.video_status({"made_for_kids": False}, "public")
                      ["selfDeclaredMadeForKids"], False)


class BankIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.bank = json.loads((C.DATA / "questions.json").read_text(encoding="utf-8"))

    def test_shape(self):
        for q in self.bank:
            self.assertEqual(len(q["opts"]), 4, q["id"])
            self.assertEqual(len(set(q["opts"])), 4, q["id"])
            self.assertIn(q["ans"], range(4), q["id"])
            self.assertTrue(q.get("why"), q["id"])

    def test_no_duplicate_warning(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            pick.load_bank()
        self.assertNotIn("WARNING duplicate", buf.getvalue())

    def test_no_kid_wording_in_questions(self):
        for q in self.bank:
            blob = (q["q"] + " " + " ".join(q["opts"])).lower()
            for bad in ("कक्षा", "class 1", "स्कूल", "होमवर्क", "बच्चों"):
                self.assertNotIn(bad, blob, q["id"])


class HintMaskTests(unittest.TestCase):
    def setUp(self):
        import tts
        self.m = tts.mask_answer

    def q(self, ans, opts=None):
        opts = opts or [ans, "x1", "x2", "x3"]
        return {"opts": opts, "ans": opts.index(ans)}

    def test_short_number_masked(self):
        out = self.m("हर टीम के 11 खिलाड़ी मैदान पर होते हैं।", self.q("11"), "ये")
        self.assertNotIn("11", out)

    def test_number_word_masked(self):
        out = self.m("कुल सात रंग होते हैं।", self.q("7"), "ये")
        self.assertNotIn("सात", out)

    def test_number_inside_bigger_number_kept(self):
        out = self.m("2022 में मंगल के 2 चाँद गिने गए।", self.q("2"), "ये")
        self.assertIn("2022", out)

    def test_inflected_form_masked(self):
        out = self.m("कछुए के ऊपर और नीचे खोल होता है।", self.q("कछुआ"), "ये")
        self.assertNotIn("कछुए", out)

    def test_no_garbled_suffix(self):
        out = self.m("दुनिया का ज़्यादातर दूध गायों से आता है।", self.q("गाय"), "ये")
        self.assertNotIn("येों", out)
        self.assertNotIn("गाय", out)

    def test_multiword_collapses(self):
        out = self.m("सरदार वल्लभभाई पटेल ने रियासतें मिलाईं।",
                     self.q("सरदार वल्लभभाई पटेल"), "ये")
        self.assertNotIn("ये ये", out)
        self.assertNotIn("पटेल", out)

    def test_unit_word_kept(self):
        out = self.m("रोशनी एक सेकंड में 3 लाख किमी चलती है।", self.q("1.3 सेकंड"), "ये")
        self.assertIn("सेकंड", out)


class SecretAndCommentTests(unittest.TestCase):
    def test_gh_secret_uses_stdin_not_body(self):
        import upload
        with mock.patch("subprocess.run") as run:
            upload.set_github_secret_value("YOUTUBE_REFRESH_TOKEN", "tok123")
        args, kw = run.call_args
        cmd = args[0]
        self.assertNotIn("--body", cmd)
        self.assertNotIn("-b", cmd)
        self.assertEqual(cmd[:4], ["gh", "secret", "set", "YOUTUBE_REFRESH_TOKEN"])
        self.assertIn("-R", cmd)
        self.assertEqual(cmd[cmd.index("-R") + 1], "bazarblast140-bot/finance-english-youtube-auto")
        self.assertEqual(kw["input"], b"tok123")
        self.assertNotIn("tok123", " ".join(cmd))

    def _ledger(self, d, rows):
        led = Path(d) / "uploads.json"
        led.write_text(json.dumps(rows), encoding="utf-8")
        return led

    def test_pending_comment_attempts_capped(self):
        import upload
        rows = [{"video_id": "A", "pinned_comment": "x", "publish_at": "2026-01-01T00:00:00Z",
                 "comment_attempts": upload.COMMENT_MAX_ATTEMPTS},
                {"video_id": "B", "pinned_comment": "x", "publish_at": "2026-01-01T00:00:00Z"}]
        with tempfile.TemporaryDirectory() as d:
            led = self._ledger(d, rows)
            with mock.patch.object(upload, "LEDGER", led), \
                 mock.patch.object(upload, "_creds", return_value=mock.MagicMock(token="t")), \
                 mock.patch.object(upload, "granted_scopes", return_value=None), \
                 mock.patch("googleapiclient.discovery.build", create=True), \
                 mock.patch.object(upload, "post_comment", side_effect=RuntimeError("boom")) as pc:
                upload.post_pending_comments()
            self.assertEqual([c.args[1] for c in pc.call_args_list], ["B"])
            saved = json.loads(led.read_text(encoding="utf-8"))
            self.assertEqual(saved[1]["comment_attempts"], 1)

    def test_pending_comments_stop_on_quota(self):
        import upload
        rows = [{"video_id": v, "pinned_comment": "x", "publish_at": "2026-01-01T00:00:00Z"}
                for v in ("A", "B", "C")]
        with tempfile.TemporaryDirectory() as d:
            led = self._ledger(d, rows)
            with mock.patch.object(upload, "LEDGER", led), \
                 mock.patch.object(upload, "_creds", return_value=mock.MagicMock(token="t")), \
                 mock.patch.object(upload, "granted_scopes", return_value=None), \
                 mock.patch("googleapiclient.discovery.build", create=True), \
                 mock.patch.object(upload, "post_comment",
                                   side_effect=RuntimeError("quotaExceeded")) as pc:
                upload.post_pending_comments()
            self.assertEqual(pc.call_count, 1)

    def test_research_does_not_use_upload_oauth_by_default(self):
        import competitor_research as cr
        env = {k: v for k, v in os.environ.items()
               if k not in ("YT_DATA_API_KEY", "RESEARCH_ALLOW_OAUTH")}
        env.update(YT_CLIENT_ID="a", YT_CLIENT_SECRET="b", YT_REFRESH_TOKEN="c")
        with mock.patch.dict(os.environ, env, clear=True):
            yt, how = cr.get_client()
        self.assertIsNone(yt)


class SyncStateTests(unittest.TestCase):
    def test_merges(self):
        import sync_state as ss
        base = {"history": [{"id": "g1", "at": "t1"}]}
        ours = {"history": [{"id": "g1", "at": "t1"}, {"id": "g2", "at": "t2"}]}
        remote = {"history": [{"id": "g1", "at": "t1"}, {"id": "g9", "at": "t3"}]}
        added = ss.new_used_entries(base, ours)
        self.assertEqual(added, [{"id": "g2", "at": "t2"}])
        merged = ss.merge_used(remote, added)
        self.assertEqual([h["id"] for h in merged["history"]], ["g1", "g9", "g2"])
        led_base = [{"video_id": "A", "comment_posted": None}]
        led_ours = [{"video_id": "A", "comment_posted": "now"}, {"video_id": "N"}]
        led_remote = [{"video_id": "A", "comment_posted": None}, {"video_id": "R"}]
        ch = ss.changed_ledger_rows(led_base, led_ours)
        out = ss.merge_ledger(led_remote, ch)
        self.assertEqual([r["video_id"] for r in out], ["A", "R", "N"])
        self.assertEqual(out[0]["comment_posted"], "now")

    def test_push_survives_concurrent_remote_commit(self):
        """Remote par beech me doosre run ka commit aa jaaye — phir bhi dono ke
        used entries bache rahein (30-Sep wala repeat bug)."""
        import shutil
        import subprocess
        if not shutil.which("git"):
            self.skipTest("git nahi")
        src = Path(__file__).resolve().parent.parent / "src"

        def g(cwd, *a):
            return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            g(d, "init", "-q", "--bare", "-b", "main", "remote.git")
            for name in ("a", "b"):
                g(d, "clone", "-q", str(d / "remote.git"), name) if name == "b" else None
            seed = d / "seed"
            g(d, "clone", "-q", str(d / "remote.git"), "seed")
            q = seed / "kq"
            (q / "data").mkdir(parents=True)
            (q / "data" / "used.json").write_text(json.dumps({"history": []}), encoding="utf-8")
            (q / "data" / "uploads.json").write_text("[]", encoding="utf-8")
            for r in (seed,):
                g(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
                g(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")
                g(r, "push", "-q", "origin", "HEAD:main")
            # run A ki working copy
            g(d, "clone", "-q", str(d / "remote.git"), "a")
            a = d / "a" / "kq"
            (a / "data" / "used.json").write_text(json.dumps(
                {"history": [{"id": "g005", "at": "2026-09-30T12:16"}]}), encoding="utf-8")
            (a / "LAST_RUN.md").write_text("# run A", encoding="utf-8")
            # beech me run B ne push kar diya
            b = seed / "kq"
            (b / "data" / "used.json").write_text(json.dumps(
                {"history": [{"id": "g135", "at": "2026-09-30T17:36"}]}), encoding="utf-8")
            g(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "run B")
            g(seed, "push", "-q", "origin", "HEAD:main")
            env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
            code = subprocess.run(
                [sys.executable, "-c",
                 "import sys,pathlib; sys.path.insert(0, sys.argv[1]); import sync_state as s; "
                 "s.HERE = pathlib.Path(sys.argv[2]); "
                 "sys.exit(s.main(['--message','m','--include-used','true','--attempts','2']))",
                 str(src), str(a)],
                cwd=a, env=env, capture_output=True, text=True)
            self.assertEqual(code.returncode, 0, code.stdout + code.stderr)
            g(d / "b", "pull", "-q", "origin", "main")
            hist = json.loads((d / "b" / "kq" / "data" / "used.json").read_text(encoding="utf-8"))
            self.assertEqual({h["id"] for h in hist["history"]}, {"g005", "g135"})
            self.assertEqual((d / "b" / "kq" / "LAST_RUN.md").read_text(encoding="utf-8"), "# run A")


if __name__ == "__main__":
    unittest.main()
