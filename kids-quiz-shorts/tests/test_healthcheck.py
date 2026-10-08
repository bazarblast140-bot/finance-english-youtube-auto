"""Offline tests for the pipeline health check. No network, no secrets."""
import json
import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config as C  # noqa: E402
import healthcheck as H  # noqa: E402
import pick  # noqa: E402
import tts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
UTC = timezone.utc

SCOPES = " ".join(H.REQUIRED_SCOPES)
CHANNEL = {
    "items": [{
        "id": H.EXPECTED_CHANNEL_ID,
        "snippet": {"title": H.EXPECTED_CHANNEL_TITLE},
    }]
}


class FakeClient:
    def __init__(self, handler):
        self.calls = []
        self.handler = handler

    def request(self, method, url, *, headers=None, body=None, timeout=20):
        self.calls.append({
            "method": method, "url": url, "headers": headers or {}, "body": body,
        })
        return self.handler(method, url, headers or {}, body)


def _q(qid, sub, text="सवाल", answer="अ"):
    return {
        "id": qid, "sub": sub, "q": text,
        "opts": [answer, "ब", "स", "द"], "ans": 0, "why": "कारण",
    }


def _run(at, event="schedule", conclusion="success", status="completed", url="https://github.test/run/1"):
    return {
        "id": 1,
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "created_at": at,
        "html_url": url,
        "head_branch": "main",
    }


def _codes(findings):
    return {f.code for f in findings}


def _finding(findings, code):
    return next(f for f in findings if f.code == code)


class RedactTests(unittest.TestCase):
    def test_strips_secret_shapes_and_leaves_normal_prose(self):
        raw = (
            "channel QUIZ PATHSHALA token refresh pass. "
            "access_token=ya29.SUPERSECRET refresh_token=1//refreshsecretvalue "
            "client_secret=GOCSPX-supersecretvalue sk_elevensecretvalue "
            "sk-deepseeksecret Bearer abc.def AIzaSyAAAAAAAAAAAAAAAAAAAA"
        )
        cleaned = H.redact(raw)
        for secret in (
            "ya29.SUPERSECRET", "1//refreshsecretvalue", "GOCSPX-supersecretvalue",
            "sk_elevensecretvalue", "sk-deepseeksecret", "abc.def",
            "AIzaSyAAAAAAAAAAAAAAAAAAAA",
        ):
            self.assertNotIn(secret, cleaned)
        self.assertIn("QUIZ PATHSHALA", cleaned)
        self.assertIn("token refresh pass", cleaned)

    def test_key_prefix_sentence_is_not_eaten(self):
        text = "ElevenLabs key 'sk_' se shuru nahi hoti."
        self.assertEqual(H.redact(text), text)


