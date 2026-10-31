"""Coverage planner for QUIZ PATHSHALA slots.

GitHub drops scheduled crons. This module decides which IST slot-times in the
next 36 hours have no public or scheduled YouTube video, and which one a late
run should fill. It does not render or upload.

Backup buffer: the catch-up workflow keeps the next 24–36 h of active slots
scheduled on YouTube (private + publishAt). That queue is the buffer. A dropped
runner does not empty a slot whose video is already scheduled. There is no
separate pre-render cache — one source of truth, no second copy of the MP4.

YouTube reads are cheap list calls only (about 3 quota units):
  channels.list mine=true            1
  playlistItems.list (uploads, 50)   1
  videos.list status,snippet         1
No upload, no video update, and no search.

Quota budget (YouTube project quiz-pathshala-yt, 10_000 units/day, reset
midnight Pacific):
  5 uploads × ~1_600                          8_000
  catch-up 3×/hour × 24 × 3 list units          216
  5 build-time coverage rechecks × 3              15
  pending-comment videos.list, upper bound       72
  5 comment inserts × 50                        250
  total                                       ~8_553  (under 10_000)

Worst case if every comment insert fails its 3 tries: 5 × 3 × 50 = 750
instead of 250, total ~9_053. Still under 10_000. One build per slot+date,
then at most one retry; after that a GitHub issue labelled health-alert.
Dispatch also stops at 5 new uploads per Pacific quota day.

QUIZ_ACTIVE_SLOTS (comma-separated slot names, empty = all five) is honoured
everywhere a slot list is built.

CLI (CI):
  python src/slot_planner.py prepare ...     # one build workflow: claim or skip
  python src/slot_planner.py catchup ...     # dispatcher: claim, dispatch, comments
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
PT = ZoneInfo("America/Los_Angeles")

# Next 36 h stays scheduled, so each slot is on YouTube well before the 12 h
# lead we want. 24 h of coverage is the subset we must not leave empty.
HORIZON_HOURS = 36
LEAD_HOURS = 12
IMMEDIATE_MINUTES = 10
LATE_GRACE_MINUTES = 45
# A late immediate post (up to LATE_GRACE after the slot) still belongs to
# that slot. Slots are 90 min apart at the closest, so 50 min cannot claim both.
MATCH_TOLERANCE = timedelta(minutes=50)
MAX_ATTEMPTS = 2          # first build + one retry
MAX_UPLOADS_PER_QUOTA_DAY = 5
IN_FLIGHT_MINUTES = 40    # build job timeout is 30
UPLOAD_UNITS = 1600
PLANNER_UNITS = 3
COMMENT_UNITS = 50
CATCHUP_RUNS_PER_DAY = 3 * 24

# Same crons as .github/workflows/kids-gk-shorts.yml. Unknown crons skip
# rather than defaulting to morning (that duplicated a slot).
CRON_TO_SLOT = {
    "0 6 * * *": "morning",
    "0 12 * * *": "noon",
    "30 14 * * *": "paheli",
    "0 16 * * *": "evening",
    "0 19 * * *": "night",
}

ATTEMPTS_REL = "kids-quiz-shorts/data/slot_attempts.json"
ALERT_LABEL = "health-alert"
ALERT_TITLE_PREFIX = "Quiz slot uncovered: "
WORKFLOW_NAME = "Quiz Pathshala GK Shorts"


# ---------------------------------------------------------------- time
def active_slots(raw=None):
    """QUIZ_ACTIVE_SLOTS. Empty or all-unknown → every slot, SLOT_ORDER order."""
    if raw is None:
        raw = os.getenv("QUIZ_ACTIVE_SLOTS", "")
    text = (raw or "").strip()
    if not text:
        return list(C.SLOT_ORDER)
    wanted = {part.strip() for part in text.split(",") if part.strip()}
    picked = [slot for slot in C.SLOT_ORDER if slot in wanted]
    return picked or list(C.SLOT_ORDER)


def slot_hm(slot):
    label = C.SLOTS[slot]
    hh, mm = label.split()[0].split(":")
    return int(hh), int(mm)


def parse_time(value):
    text = str(value).strip()
    if not text:
        raise ValueError("empty timestamp")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_rfc3339(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slot_datetime(slot, day):
    """day is a datetime.date. Returns that slot's clock time as aware IST."""
    hour, minute = slot_hm(slot)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


