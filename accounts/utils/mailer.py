import logging
import threading
import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _

logger = logging.getLogger("technical")

_SUPPORTED_LOCALES = frozenset({"en", "de", "es", "fr"})


def _normalize_locale(user_language):
    lang = (user_language or "en").split("-")[0].lower()
    return lang if lang in _SUPPORTED_LOCALES else "en"


def send_otp_email(to_email, first_name, otp, user_language="en"):
    """
    Send OTP email via MailerSend API in a background thread for faster response.
    """
    lang = _normalize_locale(user_language)
    thread = threading.Thread(
        target=_send_otp_email,
        args=(to_email, first_name, otp, lang),
    )
    thread.start()


def _send_otp_email(to_email, first_name, otp, user_language="en"):
    """
    Send OTP email via MailerSend API.
    """
    try:
        api_key = settings.MAILERSEND_API_KEY
        from_email = settings.MAILERSEND_FROM_EMAIL
        from_name = settings.MAILERSEND_FROM_NAME

        with translation.override(user_language):
            subject = _("FONTESIN – Your password reset code")
            context = {"first_name": first_name, "otp": otp}
            text_body = render_to_string("email/otp_password_reset.txt", context)
            html_body = render_to_string("email/otp_password_reset.html", context)

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
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }

        api_url = settings.MAILERSEND_API_URL
        response = requests.post(
            api_url,
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
