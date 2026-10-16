"""Read-only health check for the QUIZ PATHSHALA upload pipeline.

Nothing here uploads a video or writes to YouTube. The only YouTube calls are
an OAuth token refresh, tokeninfo (scopes), and channels.list part=snippet
mine=true (1 quota unit). There is no video insert, video update, channel
update, or comment insert. Exact daily quota remaining is not in the API; it
lives in the GCP console for project quiz-pathshala-yt.

Secrets are read from the environment and must never be printed, logged, or
copied into a GitHub issue. HTTP redirects are not followed, so a token is
not sent to another host.

    python src/healthcheck.py            # CI: checks + health-alert issue
    python src/healthcheck.py --dry-run  # print the report, do not touch issues
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import tts  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))

# Channel the upload token must belong to. Public id, not a secret.
EXPECTED_CHANNEL_ID = "UCSIJMHyB_h02gHc5HZkmYqg"
EXPECTED_CHANNEL_TITLE = "QUIZ PATHSHALA"
GCP_QUOTA_PROJECT = "quiz-pathshala-yt"

# Same set as upload.py SCOPES. Refresh itself does not send a scope param.
REQUIRED_SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
)
QUOTA_REASONS = ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded")

# Build crons from .github/workflows/kids-gk-shorts.yml (UTC). These are when
# GitHub *starts* the upload, not the IST publish clock (that is publishAt).
UPLOAD_CRONS = {
    "morning": "0 6 * * *",
    "noon": "0 12 * * *",
    "paheli": "30 14 * * *",
    "evening": "0 16 * * *",
    "night": "0 19 * * *",
}
UPLOAD_WORKFLOW_FILE = "kids-gk-shorts.yml"

# 3x daily, shortly before each cluster of those build crons.
# Lead is 45–75 min so a typical 5–30 min GitHub slip still lands first.
# Multi-hour slips are not something a "shortly before" cron can outrun; the
# missed-run check waits SCHEDULE_GRACE_HOURS instead.
HEALTH_CRONS = (
    ("45 4 * * *", ("morning",)),
    ("15 11 * * *", ("noon", "paheli")),
    ("15 15 * * *", ("evening", "night")),
)

# kids-gk-shorts.yml is often 10–20h late, which is why its crons fire ~20h
# before publish. Wait 22h after the cron timestamp before calling a slot
# missing, and accept a schedule run created in the following 23h (so the
# next day's cron, at +24h, is not counted as this one).
SCHEDULE_GRACE_HOURS = 22
SCHEDULE_MATCH_HOURS = 23
RECENT_RUN_HOURS = 48
# GitHub runs list: 100 runs of kids-gk-shorts.yml ~1.5 MB JSON (har run me
# poora repository object aata hai). Pehle body 1_000_000 byte par kaat di
# jaati thi -> JSON adhoora -> payload None -> "wf_api_error (http 200)"
# (runs 37501775483, 37525759888, 37613252532). Ab cap 8 MB, aur list sirf
# utni purani jitni checks ko chahiye (WORKFLOW_LOOKBACK_HOURS).
MAX_BODY_BYTES = 8_000_000
WORKFLOW_LOOKBACK_HOURS = 72
STUCK_RUN_HOURS = 2
BAD_CONCLUSIONS = ("failure", "timed_out", "startup_failure", "action_required", "stale")

# ElevenLabs: warn when remaining characters cannot cover this many days of
# uploads at the current active-slot count. Usage is the mean length of the
# lines build.py actually sends (question, options, CTA, answer — and hint
# only if HINT_BEFORE_ANSWER). The runner has no voice cache, so the CTA is
# counted on every question, every video.
CREDIT_COVER_DAYS = 2
# README's older ~450/video figure, used only when a pool is empty.
FALLBACK_CHARS_PER_VIDEO = 450

# DeepSeek balance is informational. Quiz uploads do not call DeepSeek;
# daily-finance.yml does. Alert when the key is rejected, is_available is
# false, or every reported currency is at or below this dust line. This is
# not a 2-day cost forecast — the API does not expose a burn rate.
DEEPSEEK_MIN_BALANCE = {"USD": 0.50, "CNY": 1.0}
DEEPSEEK_MIN_BALANCE_DEFAULT = 0.50
DEEPSEEK_DEFAULT_BASE = "https://api.deepseek.com"

ISSUE_TITLE = "health-alert: QUIZ PATHSHALA pipeline"
ISSUE_LABEL = "health-alert"
_FP_RE = re.compile(r"<!-- health-fingerprint: ([a-z0-9_,-]*) -->")

YT_SECRET_ENV = (
    ("YOUTUBE_CLIENT_ID", "YT_CLIENT_ID"),
    ("YOUTUBE_CLIENT_SECRET", "YT_CLIENT_SECRET"),
    ("YOUTUBE_REFRESH_TOKEN", "YT_REFRESH_TOKEN"),
)

TOKEN_URL = "https://oauth2.googleapis.com/token"
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
ELEVEN_SUB_URL = "https://api.elevenlabs.io/v1/user/subscription"

_SECRET_RE = re.compile(
    r"access_token=[^&\s]+"
    r"|refresh_token=[^&\s]+"
    r"|client_secret=[^&\s]+"
    r"|xi-api-key(?:=|\s+)[^\s]+"
    r"|sk[-_][A-Za-z0-9]+"
    r"|GOCSPX-[A-Za-z0-9_\-]+"
    r"|ya29\.[A-Za-z0-9_\-]+"
    r"|1//[A-Za-z0-9_\-]+"
    r"|AIza[0-9A-Za-z_\-]{20,}"
    r"|(?i:bearer\s+[A-Za-z0-9._\-]+)"
    r"|//[^/@\s]+:[^/@\s]+@"
)


class Finding:
    def __init__(self, check, level, code, hinglish, english):
        self.check = check
        self.level = level  # ok | warn | fail
        self.code = code
        self.hinglish = hinglish
        self.english = english

    @property
    def problem(self):
        return self.level != "ok"


class Report:
    def __init__(self, findings, generated_at, active_slots, eleven_threshold, run_url=""):
        self.findings = list(findings)
        self.generated_at = generated_at
        self.active_slots = list(active_slots)
        self.eleven_threshold = eleven_threshold
        self.run_url = run_url

    @property
    def healthy(self):
        return not any(f.problem for f in self.findings)

    @property
    def fingerprint(self):
        return ",".join(sorted(f.code for f in self.findings if f.problem))


class ClientResponse:
    def __init__(self, status, payload, text=""):
        self.status = status
        self.payload = payload
        self.text = text


def redact(text):
    if not text:
        return ""
    return _SECRET_RE.sub("REDACTED", str(text))


def fmt_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fmt_ist(dt):
    return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")


def parse_utc(value):
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cron_hour_minute(expr):
    minute_s, hour_s, dom, mon, dow = expr.split()
    if (dom, mon, dow) != ("*", "*", "*"):
        raise ValueError(f"unsupported cron {expr}")
    return int(hour_s), int(minute_s)


def parse_active_slots(raw):
    """Same rule as config.ACTIVE_SLOTS, plus the unknown names.

    Empty / all-unknown falls back to every slot. A mix keeps the known ones
    in SLOT_ORDER. Unknown names are returned so the report can warn.
    """
    text = (raw or "").strip()
    if not text:
        return list(C.SLOT_ORDER), []
    wanted = [part.strip() for part in text.split(",") if part.strip()]
    known = [slot for slot in C.SLOT_ORDER if slot in set(wanted)]
    unknown = [name for name in wanted if name not in C.SLOT_ORDER]
    if not known:
        return list(C.SLOT_ORDER), unknown
    return known, unknown


def latest_cron_at(now, hour, minute):
    now = now.astimezone(timezone.utc)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def occurrence_under_test(now, hour, minute, grace):
    """The cron fire that should already have produced a workflow run.

    The latest fire is still inside `grace` (GitHub may not have started it).
    In that case require the previous day's fire, which is already past grace
    as long as grace is under 24h.
    """
    latest = latest_cron_at(now, hour, minute)
    if now >= latest + grace:
        return latest
    return latest - timedelta(days=1)


def due_occurrences(now, active_slots, grace_hours=SCHEDULE_GRACE_HOURS):
    grace = timedelta(hours=grace_hours)
    due = []
    for slot in active_slots:
        expr = UPLOAD_CRONS.get(slot)
        if not expr:
            continue
        hour, minute = cron_hour_minute(expr)
        due.append((slot, occurrence_under_test(now, hour, minute, grace)))
    return due


def _maximum_matching(adj, run_count):
    match_to = [-1] * run_count

    def dfs(slot_i, seen):
        for run_i in adj[slot_i]:
            if run_i in seen:
                continue
            seen.add(run_i)
            prev = match_to[run_i]
            if prev == -1 or dfs(prev, seen):
                match_to[run_i] = slot_i
                return True
        return False

    matched = 0
    for slot_i in range(len(adj)):
        if dfs(slot_i, set()):
            matched += 1
    return matched


def match_schedule_runs(occurrences, runs, match_hours=SCHEDULE_MATCH_HOURS):
    """How many due slot-fires can each be given a distinct schedule run.

    GitHub's runs API does not say which cron started a run, and a 10–20h
    delay makes the windows overlap, so this is a matching problem rather
    than "the run closest to this slot". Returns (matched_count, slots whose
    window contains no schedule run at all).
    """
    schedule_runs = [run for run in runs if run.get("event") == "schedule"]
    window = timedelta(hours=match_hours)
    adj = []
    empty_slots = []
    for slot, start in occurrences:
        end = start + window
        hits = [
            i for i, run in enumerate(schedule_runs)
            if start <= run["created_at"] < end
        ]
        adj.append(hits)
        if not hits:
            empty_slots.append(slot)
    return _maximum_matching(adj, len(schedule_runs)), empty_slots


# ---------------------------------------------------------------- usage / bank
def spoken_char_count(question):
    """Characters ElevenLabs is sent for one question, after clean_for_tts.

    build.py calls these inside the per-question loop (CTA every question,
    not once per video). Hint audio is off unless HINT_BEFORE_ANSWER is set.
    """
    total = C.QUESTIONS_PER_VIDEO  # only used as the script's "question k of n"
    parts = [
        tts.clean_for_tts(tts.question_script(question, 0, total)),
        tts.clean_for_tts(tts.options_script(question)),
        tts.clean_for_tts(tts.cta_script()),
        tts.clean_for_tts(tts.answer_script(question)),
    ]
    if C.HINT_BEFORE_ANSWER:
        parts.append(tts.clean_for_tts(tts.hint_script(question)))
    return sum(len(part) for part in parts)


def _pool(bank, paheli):
    return [q for q in bank if (q.get("sub") == C.PAHELI_SUB) == paheli]


def video_chars(pool, questions_per_video):
    if not pool:
        return float(FALLBACK_CHARS_PER_VIDEO)
    mean = sum(spoken_char_count(q) for q in pool) / len(pool)
    return mean * questions_per_video


def daily_spoken_characters(bank, active_slots, questions_per_video):
    quiz_slots = [s for s in active_slots if s in C.QUIZ_SLOTS]
    paheli_slots = [s for s in active_slots if s in C.PAHELI_SLOTS]
    total = 0.0
    if quiz_slots:
        total += len(quiz_slots) * video_chars(_pool(bank, False), questions_per_video)
    if paheli_slots:
        total += len(paheli_slots) * video_chars(_pool(bank, True), questions_per_video)
    if total <= 0:
        total = float(FALLBACK_CHARS_PER_VIDEO) * max(1, len(active_slots))
    return total


def credit_threshold(bank, active_slots, questions_per_video, days=CREDIT_COVER_DAYS):
    return math.ceil(daily_spoken_characters(bank, active_slots, questions_per_video) * days)


def stock_rows(bank, used_ids, active_slots, questions_per_video):
    """Fresh-stock days. Same arithmetic as pick.stock_report (never-used ids)."""
    rows = []
    for name, paheli, slot_names in (
        ("quiz", False, C.QUIZ_SLOTS),
        ("paheli", True, C.PAHELI_SLOTS),
    ):
        active = [slot for slot in slot_names if slot in active_slots]
        per_day = questions_per_video * len(active)
        pool = _pool(bank, paheli)
        fresh = sum(1 for q in pool if q.get("id") not in used_ids)
        days = (fresh / per_day) if per_day else None
        rows.append({
            "name": name,
            "fresh": fresh,
            "pool": len(pool),
            "per_day": per_day,
            "days": days,
            "active": active,
        })
    return rows


# ---------------------------------------------------------------- evaluators
def _scope_name(scope):
    return scope.rstrip("/").rsplit("/", 1)[-1]


def _normalize_scope(scope):
    scope = (scope or "").strip()
    if not scope:
        return ""
    if scope.startswith("http://") or scope.startswith("https://"):
        return scope
    return "https://www.googleapis.com/auth/" + scope


def evaluate_youtube(obs):
    missing = obs.get("missing_secrets") or []
    if missing:
        names = ", ".join(missing)
        return [Finding(
            "youtube", "fail", "yt_missing_secret",
            f"YouTube secret set nahi hai: {names}. Token refresh try nahi hua.",
            f"Missing YouTube secret(s): {names}. The refresh call was not attempted.",
        )]
    if obs.get("refresh_error"):
        err = obs["refresh_error"]
        return [Finding(
            "youtube", "fail", "yt_refresh_failed",
            f"YouTube token refresh fail ({err}). Naya refresh token chahiye — "
            "channel QUIZ PATHSHALA, scopes upload / readonly / youtube / force-ssl. "
            "Laptop: python src/upload.py --auth",
            f"The refresh-token grant failed ({err}). Uploads cannot start until "
            "YOUTUBE_REFRESH_TOKEN works with the current OAuth client "
            f"(expected channel {EXPECTED_CHANNEL_ID}, {EXPECTED_CHANNEL_TITLE}).",
        )]

    findings = [Finding(
        "youtube", "ok", "yt_refresh",
        "YouTube token refresh pass ho gaya.",
        "YouTube refresh-token grant returned an access token.",
    )]

    scopes = obs.get("scopes")
    if scopes is None:
        findings.append(Finding(
            "youtube", "warn", "yt_scopes_unreadable",
            "Token refresh ho gaya, par granted scopes padhe nahi ja sake (tokeninfo).",
            "Refresh succeeded, but tokeninfo did not return the granted scopes, "
            "so youtube.force-ssl could not be confirmed.",
        ))
    else:
        have = {_normalize_scope(s) for s in scopes}
        absent = [s for s in REQUIRED_SCOPES if s not in have]
        if absent:
            short = ", ".join(_scope_name(s) for s in absent)
            findings.append(Finding(
                "youtube", "fail", "yt_scopes_missing",
                f"Token me ye scopes nahi hain: {short}. Comments / channel write inke bina fail hote hain.",
                f"Granted scopes are missing: {short}. Required: "
                + ", ".join(_scope_name(s) for s in REQUIRED_SCOPES) + ".",
            ))
        else:
            findings.append(Finding(
                "youtube", "ok", "yt_scopes",
                "Saare required scopes maujood hain: "
                + ", ".join(_scope_name(s) for s in REQUIRED_SCOPES) + ".",
                "Token includes youtube.upload, youtube.readonly, youtube, and youtube.force-ssl.",
            ))

    if obs.get("quota_error"):
        reason = obs["quota_error"]
        findings.append(Finding(
            "quota", "fail", "yt_quota",
            f"YouTube quota probe fail ({reason}). channels.list (1 unit) bhi nahi chala. "
            f"Exact remaining units sirf GCP console me hain — project {GCP_QUOTA_PROJECT}.",
            f"The cheap quota probe (channels.list, 1 unit) returned {reason}. "
            "Exact daily quota remaining is not available from the API; it is only in the "
            f"GCP console for project {GCP_QUOTA_PROJECT} "
            "(APIs & Services → YouTube Data API v3 → Quotas). Nothing was uploaded.",
        ))
        findings.append(Finding(
            "youtube", "fail", "yt_channel_unverified",
            "Quota error ki wajah se channel id/title confirm nahi ho saka.",
            "Channel id and title were not checked because the channels.list probe failed.",
        ))
        return findings

    if obs.get("api_error"):
        findings.append(Finding(
            "quota", "fail", "yt_api_error",
            f"YouTube read-only probe fail ({obs['api_error']}). Quota bhi confirm nahi hui. Upload nahi kiya.",
            f"channels.list failed ({obs['api_error']}). This was a read-only 1-unit call; "
            "quota could not be confirmed and nothing was written to YouTube.",
        ))
        return findings

    findings.append(Finding(
        "quota", "ok", "yt_quota",
        "Quota probe pass: channels.list (part=snippet, mine=true) = 1 unit, read-only. "
        f"Exact remaining quota API nahi batati — sirf GCP console, project {GCP_QUOTA_PROJECT} "
        "(APIs & Services → YouTube Data API v3 → Quotas).",
        "channels.list succeeded (1 quota unit, read-only). Exact remaining daily quota "
        f"is only in the GCP console for project {GCP_QUOTA_PROJECT}, not in this API. "
        "No video upload, video update, channel update, or comment insert was made.",
    ))

    channels = obs.get("channels") or []
    match = next((ch for ch in channels if ch.get("id") == EXPECTED_CHANNEL_ID), None)
    if match is None:
        seen = ", ".join(
            f"{(ch.get('title') or '?')} ({ch.get('id') or '?'})" for ch in channels
        ) or "(koi channel nahi)"
        findings.append(Finding(
            "youtube", "fail", "yt_channel_mismatch",
            f"Token galat channel pe hai. Expect {EXPECTED_CHANNEL_TITLE} ({EXPECTED_CHANNEL_ID}). Mila: {seen}.",
            f"Authenticated channel is not {EXPECTED_CHANNEL_TITLE} ({EXPECTED_CHANNEL_ID}). Seen: {seen}.",
        ))
        return findings
    title = (match.get("title") or "").strip()
    if title != EXPECTED_CHANNEL_TITLE:
        findings.append(Finding(
            "youtube", "fail", "yt_channel_mismatch",
            f"Channel id sahi hai ({EXPECTED_CHANNEL_ID}) par title {title!r} hai, "
            f"{EXPECTED_CHANNEL_TITLE!r} hona chahiye.",
            f"Channel id {EXPECTED_CHANNEL_ID} matched, but title is {title!r}, "
            f"expected {EXPECTED_CHANNEL_TITLE!r}.",
        ))
        return findings
    findings.append(Finding(
        "youtube", "ok", "yt_channel",
        f"Channel sahi hai: {EXPECTED_CHANNEL_TITLE} ({EXPECTED_CHANNEL_ID}).",
        f"Token belongs to {EXPECTED_CHANNEL_TITLE} ({EXPECTED_CHANNEL_ID}).",
    ))
    return findings


def _remaining_characters(payload):
    if not isinstance(payload, dict):
        return None, None, None
    limit = payload.get("character_limit")
    used = payload.get("character_count")
    extra = payload.get("max_character_limit_extension") or 0
    if limit is None or used is None:
        return None, None, None
    try:
        remaining = int(limit) + int(extra) - int(used)
        return remaining, int(limit), int(used)
    except (TypeError, ValueError):
        return None, None, None


def evaluate_elevenlabs(obs, threshold, active_slots, primary="elevenlabs"):
    """ElevenLabs findings. Only fatal when ElevenLabs is the primary TTS.

    With QUIZ_TTS_PROVIDER=gemini (or edge) ElevenLabs is just a fallback, so
    key/credit problems are downgraded to warnings: the build still voices
    via the primary or Edge.
    """
    findings = _evaluate_elevenlabs(obs, threshold, active_slots)
    if primary == "elevenlabs":
        return findings
    for f in findings:
        if f.level == "fail":
            f.level = "warn"
            f.hinglish += f" (Primary TTS {primary} hai, ElevenLabs sirf fallback — warning.)"
            f.english += f" (Primary TTS is {primary}; ElevenLabs is only a fallback, so this is a warning.)"
    return findings


def evaluate_tts_primary(env, primary):
    """Cheap presence check for the primary provider's keys. Values are never read out."""
    if primary != "gemini":
        return [Finding("tts", "ok", "tts_primary",
                        f"Primary TTS: {primary}.", f"Primary TTS provider: {primary}.")]
    present = [
        name for name in tts.GEMINI_KEY_ENVS
        if str(env.get(name + "_SET", "")).strip().lower() == "true" or env.get(name)
    ]
    if not present:
        return [Finding(
            "tts", "fail", "tts_gemini_no_key",
            "Primary TTS gemini hai par koi GEMINI_API_KEY* secret set nahi.",
            "Primary TTS is gemini but none of " + ", ".join(tts.GEMINI_KEY_ENVS) + " is set.",
        )]
    return [Finding(
        "tts", "ok", "tts_gemini_keys",
        f"Gemini keys maujood: {', '.join(present)}.",
        f"Gemini primary TTS has key(s) present: {', '.join(present)} (values not printed).",
    )]