def quota_day(now):
    """YouTube Data API quota resets at midnight Pacific."""
    return now.astimezone(PT).date().isoformat()


def classify_timing(when, now):
    """schedule | immediate | late | past.

    under ~10 min left → publish now (YouTube rejects a publishAt that the
    upload itself would miss). Up to LATE_GRACE after the slot, a late post
    still counts — a late complete post beats a skip.
    """
    now = now.astimezone(timezone.utc)
    when = when.astimezone(timezone.utc)
    delta = when - now
    if delta > timedelta(minutes=IMMEDIATE_MINUTES):
        return "schedule"
    if delta > timedelta(0):
        return "immediate"
    if now - when <= timedelta(minutes=LATE_GRACE_MINUTES):
        return "late"
    return "past"


def nearest_slot(when, slots=None):
    """Map a timestamp to (slot, IST date) or None.

    publishAt wins over the upload clock. One video covers one slot: the
    nearest clock time within MATCH_TOLERANCE. Ties go to the earlier slot
    (the one a late post is catching).
    """
    slots = list(slots or C.SLOT_ORDER)
    when_ist = when.astimezone(IST)
    best = None
    best_delta = None
    for slot in slots:
        hour, minute = slot_hm(slot)
        target = when_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        delta = abs(when_ist - target)
        if delta > MATCH_TOLERANCE:
            continue
        if best_delta is None or delta < best_delta or (
            delta == best_delta and target < best[2]
        ):
            best = (slot, when_ist.date().isoformat(), target)
            best_delta = delta
    if best is None:
        return None
    return best[0], best[1]


def occurrences(now, slots, horizon_hours=HORIZON_HOURS, late_grace_minutes=LATE_GRACE_MINUTES):
    """Active slot times from (now - grace) through (now + horizon), IST dates."""
    now_ist = now.astimezone(IST)
    start = now_ist - timedelta(minutes=late_grace_minutes)
    end = now_ist + timedelta(hours=horizon_hours)
    day = start.date() - timedelta(days=1)
    last = end.date() + timedelta(days=1)
    out = []
    while day <= last:
        for slot in slots:
            when = slot_datetime(slot, day)
            if start <= when <= end:
                out.append({"slot": slot, "date": day.isoformat(), "when": when})
        day += timedelta(days=1)
    out.sort(key=lambda item: item["when"])
    return out


# ---------------------------------------------------------------- coverage
def covered_from_videos(videos, slots=None):
    """Public videos and scheduled ones (status.publishAt). Unlisted tests do not count."""
    slots = list(slots or C.SLOT_ORDER)
    keys = set()
    for video in videos or []:
        if not isinstance(video, dict):
            continue
        privacy = (video.get("privacyStatus") or "").lower()
        publish_at = video.get("publishAt")
        try:
            if publish_at:
                when = parse_time(publish_at)
            elif privacy == "public" and video.get("publishedAt"):
                when = parse_time(video["publishedAt"])
            else:
                continue
        except ValueError:
            continue
        key = nearest_slot(when, slots)
        if key:
            keys.add(key)
    return keys


