"""Planner: coverage, late runs, no duplicates, active slots, IST/UTC.

No network. No upload. No TTS.
"""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import slot_planner as sp

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[2]


def ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=sp.IST)


class TimeAndCoverageTests(unittest.TestCase):
    def test_ist_utc_including_date_rollover(self):
        # Slot clocks stay on the same UTC date (earliest is 02:00 UTC).
        morning = sp.slot_datetime("morning", datetime(2026, 10, 3).date())
        self.assertEqual(sp.to_rfc3339(morning), "2026-10-03T02:00:00Z")
        night = sp.slot_datetime("night", datetime(2026, 10, 2).date())
        self.assertEqual(sp.to_rfc3339(night), "2026-10-02T15:00:00Z")
        paheli = sp.slot_datetime("paheli", datetime(2026, 10, 2).date())
        self.assertEqual(sp.to_rfc3339(paheli), "2026-10-02T10:30:00Z")
        noon = sp.slot_datetime("noon", datetime(2026, 10, 2).date())
        self.assertEqual(sp.to_rfc3339(noon), "2026-10-02T08:00:00Z")
        evening = sp.slot_datetime("evening", datetime(2026, 10, 2).date())
        self.assertEqual(sp.to_rfc3339(evening), "2026-10-02T12:00:00Z")
        # Converter itself rolls the UTC date when the IST clock is after midnight
        # but before 05:30.
        self.assertEqual(sp.to_rfc3339(ist(2026, 10, 3, 0, 30)), "2026-10-02T19:00:00Z")

    def test_horizon_crosses_midnight_ist(self):
        now = ist(2026, 10, 2, 23, 0)
        keys = [(o["slot"], o["date"]) for o in sp.occurrences(now, ["morning", "night"])]
        self.assertNotIn(("morning", "2026-10-02"), keys)
        self.assertNotIn(("night", "2026-10-02"), keys)  # 20:30 was 2.5h ago
        self.assertIn(("morning", "2026-10-03"), keys)
        self.assertIn(("night", "2026-10-03"), keys)
        # 36h from 23:00 IST 2 Oct is 11:00 IST 4 Oct — morning 4 Oct is inside,
        # noon 4 Oct is not.
        self.assertIn(("morning", "2026-10-04"), keys)
        far = sp.uncovered_slots(now, set(), ["morning"])
        dates = {item["date"] for item in far}
        self.assertIn("2026-10-03", dates)
        self.assertNotIn("2026-10-05", dates)

    def test_thirty_hours_in_horizon_forty_hours_out(self):
        now = ist(2026, 10, 2, 10, 0)
        needed = {(i["slot"], i["date"]) for i in sp.uncovered_slots(now, set(), sp.active_slots(""))}
        # morning 3 Oct 07:30 is 21.5h away; morning 4 Oct 07:30 is 45.5h — out.
        self.assertIn(("morning", "2026-10-03"), needed)
        self.assertNotIn(("morning", "2026-10-04"), needed)
        self.assertGreaterEqual(sp.HORIZON_HOURS, 24)
        self.assertGreaterEqual(sp.HORIZON_HOURS, sp.LEAD_HOURS)

    def test_publish_at_wins_over_upload_clock_and_build_date(self):
        # The 2 Oct incident: built that afternoon, scheduled for 3 Oct 07:30.
        videos = [{
            "id": "Un7jdLyS23w",
            "privacyStatus": "private",
            "publishAt": "2026-10-03T02:00:00Z",
            "publishedAt": "2026-10-02T12:15:00Z",
        }]
        covered = sp.covered_from_videos(videos)
        self.assertIn(("morning", "2026-10-03"), covered)
        self.assertNotIn(("morning", "2026-10-02"), covered)
        ledger = [{
            "video_id": "Un7jdLyS23w",
            "slot": "morning",
            "date": "2026-10-02",  # build day, not the slot day
            "publish_at": "2026-10-03T02:00:00Z",
            "privacy": "public",
        }]
        led = sp.covered_from_ledger(ledger)
        self.assertEqual(led, {("morning", "2026-10-03")})

    def test_public_published_at_maps_to_slot_unlisted_does_not(self):
        videos = [
            {"id": "e", "privacyStatus": "public", "publishedAt": "2026-10-02T12:00:00Z"},
            {"id": "u", "privacyStatus": "unlisted", "publishedAt": "2026-10-02T08:00:00Z"},
            {"id": "d", "privacyStatus": "private"},
        ]
        covered = sp.covered_from_videos(videos)
        self.assertEqual(covered, {("evening", "2026-10-02")})

    def test_tie_goes_to_the_earlier_slot(self):
        # 16:45 IST is 45 min from paheli 16:00 and evening 17:30.
        when = ist(2026, 10, 2, 16, 45)
        self.assertEqual(sp.nearest_slot(when), ("paheli", "2026-10-02"))

    def test_quota_day_rolls_at_pacific_midnight(self):
        # Oct 2026 is still PDT (UTC-7). Quota midnight is 07:00 UTC.
        self.assertEqual(sp.quota_day(datetime(2026, 10, 2, 6, 59, tzinfo=UTC)), "2026-10-01")
        self.assertEqual(sp.quota_day(datetime(2026, 10, 2, 7, 0, tzinfo=UTC)), "2026-10-02")