class SlotAndCronTests(unittest.TestCase):
    def test_active_slots_follow_config_rules(self):
        self.assertEqual(H.parse_active_slots("")[0], list(C.SLOT_ORDER))
        self.assertEqual(H.parse_active_slots(None)[0], list(C.SLOT_ORDER))
        slots, unknown = H.parse_active_slots("night, morning, bogus")
        self.assertEqual(slots, ["morning", "night"])
        self.assertEqual(unknown, ["bogus"])
        slots, unknown = H.parse_active_slots("nope")
        self.assertEqual(slots, list(C.SLOT_ORDER))
        self.assertEqual(unknown, ["nope"])

    def test_health_crons_lead_upload_builds(self):
        covered = []
        for expr, slots in H.HEALTH_CRONS:
            health_h, health_m = H.cron_hour_minute(expr)
            health_min = health_h * 60 + health_m
            for slot in slots:
                upload_h, upload_m = H.cron_hour_minute(H.UPLOAD_CRONS[slot])
                lead = (upload_h * 60 + upload_m) - health_min
                self.assertGreaterEqual(lead, 45, slot)
            covered.extend(slots)
        self.assertEqual(covered, list(H.UPLOAD_CRONS))
        self.assertEqual(list(H.UPLOAD_CRONS), list(C.SLOT_ORDER))
        self.assertLess(H.SCHEDULE_GRACE_HOURS, 24)
        self.assertLess(H.SCHEDULE_GRACE_HOURS, H.SCHEDULE_MATCH_HOURS)
        self.assertGreaterEqual(H.SCHEDULE_GRACE_HOURS, 20)

    def test_grace_uses_previous_fire_until_the_latest_is_overdue(self):
        # 4h after Tuesday's 06:00 cron — still inside the 22h grace.
        now = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
        got = H.occurrence_under_test(now, 6, 0, timedelta(hours=22))
        self.assertEqual(got, datetime(2026, 10, 5, 6, 0, tzinfo=UTC))
        # 23h after Monday 06:00 (Tuesday 05:00 is before 06:00, so latest is Monday).
        now = datetime(2026, 10, 7, 5, 0, tzinfo=UTC)
        got = H.occurrence_under_test(now, 6, 0, timedelta(hours=22))
        self.assertEqual(got, datetime(2026, 10, 6, 6, 0, tzinfo=UTC))

    def test_overlapping_delayed_runs_still_match(self):
        now = datetime(2026, 10, 2, 15, 15, tzinfo=UTC)
        due = H.due_occurrences(now, list(C.SLOT_ORDER))
        # ~20h after each due cron, which is inside that cron's 23h window.
        runs = [_run(start + timedelta(hours=20)) for _slot, start in due]
        matched, empty = H.match_schedule_runs(due, runs)
        self.assertEqual(matched, len(due))
        self.assertEqual(empty, [])

    def test_one_missing_run_is_not_hidden_by_overlap(self):
        now = datetime(2026, 10, 2, 15, 15, tzinfo=UTC)
        due = H.due_occurrences(now, list(C.SLOT_ORDER))
        runs = [_run(start + timedelta(hours=20)) for _slot, start in due[:-1]]
        matched, _empty = H.match_schedule_runs(due, runs)
        self.assertEqual(matched, len(due) - 1)

    def test_run_exactly_at_cron_counts_and_next_cron_does_not(self):
        start = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
        due = [("morning", start)]
        matched, empty = H.match_schedule_runs(due, [_run(start)])
        self.assertEqual((matched, empty), (1, []))
        too_late = start + timedelta(hours=H.SCHEDULE_MATCH_HOURS)
        matched, empty = H.match_schedule_runs(due, [_run(too_late)])
        self.assertEqual(matched, 0)
        self.assertEqual(empty, ["morning"])


class CharacterThresholdTests(unittest.TestCase):
    def test_spoken_chars_follow_build_scripts(self):
        question = _q("g1", "विज्ञान", "2+2 kitna hai?")
        parts = [
            tts.clean_for_tts(tts.question_script(question, 0, C.QUESTIONS_PER_VIDEO)),
            tts.clean_for_tts(tts.options_script(question)),
            tts.clean_for_tts(tts.cta_script()),
            tts.clean_for_tts(tts.answer_script(question)),
        ]
        if C.HINT_BEFORE_ANSWER:
            parts.append(tts.clean_for_tts(tts.hint_script(question)))
        self.assertEqual(H.spoken_char_count(question), sum(len(part) for part in parts))
        self.assertGreater(H.spoken_char_count(question), len(question["q"]))

    def test_threshold_scales_with_slots_and_days(self):
        bank = [_q("g1", "विज्ञान", "सवाल एक")]
        one = H.credit_threshold(bank, ["morning"], C.QUESTIONS_PER_VIDEO, days=2)
        two = H.credit_threshold(bank, ["morning", "noon"], C.QUESTIONS_PER_VIDEO, days=2)
        self.assertEqual(two, one * 2)
        half = H.credit_threshold(bank, ["morning"], C.QUESTIONS_PER_VIDEO, days=1)
        self.assertEqual(one, math.ceil(half * 2))
        self.assertEqual(H.CREDIT_COVER_DAYS, 2)

    def test_paheli_pool_is_separate_from_quiz(self):
        bank = [
            _q("g1", "विज्ञान", "यह एक लम्बा सामान्य ज्ञान वाला सवाल है"),
            _q("p1", C.PAHELI_SUB, "छोटा"),
        ]
        quiz_only = H.credit_threshold(bank, ["morning"], 2, days=2)
        paheli_only = H.credit_threshold(bank, ["paheli"], 2, days=2)
        self.assertNotEqual(quiz_only, paheli_only)

    def test_current_bank_two_day_line_is_typical_usage(self):
        bank = json.loads((C.DATA / "questions.json").read_text(encoding="utf-8"))
        daily = H.daily_spoken_characters(bank, list(C.SLOT_ORDER), C.QUESTIONS_PER_VIDEO)
        threshold = H.credit_threshold(bank, list(C.SLOT_ORDER), C.QUESTIONS_PER_VIDEO, days=2)
        self.assertEqual(threshold, math.ceil(daily * 2))
        # Bounds per sawaal, taaki QUESTIONS_PER_VIDEO 1 ho ya 2, test sach rahe.
        n = C.QUESTIONS_PER_VIDEO
        per_question = daily / len(C.SLOT_ORDER) / n
        self.assertGreater(per_question, 100)
        self.assertLess(per_question, 250)
        self.assertGreater(daily, 500 * n)
        self.assertLess(daily, 1500 * n)