def _uploaded_ist(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        naive = datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return naive.replace(tzinfo=IST)


def covered_from_ledger(rows, slots=None):
    """Ledger supplement. The `date` field is the build day, not the slot day.

    Un7jdLyS23w was built on 2026-10-02 and publishAt 2026-10-03T02:00:00Z
    (morning 3 Oct). Coverage follows publishAt, never the build date.
    """
    slots = list(slots or C.SLOT_ORDER)
    keys = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("publish_at"):
            try:
                when = parse_time(row["publish_at"])
            except ValueError:
                continue
            key = nearest_slot(when, slots)
            if key:
                keys.add(key)
            continue
        if (row.get("privacy") or "").lower() != "public":
            continue
        when = _uploaded_ist(row.get("uploaded_ist"))
        if when is None:
            continue
        key = nearest_slot(when, slots)
        if key:
            keys.add(key)
    return keys


def uncovered_slots(now, covered, active):
    """Slot occurrences in the horizon that still need a video."""
    needed = []
    for occ in occurrences(now, active):
        mode = classify_timing(occ["when"], now)
        if mode == "past":
            continue
        if (occ["slot"], occ["date"]) in covered:
            continue
        needed.append({
            "slot": occ["slot"],
            "date": occ["date"],
            "when": occ["when"],
            "mode": mode,
            "publish_at": None if mode in ("immediate", "late") else to_rfc3339(occ["when"]),
            "immediate": mode in ("immediate", "late"),
        })
    return needed


# ---------------------------------------------------------------- attempts / quota
def empty_state():
    return {"version": 1, "slots": {}}


def slot_key(slot, date):
    return f"{slot}|{date}"


def _in_flight(rec, now):
    if not isinstance(rec, dict) or rec.get("state") != "dispatched":
        return False
    try:
        started = parse_time(rec.get("dispatched_at") or "")
    except ValueError:
        return False
    return now - started <= timedelta(minutes=IN_FLIGHT_MINUTES)


def quota_reserved(state, now):
    day = quota_day(now)
    count = 0
    for rec in (state.get("slots") or {}).values():
        if not isinstance(rec, dict):
            continue
        if rec.get("counts_quota") and rec.get("quota_day") == day and rec.get("state") != "failed":
            count += 1
    return count


def reconcile(state, now, covered):
    """Mark covered claims uploaded. Expire stale dispatches so a retry can run."""
    state = {"version": 1, "slots": {k: dict(v) for k, v in (state.get("slots") or {}).items()}}
    for key, rec in state["slots"].items():
        slot, date = key.split("|", 1)
        if (slot, date) in covered:
            rec["state"] = "uploaded"
            rec["counts_quota"] = True
            rec["uploaded_at"] = rec.get("uploaded_at") or to_rfc3339(now)
            continue
        if rec.get("state") != "dispatched":
            continue
        try:
            started = parse_time(rec.get("dispatched_at") or "")
        except ValueError:
            started = now - timedelta(minutes=IN_FLIGHT_MINUTES + 1)
        if now - started > timedelta(minutes=IN_FLIGHT_MINUTES):
            rec["state"] = "failed"
            rec["counts_quota"] = False
            rec["failed_at"] = to_rfc3339(now)
    return state


def select_dispatches(needed, state, now, limit=None):
    """Claim uncovered slots, soonest first, without duplicating an in-flight build.

    Returns dispatch (newly claimed), alerts (retry cap hit), and the new state.
    """
    state = {"version": 1, "slots": {k: dict(v) for k, v in (state.get("slots") or {}).items()}}
    slots = state["slots"]
    reserved = quota_reserved(state, now)
    dispatch = []
    alerts = []
    day = quota_day(now)
    for item in needed:
        key = slot_key(item["slot"], item["date"])
        rec = slots.get(key) or {}
        attempts = int(rec.get("attempts") or 0)
        if _in_flight(rec, now):
            continue
        if attempts >= MAX_ATTEMPTS:
            alerts.append({
                "slot": item["slot"],
                "date": item["date"],
                "attempts": attempts,
                "reason": "retry cap",
            })
            continue
        if limit is not None and len(dispatch) >= limit:
            continue
        if reserved >= MAX_UPLOADS_PER_QUOTA_DAY:
            continue
        attempts += 1
        slots[key] = {
            "attempts": attempts,
            "state": "dispatched",
            "dispatched_at": to_rfc3339(now),
            "quota_day": day,
            "counts_quota": True,
        }
        reserved += 1
        dispatch.append({**item, "attempt": attempts})
    return {"dispatch": dispatch, "alerts": alerts, "state": state, "quota_reserved": reserved}


def _build(slot, date, when, mode, reason):
    immediate = mode in ("immediate", "late")
    return {
        "action": "build",
        "slot": slot,
        "date": date,
        "privacy": "public",
        "publish_at": "" if immediate else to_rfc3339(when),
        "immediate": immediate,
        "skip_coverage": False,
        "mode": mode,
        "reason": reason,
    }


def _skip(reason, alert=False):
    return {
        "action": "skip",
        "slot": "",
        "date": "",
        "privacy": "public",
        "publish_at": "",
        "immediate": False,
        "skip_coverage": False,
        "reason": reason,
        "alert": alert,
    }


def decide_unscheduled(slot, now, covered, active):
    """Cron / manual public run with no explicit date.

    If today's slot has not passed (or is inside the late grace) and is
    uncovered, build it. If it has passed, fill the nearest uncovered upcoming
    slot — not the same slot tomorrow when that one is already covered.
    """
    if slot not in active:
        return _skip(f"inactive {slot}")
    today = now.astimezone(IST).date()
    when = slot_datetime(slot, today)
    mode = classify_timing(when, now)
    if mode != "past":
        if (slot, today.isoformat()) in covered:
            return _skip(f"covered {slot} {today.isoformat()}")
        return _build(slot, today.isoformat(), when, mode, f"today {mode}")
    needed = uncovered_slots(now, covered, active)
    if not needed:
        return _skip("no uncovered slot in the next 36h")
    nxt = needed[0]
    return _build(nxt["slot"], nxt["date"], nxt["when"], nxt["mode"],
                  f"retarget {slot} → {nxt['slot']} {nxt['date']} ({nxt['mode']})")


def decide_explicit(slot, date, now, covered, active):
    """Catch-up asked for this exact slot+date. Do not retarget the content."""
    if slot not in active:
        return _skip(f"inactive {slot}")
    try:
        year, month, day = (int(p) for p in date.split("-"))
        when = slot_datetime(slot, datetime(year, month, day).date())
    except (ValueError, AttributeError):
        return _skip(f"bad date {date!r}")
    mode = classify_timing(when, now)
    if mode == "past":
        return _skip(f"past {slot} {date}")
    if (slot, date) in covered:
        return _skip(f"covered {slot} {date}")
    return _build(slot, date, when, mode, f"explicit {mode}")


def prepare_decision(*, event, privacy, requested_slot, requested_date, schedule,
                     now, covered, active, state):
    """Returns (decision, new_state or None). new_state is set only for a new claim."""
    privacy = (privacy or "public").strip().lower()
    requested_date = (requested_date or "").strip()
    requested_slot = (requested_slot or "").strip()
    if event == "workflow_dispatch" and privacy != "public":
        day = requested_date or now.astimezone(IST).date().isoformat()
        return ({
            "action": "build",
            "slot": requested_slot or "morning",
            "date": day,
            "privacy": privacy,
            "publish_at": "",
            "immediate": True,
            "skip_coverage": True,
            "reason": "manual non-public upload",
        }, None)
    if event == "schedule":
        requested_slot = CRON_TO_SLOT.get((schedule or "").strip(), "")
        requested_date = ""
        if not requested_slot:
            return _skip("unknown schedule"), None
    if requested_date:
        decision = decide_explicit(requested_slot, requested_date, now, covered, active)
        if decision["action"] != "build":
            return decision, None
        # The dispatcher already claimed this slot. Building it is that claim,
        # not a second one. A manual dated run that nobody claimed yet claims now.
        rec = (state.get("slots") or {}).get(slot_key(decision["slot"], decision["date"])) or {}
        if _in_flight(rec, now):
            decision["reason"] = "in-flight claim; this run builds it"
            return decision, None
        sel = select_dispatches([_needed_from(decision, now)], state, now, limit=1)
        if not sel["dispatch"]:
            return _skip(f"not claimed {decision['slot']} {decision['date']}"), None
        return decision, sel["state"]
    decision = decide_unscheduled(requested_slot, now, covered, active)
    if decision["action"] != "build":
        return decision, None
    if decision["reason"].startswith("today "):
        candidates = [_needed_from(decision, now)]
    else:
        candidates = uncovered_slots(now, covered, active)
    sel = select_dispatches(candidates, state, now, limit=1)
    if not sel["dispatch"]:
        alert = bool(sel["alerts"])
        why = "attempts exhausted" if alert else "in flight or quota"
        return _skip(why, alert=alert), None
    item = sel["dispatch"][0]
    built = _build(item["slot"], item["date"], item["when"], item["mode"],
                   decision["reason"] if item["slot"] == decision["slot"] and item["date"] == decision["date"]
                   else f"claim {item['slot']} {item['date']} ({item['mode']})")
    return built, sel["state"]


def _needed_from(decision, now):
    when = slot_datetime(decision["slot"], datetime.fromisoformat(decision["date"]).date())
    mode = decision.get("mode") or classify_timing(when, now)
    return {
        "slot": decision["slot"],
        "date": decision["date"],
        "when": when,
        "mode": mode,
        "publish_at": decision.get("publish_at") or None,
        "immediate": bool(decision.get("immediate")),
    }


def plan_catchup(now, videos, ledger_rows, active, state):
    """Reconcile, then claim every uncovered slot the quota still allows."""
    covered = covered_from_videos(videos) | covered_from_ledger(ledger_rows)
    state = reconcile(state or empty_state(), now, covered)
    needed = uncovered_slots(now, covered, active)
    selected = select_dispatches(needed, state, now)
    return {
        "covered": sorted(covered),
        "needed": [{k: v for k, v in item.items() if k != "when"} | {"when": to_rfc3339(item["when"])}
                   for item in needed],
        "dispatch": [{k: v for k, v in item.items() if k != "when"} | {"when": to_rfc3339(item["when"])}
                     for item in selected["dispatch"]],
        "alerts": selected["alerts"],
        "state": selected["state"],
        "quota_reserved": selected["quota_reserved"],
    }


def quota_budget(active_n=5, planner_runs=CATCHUP_RUNS_PER_DAY, comment_inserts=5,
                 comment_lists=None, build_rechecks=None):
    """Units this design spends on a full day. Must stay under 10_000."""
    if comment_lists is None:
        comment_lists = planner_runs
    if build_rechecks is None:
        build_rechecks = active_n
    uploads = active_n * UPLOAD_UNITS
    planner = planner_runs * PLANNER_UNITS
    recheck = build_rechecks * PLANNER_UNITS
    lists = comment_lists * 1
    comments = comment_inserts * COMMENT_UNITS
    total = uploads + planner + recheck + lists + comments
    return {
        "uploads": uploads,
        "planner": planner,
        "recheck": recheck,
        "comment_lists": lists,
        "comments": comments,
        "total": total,
        "under_10k": total < 10000,
        "horizon_hours": HORIZON_HOURS,
        "lead_hours": LEAD_HOURS,
    }


# ---------------------------------------------------------------- alerts
def alert_title(slot, date):
    return f"{ALERT_TITLE_PREFIX}{slot} {date}"


def alert_plan(alerts, open_issues, covered=None):
    """Open or comment. Close our issues once that slot+date is covered.

    Titles do NOT start with 'health-alert:' — the read-only health check
    owns that prefix and would rewrite or close the issue. The label is
    health-alert, which is what operators filter on.
    """
    covered = set(covered or [])
    actions = []
    ours = []
    for issue in open_issues or []:
        title = issue.get("title") or ""
        if not title.startswith(ALERT_TITLE_PREFIX):
            continue
        ours.append(issue)
    open_by_title = {issue.get("title"): issue for issue in ours if (issue.get("state") or "open") == "open"}
    for alert in alerts or []:
        title = alert_title(alert["slot"], alert["date"])
        body = (
            f"Slot `{alert['slot']}` on {alert['date']} (IST) is still uncovered "
            f"after {alert['attempts']} build attempt(s). Max is one retry, so this "
            "slot will not be dispatched again until the issue is closed or the "
            "attempt record is cleared.\n\n"
            "Hinglish: is slot+date par video nahi bani. Ek retry ho chuka. "
            "Loop nahi chalayenge — log dekho, phir issue band karke attempts reset karo."
        )
        existing = open_by_title.get(title)
        if existing:
            actions.append({"action": "comment", "number": existing.get("number"), "title": title, "body": body})
        else:
            actions.append({
                "action": "open",
                "title": title,
                "body": body,
                "labels": [ALERT_LABEL],
            })
    for issue in ours:
        title = issue.get("title") or ""
        rest = title[len(ALERT_TITLE_PREFIX):]
        parts = rest.split()
        if len(parts) != 2:
            continue
        if (parts[0], parts[1]) in covered:
            actions.append({
                "action": "close",
                "number": issue.get("number"),
                "title": title,
                "body": f"{title} is covered now. Closing.",
            })
    return actions


# ---------------------------------------------------------------- pending comments (pure)
def is_pending_comment(row, now_rfc3339, max_attempts=3):
    """A ledger row still waiting for a top-level comment.

    Future publishAt stays pending but is not due. Once comment_posted is set
    the row leaves this set (the upload history row itself stays).
    max_attempts matches upload.COMMENT_MAX_ATTEMPTS.
    """
    if not isinstance(row, dict):
        return False
    if not row.get("pinned_comment") or row.get("comment_posted"):
        return False
    if int(row.get("comment_attempts") or 0) >= max_attempts:
        return False
    if (row.get("publish_at") or "") > now_rfc3339:
        return False
    return True


def pending_comment_rows(rows, now_rfc3339, max_attempts=3):
    return [row for row in rows or [] if is_pending_comment(row, now_rfc3339, max_attempts)]


# ---------------------------------------------------------------- youtube (list only)
def fetch_videos(yt, max_results=50):
    """channels.list + playlistItems.list + videos.list. About 3 units. No writes."""
    channels = yt.channels().list(part="contentDetails", mine=True, maxResults=1).execute()
    items = channels.get("items") or []
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    page = yt.playlistItems().list(
        part="contentDetails", playlistId=uploads, maxResults=max_results,
    ).execute()
    ids = [
        it["contentDetails"]["videoId"]
        for it in page.get("items") or []
        if it.get("contentDetails", {}).get("videoId")
    ]
    if not ids:
        return []
    listed = yt.videos().list(part="status,snippet", id=",".join(ids[:50])).execute()
    out = []
    for video in listed.get("items") or []:
        status = video.get("status") or {}
        snippet = video.get("snippet") or {}
        out.append({
            "id": video.get("id"),
            "privacyStatus": status.get("privacyStatus"),
            "publishAt": status.get("publishAt"),
            "publishedAt": snippet.get("publishedAt"),
        })
    return out


def youtube_client():
    from upload import _creds
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_creds(), cache_discovery=False)


