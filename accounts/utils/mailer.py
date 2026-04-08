import logging
import requests
from django.conf import settings

logger = logging.getLogger("technical")


def send_otp_email(to_email, first_name, otp):
    """
    Send OTP email via MailerSend API.
    """
    try:
        api_key = settings.MAILERSEND_API_KEY
        from_email = settings.MAILERSEND_FROM_EMAIL
        from_name = settings.MAILERSEND_FROM_NAME

        payload = {
            "from": {
                "email": from_email,
                "name": from_name,
            },
            "to": [
                {
                    "email": to_email,
                    "name": first_name,
                }
            ],
            "subject": "FONTESIN – Your password reset code",
            "text": (
                f"Hi {first_name},\n\n"
                f"We received a request to reset your password. "
                f"Use the following verification code:\n\n"
                f"    {otp}\n\n"
                f"This code expires in 10 minutes.\n\n"
                f"If you didn't request this, you can safely ignore this email.\n\n"
                f"– FONTESIN Team"
            ),
            "html": (
                f"<div style='font-family:Arial,sans-serif;max-width:480px;margin:0 auto;'>"
                f"<div style='background:#253D51;padding:24px 32px;border-radius:12px 12px 0 0;'>"
                f"<h2 style='color:#fff;margin:0;font-size:1.2rem;'>FONTESIN</h2>"
                f"</div>"
                f"<div style='background:#fff;padding:32px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;'>"
                f"<p style='color:#334155;font-size:.95rem;'>Hi {first_name},</p>"
                f"<p style='color:#64748b;font-size:.9rem;'>We received a request to reset your password. Use the following code:</p>"
                f"<div style='background:#f1f5f9;border-radius:10px;padding:20px;text-align:center;margin:24px 0;'>"
                f"<span style='font-size:2rem;font-weight:800;letter-spacing:.3em;color:#253D51;'>{otp}</span>"
                f"</div>"
                f"<p style='color:#94a3b8;font-size:.82rem;'>This code expires in <strong>10 minutes</strong>.</p>"
                f"<p style='color:#94a3b8;font-size:.82rem;'>If you didn't request this, you can safely ignore this email.</p>"
                f"<hr style='border:none;border-top:1px solid #e2e8f0;margin:24px 0;'>"
                f"<p style='color:#cbd5e1;font-size:.75rem;text-align:center;'>FONTESIN Team</p>"
                f"</div>"
                f"</div>"
            ),
        }

        response = requests.post(
            "https://api.mailersend.com/v1/email",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )

        if response.status_code not in (200, 202):
            logger.error(
                "MailerSend API error: status=%s, response=%s, to=%s",
                response.status_code, response.text, to_email,
            )
            return False

        return True

    except requests.ConnectionError:
        logger.error("MailerSend connection failed for %s", to_email)
        return False
    except requests.Timeout:
        logger.error("MailerSend request timed out for %s", to_email)
        return False
    except Exception as e:
        logger.error("Unexpected error sending OTP email to %s: %s", to_email, e)
        return False