def _evaluate_elevenlabs(obs, threshold, active_slots):
    slots = ", ".join(active_slots) or "(none)"
    if obs.get("missing"):
        return [Finding(
            "elevenlabs", "fail", "el_missing_secret",
            "ELEVENLABS_API_KEY set nahi hai. Build free edge-tts voice pe gir jayegi.",
            "ELEVENLABS_API_KEY is not set. The build falls back to edge-tts (hi-IN-SwaraNeural).",
        )]
    if obs.get("bad_format"):
        return [Finding(
            "elevenlabs", "fail", "el_bad_key_format",
            "ElevenLabs key 'sk_' se shuru nahi hoti. Aksar dashboard wali key-id copy ho jaati hai, "
            "asli API key nahi. Value yahan print nahi ki.",
            "ELEVENLABS_API_KEY does not start with 'sk_'. tts.py treats that as a key id, "
            "not an API key, and falls back to edge-tts. The value was not printed.",
        )]
    if obs.get("status") in (401, 403):
        return [Finding(
            "elevenlabs", "fail", "el_invalid_key",
            f"ElevenLabs key reject ho gayi (HTTP {obs.get('status')}).",
            f"ElevenLabs rejected the API key (HTTP {obs.get('status')}).",
        )]
    if obs.get("error"):
        return [Finding(
            "elevenlabs", "fail", "el_api_error",
            f"ElevenLabs subscription check fail ({obs['error']}).",
            f"ElevenLabs subscription check failed ({obs['error']}).",
        )]
    remaining, limit, used = _remaining_characters(obs.get("payload"))
    if remaining is None:
        return [Finding(
            "elevenlabs", "warn", "el_credit_unreadable",
            "ElevenLabs key chal gayi, par bache hue characters nahi mile. "
            f"2-din ki line {threshold} characters hai (slots: {slots}).",
            f"The key was accepted, but character_limit/character_count were missing. "
            f"The 2-day warning line is {threshold} characters (slots: {slots}).",
        )]
    detail_hi = (
        f"Bache {remaining} characters (used {used} / limit {limit}). "
        f"2 din ki line {threshold} hai — slots: {slots}."
    )
    detail_en = (
        f"Remaining {remaining} characters (used {used} / limit {limit}). "
        f"Warning line is {threshold}: ceil({CREDIT_COVER_DAYS} days × mean spoken "
        "characters per video × active videos/day). Spoken text matches build.py "
        "(question + options + CTA + answer per question)."
    )
    if remaining <= 0:
        return [Finding(
            "elevenlabs", "fail", "el_low_credit",
            "ElevenLabs characters khatam. " + detail_hi,
            "ElevenLabs character credit is exhausted. " + detail_en,
        )]
    if remaining < threshold:
        return [Finding(
            "elevenlabs", "warn", "el_low_credit",
            "ElevenLabs characters 2 din ke uploads se kam hain. " + detail_hi,
            "ElevenLabs character credit is below the 2-day upload line. " + detail_en,
        )]
    return [Finding(
        "elevenlabs", "ok", "el_credit",
        "ElevenLabs theek hai. " + detail_hi,
        "ElevenLabs key is valid and remaining credit covers about 2 days of uploads. " + detail_en,
    )]


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deepseek_root(base):
    root = (base or "").strip().rstrip("/") or DEEPSEEK_DEFAULT_BASE
    if root.endswith("/v1"):
        root = root[:-3]
    return root


