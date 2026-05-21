"""SMTP email tool for sending drowning case summary reports."""
import os
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders


def send_summary_email(subject: str, body_text: str, body_html: str = "", attachment_paths: list = None) -> dict:
    """Send a summary email report via SMTP.

    Reads connection settings from environment variables:
      SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
      EMAIL_FROM, EMAIL_TO

    Args:
        subject: Email subject line.
        body_text: Plain-text version of the email body.
        body_html: Optional HTML version of the email body.
        attachment_paths: Optional list of file paths to attach as PDFs.

    Returns:
        A dict with 'success' (bool) and 'message' (status or error string).
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("EMAIL_FROM", username)
    to_addr = os.getenv("EMAIL_TO")

    if not all([username, password, to_addr]):
        return {
            "success": False,
            "message": "Missing required env vars: SMTP_USERNAME, SMTP_PASSWORD, EMAIL_TO",
        }

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    # Body (alternative: plain + html)
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body_text, "plain"))
    if body_html:
        body_part.attach(MIMEText(body_html, "html"))
    msg.attach(body_part)

    # PDF attachments
    for path in (attachment_paths or []):
        try:
            with open(path, "rb") as f:
                part = MIMEBase("application", "pdf")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                filename = os.path.basename(path)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                msg.attach(part)
        except Exception:
            pass  # skip unreadable attachments

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(from_addr, to_addr, msg.as_string())
        return {"success": True, "message": f"Email sent to {to_addr}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