class YouTubeEvalTests(unittest.TestCase):
    def test_matching_channel_and_scopes_pass(self):
        findings = H.evaluate_youtube({
            "scopes": SCOPES.split(),
            "channels": [{"id": H.EXPECTED_CHANNEL_ID, "title": "  QUIZ PATHSHALA  "}],
        })
        self.assertFalse(any(f.problem for f in findings))
        self.assertIn("yt_quota", _codes(findings))
        quota = _finding(findings, "yt_quota")
        self.assertIn(H.GCP_QUOTA_PROJECT, quota.english)
        self.assertIn("GCP", quota.english)

    def test_wrong_channel_missing_scope_and_quota(self):
        wrong = H.evaluate_youtube({
            "scopes": [s for s in H.REQUIRED_SCOPES if not s.endswith("force-ssl")],
            "channels": [{"id": "UCother", "title": "Other"}],
        })
        self.assertIn("yt_scopes_missing", _codes(wrong))
        self.assertIn("force-ssl", _finding(wrong, "yt_scopes_missing").english)
        self.assertIn("yt_channel_mismatch", _codes(wrong))

        quota = H.evaluate_youtube({"scopes": SCOPES.split(), "quota_error": "quotaExceeded"})
        self.assertEqual(_finding(quota, "yt_quota").level, "fail")
        self.assertIn("yt_channel_unverified", _codes(quota))

        dead = H.evaluate_youtube({"refresh_error": "invalid_grant: expired"})
        self.assertEqual(_codes(dead), {"yt_refresh_failed"})
        self.assertIn("invalid_grant", _finding(dead, "yt_refresh_failed").english)

        missing = H.evaluate_youtube({"missing_secrets": ["YOUTUBE_REFRESH_TOKEN"]})
        self.assertIn("YOUTUBE_REFRESH_TOKEN", _finding(missing, "yt_missing_secret").english)
        self.assertNotIn("=", _finding(missing, "yt_missing_secret").english)

        empty = H.evaluate_youtube({"scopes": [], "channels": [{
            "id": H.EXPECTED_CHANNEL_ID, "title": H.EXPECTED_CHANNEL_TITLE,
        }]})
        self.assertIn("yt_scopes_missing", _codes(empty))
        self.assertNotIn("yt_scopes_unreadable", _codes(empty))