def evaluate_deepseek(obs):
    if obs.get("missing"):
        return [Finding(
            "deepseek", "fail", "ds_missing_secret",
            "DEEPSEEK_API_KEY set nahi hai. daily-finance.yml isi secret se chalti hai "
            "(quiz upload DeepSeek nahi bulata).",
            "DEEPSEEK_API_KEY is not set. daily-finance.yml uses it (config.json llm_provider=deepseek). "
            "The quiz upload path does not call DeepSeek.",
        )]
    if obs.get("bad_url"):
        return [Finding(
            "deepseek", "fail", "ds_api_error",
            "DEEPSEEK_BASE_URL https nahi hai, isliye key bheji hi nahi.",
            "DEEPSEEK_BASE_URL is not https, so the key was not sent.",
        )]
    if obs.get("invalid"):
        return [Finding(
            "deepseek", "fail", "ds_invalid_key",
            f"DeepSeek key reject ho gayi (HTTP {obs.get('status')}).",
            f"DeepSeek rejected the API key (HTTP {obs.get('status')}).",
        )]
    if obs.get("balance") is not None:
        return _evaluate_deepseek_balance(obs["balance"])
    if obs.get("models_ok"):
        return [Finding(
            "deepseek", "ok", "ds_balance_unexposed",
            "DeepSeek key valid hai (GET /models). /user/balance is API par nahi hai, "
            "isliye balance skip.",
            "DeepSeek key is valid (GET /models returned 200). GET /user/balance is not "
            "exposed by this API, so balance was not a failure.",
        )]
    if obs.get("error"):
        return [Finding(
            "deepseek", "fail", "ds_api_error",
            f"DeepSeek check fail ({obs['error']}).",
            f"DeepSeek check failed ({obs['error']}).",
        )]
    return [Finding(
        "deepseek", "fail", "ds_key_unverified",
        "DeepSeek key confirm nahi ho saki — balance endpoint nahi mila aur /models bhi pass nahi hua.",
        "Could not validate the DeepSeek key: the balance endpoint was missing and GET /models did not succeed.",
    )]