class ActiveSlotTests(unittest.TestCase):
    def test_empty_means_all_and_order_follows_slot_order(self):
        self.assertEqual(sp.active_slots(""), list(sp.C.SLOT_ORDER))
        self.assertEqual(sp.active_slots("night, morning"), ["morning", "night"])

    def test_unknown_names_do_not_drop_known_ones(self):
        self.assertEqual(sp.active_slots("noon, not-a-slot"), ["noon"])
        self.assertEqual(sp.active_slots("nope,zzz"), list(sp.C.SLOT_ORDER))

    def test_uncovered_respects_active_slots(self):
        now = ist(2026, 10, 2, 6, 0)
        needed = sp.uncovered_slots(now, set(), sp.active_slots("morning,paheli,night"))
        slots = {item["slot"] for item in needed}
        self.assertIn("morning", slots)
        self.assertIn("paheli", slots)
        self.assertNotIn("noon", slots)
        self.assertNotIn("evening", slots)


class LateRunTests(unittest.TestCase):
    def setUp(self):
        # 17:43 IST on 2 Oct 2026 — the late morning cron.
        self.now = datetime(2026, 10, 2, 12, 13, tzinfo=UTC)
        self.active = sp.active_slots("")

    def test_late_run_fills_nearest_hole_not_tomorrow_morning(self):
        # Tomorrow morning is already scheduled (the bug upload). Evening is
        # 13 min past and still inside the late grace.
        covered = {("morning", "2026-10-03")}
        decision = sp.decide_unscheduled("morning", self.now, covered, self.active)
        self.assertEqual(decision["action"], "build")
        self.assertEqual(decision["slot"], "evening")
        self.assertEqual(decision["date"], "2026-10-02")
        self.assertTrue(decision["immediate"])
        self.assertEqual(decision["publish_at"], "")
        self.assertNotEqual((decision["slot"], decision["date"]), ("morning", "2026-10-03"))

    def test_when_evening_is_covered_the_next_hole_is_night(self):
        covered = {("morning", "2026-10-03"), ("evening", "2026-10-02")}
        decision = sp.decide_unscheduled("morning", self.now, covered, self.active)
        self.assertEqual((decision["slot"], decision["date"]), ("night", "2026-10-02"))
        self.assertFalse(decision["immediate"])
        self.assertEqual(decision["publish_at"], "2026-10-02T15:00:00Z")

    def test_explicit_duplicate_is_a_skip(self):
        covered = {("morning", "2026-10-03")}
        decision = sp.decide_explicit("morning", "2026-10-03", self.now, covered, self.active)
        self.assertEqual(decision["action"], "skip")
        self.assertIn("covered", decision["reason"])

    def test_schedule_event_uses_the_same_retarget(self):
        covered = {("morning", "2026-10-03")}
        decision, _state = sp.prepare_decision(
            event="schedule", privacy="public", requested_slot="", requested_date="",
            schedule="0 6 * * *", now=self.now, covered=covered, active=self.active,
            state=sp.empty_state(),
        )
        self.assertEqual(decision["action"], "build")
        self.assertEqual(decision["slot"], "evening")
        self.assertNotEqual(decision["date"], "2026-10-03")

    def test_unknown_cron_does_not_default_to_morning(self):
        decision, state = sp.prepare_decision(
            event="schedule", privacy="public", requested_slot="morning",
            requested_date="", schedule="15 1 * * *", now=self.now, covered=set(),
            active=self.active, state=sp.empty_state(),
        )
        self.assertEqual(decision["action"], "skip")
        self.assertIsNone(state)

    def test_under_ten_minutes_publishes_now_eleven_schedules(self):
        active = self.active
        almost = datetime(2026, 10, 3, 1, 50, tzinfo=UTC)  # 07:20 IST, 10 min left
        decision = sp.decide_unscheduled("morning", almost, set(), active)
        self.assertEqual(decision["action"], "build")
        self.assertEqual(decision["date"], "2026-10-03")
        self.assertTrue(decision["immediate"])
        earlier = datetime(2026, 10, 3, 1, 49, tzinfo=UTC)  # 11 min left
        scheduled = sp.decide_unscheduled("morning", earlier, set(), active)
        self.assertFalse(scheduled["immediate"])
        self.assertEqual(scheduled["publish_at"], "2026-10-03T02:00:00Z")
        self.assertEqual(scheduled["slot"], "morning")

    def test_early_night_cron_still_builds_tonights_night(self):
        # 19:00 UTC = 00:30 IST next day. Night 20:30 has not passed.
        now = datetime(2026, 10, 2, 19, 0, tzinfo=UTC)
        decision = sp.decide_unscheduled("night", now, set(), self.active)
        self.assertEqual((decision["slot"], decision["date"]), ("night", "2026-10-03"))
        self.assertEqual(decision["publish_at"], "2026-10-03T15:00:00Z")
        self.assertFalse(decision["immediate"])

    def test_inactive_slot_is_skipped(self):
        active = sp.active_slots("morning,night")
        decision = sp.decide_explicit("noon", "2026-10-03", self.now, set(), active)
        self.assertEqual(decision["action"], "skip")
        self.assertIn("inactive", decision["reason"])

    def test_manual_unlisted_does_not_claim_or_schedule(self):
        decision, state = sp.prepare_decision(
            event="workflow_dispatch", privacy="unlisted", requested_slot="noon",
            requested_date="", schedule="", now=self.now, covered=set(),
            active=self.active, state=sp.empty_state(),
        )
        self.assertEqual(decision["action"], "build")
        self.assertTrue(decision["skip_coverage"])
        self.assertEqual(decision["privacy"], "unlisted")
        self.assertIsNone(state)