def load_ledger(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def load_state_text(text):
    try:
        data = json.loads(text) if text else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return empty_state()
    slots = data.get("slots") if isinstance(data.get("slots"), dict) else {}
    return {"version": 1, "slots": slots}


def dump_state(state):
    slots = state.get("slots") or {}
    ordered = {key: slots[key] for key in sorted(slots)}
    return json.dumps({"version": 1, "slots": ordered}, ensure_ascii=False, indent=1) + "\n"


# ---------------------------------------------------------------- git claim
def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True,
    )


def _repo_root():
    return Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())


def update_attempts(repo, branch, mutator, message, attempts=5):
    """Serialize claims with git push. mutator(state) -> (result, new_state or None)."""
    repo = Path(repo)
    rel = ATTEMPTS_REL
    for attempt in range(1, attempts + 1):
        _git(repo, "fetch", "--quiet", "origin", branch)
        shown = _git(repo, "show", f"origin/{branch}:{rel}", check=False)
        state = load_state_text(shown.stdout if shown.returncode == 0 else "")
        result, new_state = mutator(state)
        if new_state is None:
            return result
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_state(new_state), encoding="utf-8")
        _git(repo, "add", "--", rel)
        committed = _git(repo, "commit", "-m", message, check=False)
        if committed.returncode != 0:
            blob = (committed.stdout or "") + (committed.stderr or "")
            if "nothing to commit" in blob or "nothing added to commit" in blob:
                return result
            raise SystemExit(f"[planner] commit failed: {blob[-300:]}")
        pushed = _git(repo, "push", "--quiet", "origin", f"HEAD:{branch}", check=False)
        if pushed.returncode == 0:
            return result
        _git(repo, "reset", "--hard", f"origin/{branch}")
        time.sleep(min(20, 2 ** attempt))
    raise SystemExit("[planner] slot_attempts.json push nahi hua")


