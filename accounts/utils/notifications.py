"""Helpers for emitting in-app Notification rows.

Kept separate from the view module so any code path (views, signals, future
celery tasks) can drop a notification without dragging in the messages view's
dependencies. All helpers silently swallow errors — notification delivery
should never break the originating user action.

Notification title/body strings are composed as ``Msg`` / ``MsgSeq`` objects
(see ``accounts.utils.i18n_messages``) rather than finished sentences. The
msgid and its parameters are stored alongside the text, so the inbox is
re-translated on every read and follows the reader's current language choice
instead of freezing in whatever language they preferred when the row was
written. The plain ``title`` / ``body`` columns are still filled — in the
recipient's preferred language — as the fallback for anything that can't be
re-rendered.
"""

import logging

from django.urls import reverse, NoReverseMatch
from django.utils import translation

from accounts.models import Notification
from accounts.utils.i18n_messages import Msg, MsgSeq, render_payload, to_payload
from FontEsin.i18n import user_language


logger = logging.getLogger("technical")


_UNRESOLVED = object()


def scope_notifications_qs(qs, user, active_company=_UNRESOLVED):
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

    # Callers that already resolved the acting company (e.g. the context
    # processor, which needs it several times per request) pass it in; the
    # sentinel keeps "caller passed None" distinguishable from "not passed",
    # so an explicit None doesn't trigger a redundant resolve.
    if active_company is _UNRESOLVED:
        from billing.utils import resolve_active_company
        active_company = resolve_active_company(user)
    if active_company is None:
        return qs
    return qs.filter(Q(related_company__isnull=True) | Q(related_company=active_company))


def notify(*, recipient, sender=None, kind=Notification.KIND_GENERIC,
           title, body="", link_url="", related_company=None):
    """Create a Notification. Recipient must be authenticated User; everything
    else is optional. Returns the Notification or None on failure.

    `title` / `body` may be ``Msg`` / ``MsgSeq`` objects — preferred, because
    those keep the catalog entry and re-translate on read — or plain strings,
    which are stored as-is and can never be re-translated.
    """
    if not recipient:
        return None
    title_i18n = to_payload(title)
    body_i18n = to_payload(body)
    # The frozen columns are the fallback, so render them in the language the
    # recipient prefers today rather than the acting user's request locale.
    with translation.override(user_language(recipient)):
        title_text = render_payload(title_i18n) if title_i18n else str(title or "")
        body_text = render_payload(body_i18n) if body_i18n else str(body or "")
    try:
        return Notification.objects.create(
            recipient=recipient,
            sender=sender,
            kind=kind,
            title=title_text[:200],
            body=body_text,
            title_i18n=title_i18n,
            body_i18n=body_i18n,
            link_url=link_url or "",
            related_company=related_company,
        )
    except Exception as e:
        logger.error("notify(): failed to create notification: %s", e)
        return None


def _user_label(user):
    """Display name for a user — never translated, it's their own name."""
    if not user:
        return ""
    return f"{user.first_name} {user.last_name}".strip() or user.email


