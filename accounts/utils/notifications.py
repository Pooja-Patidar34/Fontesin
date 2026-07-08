"""Helpers for emitting in-app Notification rows.

Kept separate from the view module so any code path (views, signals, future
celery tasks) can drop a notification without dragging in the messages view's
dependencies. All helpers silently swallow errors — notification delivery
should never break the originating user action.

Notification title/body strings are translated at write-time in the
recipient's preferred language via ``translation.override``.
"""

import logging

from django.urls import reverse, NoReverseMatch
from django.utils import translation
from django.utils.translation import gettext as _

from accounts.models import Notification
from FontEsin.i18n import user_language


logger = logging.getLogger("technical")


def scope_notifications_qs(qs, user):
    """Restrict a Notification queryset to what `user` should see given the
    company they're currently acting as.

    Plans and companies are company-scoped, so a Business User acting as one
    company shouldn't see notifications tied to their OTHER companies. This
    keeps notifications with a matching ``related_company`` (the active
    company) plus account-level ones (``related_company`` is null — e.g.
    coordinator-request or generic messages), and drops the rest. Non-business
    roles (consultant / coordinator / franchise / admin) and superusers see
    everything unchanged. A business user with no active company also sees
    everything (nothing to scope to yet).
    """
    from django.db.models import Q

    if not user or getattr(user, "is_superuser", False):
        return qs
    role_code = (user.role.code or "").lower() if getattr(user, "role", None) else ""
    if role_code != "business_user":
        return qs

    from billing.utils import resolve_active_company
    active_company = resolve_active_company(user)
    if active_company is None:
        return qs
    return qs.filter(Q(related_company__isnull=True) | Q(related_company=active_company))


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


def _localized_notify(recipient, *, sender=None, kind=Notification.KIND_GENERIC,
                      title="", body="", link_url="", related_company=None):
    """Create a notification with title/body translated for the recipient."""
    if not recipient:
        return None
    with translation.override(user_language(recipient)):
        return notify(
            recipient=recipient,
            sender=sender,
            kind=kind,
            title=title,
            body=body,
            link_url=link_url,
            related_company=related_company,
        )


def _commission_labels(commission):
    """Shared label bits for commission notifications (names stay untranslated)."""
    consultant = commission.consultant
    amount = f"{commission.commission_amount} {commission.currency}"
    bu = getattr(commission, "business_user", None)
    bu_label = (
        (f"{bu.first_name} {bu.last_name}".strip() or bu.email) if bu else None
    )
    company_name = commission.company.name if getattr(commission, "company_id", None) else ""
    via = company_name  # translated wrapper applied in message templates
    consultant_label = (
        f"{consultant.first_name} {consultant.last_name}".strip() or consultant.email
    )
    return amount, bu_label, via, consultant_label


def _notify_commission(commission, *, build_consultant_msgs, build_su_msgs):
    """Send a commission notification to the consultant AND every active
    superuser. Shared by the pending + earned (paid) notifications."""
    from accounts.models import User

    consultant = getattr(commission, "consultant", None)
    if not consultant:
        return None
    try:
        link = reverse("commissions")
    except NoReverseMatch:
        link = ""

    with translation.override(user_language(consultant)):
        consultant_title, consultant_body = build_consultant_msgs()
    last = notify(
        recipient=consultant,
        kind=Notification.KIND_GENERIC,
        title=consultant_title,
        body=consultant_body,
        link_url=link,
    )
    for su in User.objects.filter(is_superuser=True, is_active=True):
        with translation.override(user_language(su)):
            su_title, su_body = build_su_msgs()
        last = notify(
            recipient=su,
            sender=consultant,
            kind=Notification.KIND_GENERIC,
            title=su_title,
            body=su_body,
            link_url=link,
        )
    return last