def _emit(decision):
    fields = {
        "action": decision.get("action") or "skip",
        "slot": decision.get("slot") or "",
        "date": decision.get("date") or "",
        "privacy": decision.get("privacy") or "public",
        "publish_at": decision.get("publish_at") or "",
        "immediate": "true" if decision.get("immediate") else "false",
        "skip_coverage": "true" if decision.get("skip_coverage") else "false",
        "reason": (decision.get("reason") or "").replace("\n", " ")[:300],
    }
    print(json.dumps({**decision, "publish_at": fields["publish_at"]}, default=str))
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for key, value in fields.items():
                fh.write(f"{key}={value}\n")
    return fields


def _covered_now(ledger_path):
    yt = youtube_client()
    videos = fetch_videos(yt)
    ledger = load_ledger(ledger_path)
    return covered_from_videos(videos) | covered_from_ledger(ledger), videos, ledger


def dispatch_stagger_seconds(raw=None):
    """Seconds between catch-up dispatches (env QUIZ_DISPATCH_STAGGER_SEC, default 150, 0-600)."""
    if raw is None:
        raw = os.getenv("QUIZ_DISPATCH_STAGGER_SEC", "150")
    try:
        v = int(float(raw))
    except (TypeError, ValueError):
        v = 150
    return max(0, min(600, v))