class ElevenDeepSeekEvalTests(unittest.TestCase):
    def test_elevenlabs_threshold_boundaries(self):
        slots = ["morning", "night"]
        ok = H.evaluate_elevenlabs(
            {"payload": {"character_limit": 100, "character_count": 0}}, 100, slots)
        self.assertEqual(_finding(ok, "el_credit").level, "ok")
        warn = H.evaluate_elevenlabs(
            {"payload": {"character_limit": 100, "character_count": 1}}, 100, slots)
        self.assertEqual(_finding(warn, "el_low_credit").level, "warn")
        empty = H.evaluate_elevenlabs(
            {"payload": {"character_limit": 100, "character_count": 100,
                         "max_character_limit_extension": 0}}, 100, slots)
        self.assertEqual(_finding(empty, "el_low_credit").level, "fail")
        bad = H.evaluate_elevenlabs({"status": 401}, 100, slots)
        self.assertIn("el_invalid_key", _codes(bad))
        fmt = H.evaluate_elevenlabs({"bad_format": True}, 100, slots)
        self.assertIn("el_bad_key_format", _codes(fmt))
        self.assertNotIn("sk_real", _finding(fmt, "el_bad_key_format").hinglish)

    def test_deepseek_balance_rules(self):
        ok = H.evaluate_deepseek({"balance": {
            "is_available": True,
            "balance_infos": [{"currency": "USD", "total_balance": "1.25"}],
        }})
        self.assertEqual(_finding(ok, "ds_balance").level, "ok")
        dust = H.evaluate_deepseek({"balance": {
            "is_available": True,
            "balance_infos": [{"currency": "USD", "total_balance": "0.50"}],
        }})
        self.assertEqual(_finding(dust, "ds_low_balance").level, "fail")
        closed = H.evaluate_deepseek({"balance": {
            "is_available": False,
            "balance_infos": [{"currency": "USD", "total_balance": "100"}],
        }})
        self.assertIn("ds_low_balance", _codes(closed))
        mixed = H.evaluate_deepseek({"balance": {
            "is_available": True,
            "balance_infos": [
                {"currency": "USD", "total_balance": "3"},
                {"currency": "CNY", "total_balance": "0"},
            ],
        }})
        self.assertEqual(_finding(mixed, "ds_balance").level, "ok")
        hidden = H.evaluate_deepseek({"models_ok": True})
        self.assertEqual(_finding(hidden, "ds_balance_unexposed").level, "ok")
        rejected = H.evaluate_deepseek({"invalid": True, "status": 401})
        self.assertIn("ds_invalid_key", _codes(rejected))
        absent = H.evaluate_deepseek({"missing": True})
        self.assertIn("DEEPSEEK_API_KEY", _finding(absent, "ds_missing_secret").english)


class WorkflowEvalTests(unittest.TestCase):
    def test_recent_failure_and_missing_schedule(self):
        now = datetime(2026, 10, 2, 15, 15, tzinfo=UTC)
        due = H.due_occurrences(now, ["morning"])
        start = due[0][1]
        runs = [
            _run(start + timedelta(hours=1), conclusion="failure",
                 url="https://github.test/runs/99"),
            _run(now - timedelta(hours=1), event="workflow_dispatch", conclusion="cancelled",
                 url="https://github.test/runs/manual"),
        ]
        findings = H.evaluate_workflows({"runs": runs}, now, ["morning"])
        self.assertIn("wf_schedule", _codes(findings))
        failed = _finding(findings, "wf_failed")
        self.assertIn("https://github.test/runs/99", failed.english)
        self.assertNotIn("manual", failed.english)

        old = _run(now - timedelta(hours=49), conclusion="failure")
        quiet = H.evaluate_workflows({"runs": [old, _run(start + timedelta(hours=1))]}, now, ["morning"])
        self.assertFalse(any(f.problem for f in quiet))

    def test_stuck_run_and_local_skip(self):
        now = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
        stuck = _run(now - timedelta(hours=3), conclusion=None, status="in_progress")
        findings = H.evaluate_workflows({"runs": [stuck]}, now, ["morning"])
        self.assertIn("wf_failed", _codes(findings))
        young = _run(now - timedelta(minutes=20), conclusion=None, status="queued")
        # Still inside grace for today's fire; previous day's window will not
        # contain this run, so the schedule check can fail. Stuck must not.
        findings = H.evaluate_workflows({"runs": [young]}, now, ["morning"])
        self.assertNotIn("wf_failed", _codes(findings))
        skipped = H.evaluate_workflows({"error": "missing_token", "required": False}, now, ["morning"])
        self.assertEqual(_finding(skipped, "wf_skipped_local").level, "ok")
        required = H.evaluate_workflows({"error": "missing_token", "required": True}, now, ["morning"])
        self.assertEqual(_finding(required, "wf_missing_token").level, "fail")