def _reverse(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return ""


def _level_label(level_code):
    """Translatable label for a franchise tier (lazy — resolved at render)."""
    from accounts.constants import FranchiseLevel

    return dict(FranchiseLevel.CHOICES).get(level_code, level_code or "")


def _country_label(code):
    """Translatable label for a country code (lazy — resolved at render)."""
    from accounts.constants import CountryChoices

    code = (code or "").strip()
    if not code:
        return ""
    return dict(CountryChoices.CHOICES).get(code.upper(), code)


def _commission_labels(commission):
    """Shared label bits for commission notifications (names stay untranslated).

    Returns the ready-to-interpolate pieces — including the "a business user"
    fallback and the optional " via <company>" clause — so the pending and
    earned senders can't drift apart."""
    consultant = commission.consultant
    amount = f"{commission.commission_amount} {commission.currency}"
    bu = getattr(commission, "business_user", None)
    bu_label = _user_label(bu) if bu else None
    company_name = commission.company.name if getattr(commission, "company_id", None) else ""

    bu_text = bu_label or Msg("a business user")
    # The separating space is a literal part, NOT baked into the msgid: a msgid
    # with a leading space is invisible in .po review and translators routinely
    # drop it, which would silently glue the clause onto the preceding word.
    via_text = (
        MsgSeq(" ", Msg("via %(company)s", company=company_name))
        if company_name else ""
    )
    return amount, bu_text, via_text, _user_label(consultant)


def _notify_commission(commission, *, consultant_msgs, su_msgs):
    """Send a commission notification to the consultant AND every active
    superuser. Shared by the pending + earned (paid) notifications."""
    from accounts.models import User

    consultant = getattr(commission, "consultant", None)
    if not consultant:
        return None
    link = _reverse("commissions")

    consultant_title, consultant_body = consultant_msgs
    last = notify(
        recipient=consultant,
        kind=Notification.KIND_GENERIC,
        title=consultant_title,
        body=consultant_body,
        link_url=link,
    )
    su_title, su_body = su_msgs
    for su in User.objects.filter(is_superuser=True, is_active=True):
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
    amount, bu_text, via_text, consultant_label = _commission_labels(commission)

    return _notify_commission(
        commission,
        consultant_msgs=(
            Msg("Commission pending — %(amount)s", amount=amount),
            Msg(
                "A %(amount)s commission from %(user)s's subscription%(via)s is pending. "
                "You'll be notified once it's marked paid.",
                amount=amount, user=bu_text, via=via_text,
            ),
        ),
        su_msgs=(
            Msg("Commission pending: %(consultant)s (%(amount)s)",
                consultant=consultant_label, amount=amount),
            Msg(
                "%(consultant)s has a pending %(amount)s commission from "
                "%(user)s's subscription%(via)s.",
                consultant=consultant_label, amount=amount, user=bu_text, via=via_text,
            ),
        ),
    )


def notify_commission_earned(commission):
    """A commission was MARKED PAID — notify the consultant they've earned it,
    and every superuser."""
    if not getattr(commission, "consultant", None):
        return None
    amount, bu_text, via_text, consultant_label = _commission_labels(commission)

    return _notify_commission(
        commission,
        consultant_msgs=(
            Msg("You earned a commission of %(amount)s", amount=amount),
            Msg(
                "Your %(amount)s commission from %(user)s's subscription%(via)s has been paid.",
                amount=amount, user=bu_text, via=via_text,
            ),
        ),
        su_msgs=(
            Msg("Commission paid: %(consultant)s (%(amount)s)",
                consultant=consultant_label, amount=amount),
            Msg(
                "You marked %(consultant)s's %(amount)s commission from "
                "%(user)s's subscription%(via)s as paid.",
                consultant=consultant_label, amount=amount, user=bu_text, via=via_text,
            ),
        ),
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
    buyer_label = _user_label(buyer)
    consultant_label = _user_label(getattr(company, "certified_by", None))

    title = Msg("Plan request: %(company)s → %(plan)s",
                company=company_name, plan=plan_name)
    body = MsgSeq(Msg(
        "%(buyer)s is requesting the %(plan)s plan for %(company)s. "
        "Approve it once payment arrives to activate the plan.",
        buyer=buyer_label or Msg("A business user"),
        plan=plan_name, company=company_name,
    ))
    if consultant_label:
        body.line(Msg("Certifying consultant (commission on approval): %(consultant)s.",
                      consultant=consultant_label))

    link = _reverse("payments")
    last = None
    for su in User.objects.filter(is_superuser=True, is_active=True):
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
    link = _reverse("certifications")
    submitter_label = _user_label(submitted_by)

    title = Msg("New certification request: %(company)s", company=company.name)
    body = MsgSeq(Msg("%(company)s has requested certification and is awaiting review.",
                      company=company.name))
    if submitter_label:
        body.line(Msg("Submitted by %(name)s.", name=submitter_label))

    last = None
    for consultant in consultants:
        last = notify(
            recipient=consultant,
            sender=submitted_by,
            kind=Notification.KIND_CERTIFICATION_REQUEST,
            title=title,
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
    link = _reverse("certifications")
    decider_label = _user_label(decided_by)

    if approved:
        kind = Notification.KIND_CERTIFICATION_APPROVED
        title = Msg("%(company)s has been certified", company=company.name)
        body = MsgSeq(Msg("Your certification request was approved"))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(Msg(". Your company is now visible in the public directory."))
    else:
        kind = Notification.KIND_CERTIFICATION_DECLINED
        title = Msg("Certification declined for %(company)s", company=company.name)
        body = MsgSeq(Msg("Your certification request was declined"))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(Msg(". You can update your company details and resubmit from your profile."))

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

    user_label = _user_label(new_user)
    role_label = ""
    if getattr(new_user, "role", None) and new_user.role.name:
        role_label = new_user.role.name.replace("_", " ").title()
    country_label = _country_label(getattr(new_user, "country", ""))
    link = _reverse("business-users")

    body = MsgSeq(Msg("%(name)s is using the system.", name=user_label))
    body.blank_line(Msg("Registration details:"))
    body.line(Msg("Name: %(name)s", name=user_label))
    body.line(Msg("Email: %(email)s", email=new_user.email))
    if getattr(new_user, "phone", ""):
        prefix = (getattr(new_user, "national_prefix", "") or "").strip()
        phone = f"+{prefix} {new_user.phone}".strip() if prefix else new_user.phone
        body.line(Msg("Phone: %(phone)s", phone=phone))
    if country_label:
        body.line(Msg("Country: %(country)s", country=country_label))
    if role_label:
        body.line(Msg("Registering as: %(role)s", role=role_label))
    if language:
        body.line(Msg("Preferred language: %(lang)s", lang=language))
    if interest:
        body.line(Msg("Interest: %(interest)s", interest=interest))
    body.blank_line(Msg("Open the Users tab to view the full profile."))

    title = Msg("%(name)s is using the system", name=user_label)
    last = None
    for consultant in consultants:
        last = notify(
            recipient=consultant,
            sender=new_user,
            kind=Notification.KIND_NEW_USER,
            title=title,
            body=body,
            link_url=link,
        )
    return last


def notify_contact_message(contact_msg):
    """Broadcast a contact form message to every active superuser."""
    from accounts.models import User

    link = _reverse("contact-messages")
    who = contact_msg.full_name

    body = MsgSeq(Msg("%(who)s sent a message via the website contact form.", who=who))
    if contact_msg.subject:
        body.line(Msg("Subject: %(subject)s", subject=contact_msg.subject))
    body.line(Msg("Email: %(email)s", email=contact_msg.email))
    if contact_msg.phone:
        body.line(Msg("Phone: %(phone)s", phone=contact_msg.phone))
    if contact_msg.company_name:
        body.line(Msg("Company: %(company)s", company=contact_msg.company_name))
    # The visitor's own words — never translated.
    body.blank_line(contact_msg.message)

    title = Msg("New contact message from %(who)s", who=who)
    last = None
    for su in User.objects.filter(is_superuser=True, is_active=True):
        last = notify(
            recipient=su,
            kind=Notification.KIND_GENERIC,
            title=title,
            body=body,
            link_url=link,
        )
    return last


def notify_coordinator_request_submitted(coord_request):
    """Broadcast a coordinator role request to every superuser."""
    from accounts.models import User

    requester = coord_request.user
    requester_label = _user_label(requester)
    link = _reverse("coordinator-requests")

    body = MsgSeq(Msg("%(name)s has requested to become a Coordinator.",
                      name=requester_label))
    if coord_request.target_region:
        body.line(Msg("Target region: %(region)s.", region=coord_request.target_region))

    last = None
    for su in User.objects.filter(is_superuser=True, is_active=True):
        last = notify(
            recipient=su,
            sender=requester,
            kind=Notification.KIND_COORDINATOR_REQUEST,
            title=Msg("New coordinator role request"),
            body=body,
            link_url=link,
        )
    return last


def notify_application_submitted(applicant):
    """Broadcast a franchise/coordinator application to every superuser."""
    from accounts.models import User

    applicant_label = _user_label(applicant)
    role_label = (
        (applicant.role.name or applicant.role.code or "applicant").replace("_", " ").title()
        if applicant.role else "applicant"
    )
    link = _reverse("applications")

    body = MsgSeq(Msg(
        "%(name)s submitted a %(role)s account application and is awaiting your review.",
        name=applicant_label, role=role_label,
    ))
    if applicant.target_region:
        body.line(Msg("Target region: %(region)s.", region=applicant.target_region))

    title = Msg("New %(role)s application", role=role_label)
    last = None
    for su in User.objects.filter(is_superuser=True, is_active=True):
        last = notify(
            recipient=su,
            sender=applicant,
            kind=Notification.KIND_APPLICATION_REQUEST,
            title=title,
            body=body,
            link_url=link,
        )
    return last


def notify_application_decision(applicant, *, approved):
    """Inform the applicant of the Super Admin's approve/decline decision."""
    if not applicant:
        return None
    decider = applicant.application_decided_by
    decider_label = _user_label(decider)
    link = _reverse("dashboard") if approved else _reverse("application-pending")

    if approved:
        kind = Notification.KIND_APPLICATION_APPROVED
        title = Msg("Your account application has been approved")
        body = MsgSeq(Msg("Your account application was approved"))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(Msg(
            ". You now have full access — sign out and back in if your sidebar doesn't update."
        ))
    else:
        kind = Notification.KIND_APPLICATION_DECLINED
        title = Msg("Your account application was declined")
        body = MsgSeq(Msg("Your account application was declined"))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(".")
        reason = (applicant.application_decline_reason or "").strip()
        if reason:
            body.line(Msg("Reason: %(reason)s", reason=reason))

    return notify(
        recipient=applicant,
        sender=decider,
        kind=kind,
        title=title,
        body=body,
        link_url=link,
    )


def _franchise_summary(application):
    """Human label for a franchise application's requested level + territory.

    The territory is a sequence rather than a finished string so the country
    part keeps its catalog entry and translates with everything else.
    """
    level_label = _level_label(application.requested_level)
    parts = [
        application.requested_local_area,
        application.requested_city,
        application.requested_region,
        _country_label(application.requested_country),
    ]
    territory = MsgSeq()
    for part in parts:
        if not str(part or "").strip():
            continue
        territory.add(part, sep=", " if len(territory) else "")
    return level_label, (territory if len(territory) else None)


def notify_franchise_application_submitted(application):
    """Notify the right reviewers of a new franchise application (spec §4.2).

    MASTER → the Platform Admin(s). Sub-franchise → the DIRECT PARENT franchise
    holder (the operational reviewer) AND the Platform Admin(s), each linked to
    the queue they act in."""
    from accounts.constants import FranchiseLevel
    from accounts.models import User

    applicant = application.applicant_user
    applicant_label = _user_label(applicant)
    level_label, territory = _franchise_summary(application)
    parent = application.parent_franchise

    title = Msg("New %(level)s request", level=level_label)

    last = None
    # Everyone already told, so nobody is notified twice when the same person
    # owns several nodes in the chain, and the applicant never notifies themself.
    notified = {applicant.id} if applicant else set()

    # Direct parent (operational reviewer) for a sub-franchise.
    if parent is not None and parent.owner_user_id:
        body = MsgSeq(Msg(
            "%(name)s has requested a %(level)s under %(parent)s and is awaiting your review.",
            name=applicant_label, level=level_label, parent=parent.name,
        ))
        if territory:
            body.line(Msg("Territory: %(territory)s.", territory=territory))
        if parent.owner_user_id not in notified:
            notified.add(parent.owner_user_id)
            last = notify(
                recipient=parent.owner_user,
                sender=applicant,
                kind=Notification.KIND_FRANCHISE_REQUEST,
                title=title,
                body=body,
                link_url=_reverse("franchise-child-requests"),
            )

    # Everyone further up the tree, to the Master. They don't review the request
    # — the direct parent does — but a Master is entitled to know what is being
    # requested inside its territory, which it previously never heard about when
    # the request landed on a Regional or National beneath it.
    if parent is not None:
        for ancestor in parent.get_ancestors():
            if not ancestor.owner_user_id or ancestor.owner_user_id in notified:
                continue
            notified.add(ancestor.owner_user_id)
            anc_body = MsgSeq(Msg(
                "%(name)s has requested a %(level)s under %(parent)s, inside your "
                "franchise %(ancestor)s. %(parent)s reviews it — this is for your information.",
                name=applicant_label, level=level_label,
                parent=parent.name, ancestor=ancestor.name,
            ))
            if territory:
                anc_body.line(Msg("Territory: %(territory)s.", territory=territory))
            last = notify(
                recipient=ancestor.owner_user,
                sender=applicant,
                kind=Notification.KIND_FRANCHISE_REQUEST,
                title=title,
                body=anc_body,
                link_url=_reverse("franchise-tree"),
            )

    # Platform Admin(s) — always notified (§4.2 notification target).
    if parent is not None:
        su_body = MsgSeq(Msg(
            "%(name)s requested a %(level)s under %(parent)s. %(parent)s reviews it; "
            "you'll activate it after approval.",
            name=applicant_label, level=level_label, parent=parent.name,
        ))
    elif application.requested_level != FranchiseLevel.MASTER:
        # A sub-franchise for a territory nothing covers yet: there is no parent
        # to review it, so it sits with the Admin until the higher tier exists.
        su_body = MsgSeq(Msg(
            "%(name)s has requested a %(level)s in a territory no franchise covers yet. "
            "Set up the higher-level franchise it belongs under, then approve it.",
            name=applicant_label, level=level_label,
        ))
    else:
        su_body = MsgSeq(Msg(
            "%(name)s has requested a %(level)s and is awaiting your review.",
            name=applicant_label, level=level_label,
        ))
    if territory:
        su_body.line(Msg("Territory: %(territory)s.", territory=territory))

    su_link = _reverse("franchise-applications")
    for su in User.objects.filter(is_superuser=True, is_active=True):
        if su.id in notified:
            continue
        notified.add(su.id)
        last = notify(
            recipient=su,
            sender=applicant,
            kind=Notification.KIND_FRANCHISE_REQUEST,
            title=title,
            body=su_body,
            link_url=su_link,
        )
    return last


def notify_franchise_awaiting_activation(node):
    """A sub-franchise was approved by its parent and now awaits the Platform
    Admin's activation (spec §4.2 final activation authority)."""
    from accounts.models import User

    level_label = _level_label(node.franchise_level)
    link = _reverse("franchise-applications")
    title = Msg("%(level)s awaiting activation", level=level_label)
    body = Msg(
        "%(name)s was approved by its parent franchise and is awaiting activation "
        "(contract & payment).",
        name=node.name,
    )
    last = None
    for su in User.objects.filter(is_superuser=True, is_active=True):
        last = notify(
            recipient=su,
            sender=node.approved_by,
            kind=Notification.KIND_FRANCHISE_REQUEST,
            title=title,
            body=body,
            link_url=link,
        )
    return last


def notify_franchise_application_decision(application, *, approved):
    """Inform the applicant of the Super Admin's approve/reject decision."""
    applicant = application.applicant_user
    if not applicant:
        return None
    decider = application.approved_by if approved else application.rejected_by
    decider_label = _user_label(decider)
    level_label, _territory = _franchise_summary(application)
    link = _reverse("franchise-request")

    if approved:
        kind = Notification.KIND_FRANCHISE_APPROVED
        title = Msg("Your %(level)s request was approved", level=level_label)
        body = MsgSeq(Msg("Your %(level)s request was approved", level=level_label))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(Msg(
            ". The franchise is now pending contract and payment — the Super "
            "Admin will activate it once those are complete."
        ))
    else:
        kind = Notification.KIND_FRANCHISE_REJECTED
        title = Msg("Your %(level)s request was rejected", level=level_label)
        body = MsgSeq(Msg("Your %(level)s request was rejected", level=level_label))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(".")
        reason = (application.board_note or "").strip()
        if reason:
            body.line(Msg("Reason: %(reason)s", reason=reason))

    return notify(
        recipient=applicant,
        sender=decider,
        kind=kind,
        title=title,
        body=body,
        link_url=link,
    )


def notify_franchise_activated(node):
    """Inform the franchise holder that their franchise is now ACTIVE (spec §2 —
    activation grants the Franchise Management section)."""
    owner = getattr(node, "owner_user", None)
    if not owner:
        return None
    return notify(
        recipient=owner,
        sender=node.approved_by,
        kind=Notification.KIND_FRANCHISE_ACTIVATED,
        title=Msg("Your %(level)s is now active", level=_level_label(node.franchise_level)),
        body=Msg(
            "%(name)s has been activated. Sign out and back in if your sidebar "
            "doesn't show the Franchises section yet.",
            name=node.name,
        ),
        link_url=_reverse("franchise-request"),
    )


def notify_franchise_fee_paid(node):
    """Tell the people who act next that a franchise fee has been recorded paid.

    The holder of the node's DIRECT PARENT activates it from their queue, so
    they are the one who needs prompting; the node's own holder is told their
    payment landed. Returns the last notification sent."""
    last = None
    parent = getattr(node, "parent", None)
    level_label = _level_label(node.franchise_level)

    if parent is not None and parent.owner_user_id:
        last = notify(
            recipient=parent.owner_user,
            kind=Notification.KIND_FRANCHISE_REQUEST,
            title=Msg("%(level)s ready to activate", level=level_label),
            body=Msg(
                "The franchise fee for %(name)s has been marked as paid by the Platform "
                "Admin. You can activate it now — it will then appear in your franchise tree.",
                name=node.name,
            ),
            link_url=_reverse("franchise-child-requests"),
        )

    owner = getattr(node, "owner_user", None)
    if owner is not None and owner.id != getattr(parent, "owner_user_id", None):
        last = notify(
            recipient=owner,
            kind=Notification.KIND_FRANCHISE_REQUEST,
            title=Msg("Franchise fee received"),
            body=Msg(
                "Your payment for %(name)s has been recorded. It goes live once "
                "%(activator)s activates it.",
                name=node.name,
                # A nested Msg keeps the fallback wording translatable too.
                activator=(parent.name if parent is not None else Msg("the Platform Admin")),
            ),
            link_url=_reverse("franchise-request"),
        )
    return last


def notify_franchise_removed(node, *, removed_by=None, reason="", cascaded=False):
    """Tell a holder their franchise was removed by the Platform Admin.

    `cascaded` marks a sub-franchise that went with its parent: the holder did
    nothing wrong and their own node was not the one the admin acted on, so the
    body says so rather than leaving them guessing."""
    owner = getattr(node, "owner_user", None)
    if not owner:
        return None

    title = Msg("Your %(level)s was removed", level=_level_label(node.franchise_level))
    if cascaded:
        body = MsgSeq(Msg(
            "%(name)s was removed because the franchise above it was removed by "
            "the Platform Admin. Your existing data is preserved, but the "
            "franchise rights for this territory have ended.",
            name=node.name,
        ))
    else:
        body = MsgSeq(Msg(
            "%(name)s was removed by the Platform Admin. Your existing data is "
            "preserved, but the franchise rights for this territory have ended.",
            name=node.name,
        ))
    reason = (reason or "").strip()
    if reason:
        body.line(Msg("Reason: %(reason)s", reason=reason))

    return notify(
        recipient=owner,
        sender=removed_by if removed_by and removed_by.is_authenticated else None,
        kind=Notification.KIND_FRANCHISE_REMOVED,
        title=title,
        body=body,
        link_url=_reverse("franchise-request"),
    )


def notify_coordinator_request_decision(coord_request, *, approved):
    """Inform the requesting BU of the Super Admin's decision."""
    requester = coord_request.user
    if not requester:
        return None
    decider = coord_request.decided_by
    decider_label = _user_label(decider)

    if approved:
        kind = Notification.KIND_COORDINATOR_APPROVED
        title = Msg("Your Coordinator role has been approved")
        body = MsgSeq(Msg("Your request to become a Coordinator was approved"))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(Msg(
            ". Sign out and back in to see the Coordinator features in your sidebar."
        ))
    else:
        kind = Notification.KIND_COORDINATOR_DECLINED
        title = Msg("Your Coordinator request was declined")
        body = MsgSeq(Msg("Your request to become a Coordinator was declined"))
        if decider_label:
            body.add(Msg("by %(name)s", name=decider_label), sep=" ")
        body.add(".")
        reason = (coord_request.decline_reason or "").strip()
        if reason:
            body.line(Msg("Reason: %(reason)s", reason=reason))

    return notify(
        recipient=requester,
        sender=decider,
        kind=kind,
        title=title,
        body=body,
        link_url=_reverse("profile"),
    )


def notify_franchise_removal_requested(removal_request):
    """Tell the reviewer a holder wants to give up their franchise.

    Routing mirrors the application flow in reverse: a Master exit goes to the
    Platform Admin(s); a sub-franchise exit goes to the DIRECT PARENT holder,
    who granted the territory in the first place.
    """
    from accounts.models import User

    node = removal_request.node
    requester = removal_request.requested_by
    requester_label = _user_label(requester)
    level_label = _level_label(node.franchise_level)
    reviewer_node = removal_request.reviewer_franchise

    title = Msg("Request to remove a %(level)s", level=level_label)
    body = MsgSeq(Msg(
        "%(name)s has asked to give up %(node)s and is awaiting your decision.",
        name=requester_label, node=node.name,
    ))
    reason = (removal_request.reason or "").strip()
    if reason:
        body.line(Msg("Reason: %(reason)s", reason=reason))

    def _send(recipient, link):
        return notify(
            recipient=recipient,
            sender=requester,
            kind=Notification.KIND_FRANCHISE_REQUEST,
            title=title,
            body=body,
            link_url=link,
        )

    last = None
    if reviewer_node is not None and reviewer_node.owner_user_id:
        last = _send(reviewer_node.owner_user, _reverse("franchise-child-requests"))
    else:
        for admin in User.objects.filter(is_superuser=True, is_active=True):
            last = _send(admin, _reverse("franchise-applications"))
    return last


def notify_franchise_removal_decision(removal_request, *, approved):
    """Tell the holder whether their request to give up a franchise was granted.

    The approved case is followed by `notify_franchise_removed` from the
    wind-down itself, so this one stays short and only carries the decision.
    """
    requester = removal_request.requested_by
    if not requester:
        return None
    node = removal_request.node

    if approved:
        title = Msg("Your removal request was approved")
        body = MsgSeq(Msg("%(node)s will be removed from your account.", node=node.name))
    else:
        title = Msg("Your removal request was declined")
        body = MsgSeq(Msg("%(node)s stays with you for now.", node=node.name))
    note = (removal_request.decision_note or "").strip()
    if note:
        body.line(Msg("Note: %(note)s", note=note))

    return notify(
        recipient=requester,
        sender=removal_request.decided_by,
        kind=(Notification.KIND_FRANCHISE_APPROVED if approved
              else Notification.KIND_FRANCHISE_REJECTED),
        title=title,
        body=body,
        link_url=_reverse("franchise-request"),
    )