def _dispatch_one(repo, workflow, slot, date):
    cmd = [
        "gh", "workflow", "run", workflow, "--repo", repo,
        "-f", f"slot={slot}",
        "-f", f"date={date}",
        "-f", "privacy=public",
    ]
    subprocess.run(cmd, check=True)


def _list_issues(repo):
    proc = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--label", ALERT_LABEL,
         "--state", "open", "--limit", "50", "--json", "number,title,state"],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(proc.stdout or "[]")
    return data if isinstance(data, list) else []


def _apply_alerts(actions, repo):
    if not actions:
        return
    subprocess.run(
        ["gh", "label", "create", ALERT_LABEL, "--repo", repo, "--color", "d93f0b",
         "--description", "Quiz slot missed after the retry cap", "--force"],
        check=False,
    )
    for action in actions:
        if action["action"] == "open":
            subprocess.run(
                ["gh", "issue", "create", "--repo", repo, "--title", action["title"],
                 "--body", action["body"], "--label", ALERT_LABEL],
                check=True,
            )
        elif action["action"] == "comment" and action.get("number"):
            subprocess.run(
                ["gh", "issue", "comment", str(action["number"]), "--repo", repo,
                 "--body", action["body"]],
                check=True,
            )
        elif action["action"] == "close" and action.get("number"):
            subprocess.run(
                ["gh", "issue", "comment", str(action["number"]), "--repo", repo,
                 "--body", action["body"]],
                check=False,
            )
            subprocess.run(
                ["gh", "issue", "close", str(action["number"]), "--repo", repo,
                 "--reason", "completed"],
                check=False,
            )