class BankTests(unittest.TestCase):
    def test_low_stock_uses_active_slot_count(self):
        quiz = [_q(f"g{i}", "विज्ञान") for i in range(10)]
        paheli = [_q(f"p{i}", C.PAHELI_SUB) for i in range(14)]
        bank = quiz + paheli
        # paheli only: 2 questions/video × 1 slot = 2/day. 14 fresh = 7.0 days, not low.
        # 3 of them used -> 11 fresh = 5.5 days, low. Quiz slot is off.
        used = {f"p{i}" for i in range(3)}
        findings = H.evaluate_bank(
            bank, used, ["paheli"], [], 2, C.BANK_LOW_DAYS)
        self.assertIn("bank_low_paheli", _codes(findings))
        self.assertEqual(_finding(findings, "bank_quiz_off").level, "ok")
        full = H.evaluate_bank(
            bank, set(), ["paheli"], [], 2, 7)
        self.assertIn("bank_paheli", _codes(full))
        self.assertNotIn("bank_low_paheli", _codes(full))

    def test_unknown_slot_warns_and_stock_matches_pick(self):
        findings = H.evaluate_bank(
            [_q("g1", "विज्ञान")], set(), ["morning"], ["bogus"], 2, 7)
        self.assertEqual(_finding(findings, "config_unknown_slots").level, "warn")
        bank = [_q(f"g{i}", "विज्ञान") for i in range(8)]
        bank += [_q(f"p{i}", C.PAHELI_SUB) for i in range(4)]
        last = {"g0": "2026-09-01T00:00:00"}
        rows = H.stock_rows(bank, set(last), list(C.SLOT_ORDER), C.QUESTIONS_PER_VIDEO)
        if list(C.ACTIVE_SLOTS) == list(C.SLOT_ORDER):
            lines = "\n".join(pick.stock_report(bank, last, C.QUESTIONS_PER_VIDEO))
            for row in rows:
                self.assertIn(f"~{row['days']:.1f} din", lines)

    def test_real_bank_loads(self):
        bank = H.load_questions()
        used = H.load_used_ids()
        self.assertGreater(len(bank), 0)
        findings = H.evaluate_bank(
            bank, used, list(C.SLOT_ORDER), [], C.QUESTIONS_PER_VIDEO, C.BANK_LOW_DAYS)
        self.assertTrue(any(f.check == "bank" and "quiz" in f.code for f in findings))
        self.assertTrue(any(f.check == "bank" and "paheli" in f.code for f in findings))