def _evaluate_deepseek_balance(payload):
    if not isinstance(payload, dict):
        return [Finding(
            "deepseek", "fail", "ds_balance_unreadable",
            "DeepSeek /user/balance ka jawab samajh nahi aaya.",
            "DeepSeek /user/balance returned a response that was not a JSON object.",
        )]
    infos = [i for i in (payload.get("balance_infos") or []) if isinstance(i, dict)]
    lines = []
    low = []
    for info in infos:
        currency = str(info.get("currency") or "?").upper()
        total = _as_float(info.get("total_balance"))
        lines.append(f"{currency} {info.get('total_balance')}")
        minimum = DEEPSEEK_MIN_BALANCE.get(currency, DEEPSEEK_MIN_BALANCE_DEFAULT)
        if total is None or total <= minimum:
            low.append(f"{currency}<={minimum}")
    summary = ", ".join(lines) or "(balance_infos empty)"
    if payload.get("is_available") is False:
        return [Finding(
            "deepseek", "fail", "ds_low_balance",
            f"DeepSeek is_available=false. Balance: {summary}.",
            f"DeepSeek reports is_available=false. Balances: {summary}.",
        )]
    if infos and len(low) == len(infos):
        return [Finding(
            "deepseek", "fail", "ds_low_balance",
            f"DeepSeek balance bahut kam hai ({summary}). "
            f"Line: USD {DEEPSEEK_MIN_BALANCE['USD']} / CNY {DEEPSEEK_MIN_BALANCE['CNY']}.",
            f"Every DeepSeek balance is at or below the dust threshold "
            f"(USD {DEEPSEEK_MIN_BALANCE['USD']}, CNY {DEEPSEEK_MIN_BALANCE['CNY']}, "
            f"other currencies {DEEPSEEK_MIN_BALANCE_DEFAULT}). Reported: {summary}.",
        )]
    if payload.get("is_available") is True or (infos and len(low) < len(infos)):
        return [Finding(
            "deepseek", "ok", "ds_balance",
            f"DeepSeek key valid, balance theek: {summary}.",
            f"DeepSeek key is valid and balance is above the dust threshold: {summary}.",
        )]
    return [Finding(
        "deepseek", "fail", "ds_balance_unreadable",
        "DeepSeek balance jawab me na is_available hai na usable balance.",
        "DeepSeek balance response had neither is_available nor a usable balance list.",
    )]