def cmd_prepare(args):
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    active = active_slots(args.active_slots if args.active_slots is not None else None)
    event = args.event or "schedule"
    privacy = args.privacy or ""
    if event == "workflow_dispatch" and privacy and privacy != "public":
        decision, _state = prepare_decision(
            event=event, privacy=privacy, requested_slot=args.slot or "",
            requested_date=args.date or "", schedule=args.schedule or "",
            now=now, covered=set(), active=active, state=empty_state(),
        )
        _emit(decision)
        return 0
    try:
        covered, _videos, _ledger = _covered_now(args.ledger)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — fail closed, do not upload blind
        print(f"::warning::coverage check failed ({type(exc).__name__}: {exc}) — build skip")
        _emit(_skip(f"coverage check failed: {type(exc).__name__}"))
        return 0

    def mutate(state):
        reconciled = reconcile(state, now, covered)
        decision, claimed = prepare_decision(
            event=event, privacy=privacy or "public", requested_slot=args.slot or "",
            requested_date=args.date or "", schedule=args.schedule or "",
            now=now, covered=covered, active=active, state=reconciled,
        )
        final = claimed if claimed is not None else reconciled
        if dump_state(final) == dump_state(state):
            return decision, None
        return decision, final

    if args.push:
        decision = update_attempts(_repo_root(), args.branch, mutate,
                                   "chore(quiz): claim slot [skip ci]")
    else:
        shown = Path(args.state) if args.state else None
        state = load_state_text(shown.read_text(encoding="utf-8") if shown and shown.exists() else "")
        decision, _new = mutate(state)
    _emit(decision)
    return 0