class ReportAndIssueTests(unittest.TestCase):
    def _report(self, findings, threshold=2881):
        return H.Report(
            findings,
            datetime(2026, 10, 2, 4, 45, tzinfo=UTC),
            ["morning", "noon", "paheli", "evening", "night"],
            threshold,
        )

    def test_report_is_bilingual_and_redacts(self):
        report = self._report([
            H.Finding("youtube", "fail", "yt_refresh_failed",
                      "refresh fail", "leaked sk_elevensecretvalue and 1//refreshsecretvalue"),
            H.Finding("quota", "ok", "yt_quota", "quota theek",
                      f"GCP console project {H.GCP_QUOTA_PROJECT}"),
        ])
        body = H.render_report(report)
        self.assertIn("Hinglish:", body)
        self.assertIn("English:", body)
        self.assertIn("PROBLEM", body)
        self.assertIn(H.GCP_QUOTA_PROJECT, body)
        self.assertIn("<!-- health-fingerprint: yt_refresh_failed -->", body)
        self.assertNotIn("sk_elevensecretvalue", body)
        self.assertNotIn("1//refreshsecretvalue", body)
        self.assertIn("never", body.lower())

    def test_issue_lifecycle(self):
        bad = self._report([
            H.Finding("bank", "warn", "bank_low_quiz", "kam stock", "under 7 days"),
        ])
        created = H.plan_issue_action([], bad)
        self.assertEqual(created["action"], "create")
        self.assertEqual(created["title"], H.ISSUE_TITLE)
        self.assertIsNone(created["comment"])
        same = H.plan_issue_action(
            [{"number": 4, "title": H.ISSUE_TITLE, "body": created["body"]}], bad)
        self.assertEqual(same["action"], "update")
        self.assertEqual(same["number"], 4)
        self.assertIsNone(same["comment"])
        worse = self._report([
            H.Finding("bank", "warn", "bank_low_quiz", "kam stock", "under 7 days"),
            H.Finding("elevenlabs", "warn", "el_low_credit", "kam credit", "below the line"),
        ])
        changed = H.plan_issue_action(
            [{"number": 4, "title": H.ISSUE_TITLE, "body": created["body"]}], worse)
        self.assertIsNotNone(changed["comment"])
        self.assertIn("English:", changed["comment"])
        healthy = self._report([
            H.Finding("youtube", "ok", "yt_refresh", "theek", "refresh worked"),
        ])
        self.assertEqual(H.plan_issue_action([], healthy)["action"], "noop")
        closed = H.plan_issue_action(
            [{"number": 4, "title": H.ISSUE_TITLE, "body": created["body"]}], healthy)
        self.assertEqual(closed["action"], "close")
        self.assertIn("English:", closed["comment"])
        self.assertIn("OK", closed["body"])

    def test_sync_creates_updates_and_closes_without_leaking_token(self):
        secret = "ghp_shouldneverprint"
        bad = self._report([
            H.Finding("bank", "warn", "bank_low_quiz", "kam", "low"),
        ])
        state = {"issues": []}

        def handler(method, url, headers, body):
            self.assertNotIn(secret, url)
            if body:
                self.assertNotIn(secret, body.decode("utf-8"))
            self.assertEqual(headers.get("Authorization"), f"Bearer {secret}")
            if method == "GET" and url.endswith("labels=health-alert&per_page=50") or (
                method == "GET" and "labels=health-alert" in url
            ):
                return H.ClientResponse(200, list(state["issues"]))
            if method == "POST" and url.endswith("/labels"):
                return H.ClientResponse(201, {"name": "health-alert"})
            if method == "POST" and url.endswith("/issues"):
                state["issues"].append({
                    "number": 12, "title": H.ISSUE_TITLE,
                    "body": json.loads(body.decode("utf-8"))["body"],
                })
                return H.ClientResponse(201, {"number": 12})
            if method == "POST" and "/comments" in url:
                return H.ClientResponse(201, {"id": 1})
            if method == "PATCH":
                return H.ClientResponse(200, {"number": 12})
            raise AssertionError((method, url))

        client = FakeClient(handler)
        env = {"GH_TOKEN": secret, "GITHUB_REPOSITORY": "acme/widgets"}
        self.assertEqual(H.sync_health_issue(client, env, bad), "created #12")
        methods = [call["method"] for call in client.calls]
        self.assertIn("POST", methods)
        self.assertTrue(any(call["url"].endswith("/labels") for call in client.calls))
        client.calls.clear()
        self.assertEqual(H.sync_health_issue(client, env, bad), "updated #12")
        self.assertFalse(any(call["method"] == "POST" and call["url"].endswith("/comments")
                             for call in client.calls))
        healthy = self._report([
            H.Finding("bank", "ok", "bank_quiz", "theek", "enough stock"),
        ])
        client.calls.clear()
        self.assertEqual(H.sync_health_issue(client, env, healthy), "closed #12")
        self.assertTrue(any("/comments" in call["url"] for call in client.calls))
        patch = next(call for call in client.calls if call["method"] == "PATCH")
        self.assertEqual(json.loads(patch["body"].decode("utf-8"))["state"], "closed")
        client.calls.clear()
        state["issues"].clear()
        self.assertEqual(H.sync_health_issue(client, env, healthy), "noop")
        self.assertEqual([call["method"] for call in client.calls], ["GET"])