def _is_bad_run(run):
    conclusion = run.get("conclusion")
    if conclusion in BAD_CONCLUSIONS:
        return True
    return conclusion == "cancelled" and run.get("event") == "schedule"


def _is_stuck(run, now, stuck_hours):
    if run.get("conclusion"):
        return False
    if run.get("status") in ("completed",):
        return False
    if run.get("event") not in ("schedule", "workflow_dispatch"):
        return False
    return now - run["created_at"] > timedelta(hours=stuck_hours)


def evaluate_workflows(obs, now, active_slots, grace_hours=SCHEDULE_GRACE_HOURS,
                       match_hours=SCHEDULE_MATCH_HOURS, recent_hours=RECENT_RUN_HOURS,
                       stuck_hours=STUCK_RUN_HOURS):
    if obs.get("error") == "missing_token":
        if obs.get("required"):
            return [Finding(
                "workflows", "fail", "wf_missing_token",
                "GitHub token nahi mila, isliye upload workflow runs check nahi ho saka. "
                "Workflow ko actions: read chahiye.",
                "GH_TOKEN / GITHUB_TOKEN is missing in GitHub Actions, so scheduled upload "
                "runs could not be listed. The workflow needs actions: read.",
            )]
        return [Finding(
            "workflows", "ok", "wf_skipped_local",
            "Local run: GitHub token nahi hai, upload-run check skip.",
            "Not running in GitHub Actions and no token was set, so the workflow-run check was skipped.",
        )]
    if obs.get("error"):
        return [Finding(
            "workflows", "fail", "wf_api_error",
            f"Upload workflow runs padhe nahi ja sake ({obs['error']}).",
            f"Could not list {UPLOAD_WORKFLOW_FILE} runs ({obs['error']}).",
        )]
    if not active_slots:
        return [Finding(
            "workflows", "fail", "wf_no_slots",
            "Koi active slot nahi bana, isliye schedule check adhoora hai.",
            "No active upload slots were resolved, so the schedule check could not run.",
        )]

    runs = obs.get("runs") or []
    occurrences = due_occurrences(now, active_slots, grace_hours)
    matched, empty_slots = match_schedule_runs(occurrences, runs, match_hours)
    due_txt = "; ".join(f"{slot} {fmt_utc(when)}" for slot, when in occurrences)
    if matched < len(occurrences):
        short = len(occurrences) - matched
        if empty_slots:
            who = ", ".join(empty_slots)
            who_hi = f"In slots ki window khali thi: {who}."
            who_en = f"Windows with no schedule run: {who}."
        else:
            who_hi = ("Kaunsa slot chhoota hai ye pakka nahi — GitHub run me cron id nahi hoti "
                      "aur delay se windows overlap karti hain.")
            who_en = ("Which slot is missing is not certain: the runs API has no cron id, "
                      "and the delay windows overlap.")
        schedule = Finding(
            "workflows", "fail", "wf_missing_schedule",
            f"Scheduled upload run kam hai: {matched}/{len(occurrences)} match, {short} kam. "
            f"Active slots: {', '.join(active_slots)}. {who_hi} "
            f"Grace {grace_hours}h, window {match_hours}h. Due: {due_txt}.",
            f"Scheduled {UPLOAD_WORKFLOW_FILE} runs are short: matched {matched} of "
            f"{len(occurrences)} due slot fires ({short} missing). Active slots: "
            f"{', '.join(active_slots)}. {who_en} "
            f"A run is required only after {grace_hours}h (documented 10–20h cron delay) "
            f"and counts if it was created within {match_hours}h of that cron. Due: {due_txt}.",
        )
    else:
        schedule = Finding(
            "workflows", "ok", "wf_schedule",
            f"Scheduled runs mil gaye: {matched}/{len(occurrences)} active slots. Due: {due_txt}.",
            f"Each due active-slot cron has a matching schedule run of {UPLOAD_WORKFLOW_FILE} "
            f"({matched}/{len(occurrences)}). Due: {due_txt}.",
        )

    recent_start = now - timedelta(hours=recent_hours)
    # A failure followed by a later success is superseded (e.g. the 14-Oct
    # billing block): only failures after the newest successful run count.
    successes = [
        r["created_at"] for r in runs
        if r.get("conclusion") == "success"
        and r.get("event") in ("schedule", "workflow_dispatch")
    ]
    latest_success = max(successes) if successes else None
    bad = []
    stuck = []
    for run in runs:
        if run["created_at"] < recent_start:
            continue
        if run.get("event") not in ("schedule", "workflow_dispatch"):
            continue
        if _is_bad_run(run):
            if latest_success is not None and run["created_at"] <= latest_success:
                continue
            bad.append(run)
        elif _is_stuck(run, now, stuck_hours):
            stuck.append(run)
    if not bad and not stuck:
        recent = Finding(
            "workflows", "ok", "wf_recent",
            f"Pichhle {recent_hours}h me koi failed, cancelled, ya atka hua upload run nahi.",
            f"No failed, schedule-cancelled, or long-queued upload run in the last {recent_hours} hours.",
        )
    else:
        bits = []
        for run in bad:
            bits.append(
                f"{run.get('event')} {run.get('conclusion')} {fmt_utc(run['created_at'])} {run.get('html_url') or ''}"
            )
        for run in stuck:
            bits.append(
                f"{run.get('event')} stuck status={run.get('status')} {fmt_utc(run['created_at'])} "
                f"{run.get('html_url') or ''}"
            )
        detail = " | ".join(bits)
        recent = Finding(
            "workflows", "fail", "wf_failed",
            f"Recent upload run theek nahi: {detail}",
            f"Recent {UPLOAD_WORKFLOW_FILE} run(s) did not succeed: {detail}",
        )
    return [schedule, recent]


