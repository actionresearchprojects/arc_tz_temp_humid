"""
send_alert_email.py - Send the ARC staleness alert email via Gmail SMTP.

Reads /tmp/alert_subject.txt and /tmp/alert_body.html written by check_staleness.py.
Requires env vars: GMAIL_USERNAME, GMAIL_APP_PASSWORD, ALERT_EMAILS (comma-separated).
"""

import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

username = os.environ["GMAIL_USERNAME"]
password = os.environ["GMAIL_APP_PASSWORD"]
to_addrs = os.environ["ALERT_EMAILS"]

try:
    with open("/tmp/alert_subject.txt", encoding="utf-8") as f:
        subject = f.read().strip()
except OSError:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"⚠️ ARC Dashboard: staleness check failed ({now})"

try:
    with open("/tmp/alert_body.html", encoding="utf-8") as f:
        html_body = f.read()
except OSError:
    html_body = "<p>Staleness check failed - please check the workflow logs.</p>"

msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"] = f"ARC Monitor <{username}>"
msg["To"] = to_addrs
msg.attach(MIMEText(html_body, "html", "utf-8"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(username, password)
    recipients = [addr.strip() for addr in to_addrs.split(",")]
    smtp.sendmail(username, recipients, msg.as_string())
    print(f"Email sent to: {to_addrs}")