class FetchTests(unittest.TestCase):
    def _env(self):
        return {
            "YT_CLIENT_ID": "client-id",
            "YT_CLIENT_SECRET": "GOCSPX-supersecretvalue",
            "YT_REFRESH_TOKEN": "1//refreshsecretvalue",
            "ELEVENLABS_API_KEY": "sk_elevensecretvalue",
            "DEEPSEEK_API_KEY": "sk-deepseeksecret",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
            "GH_TOKEN": "ghp_workflowtoken",
            "GITHUB_REPOSITORY": "acme/widgets",
            "GITHUB_ACTIONS": "true",
            "QUIZ_ACTIVE_SLOTS": "morning,paheli",
        }

    def test_fetches_are_read_only_and_secrets_stay_out_of_the_report(self):
        access = "ya29.SUPERSECRET"
        now = datetime(2026, 10, 2, 15, 15, tzinfo=UTC)
        due = H.due_occurrences(now, ["morning", "paheli"])

        def handler(method, url, headers, body):
            parsed = urlparse(url)
            if parsed.netloc == "oauth2.googleapis.com" and parsed.path == "/token":
                self.assertEqual(method, "POST")
                form = parse_qs(body.decode("ascii"))
                self.assertEqual(form["grant_type"], ["refresh_token"])
                self.assertNotIn("scope", form)
                return H.ClientResponse(200, {"access_token": access})
            if parsed.path == "/tokeninfo":
                self.assertIn(access, parse_qs(parsed.query)["access_token"][0])
                return H.ClientResponse(200, {"scope": SCOPES})
            if parsed.path == "/youtube/v3/channels":
                self.assertEqual(method, "GET")
                query = parse_qs(parsed.query)
                self.assertEqual(query["part"], ["snippet"])
                self.assertEqual(query["mine"], ["true"])
                self.assertEqual(headers.get("Authorization"), f"Bearer {access}")
                return H.ClientResponse(200, CHANNEL)
            if "elevenlabs" in parsed.netloc:
                self.assertEqual(headers.get("xi-api-key"), "sk_elevensecretvalue")
                return H.ClientResponse(200, {
                    "character_count": 10, "character_limit": 500000,
                })
            if parsed.netloc == "api.deepseek.com" and parsed.path == "/user/balance":
                self.assertNotIn("/v1/", url)
                self.assertEqual(headers.get("Authorization"), "Bearer sk-deepseeksecret")
                return H.ClientResponse(404, {"error": "not found"})
            if parsed.path == "/models":
                return H.ClientResponse(200, {"data": []})
            if parsed.netloc == "api.github.com" and parsed.path.endswith("/runs"):
                runs = []
                for slot, start in due:
                    runs.append({
                        "id": slot,
                        "event": "schedule",
                        "status": "completed",
                        "conclusion": "success",
                        "created_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "html_url": f"https://github.test/{slot}",
                        "head_branch": "main",
                    })
                return H.ClientResponse(200, {"workflow_runs": runs})
            raise AssertionError(url)

        client = FakeClient(handler)
        bank = [_q(f"g{i}", "विज्ञान", "सवाल") for i in range(40)]
        bank += [_q(f"p{i}", C.PAHELI_SUB, "पहेली सवाल") for i in range(40)]
        report = H.run_checks(client, self._env(), bank, set(), now)
        urls = [call["url"] for call in client.calls]
        self.assertTrue(any("/youtube/v3/channels" in url for url in urls))
        for url in urls:
            self.assertNotIn("/videos", url)
            self.assertNotIn("commentThreads", url)
        blob = H.render_report(report)
        for secret in (
            "GOCSPX-supersecretvalue", "1//refreshsecretvalue", "sk_elevensecretvalue",
            "sk-deepseeksecret", "ya29.SUPERSECRET", "ghp_workflowtoken", "client-id",
        ):
            self.assertNotIn(secret, blob, secret)
        self.assertIn("ds_balance_unexposed", _codes(report.findings))
        self.assertIn("yt_channel", _codes(report.findings))
        self.assertTrue(report.eleven_threshold > 0)
        # Balance 404 must not be followed by a second balance call, and models
        # is the fallback. No write method except the OAuth token POST.
        self.assertEqual(
            [call["method"] for call in client.calls if call["method"] != "GET"],
            ["POST"],
        )

    def test_refresh_error_body_cannot_leak_the_token(self):
        def handler(method, url, headers, body):
            if url == H.TOKEN_URL:
                return H.ClientResponse(400, {
                    "error": "invalid_grant",
                    "error_description": "revoked 1//refreshsecretvalue",
                })
            if "elevenlabs" in url:
                return H.ClientResponse(401, {})
            if "deepseek" in url:
                return H.ClientResponse(401, {})
            if "api.github.com" in url:
                return H.ClientResponse(200, {"workflow_runs": []})
            raise AssertionError(url)

        report = H.run_checks(
            FakeClient(handler), self._env(), [], set(),
            datetime(2026, 10, 2, tzinfo=UTC),
        )
        blob = H.render_report(report)
        self.assertIn("yt_refresh_failed", _codes(report.findings))
        self.assertNotIn("1//refreshsecretvalue", blob)
        self.assertNotIn("GOCSPX-supersecretvalue", blob)

    def test_deepseek_401_does_not_ask_for_models(self):
        seen = []

        def handler(method, url, headers, body):
            seen.append(url)
            return H.ClientResponse(401, {"error": "invalid"})

        obs = H.fetch_deepseek(FakeClient(handler), {"DEEPSEEK_API_KEY": "sk-deepseeksecret"})
        self.assertTrue(obs.get("invalid"))
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].endswith("/user/balance"))