def evaluate_bank(bank, used_ids, active_slots, unknown_slots,
                  questions_per_video, low_days, bank_error=None):
    findings = []
    if bank_error:
        findings.append(Finding(
            "bank", "fail", "bank_unreadable",
            f"Question bank padhi nahi ja saki ({bank_error}).",
            f"Could not read the question bank or used.json ({bank_error}).",
        ))
    if unknown_slots:
        findings.append(Finding(
            "config", "warn", "config_unknown_slots",
            "QUIZ_ACTIVE_SLOTS me anjaan naam: " + ", ".join(unknown_slots)
            + f". Use ho rahe slots: {', '.join(active_slots)}.",
            "QUIZ_ACTIVE_SLOTS contains unknown slot names: " + ", ".join(unknown_slots)
            + f". Slots in use: {', '.join(active_slots)}.",
        ))
    if bank_error:
        return findings
    for row in stock_rows(bank, used_ids, active_slots, questions_per_video):
        name = row["name"]
        if not row["per_day"]:
            findings.append(Finding(
                "bank", "ok", f"bank_{name}_off",
                f"{name}: koi active slot nahi, stock check skip.",
                f"{name}: no active slot, so fresh-stock was not required.",
            ))
            continue
        days = row["days"]
        summary_hi = (
            f"{name}: {row['fresh']}/{row['pool']} fresh (~{days:.1f} din), "
            f"{row['per_day']} sawaal/din (slots: {', '.join(row['active'])})."
        )
        summary_en = (
            f"{name}: {row['fresh']}/{row['pool']} never-used questions "
            f"(~{days:.1f} days) at {row['per_day']} questions/day "
            f"(slots: {', '.join(row['active'])}, {questions_per_video} per video)."
        )
        if days < low_days:
            findings.append(Finding(
                "bank", "warn", f"bank_low_{name}",
                f"Fresh stock {low_days} din se kam hai. {summary_hi} "
                "Naye sawaal data/questions.json me jodo.",
                f"Fresh stock is under {low_days} days (BANK_LOW_DAYS). {summary_en} "
                "Add questions to kids-quiz-shorts/data/questions.json. "
                "Until then pick.py reuses the least-recently-used items.",
            ))
        else:
            findings.append(Finding(
                "bank", "ok", f"bank_{name}",
                f"Stock theek hai. {summary_hi}",
                f"Fresh stock covers at least {low_days} days. {summary_en}",
            ))
    return findings


# ---------------------------------------------------------------- render / issues
_CHECK_ORDER = ("youtube", "quota", "tts", "elevenlabs", "deepseek", "workflows", "bank", "config")


def render_report(report):
    return redact(_render_report(report))


def _render_report(report):
    status = "OK — sab theek / all checks passed" if report.healthy else "PROBLEM — dhyan do / action needed"
    lines = [
        f"## QUIZ PATHSHALA health check — {status}",
        "",
        f"Checked: {fmt_utc(report.generated_at)} ({fmt_ist(report.generated_at)})",
        f"Active slots: {', '.join(report.active_slots) or '(none)'}",
        (
            f"ElevenLabs 2-day character threshold: **{report.eleven_threshold}** "
            "(ceil of mean spoken characters × active videos/day × 2; "
            "question + options + CTA + answer per question, same scripts as build.py)."
        ),
        "",
        f"<!-- health-fingerprint: {report.fingerprint} -->",
        "",
    ]
    if report.run_url:
        lines.append(f"Run: {report.run_url}")
        lines.append("")
    problems = [f for f in report.findings if f.problem]
    passed = [f for f in report.findings if not f.problem]
    lines.append("### Samasya / Problems" if problems else "### Samasya / Problems")
    lines.append("")
    if not problems:
        lines.append("Koi problem nahi. / No problems.")
    else:
        for index, finding in enumerate(_ordered(problems), start=1):
            lines.extend(_finding_lines(index, finding))
    lines.append("")
    lines.append("### Jo theek hai / Passed")
    lines.append("")
    if not passed:
        lines.append("(kuch pass nahi hua / nothing passed)")
    else:
        for index, finding in enumerate(_ordered(passed), start=1):
            lines.extend(_finding_lines(index, finding))
    lines.extend([
        "",
        "### YouTube quota",
        "",
        "Exact daily quota remaining is **not** available from the YouTube Data API. "
        f"It is only in the Google Cloud console for project `{GCP_QUOTA_PROJECT}` "
        "(APIs & Services → YouTube Data API v3 → Quotas). "
        "This check spends 1 unit on `channels.list` (part=snippet, mine=true) and never "
        "uploads a video, edits a video, updates the channel, or inserts a comment.",
        "",
    ])
    return "\n".join(lines)


def _ordered(findings):
    rank = {name: i for i, name in enumerate(_CHECK_ORDER)}
    return sorted(findings, key=lambda f: (rank.get(f.check, 99), f.code))


def _finding_lines(index, finding):
    return [
        f"{index}. **{finding.check}** ({finding.level}) `{finding.code}`",
        f"   - Hinglish: {finding.hinglish}",
        f"   - English: {finding.english}",
    ]


def extract_fingerprint(body):
    match = _FP_RE.search(body or "")
    if not match:
        return None
    return match.group(1)


def plan_issue_action(existing_issues, report):
    """Decide create / update / close / noop. Does not call the network.

    `existing_issues` are open issues already labelled health-alert that this
    checker owns (title prefix or a fingerprint comment).
    """
    owned = [issue for issue in existing_issues if _is_health_issue(issue)]
    primary = min(owned, key=lambda issue: issue.get("number") or 0) if owned else None
    extra = max(0, len(owned) - 1)
    body = render_report(report)
    if extra:
        body += (
            f"\nNote: {extra} aur open health-alert issue(s) hain. "
            f"Canonical thread: #{primary.get('number')}.\n"
        )
    if report.healthy:
        if primary is None:
            return {"action": "noop", "body": body}
        return {
            "action": "close",
            "number": primary["number"],
            "body": body,
            "comment": (
                "Health check wapas pass ho gaya — saare checks theek hain. Issue close kar rahe hain.\n\n"
                "English: All health checks passed. Closing this alert."
            ),
        }
    if primary is None:
        return {"action": "create", "title": ISSUE_TITLE, "body": body, "comment": None}
    old = extract_fingerprint(primary.get("body") or "")
    comment = None
    if old != report.fingerprint:
        comment = (
            "Health check update — problem list badli.\n\n"
            f"Pehle / before: `{old if old is not None else '(none)'}`\n"
            f"Ab / now: `{report.fingerprint}`\n\n"
            "English: The set of failing checks changed. The latest Hinglish + English "
            "detail is in the issue body."
        )
    return {
        "action": "update",
        "number": primary["number"],
        "body": body,
        "comment": comment,
    }


def _is_health_issue(issue):
    if not isinstance(issue, dict) or issue.get("pull_request"):
        return False
    title = issue.get("title") or ""
    body = issue.get("body") or ""
    return title.startswith("health-alert:") or "health-fingerprint:" in body


