"""python -m unittest discover -s tests   (kids-quiz-shorts/ se). Network nahi chahiye."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import channel_settings as cs  # noqa: E402

CFG_PATH = ROOT / "channel" / "channel_profile.json"


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = cs.load_config(CFG_PATH)
        self.prop = cs.proposed_channel(self.cfg)

    def test_committed_config_is_valid(self):
        self.assertEqual(cs.validate(self.prop), [])
        self.assertLessEqual(len(self.prop["description"]), 1000)

    def test_description_includes_about_links(self):
        d = self.prop["description"]
        self.assertIn("https://www.instagram.com/quizpathshala2/", d)
        self.assertIn("https://www.facebook.com/reel.mania/", d)
        self.assertIn("https://www.youtube.com/@QuizPathshalaIndia", d)

        self.assertLessEqual(len(self.prop["keywords"]), 500)

    def test_general_audience(self):
        self.assertIs(self.cfg["status"]["selfDeclaredMadeForKids"], False)
        self.assertEqual(self.prop["defaultLanguage"], "hi")
        self.assertEqual(self.cfg["channel_id"], "UCSIJMHyB_h02gHc5HZkmYqg")
        self.assertEqual(self.cfg["expected_title"], "QUIZ PATHSHALA")
        low = self.prop["description"].lower()
        for bad in ("बच्च", "class 1", "school", "स्कूल", "kids"):
            self.assertNotIn(bad, low)

    def test_keywords_multiword_quoted(self):
        kw = self.prop["keywords"]
        self.assertEqual(kw.count('"') % 2, 0)
        self.assertIn('"gk quiz hindi"', kw)


class ValidateTests(unittest.TestCase):
    def test_too_long_and_angle_brackets(self):
        errs = cs.validate({"description": "x" * 1001, "keywords": "k" * 501})
        self.assertEqual(len(errs), 2)
        self.assertTrue(cs.validate({"description": "a <b> c"}))
        self.assertTrue(cs.validate({"keywords": '"gk quiz'}))
        self.assertEqual(cs.validate({"description": "ok", "keywords": '"gk quiz" ssc'}), [])


class MergeTests(unittest.TestCase):
    def test_carries_over_unmanaged_and_keeps_title(self):
        current = {"title": "QUIZ PATHSHALA", "description": "old", "keywords": "old",
                   "unsubscribedTrailer": "abc123def45", "trackingAnalyticsAccountId": "UA-1",
                   "country": "IN"}
        proposed = {"title": "HACKED", "description": "new", "keywords": '"gk quiz"',
                    "defaultLanguage": "hi", "country": "IN"}
        m = cs.merge_channel(current, proposed)
        self.assertEqual(m["title"], "QUIZ PATHSHALA")
        self.assertEqual(m["unsubscribedTrailer"], "abc123def45")
        self.assertEqual(m["trackingAnalyticsAccountId"], "UA-1")
        self.assertEqual(m["description"], "new")
        self.assertEqual(m["defaultLanguage"], "hi")

    def test_empty_current(self):
        m = cs.merge_channel({}, {"description": "d", "keywords": "k"})
        self.assertNotIn("title", m)
        self.assertEqual(m, {"description": "d", "keywords": "k"})

    def test_drops_unknown_current_fields(self):
        m = cs.merge_channel({"title": "T", "moderateComments": True}, {"description": "d"})
        self.assertNotIn("moderateComments", m)


class DiffAndScopeTests(unittest.TestCase):
    def test_field_diffs(self):
        d = cs.field_diffs({"description": "a", "keywords": "k", "selfDeclaredMadeForKids": None},
                           {"description": "b", "keywords": "k", "selfDeclaredMadeForKids": False})
        self.assertIn("description", d)
        self.assertNotIn("keywords", d)
        self.assertIn("selfDeclaredMadeForKids", d)

    def test_scopes(self):
        self.assertFalse(cs.has_write_scope({"https://www.googleapis.com/auth/youtube.upload",
                                             "https://www.googleapis.com/auth/youtube.readonly"}))
        self.assertTrue(cs.has_write_scope({"https://www.googleapis.com/auth/youtube.force-ssl"}))
        self.assertTrue(cs.has_write_scope({"https://www.googleapis.com/auth/youtube"}))
        self.assertIsNone(cs.has_write_scope(None))

    def test_scope_error_detection(self):
        txt = json.dumps({"error": {"errors": [{"reason": "insufficientPermissions"}],
                                    "message": "Request had insufficient authentication scopes."}})
        self.assertTrue(cs.is_scope_error(403, txt))
        self.assertFalse(cs.is_scope_error(400, txt))
        self.assertFalse(cs.is_scope_error(403, '{"error":{"errors":[{"reason":"channelForbidden"}]}}'))


# ------------------------------------------------------------- flow (stubbed)
import io  # noqa: E402
import types  # noqa: E402
from contextlib import redirect_stdout  # noqa: E402
from unittest import mock  # noqa: E402


class _HttpError(Exception):
    def __init__(self, status, content):
        super().__init__(status)
        self.resp = types.SimpleNamespace(status=status)
        self.content = content


class _Req:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class _Channels:
    def __init__(self, title="QUIZ PATHSHALA", fail=None):
        self.title, self.fail, self.calls = title, fail, []

    def list(self, **kw):
        self.calls.append(("list", kw["part"]))
        return _Req(lambda: {"items": [{
            "id": "UCSIJMHyB_h02gHc5HZkmYqg",
            "snippet": {"title": self.title},
            "brandingSettings": {"channel": {"title": self.title, "description": "old",
                                             "unsubscribedTrailer": "vid12345678"}},
            "status": {"madeForKids": False}}]})

    def update(self, part, body):
        self.calls.append(("update", part, body))

        def run():
            if self.fail and part in self.fail:
                status, reason = self.fail[part]
                raise _HttpError(status, json.dumps({"error": {"errors": [{"reason": reason}],
                                 "message": "Request had insufficient authentication scopes."
                                 if reason == "insufficientPermissions" else reason}}).encode())
            return {}
        return _Req(run)


class FlowTests(unittest.TestCase):
    def run_main(self, mode, chans, scopes):
        yt = types.SimpleNamespace(channels=lambda: chans)
        mods = {"googleapiclient": types.ModuleType("googleapiclient"),
                "googleapiclient.discovery": types.ModuleType("googleapiclient.discovery"),
                "googleapiclient.errors": types.ModuleType("googleapiclient.errors")}
        mods["googleapiclient.discovery"].build = lambda *a, **k: yt
        mods["googleapiclient.errors"].HttpError = _HttpError
        out = io.StringIO()
        with mock.patch.dict(sys.modules, mods), \
                mock.patch.object(cs, "get_creds", lambda: types.SimpleNamespace(token="x")), \
                mock.patch.object(cs, "granted_scopes", lambda c: scopes), redirect_stdout(out):
            rc = cs.main(["--mode", mode, "--config", str(CFG_PATH)])
        return rc, out.getvalue()

    FULL = {"https://www.googleapis.com/auth/youtube"}
    UPLOAD_ONLY = {"https://www.googleapis.com/auth/youtube.upload",
                   "https://www.googleapis.com/auth/youtube.readonly"}

    def test_dry_run_never_writes(self):
        ch = _Channels()
        rc, out = self.run_main("dry-run", ch, self.UPLOAD_ONLY)
        self.assertEqual(rc, 0)
        self.assertFalse([c for c in ch.calls if c[0] == "update"])
        self.assertIn("needs re-auth with youtube.force-ssl", out)

    def test_wrong_channel_aborts(self):
        ch = _Channels(title="The Money Rule")
        rc, out = self.run_main("apply", ch, self.FULL)
        self.assertEqual(rc, 1)
        self.assertFalse([c for c in ch.calls if c[0] == "update"])

    def test_apply_without_scope_does_not_call_update(self):
        ch = _Channels()
        rc, out = self.run_main("apply", ch, self.UPLOAD_ONLY)
        self.assertEqual(rc, 1)
        self.assertFalse([c for c in ch.calls if c[0] == "update"])

    def test_apply_403_prints_reauth(self):
        ch = _Channels(fail={"brandingSettings": (403, "insufficientPermissions")})
        rc, out = self.run_main("apply", ch, None)   # tokeninfo unknown -> tries
        self.assertEqual(rc, 1)
        self.assertIn("needs re-auth with youtube.force-ssl", out)

    def test_apply_ok_keeps_trailer_and_title_status_400_tolerated(self):
        ch = _Channels(fail={"status": (400, "invalidPart")})
        rc, out = self.run_main("apply", ch, self.FULL)
        self.assertEqual(rc, 0)
        upd = [c for c in ch.calls if c[0] == "update"]
        self.assertEqual([c[1] for c in upd], ["brandingSettings", "status"])
        sent = upd[0][2]["brandingSettings"]["channel"]
        self.assertEqual(sent["title"], "QUIZ PATHSHALA")
        self.assertEqual(sent["unsubscribedTrailer"], "vid12345678")
        self.assertEqual(sent["defaultLanguage"], "hi")
        self.assertIs(upd[1][2]["status"]["selfDeclaredMadeForKids"], False)
        self.assertIn("YouTube Studio", out)


if __name__ == "__main__":
    unittest.main()
