"""Helpers for emitting in-app Notification rows.

Kept separate from the view module so any code path (views, signals, future
celery tasks) can drop a notification without dragging in the messages view's
dependencies. All helpers silently swallow errors — notification delivery
should never break the originating user action.
"""

import logging

from django.urls import reverse, NoReverseMatch

from accounts.models import Notification


logger = logging.getLogger("technical")


def notify(*, recipient, sender=None, kind=Notification.KIND_GENERIC,
           title, body="", link_url="", related_company=None):
    """Create a Notification. Recipient must be authenticated User; everything
    else is optional. Returns the Notification or None on failure."""
    if not recipient:
        return None
    try:
        return Notification.objects.create(
            recipient=recipient,
            sender=sender,
            kind=kind,
            title=title,
            body=body or "",
            link_url=link_url or "",
            related_company=related_company,
        )
    except Exception as e:
        logger.error("notify(): failed to create notification: %s", e)
        return None


def notify_certification_request(company, *, submitted_by):
    """Land a 'Company X requested certification' note in the routed
    consultant's inbox. No-op if the company has no consultant assigned —
    the routing layer handles that case separately."""
    consultant = getattr(company, "consultant", None)
    if not consultant:
        return None
    try:
        link = reverse("certifications")
    except NoReverseMatch:
        link = ""
    submitter_label = ""
    if submitted_by:
        submitter_label = (
            f"{submitted_by.first_name} {submitted_by.last_name}".strip()
            or submitted_by.email
        )
    body = f"{company.name} has requested certification and is awaiting your review."
    if submitter_label:
        body += f"\nSubmitted by {submitter_label}."
    return notify(
        recipient=consultant,
        sender=submitted_by,
        kind=Notification.KIND_CERTIFICATION_REQUEST,
        title=f"New certification request: {company.name}",
        body=body,
        link_url=link,
        related_company=company,
    )


def notify_certification_decision(company, *, decided_by, approved):
    """Inform the owner_user of the consultant's decision."""
    owner = getattr(company, "owner_user", None)
    if not owner:
        return None
    try:
        link = reverse("certifications")
    except NoReverseMatch:
        link = ""
    decider_label = ""
    if decided_by:
        decider_label = (
            f"{decided_by.first_name} {decided_by.last_name}".strip()
            or decided_by.email
        )
    if approved:
        kind = Notification.KIND_CERTIFICATION_APPROVED
        title = f"{company.name} has been certified"
        body = (
            f"Your certification request was approved"
            f"{f' by {decider_label}' if decider_label else ''}. "
            "Your company is now visible in the public directory."
        )
    else:
        kind = Notification.KIND_CERTIFICATION_DECLINED
        title = f"Certification declined for {company.name}"
        body = (
            f"Your certification request was declined"
            f"{f' by {decider_label}' if decider_label else ''}. "
            "You can update your company details and resubmit from your profile."
        )
    return notify(
        recipient=owner,
        sender=decided_by,
        kind=kind,
        title=title,
        body=body,
        link_url=link,
        related_company=company,
    )