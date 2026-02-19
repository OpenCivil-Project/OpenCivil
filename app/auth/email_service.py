import os
import smtplib
import logging
import random
import string
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / ".env")

logger      = logging.getLogger(__name__)
SENDER_NAME = "OpenCivil"

def _creds():
    addr = os.getenv("GMAIL_ADDRESS", "")
    pwd  = os.getenv("GMAIL_APP_PASS", "")
    if not addr or not pwd:
        raise ValueError("GMAIL_ADDRESS / GMAIL_APP_PASS not set in .env")
    return addr, pwd

def _send(to_email: str, subject: str, html_body: str):
    addr, pwd = _creds()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{SENDER_NAME} <{addr}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(addr, pwd)
        server.sendmail(addr, to_email, msg.as_string())
    logger.info("Email sent to %s | %s", to_email, subject)

def generate_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))

def _base_template(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#F0F4F8;font-family:'Segoe UI',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F4F8;padding:40px 0;">
        <tr><td align="center">
          <table width="480" cellpadding="0" cellspacing="0"
                 style="background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.08);overflow:hidden;">
            <tr><td style="background:#0F62FE;padding:28px 40px;">
              <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">◈ OpenCivil</h1>
              <p style="margin:4px 0 0;color:rgba(255,255,255,0.75);font-size:13px;">{title}</p>
            </td></tr>
            <tr><td style="padding:36px 40px 40px;">{body_html}</td></tr>
            <tr><td style="padding:20px 40px;border-top:1px solid #F0F4F8;">
              <p style="margin:0;color:#94A3B8;font-size:11px;">
                Sent by OpenCivil Analysis Engine. If you didn't request this, ignore it.
              </p>
            </td></tr>
          </table>
        </td></tr>
      </table>
    </body></html>"""

def send_verification_email(to_email: str, name: str, code: str):
    body = f"""
      <p style="margin:0 0 8px;color:#0F1C2E;font-size:16px;font-weight:600;">Hi {name.split()[0]}, welcome!</p>
      <p style="margin:0 0 28px;color:#64748B;font-size:14px;line-height:1.6;">
        Use this code to verify your email. Expires in <strong>10 minutes</strong>.
      </p>
      <div style="background:#F8FAFC;border:1.5px solid #E2E8F0;border-radius:12px;
                  padding:24px;text-align:center;margin-bottom:28px;">
        <p style="margin:0 0 6px;color:#94A3B8;font-size:12px;text-transform:uppercase;letter-spacing:1px;">
          Verification Code</p>
        <p style="margin:0;color:#0F1C2E;font-size:38px;font-weight:700;
                  letter-spacing:10px;font-family:monospace;">{code}</p>
      </div>
      <p style="margin:0;color:#94A3B8;font-size:13px;">Enter this in the OpenCivil app to activate your account.</p>
    """
    _send(to_email, "Your OpenCivil verification code", _base_template("Email Verification", body))

def send_reset_email(to_email: str, name: str, code: str):
    first = name.split()[0] if name else "there"
    body = f"""
      <p style="margin:0 0 8px;color:#0F1C2E;font-size:16px;font-weight:600;">Password reset requested</p>
      <p style="margin:0 0 28px;color:#64748B;font-size:14px;line-height:1.6;">
        Hi {first}, use this code to reset your password. Expires in <strong>15 minutes</strong>.
      </p>
      <div style="background:#FFF8F8;border:1.5px solid #FEE2E2;border-radius:12px;
                  padding:24px;text-align:center;margin-bottom:28px;">
        <p style="margin:0 0 6px;color:#94A3B8;font-size:12px;text-transform:uppercase;letter-spacing:1px;">
          Reset Code</p>
        <p style="margin:0;color:#DC2626;font-size:38px;font-weight:700;
                  letter-spacing:10px;font-family:monospace;">{code}</p>
      </div>
      <p style="margin:0;color:#94A3B8;font-size:13px;">If you didn't request this, ignore it — your account is safe.</p>
    """
    _send(to_email, "Reset your OpenCivil password", _base_template("Password Reset", body))