class IdempotencyTests(unittest.TestCase):
    def test_no_second_claim_while_in_flight(self):
        now = ist(2026, 10, 3, 12, 0)
        needed = sp.uncovered_slots(now, set(), ["morning"])
        self.assertEqual([(item["slot"], item["date"]) for item in needed], [("morning", "2026-10-04")])
        first = sp.select_dispatches(needed, sp.empty_state(), now, limit=1)
        self.assertEqual(len(first["dispatch"]), 1)
        self.assertEqual(first["dispatch"][0]["attempt"], 1)
        second = sp.select_dispatches(needed, first["state"], now, limit=1)
        self.assertEqual(second["dispatch"], [])
        self.assertEqual(second["alerts"], [])

    def test_retry_then_alert_not_a_third_build(self):
        now = ist(2026, 10, 3, 12, 0)
        needed = sp.uncovered_slots(now, set(), ["morning"])
        self.assertEqual(needed[0]["date"], "2026-10-04")
        state = {
            "version": 1,
            "slots": {
                "morning|2026-10-04": {
                    "attempts": 1,
                    "state": "failed",
                    "counts_quota": False,
                    "quota_day": "2026-10-02",
                    "dispatched_at": sp.to_rfc3339(now - timedelta(hours=2)),
                }
            },
        }
        retry = sp.select_dispatches(needed, state, now, limit=1)
        self.assertEqual(len(retry["dispatch"]), 1)
        self.assertEqual(retry["dispatch"][0]["attempt"], 2)
        failed = sp.reconcile(retry["state"], now + timedelta(minutes=sp.IN_FLIGHT_MINUTES + 5), set())
        key = "morning|2026-10-04"
        self.assertEqual(failed["slots"][key]["state"], "failed")
        self.assertFalse(failed["slots"][key]["counts_quota"])
        again = sp.select_dispatches(needed, failed, now + timedelta(minutes=sp.IN_FLIGHT_MINUTES + 5))
        self.assertEqual(again["dispatch"], [])
        self.assertEqual(again["alerts"][0]["slot"], "morning")
        self.assertEqual(again["alerts"][0]["attempts"], 2)

    def test_quota_cap_is_five_and_a_failure_frees_the_slot(self):
        now = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)  # after Pacific midnight
        day = sp.quota_day(now)
        state = {"version": 1, "slots": {}}
        for i, slot in enumerate(["morning", "noon", "paheli", "evening", "night"]):
            state["slots"][f"{slot}|2026-10-02"] = {
                "attempts": 1, "state": "uploaded", "counts_quota": True, "quota_day": day,
            }
        self.assertEqual(sp.quota_reserved(state, now), 5)
        needed = sp.uncovered_slots(now, set(), ["morning"])
        # morning 2026-10-02 may be in the past; force a future candidate
        future = [{
            "slot": "morning", "date": "2026-10-04",
            "when": ist(2026, 10, 4, 7, 30), "mode": "schedule",
            "publish_at": "2026-10-04T02:00:00Z", "immediate": False,
        }]
        blocked = sp.select_dispatches(future, state, now)
        self.assertEqual(blocked["dispatch"], [])
        for rec in state["slots"].values():
            rec["state"] = "failed"
            rec["counts_quota"] = False
        self.assertEqual(sp.quota_reserved(state, now), 0)
        allowed = sp.select_dispatches(future, state, now, limit=1)
        self.assertEqual(len(allowed["dispatch"]), 1)

    def test_covered_video_is_not_dispatched(self):
        now = ist(2026, 10, 2, 12, 0)
        videos = [{"id": "n", "privacyStatus": "private", "publishAt": "2026-10-02T15:00:00Z"}]
        plan = sp.plan_catchup(now, videos, [], sp.active_slots(""), sp.empty_state())
        dispatched = {(item["slot"], item["date"]) for item in plan["dispatch"]}
        self.assertNotIn(("night", "2026-10-02"), dispatched)
        self.assertIn(("night", "2026-10-02"), plan["covered"])

    def test_explicit_in_flight_builds_without_a_second_claim(self):
        now = ist(2026, 10, 3, 0, 0)
        state = {
            "version": 1,
            "slots": {
                "morning|2026-10-03": {
                    "attempts": 1,
                    "state": "dispatched",
                    "dispatched_at": sp.to_rfc3339(now),
                    "counts_quota": True,
                    "quota_day": sp.quota_day(now),
                }
            },
        }
        decision, new_state = sp.prepare_decision(
            event="workflow_dispatch", privacy="public", requested_slot="morning",
            requested_date="2026-10-03", schedule="", now=now, covered=set(),
            active=sp.active_slots(""), state=state,
        )
        self.assertEqual(decision["action"], "build")
        self.assertEqual(decision["publish_at"], "2026-10-03T02:00:00Z")
        self.assertIsNone(new_state)

    def test_reconcile_marks_uploaded_when_youtube_has_the_video(self):
        now = ist(2026, 10, 3, 1, 0)
        state = {
            "version": 1,
            "slots": {
                "morning|2026-10-03": {
                    "attempts": 1, "state": "dispatched",
                    "dispatched_at": sp.to_rfc3339(now), "counts_quota": True,
                    "quota_day": sp.quota_day(now),
                }
            },
        }
        out = sp.reconcile(state, now, {("morning", "2026-10-03")})
        self.assertEqual(out["slots"]["morning|2026-10-03"]["state"], "uploaded")