def notify_commission_pending(commission):
    """A commission was created and is awaiting payout — notify the consultant +
    every superuser that a PENDING commission exists."""
    if not getattr(commission, "consultant", None):
        return None
    amount, bu_label, via_company, consultant_label = _commission_labels(commission)

    def _bu_text():
        return bu_label or _("a business user")

    def _via_text():
        return _(" via %(company)s") % {"company": via_company} if via_company else ""

    def build_consultant_msgs():
        return (
            _("Commission pending — %(amount)s") % {"amount": amount},
            _(
                "A %(amount)s commission from %(user)s's subscription%(via)s is pending. "
                "You'll be notified once it's marked paid."
            ) % {"amount": amount, "user": _bu_text(), "via": _via_text()},
        )

    def build_su_msgs():
        return (
            _("Commission pending: %(consultant)s (%(amount)s)")
            % {"consultant": consultant_label, "amount": amount},
            _(
                "%(consultant)s has a pending %(amount)s commission from "
                "%(user)s's subscription%(via)s."
            ) % {
                "consultant": consultant_label,
                "amount": amount,
                "user": _bu_text(),
                "via": _via_text(),
            },
        )

    return _notify_commission(
        commission,
        build_consultant_msgs=build_consultant_msgs,
        build_su_msgs=build_su_msgs,
    )


def notify_commission_earned(commission):
    """A commission was MARKED PAID — notify the consultant they've earned it,
    and every superuser."""
    if not getattr(commission, "consultant", None):
        return None
    amount, bu_label, via_company, consultant_label = _commission_labels(commission)

    def _bu_text():
        return bu_label or _("a business user")

    def _via_text():
        return _(" via %(company)s") % {"company": via_company} if via_company else ""

    def build_consultant_msgs():
        return (
            _("You earned a commission of %(amount)s") % {"amount": amount},
            _(
                "Your %(amount)s commission from %(user)s's subscription%(via)s has been paid."
            ) % {"amount": amount, "user": _bu_text(), "via": _via_text()},
        )

    def build_su_msgs():
        return (
            _("Commission paid: %(consultant)s (%(amount)s)")
            % {"consultant": consultant_label, "amount": amount},
            _(
                "You marked %(consultant)s's %(amount)s commission from "
                "%(user)s's subscription%(via)s as paid."
            ) % {
                "consultant": consultant_label,
                "amount": amount,
                "user": _bu_text(),
                "via": _via_text(),
            },
        )

    return _notify_commission(
        commission,
        build_consultant_msgs=build_consultant_msgs,
        build_su_msgs=build_su_msgs,
    )


def notify_plan_request(subscription):
    """A Business User requested a paid plan for one of their companies —
    notify every active super admin.

    Plans are company-scoped and approved by the super admin once payment
    arrives; on approval the commission flows to the consultant who CERTIFIED
    the company. So the message names the company, the requested plan, the
    buying user, AND that certifying consultant, matching the product spec:
    "a notification will be sent to the superadmin ... and the name of
    consultant A will be published there."
    """
    from accounts.models import User

    company = getattr(subscription, "company", None)
    plan = getattr(subscription, "plan", None)
    buyer = getattr(subscription, "user", None)
    if company is None or plan is None:
        return None

    plan_name = plan.name or (plan.code or "").upper()
    company_name = company.name
    buyer_label = ""
    if buyer:
        buyer_label = f"{buyer.first_name} {buyer.last_name}".strip() or buyer.email

    consultant = getattr(company, "certified_by", None)
    consultant_label = ""
    if consultant:
        consultant_label = (
            f"{consultant.first_name} {consultant.last_name}".strip() or consultant.email
        )

    try:
        link = reverse("payments")
    except NoReverseMatch:
        link = ""

    last = None
    for su in User.objects.filter(is_superuser=True, is_active=True):
        with translation.override(user_language(su)):
            title = _("Plan request: %(company)s → %(plan)s") % {
                "company": company_name,
                "plan": plan_name,
            }
            body = _(
                "%(buyer)s is requesting the %(plan)s plan for %(company)s. "
                "Approve it once payment arrives to activate the plan."
            ) % {
                "buyer": buyer_label or _("A business user"),
                "plan": plan_name,
                "company": company_name,
            }
            if consultant_label:
                body += "\n" + _(
                    "Certifying consultant (commission on approval): %(consultant)s."
                ) % {"consultant": consultant_label}
            last = notify(
                recipient=su,
                sender=buyer,
                kind=Notification.KIND_GENERIC,
                title=title,
                body=body,
                link_url=link,
                related_company=company,
            )
    return last


