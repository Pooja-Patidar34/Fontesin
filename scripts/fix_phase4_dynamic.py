#!/usr/bin/env python3
"""Fix remaining dynamic user-facing strings in Phase 4 view files."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS = [
    # join_request.py - JoinRequestError messages
    (
        "accounts/view/join_request.py",
        'raise JoinRequestError(\n            "Your role represents a single company — please register your "\n            "company instead of joining an existing one.",',
        'raise JoinRequestError(\n            _(\n                "Your role represents a single company — please register your "\n                "company instead of joining an existing one."\n            ),',
    ),
    (
        "accounts/view/join_request.py",
        'raise JoinRequestError("That company is unavailable. Please pick another.")',
        'raise JoinRequestError(_("That company is unavailable. Please pick another."))',
    ),
    (
        "accounts/view/join_request.py",
        'raise JoinRequestError("You already own this company.")',
        'raise JoinRequestError(_("You already own this company."))',
    ),
    (
        "accounts/view/join_request.py",
        'raise JoinRequestError(f"You\'re already linked to {company.name}.")',
        'raise JoinRequestError(_("You\'re already linked to %(company)s.") % {"company": company.name})',
    ),
    (
        "accounts/view/join_request.py",
        'raise JoinRequestError(\n                f"You already have a pending request to join {company.name}."\n            )',
        'raise JoinRequestError(\n                _("You already have a pending request to join %(company)s.")\n                % {"company": company.name}\n            )',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = (\n            f"Join request sent to {company.name}. "\n            f"You\'ll get access once the owner approves it."\n        )',
        '        msg = _(\n            "Join request sent to %(company)s. "\n            "You\'ll get access once the owner approves it."\n        ) % {"company": company.name}',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = f"This request was already {join_request.get_status_display().lower()}."',
        '        msg = _("This request was already %(status)s.") % {"status": join_request.get_status_display().lower()}',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = f"Approved {requester.email}\'s request to join {company.name}."',
        '        msg = _("Approved %(email)s\'s request to join %(company)s.") % {"email": requester.email, "company": company.name}',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = f"Declined {requester.email}\'s request to join {company.name}."',
        '        msg = _("Declined %(email)s\'s request to join %(company)s.") % {"email": requester.email, "company": company.name}',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = "You own this company, so you can\'t leave it."',
        '        msg = _("You own this company, so you can\'t leave it.")',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = "You\'re not a member of this company."',
        '        msg = _("You\'re not a member of this company.")',
    ),
    (
        "accounts/view/join_request.py",
        '    msg = f"You\'ve left {company.name}."',
        '    msg = _("You\'ve left %(company)s.") % {"company": company.name}',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = "You don\'t have permission to cancel this request."',
        '        msg = _("You don\'t have permission to cancel this request.")',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = "Only approved requests can be revoked. Use Decline for pending requests."',
        '        msg = _("Only approved requests can be revoked. Use Decline for pending requests.")',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = "This request was declined and can\'t be cancelled."',
        '        msg = _("This request was declined and can\'t be cancelled.")',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = f"Membership in {company.name} has been removed."',
        '        msg = _("Membership in %(company)s has been removed.") % {"company": company.name}',
    ),
    (
        "accounts/view/join_request.py",
        '        msg = f"Join request to {company.name} has been withdrawn."',
        '        msg = _("Join request to %(company)s has been withdrawn.") % {"company": company.name}',
    ),
    # partnership.py
    (
        "accounts/view/partnership.py",
        '        msg = f"This request was already {connection.get_status_display().lower()}."',
        '        msg = _("This request was already %(status)s.") % {"status": connection.get_status_display().lower()}',
    ),
    (
        "accounts/view/partnership.py",
        '        msg = (\n            f"Approved {connection.user.email}\'s request to connect with "\n            f"{connection.company.name}."\n        )',
        '        msg = _(\n            "Approved %(email)s\'s request to connect with %(company)s."\n        ) % {"email": connection.user.email, "company": connection.company.name}',
    ),
    (
        "accounts/view/partnership.py",
        '        msg = (\n            f"Rejected {connection.user.email}\'s request to connect with "\n            f"{connection.company.name}."\n        )',
        '        msg = _(\n            "Rejected %(email)s\'s request to connect with %(company)s."\n        ) % {"email": connection.user.email, "company": connection.company.name}',
    ),
    (
        "accounts/view/partnership.py",
        '        msg = "You don\'t have permission to cancel this partnership."',
        '        msg = _("You don\'t have permission to cancel this partnership.")',
    ),
    (
        "accounts/view/partnership.py",
        '            msg = (\n                "Only accepted partnerships can be revoked. Use Reject for "\n                "pending requests."\n            )',
        '            msg = _(\n                "Only accepted partnerships can be revoked. Use Reject for "\n                "pending requests."\n            )',
    ),
    (
        "accounts/view/partnership.py",
        '        msg = "This request was rejected and can\'t be cancelled."',
        '        msg = _("This request was rejected and can\'t be cancelled.")',
    ),
    (
        "accounts/view/partnership.py",
        '        msg = f"Partnership with {company_name} has been ended."',
        '        msg = _("Partnership with %(company)s has been ended.") % {"company": company_name}',
    ),
    (
        "accounts/view/partnership.py",
        '        msg = f"Connection request to {company_name} has been cancelled."',
        '        msg = _("Connection request to %(company)s has been cancelled.") % {"company": company_name}',
    ),
    # company.py
    (
        "accounts/view/company.py",
        '                dup_message = (\n                    "This company couldn\'t be saved — a company with the same "\n                    "name or Registration ID already exists. Please review those "\n                    "fields and try again."\n                )',
        '                dup_message = _(\n                    "This company couldn\'t be saved — a company with the same "\n                    "name or Registration ID already exists. Please review those "\n                    "fields and try again."\n                )',
    ),
    (
        "accounts/view/company.py",
        '                success_msg = "Certification request sent successfully. A consultant will review your company shortly."',
        '                success_msg = _("Certification request sent successfully. A consultant will review your company shortly.")',
    ),
    (
        "accounts/view/company.py",
        '                success_msg = "Company updated successfully."',
        '                success_msg = _("Company updated successfully.")',
    ),
    (
        "accounts/view/company.py",
        '                success_msg = "Company created successfully."',
        '                success_msg = _("Company created successfully.")',
    ),
    (
        "accounts/view/company.py",
        '                success_msg = "Certification request submitted. A consultant will review your company shortly."',
        '                success_msg = _("Certification request submitted. A consultant will review your company shortly.")',
    ),
    # tenant.py
    (
        "accounts/view/tenant.py",
        '                duplicate_msg = "A franchise with this name (or a similar one) already exists. Please choose a different name."',
        '                duplicate_msg = _("A franchise with this name (or a similar one) already exists. Please choose a different name.")',
    ),
    # user.py
    (
        "accounts/view/user.py",
        '    messages.success(request, f"User {email} has been deleted.")',
        '    messages.success(request, _("User %(email)s has been deleted.") % {"email": email})',
    ),
    # saved_filter.py
    (
        "accounts/view/saved_filter.py",
        '        msg = "Connecting with companies is available on paid plans. Upgrade to connect."',
        '        msg = _("Connecting with companies is available on paid plans. Upgrade to connect.")',
    ),
    (
        "accounts/view/saved_filter.py",
        '        msg = "Connecting is available once your plan upgrade is approved."',
        '        msg = _("Connecting is available once your plan upgrade is approved.")',
    ),
]


def main():
    for rel, old, new in REPLACEMENTS:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if old not in text:
            print(f"SKIP (not found): {rel}")
            continue
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"OK: {rel}")


if __name__ == "__main__":
    main()