class WorkflowFileTests(unittest.TestCase):
    def test_workflow_contract(self):
        text = (ROOT / ".github/workflows/health-check.yml").read_text(encoding="utf-8")
        perms = (
            "permissions:\n"
            "  issues: write\n"
            "  contents: read\n"
            "  actions: read\n"
        )
        self.assertIn(perms, text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("videos.insert", text)
        for expr, _slots in H.HEALTH_CRONS:
            self.assertIn(f'cron: "{expr}"', text)
        for expr in H.UPLOAD_CRONS.values():
            upload = (ROOT / ".github/workflows/kids-gk-shorts.yml").read_text(encoding="utf-8")
            self.assertIn(expr, upload)
        for name in (
            "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN",
            "ELEVENLABS_API_KEY", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL",
            "QUIZ_ACTIVE_SLOTS",
        ):
            self.assertIn(name, text)
        self.assertIn("healthcheck.py", text)
        quiz_tests = (ROOT / ".github/workflows/quiz-tests.yml").read_text(encoding="utf-8")
        self.assertIn(".github/workflows/health-check.yml", quiz_tests)

    def test_source_does_not_call_write_endpoints(self):
        src = Path(H.__file__).read_text(encoding="utf-8")
        for banned in ("videos.insert", "videos().insert", "channels().update", "commentThreads"):
            self.assertNotIn(banned, src)
        self.assertIn("class _NoRedirect", src)


class MainGuardTests(unittest.TestCase):
    def test_issue_filing_only_in_actions_and_not_when_dry_run(self):
        env = {"GITHUB_ACTIONS": "true", "HEALTH_DRY_RUN": "false"}
        self.assertTrue(H.should_file_issues(False, env))
        self.assertFalse(H.should_file_issues(True, env))
        self.assertFalse(H.should_file_issues(False, {"GITHUB_ACTIONS": "true", "HEALTH_DRY_RUN": "true"}))
        self.assertFalse(H.should_file_issues(False, {}))


if __name__ == "__main__":
    unittest.main()


class WorkflowFetchTruncationTests(unittest.TestCase):
    """wf_api_error (http 200): runs list ~1.5 MB thi, body 1 MB par katti thi."""

    def test_body_cap_fits_a_full_runs_page(self):
        self.assertGreaterEqual(H.MAX_BODY_BYTES, 4_000_000)

    def test_runs_query_is_bounded_by_created_filter(self):
        now = datetime(2026, 10, 7, 11, 19, tzinfo=UTC)
        seen = []

        def handler(method, url, headers, body):
            seen.append(url)
            return H.ClientResponse(200, {"workflow_runs": [_run("2026-10-07T08:00:00Z")]})

        env = {"GH_TOKEN": "ghp_x", "GITHUB_REPOSITORY": "o/r", "GITHUB_ACTIONS": "true"}
        obs = H.fetch_workflows(FakeClient(handler), env, now)
        self.assertNotIn("error", obs)
        self.assertEqual(len(obs["runs"]), 1)
        qs = parse_qs(urlparse(seen[0]).query)
        self.assertEqual(qs["created"], [">=2026-10-04T11:19:00Z"])

    def test_unparseable_200_says_so_instead_of_bare_http_200(self):
        def handler(method, url, headers, body):
            return H.ClientResponse(200, None, '{"total_count": 5, "workflow_runs": [{"id"')

        env = {"GH_TOKEN": "ghp_x", "GITHUB_REPOSITORY": "o/r", "GITHUB_ACTIONS": "true"}
        obs = H.fetch_workflows(FakeClient(handler), env, datetime(2026, 10, 7, tzinfo=UTC))
        self.assertIn("not a JSON object", obs["error"])
        self.assertNotEqual(obs["error"], "http 200")
