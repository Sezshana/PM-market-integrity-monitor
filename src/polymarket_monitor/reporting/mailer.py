"""SMTP delivery with once-per-day deduplication."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from polymarket_monitor import config
from polymarket_monitor.reporting.dispatch import (
    mark_email_sent,
    should_skip_duplicate_send,
    should_skip_scheduled_email,
)


def send_email(body_plain: str, body_html: str, subject: str) -> bool:
    """Send digest email. Returns True if sent."""
    if not config.ALERT_EMAIL:
        print("No ALERT_EMAIL configured — skipping email")
        return False
    if not config.SMTP_PASSWORD:
        print("No SMTP password — skipping email")
        return False

    skip, reason = should_skip_scheduled_email()
    if skip:
        print(f"Skipping email — {reason}")
        return False

    skip, reason = should_skip_duplicate_send()
    if skip:
        print(f"Skipping email — {reason}")
        return False

    recipient = os.environ.get("DIGEST_RECIPIENT", config.ALERT_EMAIL).strip() or config.ALERT_EMAIL
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.ALERT_EMAIL
    msg["To"] = recipient
    msg.attach(MIMEText(body_plain, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as server:
            server.login(config.ALERT_EMAIL, config.SMTP_PASSWORD)
            refused = server.sendmail(config.ALERT_EMAIL, [recipient], msg.as_string())
        if refused:
            print(f"Email refused by server for {recipient}: {refused}")
            return False
        mark_email_sent(subject)
        print(f"Email sent to {recipient}: {subject}")
        return True
    except Exception as exc:
        print(f"Email error sending to {recipient}: {exc}")
        return False