def notify_certification_request(company, *, submitted_by):
    """Broadcast a certification request note to every active consultant."""
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
    last = None
    for consultant in consultants:
        with translation.override(user_language(consultant)):
            body = _(
                "%(company)s has requested certification and is awaiting review."
            ) % {"company": company.name}
            if submitter_label:
                body += "\n" + _("Submitted by %(name)s.") % {"name": submitter_label}
            last = notify(
                recipient=consultant,
                sender=submitted_by,
                kind=Notification.KIND_CERTIFICATION_REQUEST,
                title=_("New certification request: %(company)s") % {"company": company.name},
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
    with translation.override(user_language(owner)):
        if approved:
            kind = Notification.KIND_CERTIFICATION_APPROVED
            title = _("%(company)s has been certified") % {"company": company.name}
            body = _("Your certification request was approved")
            if decider_label:
                body += _(" by %(name)s") % {"name": decider_label}
            body += _(". Your company is now visible in the public directory.")
        else:
            kind = Notification.KIND_CERTIFICATION_DECLINED
            title = _("Certification declined for %(company)s") % {"company": company.name}
            body = _("Your certification request was declined")
            if decider_label:
                body += _(" by %(name)s") % {"name": decider_label}
            body += _(
                ". You can update your company details and resubmit from your profile."
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
    """Tell every active consultant that a new user is using the system."""
    from accounts.models import User

    consultants = (
        User.objects.filter(role__code__iexact="consultant", is_active=True)
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

    country = (getattr(new_user, "country", "") or "").strip()
    country_label = ""
    if country:
        from accounts.constants import CountryChoices
        country_label = dict(CountryChoices.CHOICES).get(country.upper(), country)

    try:
        link = reverse("business-users")
    except NoReverseMatch:
        link = ""

    last = None
    for consultant in consultants:
        with translation.override(user_language(consultant)):
            lines = [
                _("%(name)s is using the system.") % {"name": user_label},
                "",
                _("Registration details:"),
                _("Name: %(name)s") % {"name": user_label},
                _("Email: %(email)s") % {"email": new_user.email},
            ]
            if getattr(new_user, "phone", ""):
                prefix = (getattr(new_user, "national_prefix", "") or "").strip()
                phone = f"+{prefix} {new_user.phone}".strip() if prefix else new_user.phone
                lines.append(_("Phone: %(phone)s") % {"phone": phone})
            if country_label:
                lines.append(_("Country: %(country)s") % {"country": country_label})
            if role_label:
                lines.append(_("Registering as: %(role)s") % {"role": role_label})
            if language:
                lines.append(_("Preferred language: %(lang)s") % {"lang": language})
            if interest:
                lines.append(_("Interest: %(interest)s") % {"interest": interest})
            lines.append("")
            lines.append(_("Open the Users tab to view the full profile."))
            body = "\n".join(lines)
            last = notify(
                recipient=consultant,
                sender=new_user,
                kind=Notification.KIND_NEW_USER,
                title=_("%(name)s is using the system") % {"name": user_label},
                body=body,
                link_url=link,
            )
    return last


def notify_contact_message(contact_msg):
    """Broadcast a contact form message to every active superuser."""
    from accounts.models import User

    try:
        link = reverse("contact-messages")
    except NoReverseMatch:
        link = ""

    who = contact_msg.full_name
    superusers = User.objects.filter(is_superuser=True, is_active=True)
    last = None
    for su in superusers:
        with translation.override(user_language(su)):
            lines = [_("%(who)s sent a message via the website contact form.") % {"who": who}]
            if contact_msg.subject:
                lines.append(_("Subject: %(subject)s") % {"subject": contact_msg.subject})
            lines.append(_("Email: %(email)s") % {"email": contact_msg.email})
            if contact_msg.phone:
                lines.append(_("Phone: %(phone)s") % {"phone": contact_msg.phone})
            if contact_msg.company_name:
                lines.append(_("Company: %(company)s") % {"company": contact_msg.company_name})
            lines.append("")
            lines.append(contact_msg.message)
            body = "\n".join(lines)
            last = notify(
                recipient=su,
                kind=Notification.KIND_GENERIC,
                title=_("New contact message from %(who)s") % {"who": who},
                body=body,
                link_url=link,
            )
    return last


def notify_coordinator_request_submitted(coord_request):
    """Broadcast a coordinator role request to every superuser."""
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
    superusers = User.objects.filter(is_superuser=True, is_active=True)
    last = None
    for su in superusers:
        with translation.override(user_language(su)):
            body = _("%(name)s has requested to become a Coordinator.") % {"name": requester_label}
            if coord_request.target_region:
                body += "\n" + _("Target region: %(region)s.") % {
                    "region": coord_request.target_region
                }
            last = notify(
                recipient=su,
                sender=requester,
                kind=Notification.KIND_COORDINATOR_REQUEST,
                title=_("New coordinator role request"),
                body=body,
                link_url=link,
            )
    return last


def notify_application_submitted(applicant):
    """Broadcast a franchise/coordinator application to every superuser."""
    from accounts.models import User

    applicant_label = (
        f"{applicant.first_name} {applicant.last_name}".strip()
        or applicant.email
    )
    role_label = (
        (applicant.role.name or applicant.role.code or "applicant").replace("_", " ").title()
        if applicant.role else "applicant"
    )
    try:
        link = reverse("applications")
    except NoReverseMatch:
        link = ""
    superusers = User.objects.filter(is_superuser=True, is_active=True)
    last = None
    for su in superusers:
        with translation.override(user_language(su)):
            body = _(
                "%(name)s submitted a %(role)s account application and is awaiting your review."
            ) % {"name": applicant_label, "role": role_label}
            if applicant.target_region:
                body += "\n" + _("Target region: %(region)s.") % {
                    "region": applicant.target_region
                }
            last = notify(
                recipient=su,
                sender=applicant,
                kind=Notification.KIND_APPLICATION_REQUEST,
                title=_("New %(role)s application") % {"role": role_label},
                body=body,
                link_url=link,
            )
    return last


def notify_application_decision(applicant, *, approved):
    """Inform the applicant of the Super Admin's approve/decline decision."""
    if not applicant:
        return None
    decider = applicant.application_decided_by
    decider_label = ""
    if decider:
        decider_label = (
            f"{decider.first_name} {decider.last_name}".strip()
            or decider.email
        )
    try:
        link = reverse("dashboard") if approved else reverse("application-pending")
    except NoReverseMatch:
        link = ""
    with translation.override(user_language(applicant)):
        if approved:
            kind = Notification.KIND_APPLICATION_APPROVED
            title = _("Your account application has been approved")
            body = _("Your account application was approved")
            if decider_label:
                body += _(" by %(name)s") % {"name": decider_label}
            body += _(
                ". You now have full access — sign out and back in if your sidebar doesn't update."
            )
        else:
            kind = Notification.KIND_APPLICATION_DECLINED
            title = _("Your account application was declined")
            reason = (applicant.application_decline_reason or "").strip()
            body = _("Your account application was declined")
            if decider_label:
                body += _(" by %(name)s") % {"name": decider_label}
            body += "."
            if reason:
                body += "\n" + _("Reason: %(reason)s") % {"reason": reason}
    return notify(
        recipient=applicant,
        sender=decider,
        kind=kind,
        title=title,
        body=body,
        link_url=link,
    )


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
    with translation.override(user_language(requester)):
        if approved:
            kind = Notification.KIND_COORDINATOR_APPROVED
            title = _("Your Coordinator role has been approved")
            body = _("Your request to become a Coordinator was approved")
            if decider_label:
                body += _(" by %(name)s") % {"name": decider_label}
            body += _(
                ". Sign out and back in to see the Coordinator features in your sidebar."
            )
        else:
            kind = Notification.KIND_COORDINATOR_DECLINED
            title = _("Your Coordinator request was declined")
            reason = (coord_request.decline_reason or "").strip()
            body = _("Your request to become a Coordinator was declined")
            if decider_label:
                body += _(" by %(name)s") % {"name": decider_label}
            body += "."
            if reason:
                body += "\n" + _("Reason: %(reason)s") % {"reason": reason}
    return notify(
        recipient=requester,
        sender=decider,
        kind=kind,
        title=title,
        body=body,
        link_url=link,
    )