# ---------------------------------------------------------------- HTTP
class _NoRedirect(urllib.request.HTTPErrorProcessor):
    """Return 3xx/4xx responses as-is so tokens are never sent to a redirect."""

    def http_response(self, request, response):
        return response

    https_response = http_response


class UrlLibClient:
    def request(self, method, url, *, headers=None, body=None, timeout=20):
        hdrs = {
            "User-Agent": "quiz-pathshala-healthcheck",
            "Accept": "application/json",
        }
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read(MAX_BODY_BYTES)
                status = getattr(resp, "status", None) or resp.getcode()
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_BODY_BYTES) if exc.fp else b""
            status = exc.code
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(redact(str(reason))) from None
        text = raw.decode("utf-8", "replace")
        try:
            payload = json.loads(text) if text else None
        except json.JSONDecodeError:
            payload = None
        return ClientResponse(status, payload, text)


def _env_value(env, *names):
    for name in names:
        value = env.get(name)
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _oauth_reason(payload, status):
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, str):
            desc = payload.get("error_description") or ""
            return redact(f"{err}: {desc}".strip(": "))
        if isinstance(err, dict):
            reasons = [
                item.get("reason") for item in (err.get("errors") or [])
                if isinstance(item, dict) and item.get("reason")
            ]
            if reasons:
                return redact(str(reasons[0]))
    return f"http {status}"


def _youtube_reason(payload, status):
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            for item in err.get("errors") or []:
                if isinstance(item, dict) and item.get("reason"):
                    return str(item["reason"])
    return f"http {status}"