def cmd_catchup(args):
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    active = active_slots(None if args.active_slots is None else args.active_slots)
    try:
        covered, videos, ledger = _covered_now(args.ledger)
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::planner failed ({type(exc).__name__}: {exc}) — no dispatch")
        return 0
    repo_name = args.repo
    root = _repo_root()

    def mutate(state):
        plan = plan_catchup(now, videos, ledger, active, state)
        final = plan["state"]
        if dump_state(final) == dump_state(state):
            return plan, None
        return plan, final

    if args.push:
        plan = update_attempts(root, args.branch, mutate, "chore(quiz): schedule uncovered slots [skip ci]")
    else:
        plan, _new = mutate(empty_state())
    print(json.dumps({
        "dispatch": [
            {"slot": item["slot"], "date": item["date"], "attempt": item["attempt"],
             "mode": item["mode"], "publish_at": item.get("publish_at")}
            for item in plan["dispatch"]
        ],
        "alerts": plan["alerts"],
        "quota_reserved": plan["quota_reserved"],
    }, default=str))
    if args.dispatch:
        stagger = dispatch_stagger_seconds()
        for n, item in enumerate(plan["dispatch"]):
            if n and stagger:
                # Gemini TTS free tier: 5 builds ek saath -> 429 -> Edge voice.
                # Builds ko thoda aage-peeche start karo (slots/date wahi).
                print(f"[catchup] {stagger}s ruk ke agla dispatch (Gemini 429 se bachne ke liye)")
                time.sleep(stagger)
            print(f"[catchup] dispatch {item['slot']} {item['date']} privacy=public")
            _dispatch_one(repo_name, args.workflow, item["slot"], item["date"])
        try:
            issues = _list_issues(repo_name)
            actions = alert_plan(plan["alerts"], issues, covered)
            _apply_alerts(actions, repo_name)
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::health-alert issue update failed: {type(exc).__name__}: {exc}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="QUIZ PATHSHALA slot coverage planner")
    sub = ap.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--event", default="schedule")
    prep.add_argument("--slot", default="")
    prep.add_argument("--date", default="")
    prep.add_argument("--privacy", default="")
    prep.add_argument("--schedule", default="")
    prep.add_argument("--branch", default="main")
    prep.add_argument("--push", action="store_true")
    prep.add_argument("--now", default="")
    prep.add_argument("--active-slots", default=None)
    prep.add_argument("--ledger", default="data/uploads.json")
    prep.add_argument("--state", default="")
    prep.set_defaults(func=cmd_prepare)

    catch = sub.add_parser("catchup")
    catch.add_argument("--branch", default="main")
    catch.add_argument("--push", action="store_true")
    catch.add_argument("--dispatch", action="store_true")
    catch.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    catch.add_argument("--workflow", default=WORKFLOW_NAME)
    catch.add_argument("--now", default="")
    catch.add_argument("--active-slots", default=None)
    catch.add_argument("--ledger", default="data/uploads.json")
    catch.set_defaults(func=cmd_catchup)

    args = ap.parse_args(argv)
    if args.active_slots is None and "QUIZ_ACTIVE_SLOTS" in os.environ:
        args.active_slots = os.environ.get("QUIZ_ACTIVE_SLOTS")
    elif args.active_slots is None:
        args.active_slots = None
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())


def proposed_slots(enabled=None):
    """Evening-heavy proposal (config.EVENING_HEAVY, default OFF).
    OFF -> live C.SLOTS. Live schedule/cron ko ye function nahi chhoota."""
    import config as C
    on = C.EVENING_HEAVY if enabled is None else enabled
    return dict(C.EVENING_HEAVY_SLOTS if on else C.SLOTS)