class CommentAndAlertTests(unittest.TestCase):
    def test_pending_comments_wait_for_publish_and_leave_when_posted(self):
        now = "2026-10-02T18:00:00Z"
        future = {"video_id": "U", "pinned_comment": "hi", "publish_at": "2026-10-03T02:00:00Z"}
        due = {"video_id": "W", "pinned_comment": "hi", "publish_at": "2026-10-02T15:00:00Z",
               "comment_attempts": 1}
        posted = {"video_id": "K", "pinned_comment": "hi", "publish_at": "2026-10-02T12:00:00Z",
                  "comment_posted": "2026-10-02T12:15:00Z"}
        pending = sp.pending_comment_rows([future, due, posted], now)
        self.assertEqual([row["video_id"] for row in pending], ["W"])
        due["comment_posted"] = now
        self.assertEqual(sp.pending_comment_rows([due], now), [])

    def test_private_video_does_not_burn_a_comment_attempt(self):
        import upload
        from unittest import mock
        rows = [{"video_id": "V", "pinned_comment": "x", "publish_at": "2026-01-01T00:00:00Z"}]
        with mock.patch.object(upload, "_ledger", return_value=rows), \
             mock.patch.object(upload, "_save_ledger") as save, \
             mock.patch.object(upload, "_creds", return_value=mock.MagicMock(token="t")), \
             mock.patch.object(upload, "granted_scopes", return_value=None), \
             mock.patch("googleapiclient.discovery.build", create=True), \
             mock.patch.object(upload, "_public_video_ids", return_value=set()), \
             mock.patch.object(upload, "post_comment") as post:
            upload.post_pending_comments()
        post.assert_not_called()
        saved = save.call_args.args[0]
        self.assertFalse(saved[0].get("comment_attempts"))

    def test_alert_opens_comments_and_closes_without_stealing_health_prefix(self):
        alerts = [{"slot": "night", "date": "2026-10-02", "attempts": 2, "reason": "retry cap"}]
        opened = sp.alert_plan(alerts, [])
        self.assertEqual(opened[0]["action"], "open")
        self.assertTrue(opened[0]["title"].startswith("Quiz slot uncovered:"))
        self.assertFalse(opened[0]["title"].startswith("health-alert:"))
        self.assertEqual(opened[0]["labels"], ["health-alert"])
        issues = [{"number": 9, "title": opened[0]["title"], "state": "open"}]
        commented = sp.alert_plan(alerts, issues)
        self.assertEqual(commented[0]["action"], "comment")
        self.assertEqual(commented[0]["number"], 9)
        closed = sp.alert_plan([], issues, covered={("night", "2026-10-02")})
        self.assertEqual(closed[0]["action"], "close")
        # The pipeline health check's issue is a different title and is left alone.
        foreign = [{"number": 3, "title": "health-alert: QUIZ PATHSHALA pipeline", "state": "open"}]
        self.assertEqual(sp.alert_plan([], foreign, covered=set()), [])

    def test_quota_math_stays_under_10k(self):
        steady = sp.quota_budget()
        self.assertTrue(steady["under_10k"], steady)
        self.assertEqual(steady["uploads"], 5 * 1600)
        self.assertEqual(steady["planner"], 72 * 3)
        self.assertLess(steady["total"], 10000)
        # Every comment insert fails its 3 tries: 5 videos × 3 × 50.
        worst = sp.quota_budget(comment_inserts=15)
        self.assertTrue(worst["under_10k"], worst)
        self.assertLess(worst["total"], 10000)