def fetch_youtube(client, env):
    values = {}
    missing = []
    for secret_name, alias in YT_SECRET_ENV:
        value = _env_value(env, alias, secret_name)
        if not value:
            missing.append(secret_name)
        else:
            values[secret_name] = value
    if missing:
        return {"missing_secrets": missing}
    body = urllib.parse.urlencode({
        "client_id": values["YOUTUBE_CLIENT_ID"],
        "client_secret": values["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": values["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode("ascii")
    try:
        token_resp = client.request(
            "POST", TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=body,
        )
    except RuntimeError as exc:
        return {"refresh_error": redact(str(exc))}
    if token_resp.status != 200 or not isinstance(token_resp.payload, dict):
        return {"refresh_error": _oauth_reason(token_resp.payload, token_resp.status)}
    access = token_resp.payload.get("access_token")
    if not access:
        return {"refresh_error": "no_access_token"}
    obs = {}
    try:
        info = client.request(
            "GET",
            TOKENINFO_URL + "?" + urllib.parse.urlencode({"access_token": access}),
        )
    except RuntimeError as exc:
        obs["scopes"] = None
        obs["api_error"] = redact(str(exc))
        return obs
    if info.status == 200 and isinstance(info.payload, dict):
        obs["scopes"] = [s for s in str(info.payload.get("scope") or "").split() if s]
    else:
        obs["scopes"] = None
    try:
        channels = client.request(
            "GET",
            CHANNELS_URL + "?" + urllib.parse.urlencode({
                "part": "snippet",
                "mine": "true",
                "maxResults": "5",
            }),
            headers={"Authorization": f"Bearer {access}"},
        )
    except RuntimeError as exc:
        obs["api_error"] = redact(str(exc))
        return obs
    if channels.status == 200 and isinstance(channels.payload, dict):
        obs["channels"] = [
            {
                "id": item.get("id"),
                "title": ((item.get("snippet") or {}).get("title") or ""),
            }
            for item in (channels.payload.get("items") or [])
            if isinstance(item, dict)
        ]
        return obs
    reason = _youtube_reason(channels.payload, channels.status)
    if reason in QUOTA_REASONS:
        obs["quota_error"] = reason
    else:
        obs["api_error"] = redact(reason)
    return obs


def fetch_elevenlabs(client, env):
    key = _env_value(env, "ELEVENLABS_API_KEY")
    if not key:
        return {"missing": True}
    if not key.startswith("sk_"):
        return {"bad_format": True}
    try:
        resp = client.request(
            "GET", ELEVEN_SUB_URL, headers={"xi-api-key": key},
        )
    except RuntimeError as exc:
        return {"error": redact(str(exc))}
    if resp.status in (401, 403):
        return {"status": resp.status}
    if resp.status != 200:
        return {"error": f"http {resp.status}"}
    return {"payload": resp.payload if isinstance(resp.payload, dict) else {}}


def fetch_deepseek(client, env):
    key = _env_value(env, "DEEPSEEK_API_KEY")
    if not key:
        return {"missing": True}
    root = _deepseek_root(env.get("DEEPSEEK_BASE_URL"))
    if not root.startswith("https://") or "@" in root:
        return {"bad_url": True}
    headers = {"Authorization": f"Bearer {key}"}
    try:
        balance = client.request("GET", root + "/user/balance", headers=headers)
    except RuntimeError as exc:
        return {"error": redact(str(exc))}
    if balance.status in (401, 403):
        return {"invalid": True, "status": balance.status}
    if balance.status == 200:
        return {"balance": balance.payload}
    if balance.status not in (404, 405, 410):
        return {"error": f"balance http {balance.status}"}
    try:
        models = client.request("GET", root + "/models", headers=headers)
    except RuntimeError as exc:
        return {"error": redact(str(exc))}
    if models.status in (401, 403):
        return {"invalid": True, "status": models.status}
    if models.status == 200:
        return {"models_ok": True}
    return {"error": f"models http {models.status}"}


def _github_base(env):
    base = (env.get("GITHUB_API_URL") or "https://api.github.com").strip().rstrip("/")
    if not base.startswith("https://") or "@" in base:
        raise RuntimeError("bad_github_api_url")
    return base


def _github_repo(env):
    repo = (env.get("GITHUB_REPOSITORY") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise RuntimeError("bad_github_repo")
    return repo


def fetch_workflows(client, env, now):
    token = _env_value(env, "GH_TOKEN", "GITHUB_TOKEN")
    required = env.get("GITHUB_ACTIONS") == "true"
    if not token:
        return {"error": "missing_token", "required": required, "runs": []}
    try:
        base = _github_base(env)
        repo = _github_repo(env)
    except RuntimeError as exc:
        return {"error": str(exc), "runs": []}
    # Sirf utne din ke runs jitne evaluate_workflows dekhta hai (grace+match
    # aur recent window dono 72h ke andar) — response chhota rehta hai.
    since = (now - timedelta(hours=WORKFLOW_LOOKBACK_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = urllib.parse.urlencode({
        "per_page": "100",
        "exclude_pull_requests": "true",
        "created": f">={since}",
    })
    url = f"{base}/repos/{repo}/actions/workflows/{UPLOAD_WORKFLOW_FILE}/runs?{query}"
    try:
        resp = client.request(
            "GET", url,
            headers={"Authorization": f"Bearer {token}",
                     "X-GitHub-Api-Version": "2022-11-28"},
        )
    except RuntimeError as exc:
        return {"error": redact(str(exc)), "runs": []}
    if resp.status != 200:
        return {"error": f"http {resp.status}", "runs": []}
    if not isinstance(resp.payload, dict):
        size = len(resp.text or "")
        return {"error": f"http 200 but body is not a JSON object ({size} chars; truncated?)",
                "runs": []}
    runs = []
    for item in resp.payload.get("workflow_runs") or []:
        if not isinstance(item, dict) or not item.get("created_at"):
            continue
        try:
            created = parse_utc(item["created_at"])
        except (TypeError, ValueError):
            continue
        runs.append({
            "id": item.get("id"),
            "event": item.get("event") or "",
            "status": item.get("status") or "",
            "conclusion": item.get("conclusion"),
            "created_at": created,
            "html_url": item.get("html_url") or "",
            "head_branch": item.get("head_branch") or "",
        })
    return {"runs": runs}


def _safe_findings(check, fn):
    try:
        return list(fn())
    except Exception as exc:  # noqa: BLE001 — one check must not sink the report
        return [Finding(
            check, "fail", f"{check}_crash",
            f"{check} check crash ho gaya ({type(exc).__name__}).",
            f"The {check} check raised {type(exc).__name__}: {redact(str(exc))[:300]}",
        )]


def load_questions(path=None):
    path = Path(path or (C.DATA / "questions.json"))
    bank = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(bank, list):
        raise ValueError("questions.json is not a list")
    return bank


def load_used_ids(path=None):
    path = Path(path or (C.DATA / "used.json"))
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    history = data.get("history") if isinstance(data, dict) else data
    return {
        item.get("id") for item in (history or [])
        if isinstance(item, dict) and item.get("id")
    }


def run_checks(client, env, bank, used_ids, now, bank_error=None, run_url=""):
    active_slots, unknown_slots = parse_active_slots(env.get("QUIZ_ACTIVE_SLOTS"))
    threshold = credit_threshold(bank or [], active_slots, C.QUESTIONS_PER_VIDEO, CREDIT_COVER_DAYS)
    primary = tts.tts_provider(env.get("QUIZ_TTS_PROVIDER") or "")
    findings = []
    findings += _safe_findings("youtube", lambda: evaluate_youtube(fetch_youtube(client, env)))
    findings += _safe_findings(
        "elevenlabs",
        lambda: evaluate_elevenlabs(fetch_elevenlabs(client, env), threshold, active_slots,
                                    primary=primary),
    )
    findings += _safe_findings("tts", lambda: evaluate_tts_primary(env, primary))
    findings += _safe_findings("deepseek", lambda: evaluate_deepseek(fetch_deepseek(client, env)))
    findings += _safe_findings(
        "workflows",
        lambda: evaluate_workflows(fetch_workflows(client, env, now), now, active_slots),
    )
    findings += _safe_findings(
        "bank",
        lambda: evaluate_bank(
            bank or [], used_ids or set(), active_slots, unknown_slots,
            C.QUESTIONS_PER_VIDEO, C.BANK_LOW_DAYS, bank_error=bank_error,
        ),
    )
    return Report(findings, now, active_slots, threshold, run_url=run_url)


def _github_json(client, method, url, token, payload=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return client.request(method, url, headers=headers, body=body)


def sync_health_issue(client, env, report):
    token = _env_value(env, "GH_TOKEN", "GITHUB_TOKEN")
    if not token:
        raise RuntimeError("missing_github_token")
    base = _github_base(env)
    repo = _github_repo(env)
    listed = _github_json(
        client, "GET",
        f"{base}/repos/{repo}/issues?" + urllib.parse.urlencode({
            "state": "open",
            "labels": ISSUE_LABEL,
            "per_page": "50",
        }),
        token,
    )
    if listed.status != 200 or not isinstance(listed.payload, list):
        raise RuntimeError(f"list issues http {listed.status}")
    plan = plan_issue_action(listed.payload, report)
    action = plan["action"]
    if action == "noop":
        return "noop"
    if action == "create":
        label_resp = _github_json(
            client, "POST", f"{base}/repos/{repo}/labels", token,
            {
                "name": ISSUE_LABEL,
                "color": "d93f0b",
                "description": "QUIZ PATHSHALA pipeline health check failed",
            },
        )
        if label_resp.status not in (200, 201, 422):
            raise RuntimeError(f"label http {label_resp.status}")
        created = _github_json(
            client, "POST", f"{base}/repos/{repo}/issues", token,
            {"title": plan["title"], "body": plan["body"], "labels": [ISSUE_LABEL]},
        )
        if created.status not in (200, 201) or not isinstance(created.payload, dict):
            raise RuntimeError(f"create issue http {created.status}")
        number = created.payload.get("number")
        return f"created #{number}"
    number = plan["number"]
    if plan.get("comment"):
        comment = _github_json(
            client, "POST", f"{base}/repos/{repo}/issues/{number}/comments", token,
            {"body": plan["comment"]},
        )
        if comment.status not in (200, 201):
            raise RuntimeError(f"comment http {comment.status}")
    patched = _github_json(
        client, "PATCH", f"{base}/repos/{repo}/issues/{number}", token,
        {
            "body": plan["body"],
            "state": "closed" if action == "close" else "open",
        },
    )
    if patched.status != 200:
        raise RuntimeError(f"update issue http {patched.status}")
    verb = "closed" if action == "close" else "updated"
    return f"{verb} #{number}"


def _actions_run_url(env):
    repo = (env.get("GITHUB_REPOSITORY") or "").strip()
    run_id = (env.get("GITHUB_RUN_ID") or "").strip()
    if not repo or not run_id:
        return ""
    server = (env.get("GITHUB_SERVER_URL") or "https://github.com").rstrip("/")
    return f"{server}/{repo}/actions/runs/{run_id}"


def should_file_issues(dry_run, env):
    if dry_run:
        return False
    flag = (env.get("HEALTH_DRY_RUN") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return False
    return env.get("GITHUB_ACTIONS") == "true"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only QUIZ PATHSHALA pipeline health check")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the report and do not open, update, or close issues")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    bank_error = None
    bank = []
    used_ids = set()
    try:
        bank = load_questions()
        used_ids = load_used_ids()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        bank_error = redact(f"{type(exc).__name__}")
    report = run_checks(
        UrlLibClient(), os.environ, bank, used_ids, now,
        bank_error=bank_error, run_url=_actions_run_url(os.environ),
    )
    print(render_report(report))
    exit_code = 0 if report.healthy else 1
    if should_file_issues(args.dry_run, os.environ):
        try:
            action = sync_health_issue(UrlLibClient(), os.environ, report)
            print(f"[health] issue: {action}")
        except Exception as exc:  # noqa: BLE001 — surface a redacted sync failure
            print(f"[health] issue sync fail: {redact(str(exc))}", file=sys.stderr)
            exit_code = 1
    elif not args.dry_run and os.environ.get("GITHUB_ACTIONS") == "true":
        print("[health] issue sync skip (dry-run)")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
