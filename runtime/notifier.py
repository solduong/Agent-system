"""
Notifier — multi-channel alerts for the feedback loop.

Channels (configured via .env — all optional except macOS which is always on):
──────────────────────────────────────────────────────────────────────────────
  macOS desktop     always active on macOS (osascript, zero setup)
  Email             NOTIFY_EMAIL_TO + NOTIFY_EMAIL_FROM + NOTIFY_SMTP_*
  Slack             NOTIFY_SLACK_WEBHOOK

.env keys
──────────────────────────────────────────────────────────────────────────────
  NOTIFY_EMAIL_TO       recipient address  e.g. you@gmail.com
  NOTIFY_EMAIL_FROM     sender address     e.g. you@gmail.com
  NOTIFY_SMTP_HOST      e.g. smtp.gmail.com
  NOTIFY_SMTP_PORT      e.g. 587
  NOTIFY_SMTP_USER      SMTP login (often same as FROM)
  NOTIFY_SMTP_PASS      SMTP password or app-password
  NOTIFY_SLACK_WEBHOOK  full webhook URL from Slack app settings

Usage
──────────────────────────────────────────────────────────────────────────────
  from runtime.notifier import notify

  notify(
      event   = "improvement_triggered",   # see EVENT TYPES below
      summary = "reviewer 40% error rate → prompt rewrite applied",
      details = {...},                      # optional structured data
  )

EVENT TYPES
──────────────────────────────────────────────────────────────────────────────
  improvement_triggered   analysis ran and targets were found
  improvement_applied     one or more prompt changes written to disk
  improvement_blocked     human rejected a proposed change
  quality_alert           rolling avg quality dropped below threshold
  run_error               a pipeline run failed (success=False)
  health_ok               periodic check — system is healthy, nothing to do
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.parent

# ── Event metadata ─────────────────────────────────────────────────────────

_EVENT_META: dict[str, dict] = {
    "improvement_triggered": {"emoji": "🔍", "urgency": "medium", "sound": "Ping"},
    "improvement_applied":   {"emoji": "✅", "urgency": "low",    "sound": "Glass"},
    "improvement_blocked":   {"emoji": "🚫", "urgency": "medium", "sound": "Basso"},
    "quality_alert":         {"emoji": "⚠️",  "urgency": "high",   "sound": "Sosumi"},
    "run_error":             {"emoji": "❌", "urgency": "high",   "sound": "Basso"},
    "health_ok":             {"emoji": "💚", "urgency": "low",    "sound": None},
}

_DEFAULT_META = {"emoji": "ℹ️", "urgency": "low", "sound": "Ping"}


# ── Main entry point ────────────────────────────────────────────────────────

def notify(
    event: str,
    summary: str,
    details: dict[str, Any] | None = None,
    channels: list[str] | None = None,   # None = all configured channels
) -> dict[str, bool]:
    """
    Fire notifications on all configured channels.
    Returns {channel: success} dict.
    """
    meta     = _EVENT_META.get(event, _DEFAULT_META)
    title    = f"Agent System — {meta['emoji']} {event.replace('_', ' ').title()}"
    body     = summary
    results  = {}

    enabled  = set(channels) if channels else {"macos", "email", "slack"}

    if "macos" in enabled:
        results["macos"] = _send_macos(title, body, meta.get("sound"))

    if "email" in enabled and _email_configured():
        results["email"] = _send_email(title, body, details)

    if "slack" in enabled and _slack_configured():
        results["slack"] = _send_slack(event, meta["emoji"], summary, details,
                                        meta["urgency"])

    # Always write to notification log
    _append_log(event, summary, details, results)

    return results


# ── macOS desktop notification ──────────────────────────────────────────────

def _send_macos(title: str, body: str, sound: str | None = "Ping") -> bool:
    if sys.platform != "darwin":
        return False
    sound_clause = f'sound name "{sound}"' if sound else ""
    script = (
        f'display notification "{_esc(body)}" '
        f'with title "{_esc(title)}" '
        f'subtitle "qbus3600 agent-system" '
        f'{sound_clause}'
    )
    try:
        subprocess.run(["osascript", "-e", script],
                       check=True, capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _esc(s: str) -> str:
    """Escape double quotes for AppleScript strings."""
    return s.replace("\\", "\\\\").replace('"', '\\"')[:200]


# ── Email ───────────────────────────────────────────────────────────────────

def _email_configured() -> bool:
    return bool(os.environ.get("NOTIFY_EMAIL_TO") and
                os.environ.get("NOTIFY_SMTP_HOST"))


def _send_email(subject: str, body: str,
                details: dict | None = None) -> bool:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    to_addr   = os.environ["NOTIFY_EMAIL_TO"]
    from_addr = os.environ.get("NOTIFY_EMAIL_FROM", to_addr)
    host      = os.environ["NOTIFY_SMTP_HOST"]
    port      = int(os.environ.get("NOTIFY_SMTP_PORT", 587))
    user      = os.environ.get("NOTIFY_SMTP_USER", from_addr)
    password  = os.environ.get("NOTIFY_SMTP_PASS", "")

    html_details = ""
    if details:
        rows = "".join(
            f"<tr><td style='padding:4px 8px;font-weight:bold'>{k}</td>"
            f"<td style='padding:4px 8px'>{v}</td></tr>"
            for k, v in details.items()
        )
        html_details = f"<table border='1' cellpadding='0' cellspacing='0'>{rows}</table>"

    html = f"""
    <html><body>
    <p style='font-family:monospace'>{body}</p>
    {html_details}
    <hr>
    <small>qbus3600 agent-system &bull; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</small>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_addr
    msg.attach(MIMEText(body,  "plain"))
    msg.attach(MIMEText(html,  "html"))

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if port != 465:
                smtp.starttls()
            if password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to_addr], msg.as_string())
        return True
    except Exception as e:
        print(f"  [notifier/email] error: {e}")
        return False


