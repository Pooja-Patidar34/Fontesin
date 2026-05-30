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
    """Broadcast a 'Company X requested certification' note to every active
    consultant. The first consultant to approve the request claims ownership;
    after that, the company's status flips to 'certified' so it drops off all
    other consultants' pending queues automatically."""
    from accounts.models import User

    consultants = User.objects.filter(
        role__code__iexact="consultant", is_active=True
    )
    if not consultants.exists():
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
    body = f"{company.name} has requested certification and is awaiting review."
    if submitter_label:
        body += f"\nSubmitted by {submitter_label}."
    last = None
    for consultant in consultants:
        last = notify(
            recipient=consultant,
            sender=submitted_by,
            kind=Notification.KIND_CERTIFICATION_REQUEST,
            title=f"New certification request: {company.name}",
            body=body,
            link_url=link,
            related_company=company,
        )
    return last


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


def notify_consultants_new_user(new_user, *, language="", interest=""):
    """Tell every active consultant in the new user's region that a new user
    has registered, and surface the details they filled in at sign-up.

    This runs in parallel with the existing super-admin notification on plan
    selection — the consultant gets an early heads-up about a prospective
    client in their territory the moment the account is created.

    Region is matched on country (the only location signal captured at
    registration — User.country holds an ISO code for both the new user and
    the consultant). A consultant is "in the region" when their own
    User.country matches the new user's. The new user themselves is excluded
    so a consultant signing up never notifies themselves.

    `language` and `interest` are read straight from the registration form by
    the caller and passed through here so the consultant sees them even though
    register_view doesn't persist them on the User row.
    """
    from accounts.models import User

    country = (getattr(new_user, "country", "") or "").strip()
    if not country:
        # No region to route on — nothing to do. (Consultants are matched by
        # country; without it we'd have to broadcast platform-wide, which is
        # noise, so we skip instead.)
        return None

    consultants = (
        User.objects.filter(
            role__code__iexact="consultant",
            is_active=True,
            country__iexact=country,
        )
        .exclude(id=new_user.id)
    )
    if not consultants.exists():
        return None

    user_label = (
        f"{new_user.first_name} {new_user.last_name}".strip() or new_user.email
    )
    role_label = ""
    if getattr(new_user, "role", None) and new_user.role.name:
        role_label = new_user.role.name.replace("_", " ").title()

    # Human-readable country name (fall back to the raw code).
    from accounts.constants import CountryChoices
    country_label = dict(CountryChoices.CHOICES).get(country.upper(), country)

    # Compose a readable summary of everything the user filled in at sign-up.
    lines = [
        f"A new user has registered in your region ({country_label}).",
        "",
        f"Name: {user_label}",
        f"Email: {new_user.email}",
    ]
    if getattr(new_user, "phone", ""):
        prefix = (getattr(new_user, "national_prefix", "") or "").strip()
        phone = f"+{prefix} {new_user.phone}".strip() if prefix else new_user.phone
        lines.append(f"Phone: {phone}")
    lines.append(f"Country: {country_label}")
    if role_label:
        lines.append(f"Registering as: {role_label}")
    if language:
        lines.append(f"Preferred language: {language}")
    if interest:
        lines.append(f"Interest: {interest}")
    body = "\n".join(lines)

    last = None
    for consultant in consultants:
        last = notify(
            recipient=consultant,
            sender=new_user,
            kind=Notification.KIND_NEW_USER,
            title=f"New user registered in your region: {user_label}",
            body=body,
        )
    return last


def notify_coordinator_request_submitted(coord_request):
    """Broadcast a 'BU X requested coordinator role' note to every superuser
    so any of them can pick up the review."""
    from accounts.models import User

    requester = coord_request.user
    requester_label = (
        f"{requester.first_name} {requester.last_name}".strip()
        or requester.email
    )
    try:
        link = reverse("coordinator-requests")
    except NoReverseMatch:
        link = ""
    body = f"{requester_label} has requested to become a Coordinator."
    if coord_request.target_region:
        body += f"\nTarget region: {coord_request.target_region}."
    superusers = User.objects.filter(is_superuser=True, is_active=True)
    last = None
    for su in superusers:
        last = notify(
            recipient=su,
            sender=requester,
            kind=Notification.KIND_COORDINATOR_REQUEST,
            title="New coordinator role request",
            body=body,
            link_url=link,
        )
    return last


def notify_coordinator_request_decision(coord_request, *, approved):
    """Inform the requesting BU of the Super Admin's decision."""
    requester = coord_request.user
    if not requester:
        return None
    decider = coord_request.decided_by
    decider_label = ""
    if decider:
        decider_label = (
            f"{decider.first_name} {decider.last_name}".strip()
            or decider.email
        )
    try:
        link = reverse("profile")
    except NoReverseMatch:
        link = ""
    if approved:
        kind = Notification.KIND_COORDINATOR_APPROVED
        title = "Your Coordinator role has been approved"
        body = (
            f"Your request to become a Coordinator was approved"
            f"{f' by {decider_label}' if decider_label else ''}. "
            "Sign out and back in to see the Coordinator features in your sidebar."
        )
    else:
        kind = Notification.KIND_COORDINATOR_DECLINED
        title = "Your Coordinator request was declined"
        reason = (coord_request.decline_reason or "").strip()
        body = (
            f"Your request to become a Coordinator was declined"
            f"{f' by {decider_label}' if decider_label else ''}."
        )
        if reason:
            body += f"\nReason: {reason}"
    return notify(
        recipient=requester,
        sender=decider,
        kind=kind,
        title=title,
        body=body,
        link_url=link,
    )