class WorkflowContractTests(unittest.TestCase):
    def test_catchup_crons_dispatch_public_and_do_not_upload(self):
        text = (ROOT / ".github/workflows/quiz-catchup.yml").read_text(encoding="utf-8")
        crons = [line.split('"')[1] for line in text.splitlines() if "cron:" in line]
        self.assertGreaterEqual(len(crons), 3)
        for cron in crons:
            minute = int(cron.split()[0])
            self.assertNotIn(minute, (0, 30), cron)
            self.assertEqual(minute % 2, 1, cron)
        self.assertIn("privacy=public", (ROOT / "kids-quiz-shorts/src/slot_planner.py").read_text(encoding="utf-8"))
        self.assertIn("--post-pending-comments", text)
        self.assertNotIn("src/build.py", text)
        self.assertNotIn("videos.insert", text)
        self.assertIn("quiz-catchup.yml",
                      (ROOT / ".github/workflows/quiz-tests.yml").read_text(encoding="utf-8"))

    def test_build_workflow_takes_a_date_and_checks_coverage_first(self):
        text = (ROOT / ".github/workflows/kids-gk-shorts.yml").read_text(encoding="utf-8")
        self.assertIn("date:", text)
        self.assertIn("needs.plan.outputs.action == 'build'", text)
        self.assertIn("inputs.date", text)
        self.assertIn("QUIZ_TTS_PROVIDER", text)
        for expr in sp.CRON_TO_SLOT:
            self.assertIn(expr, text)
        src = (ROOT / "kids-quiz-shorts/src/slot_planner.py").read_text(encoding="utf-8")
        self.assertNotIn("videos().insert", src)
        self.assertNotIn("videos.insert", src)

    def test_attempts_file_is_empty_object(self):
        data = json.loads((ROOT / "kids-quiz-shorts/data/slot_attempts.json").read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["slots"], {})


if __name__ == "__main__":
    unittest.main()