# ── Slack ────────────────────────────────────────────────────────────────────

def _slack_configured() -> bool:
    return bool(os.environ.get("NOTIFY_SLACK_WEBHOOK"))


def _send_slack(event: str, emoji: str, summary: str,
                details: dict | None, urgency: str) -> bool:
    import urllib.request
    webhook = os.environ["NOTIFY_SLACK_WEBHOOK"]

    color = {"high": "#e74c3c", "medium": "#f39c12", "low": "#2ecc71"}.get(urgency, "#95a5a6")

    fields = []
    if details:
        for k, v in list(details.items())[:8]:   # Slack caps at ~10 fields
            fields.append({"title": k, "value": str(v)[:200], "short": True})

    payload = {
        "text": f"{emoji} *Agent System — {event.replace('_', ' ').title()}*",
        "attachments": [{
            "color":    color,
            "text":     summary,
            "fields":   fields,
            "footer":   "qbus3600 agent-system",
            "ts":       int(datetime.utcnow().timestamp()),
        }]
    }

    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            webhook, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  [notifier/slack] error: {e}")
        return False


# ── Notification log ─────────────────────────────────────────────────────────

NOTIFY_LOG = BASE / "System_logs" / "notification_log.jsonl"


def _append_log(event: str, summary: str,
                details: dict | None, results: dict) -> None:
    entry = {
        "ts":        datetime.utcnow().isoformat() + "Z",
        "event":     event,
        "summary":   summary,
        "details":   details or {},
        "channels":  results,
    }
    NOTIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTIFY_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Status report (used by check_status.py) ──────────────────────────────────

def recent_notifications(n: int = 10) -> list[dict]:
    if not NOTIFY_LOG.exists():
        return []
    lines = NOTIFY_LOG.read_text().splitlines()
    records = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records[-n:]
