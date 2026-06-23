#!/usr/bin/env python3
"""Apply gettext wrappers to remaining Phase 7 templates (profile + large dashboard)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def t(msg: str, ctx: str = "profile") -> str:
    return f'{{% trans "{msg}" context "{ctx}" %}}'


def tc(msg: str) -> str:
    return f'{{% trans "{msg}" context "common" %}}'


def tco(msg: str) -> str:
    return f'{{% trans "{msg}" context "companies" %}}'


def escjs(msg: str, ctx: str = "profile") -> str:
    return f"{{% filter escapejs %}}{{% trans '{msg}' context '{ctx}' %}}{{% endfilter %}}"


def wrap_profile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    reps: list[tuple[str, str]] = [
        (
            "Coordinator request pending Super Admin review.",
            t("Coordinator request pending Super Admin review."),
        ),
        (
            "Request to become a Coordinator",
            t("Request to become a Coordinator"),
        ),
        ('<td class="text-muted" style="width:40%;">Phone</td>', f'<td class="text-muted" style="width:40%;">{tc("Phone")}</td>'),
        ('<td class="text-muted">Country</td>', f'<td class="text-muted">{tc("Country")}</td>',),
        ('<td class="text-muted">Role</td>', f'<td class="text-muted">{t("Role")}</td>'),
        ('<td class="text-muted">Tenant</td>', f'<td class="text-muted">{t("Tenant", "dashboard")}</td>'),
        ('<td class="text-muted">Member Since</td>', f'<td class="text-muted">{t("Member Since")}</td>'),
        ('<i class="fas fa-building mr-2"></i>My Company</h3>', f'<i class="fas fa-building mr-2"></i>{t("My Company")}</h3>'),
        ('<td class="text-muted" style="width:160px;">Company Name</td>', f'<td class="text-muted" style="width:160px;">{tco("Company Name")}</td>'),
        ('<td class="text-muted">Registration No.</td>', f'<td class="text-muted">{tco("Registration No.")}</td>'),
        ('<td class="text-muted">Classification</td>', f'<td class="text-muted">{tco("Classification")}</td>'),
        ('<td class="text-muted">Website</td>', f'<td class="text-muted">{tco("Website")}</td>'),
        ('<td class="text-muted">Address Line 1</td>', f'<td class="text-muted">{t("Address Line 1")}</td>'),
        ('<td class="text-muted">Address Line 2</td>', f'<td class="text-muted">{t("Address Line 2")}</td>'),
        ('<td class="text-muted">City</td>', f'<td class="text-muted">{tco("City / Municipality")}</td>'),
        ('<td class="text-muted">State</td>', f'<td class="text-muted">{tco("State")}</td>'),
        ('<td class="text-muted">Postal Code</td>', f'<td class="text-muted">{tco("Postal Code")}</td>'),
        ('<td class="text-muted">Secondary Phone</td>', f'<td class="text-muted">{t("Secondary Phone")}</td>'),
        ('<td class="text-muted">Fax</td>', f'<td class="text-muted">{t("Fax")}</td>'),
        ('<td class="text-muted">Tenant Domain</td>', f'<td class="text-muted">{t("Tenant Domain")}</td>'),
        ('<td class="text-muted">Status</td>', f'<td class="text-muted">{tc("Status")}</td>'),
        ('<span class="badge badge-success">Active</span>', f'<span class="badge badge-success">{tc("Active")}</span>'),
        ('<span class="badge badge-secondary">Inactive</span>', f'<span class="badge badge-secondary">{tc("Inactive")}</span>'),
        ('<i class="fas fa-search mr-2"></i>Join Another Company</h3>', f'<i class="fas fa-search mr-2"></i>{t("Join Another Company")}</h3>'),
        (
            "Request to join another company that's already on the platform. The\n          company owner approves or declines your request.",
            '{% blocktrans trimmed context "profile" %}Request to join another company that\'s already on the platform. The company owner approves or declines your request.{% endblocktrans %}',
        ),
        ('<i class="fas fa-building mr-2"></i>Set Up Your Company</h3>', f'<i class="fas fa-building mr-2"></i>{t("Set Up Your Company")}</h3>'),
        (
            "You don't have a company linked yet. Register the company you represent below.",
            '{% blocktrans trimmed context "profile" %}You don\'t have a company linked yet. Register the company you represent below.{% endblocktrans %}',
        ),
        (
            "You don't have a company linked yet. Join one that's already on the platform, or register a new one.",
            '{% blocktrans trimmed context "profile" %}You don\'t have a company linked yet. Join one that\'s already on the platform, or register a new one.{% endblocktrans %}',
        ),
        ('<i class="fas fa-search mr-1"></i> Join Existing Company', f'<i class="fas fa-search mr-1"></i> {t("Join Existing Company")}'),
        ('<i class="fas fa-plus-circle mr-1"></i> Create New Company', f'<i class="fas fa-plus-circle mr-1"></i> {t("Create New Company")}'),
        ('<strong>Please fix the following before submitting:</strong>', f'<strong>{t("Please fix the following before submitting:")}</strong>'),
        ('<label>Company Name <span class="text-danger">*</span></label>', f'<label>{tco("Company Name")} <span class="text-danger">*</span></label>'),
        ('placeholder="Enter company name"', f'placeholder="{escjs("Enter company name", "companies")}"'),
        ('<label>Registration No. <span class="text-danger">*</span></label>', f'<label>{tco("Registration No.")} <span class="text-danger">*</span></label>'),
        ('placeholder="e.g. CH123456 / EIN-12-3456789"', f'placeholder="{escjs("e.g. CH123456 / EIN-12-3456789", "profile")}"'),
        ('<small class="text-muted">Legal identifier (e.g. company-house number, EIN, CIN). Must be unique.</small>', f'<small class="text-muted">{t("Legal identifier (e.g. company-house number, EIN, CIN). Must be unique.")}</small>'),
        ('<label>Domain <span class="text-danger">*</span></label>', f'<label>{t("Domain")} <span class="text-danger">*</span></label>'),
        ('placeholder="e.g. mycompany.com"', f'placeholder="{escjs("e.g. mycompany.com", "profile")}"'),
        ('<small class="text-muted">This domain will be linked to your company\'s tenant.</small>', f'<small class="text-muted">{t("This domain will be linked to your company\'s tenant.")}</small>'),
        ('<label>Legal Form</label>', f'<label>{tco("Legal Form")}</label>'),
        ('<option value="">Select Legal Form</option>', f'<option value="">{tco("Select Legal Form")}</option>'),
        ('<label>Year of Establishment</label>', f'<label>{tco("Year of Establishment")}</label>'),
        ('placeholder="e.g. 2014"', f'placeholder="{escjs("e.g. 2014", "profile")}"'),
        ('<label>Number of Employees</label>', f'<label>{tco("Number of Employees")}</label>'),
        ('<option value="">Select range</option>', f'<option value="">{t("Select range")}</option>'),
        ('<label>Classification <span class="text-danger">*</span></label>', f'<label>{tco("Classification")} <span class="text-danger">*</span></label>'),
        ('<option value="">Select Classification</option>', f'<option value="">{tco("Select Classification")}</option>'),
        ('placeholder="https://mycompany.com"', f'placeholder="{escjs("https://mycompany.com", "profile")}"'),
        ('<label>Street</label>', f'<label>{tco("Street")}</label>'),
        ('placeholder="e.g. Baker Street"', f'placeholder="{escjs("e.g. Baker Street", "profile")}"'),
        ('<label>House Number</label>', f'<label>{tco("House Number")}</label>'),
        ('placeholder="e.g. 221B"', f'placeholder="{escjs("e.g. 221B", "profile")}"'),
        ('<label>Region</label>', f'<label>{tco("Region")}</label>'),
        ('placeholder="e.g. Greater London"', f'placeholder="{escjs("e.g. Greater London", "profile")}"'),
        ('<label>District</label>', f'<label>{tco("District")}</label>'),
        ('placeholder="e.g. Westminster"', f'placeholder="{escjs("e.g. Westminster", "profile")}"'),
        ('<label>City <span class="text-danger">*</span></label>', f'<label>{tco("City / Municipality")} <span class="text-danger">*</span></label>'),
        ('placeholder="e.g. New York"', f'placeholder="{escjs("e.g. New York", "profile")}"'),
        ('<option value="">Select Country</option>', f'<option value="">{tco("Select Country")}</option>'),
        ('<label>State <span class="text-danger">*</span></label>', f'<label>{tco("State")} <span class="text-danger">*</span></label>'),
        ('<option value="">Select State</option>', f'<option value="">{tco("Select State")}</option>'),
        ('placeholder="e.g. 10001 or SW1A 1AA"', f'placeholder="{escjs("e.g. 10001 or SW1A 1AA", "profile")}"'),
        ('placeholder="+1 212 555 0100"', f'placeholder="{escjs("+1 212 555 0100", "profile")}"'),
        ('<label>Secondary Phone</label>', f'<label>{t("Secondary Phone")}</label>'),
        ('<label>Contact Email</label>', f'<label>{tco("Contact Email")}</label>'),
        ('placeholder="contact@example.com"', f'placeholder="{escjs("contact@example.com", "profile")}"'),
        ('<label>NACE / ISIC Code</label>', f'<label>{t("NACE / ISIC Code")}</label>'),
        ('placeholder="NACE / ISIC code"', f'placeholder="{escjs("NACE / ISIC code", "profile")}"'),
        ('<label>Keywords</label>', f'<label>{tco("Keywords")}</label>'),
        ('placeholder="comma-separated search keywords"', f'placeholder="{escjs("comma-separated search keywords", "profile")}"'),
        ('<small class="text-muted">Words other users will type to find this company.</small>', f'<small class="text-muted">{t("Words other users will type to find this company.")}</small>'),
        ('<label>Company Logo</label>', f'<label>{t("Company Logo")}</label>'),
        ('<small class="text-muted">PNG, JPG, SVG, WEBP or GIF (max 5 MB). Shown in the company overview.</small>', f'<small class="text-muted">{t("PNG, JPG, SVG, WEBP or GIF (max 5 MB). Shown in the company overview.")}</small>'),
        ('<i class="fas fa-certificate mr-1"></i> Request Certification', f'<i class="fas fa-certificate mr-1"></i> {tco("Request Certification")}'),
        ('<h5 class="modal-title font-weight-bold"><i class="fas fa-user-edit mr-1"></i> Edit Profile</h5>', f'<h5 class="modal-title font-weight-bold"><i class="fas fa-user-edit mr-1"></i> {t("Edit Profile")}</h5>'),
        ('aria-label="Close"', f'aria-label="{escjs("Close", "common")}"'),
        ('<label>First Name <span class="text-danger">*</span></label>', f'<label>{tc("First Name")} <span class="text-danger">*</span></label>'),
        ('<label>Last Name <span class="text-danger">*</span></label>', f'<label>{tc("Last Name")} <span class="text-danger">*</span></label>'),
        ('<label>Email</label>', f'<label>{tc("Email")}</label>'),
        ('<small class="text-muted">Email cannot be changed from here.</small>', f'<small class="text-muted">{t("Email cannot be changed from here.")}</small>'),
        ('<option value="">— Select country —</option>', f'<option value="">{t("— Select country —")}</option>'),
        ('<button type="button" class="btn btn-secondary btn-sm" data-dismiss="modal">Cancel</button>', f'<button type="button" class="btn btn-secondary btn-sm" data-dismiss="modal">{tc("Cancel")}</button>'),
        ('<button type="submit" id="edit-profile-save-btn" class="btn btn-primary btn-sm" disabled>Save Changes</button>', f'<button type="submit" id="edit-profile-save-btn" class="btn btn-primary btn-sm" disabled>{t("Save Changes")}</button>'),
    ]
    for old, new in reps:
        if old not in text:
            continue
        text = text.replace(old, new)

    # JS: join company picker
    text = text.replace(
        "(query ? 'No companies match \"' + escapeHtml(query) + '\".' : 'No companies available yet.')",
        "(query ? PROFILE_I18N.noCompaniesMatchPrefix + escapeHtml(query) + PROFILE_I18N.noCompaniesMatchSuffix : PROFILE_I18N.noCompaniesAvailable)",
    )
    text = text.replace(
        "resultsBox.innerHTML = '<div style=\"padding:18px; text-align:center; color:#b91c1c; font-size:.85rem;\">Failed to load companies. Please try again.</div>';",
        "resultsBox.innerHTML = '<div style=\"padding:18px; text-align:center; color:#b91c1c; font-size:.85rem;\">' + PROFILE_I18N.failedLoadCompanies + '</div>';",
    )

    # JS: edit profile toasts
    text = text.replace(
        'showToast(result.data.message || "Profile updated successfully.", "success");',
        'showToast(result.data.message || PROFILE_I18N.profileUpdatedSuccess, "success");',
    )
    text = text.replace(
        'const msg = result.data.message || "Could not update profile.";',
        'const msg = result.data.message || PROFILE_I18N.couldNotUpdateProfile;',
    )
    text = text.replace(
        'showToast("Network error. Please try again.", "error");',
        'showToast(PROFILE_I18N.networkError, "error");',
    )

    # JS: state dropdown
    text = text.replace(
        "stateSel.innerHTML = '<option value=\"\">Select State</option>';",
        "stateSel.innerHTML = '<option value=\"\">' + PROFILE_I18N.selectState + '</option>';",
    )
    text = text.replace(
        "let html = '<option value=\"\">Select State</option>';",
        "let html = '<option value=\"\">' + PROFILE_I18N.selectState + '</option>';",
    )

    bridge = '''
<script>
(function () {
  var g = function (s) { return (typeof gettext === 'function') ? gettext(s) : s; };
  window.PROFILE_I18N = {
    noCompaniesMatchPrefix: '{% filter escapejs %}{% trans "No companies match \\"" context "profile" %}{% endfilter %}',
    noCompaniesMatchSuffix: '{% filter escapejs %}{% trans "\\"." context "profile" %}{% endfilter %}',
    noCompaniesAvailable: '{% filter escapejs %}{% trans "No companies available yet." context "profile" %}{% endfilter %}',
    failedLoadCompanies: '{% filter escapejs %}{% trans "Failed to load companies. Please try again." context "profile" %}{% endfilter %}',
    profileUpdatedSuccess: '{% filter escapejs %}{% trans "Profile updated successfully." context "profile" %}{% endfilter %}',
    couldNotUpdateProfile: '{% filter escapejs %}{% trans "Could not update profile." context "profile" %}{% endfilter %}',
    networkError: '{% filter escapejs %}{% trans "Network error. Please try again." context "common" %}{% endfilter %}',
    selectState: '{% filter escapejs %}{% trans "Select State" context "companies" %}{% endfilter %}',
    companyNameEmpty: '{% filter escapejs %}{% trans "Company name cannot be empty or just spaces." context "profile" %}{% endfilter %}',
  };
  Object.keys(window.PROFILE_I18N).forEach(function (k) {
    window.PROFILE_I18N[k] = g(window.PROFILE_I18N[k]);
  });
})();
</script>
'''
    if "window.PROFILE_I18N" not in text:
        text = text.replace("{% if can_join_company %}\n<script>", bridge + "\n{% if can_join_company %}\n<script>")

    # Ensure join picker script references PROFILE_I18N
    text = text.replace(
        "{% if can_join_company %}\n<script>\n(function () {",
        "{% if can_join_company %}\n<script>\n(function () {\n  var PROFILE_I18N = window.PROFILE_I18N || {};",
    )

    path.write_text(text, encoding="utf-8")
    print(f"wrapped {path.name}")


def td(msg: str) -> str:
    return f'{{% trans "{msg}" context "dashboard" %}}'


def tc(msg: str) -> str:
    return f'{{% trans "{msg}" context "common" %}}'


def tco(msg: str) -> str:
    return f'{{% trans "{msg}" context "companies" %}}'


def wrap_index(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count('{% trans') > 50:
        print(f"skip {path.name} (already wrapped)")
        return

    # Bulk label replacements
    pairs = [
        (" &middot; Last login: Today", f" &middot; {td('Last login: Today')}"),
        ("Certifications this month", td("Certifications this month")),
        (" today", f" {td('today')}"),
        ("/ target ", f"/ {td('target')} "),
        ("Subscriptions sold this month", td("Subscriptions sold this month")),
        (" of ", f" {td('of')} "),
        (" (monthly target)", f" ({td('monthly target')})"),
        ("Certifications", td("Certifications")),
        ("Subscriptions sold", td("Subscriptions sold")),
        ("By plan", td("By plan")),
        ("No subscriptions sold in this month yet.", td("No subscriptions sold in this month yet.")),
        ("Click a day to see how many companies you certified that day.", td("Click a day to see how many companies you certified that day.")),
        ("Total Companies", td("Total Companies")),
        (" this month", f" {td('this month')}"),
        (" active", f" {td('active')}"),
        ("Active Subscriptions", td("Active Subscriptions")),
        (" this week", f" {td('this week')}"),
        ("Monthly Revenue", td("Monthly Revenue")),
        (" vs last month", f" {td('vs last month')}"),
        ("Active Companies", td("Active Companies")),
        (" inactive", f" {td('inactive')}"),
        ("Registered Users", td("Registered Users")),
        ("Pending Invoices", td("Pending Invoices")),
        (" overdue", f" {td('overdue')}"),
        ("Active Regions", td("Active Regions")),
        ("Countries with companies", td("Countries with companies")),
        ("Tenants", td("Tenants")),
        ("Pending Approvals", td("Pending Approvals")),
        ('Review now &rarr;', f'{td("Review now")} &rarr;'),
        ("Revenue Overview", td("Revenue Overview")),
        ("Monthly subscription revenue (USD)", td("Monthly subscription revenue (USD)")),
        ("Subscription Plans", td("Subscription Plans")),
        ("Distribution by plan type", td("Distribution by plan type")),
        ("Recent Companies", td("Recent Companies")),
        ("Latest registered companies", td("Latest registered companies")),
        ('View All &rarr;', f'{td("View All")} &rarr;'),
        (">Company</th>", f">{td('Company')}</th>"),
        (">Country</th>", f">{tc('Country')}</th>"),
        (">Plan</th>", f">{td('Plan')}</th>"),
        (">Status</th>", f">{tc('Status')}</th>"),
        ("&#10003; Verified", f"&#10003; {td('Verified')}"),
        (">Pending</span>", f">{td('Pending')}</span>"),
        ("No companies yet", td("No companies yet")),
        ("Recent Activity", td("Recent Activity")),
        ("Latest platform events", td("Latest platform events")),
        ("No recent activity", td("No recent activity")),
        ("Regional Performance", td("Regional Performance")),
        ("Companies by region", td("Companies by region")),
        ("Industry Breakdown", td("Industry Breakdown")),
        ("Companies by industry sector", td("Companies by industry sector")),
        ("Quick Actions", td("Quick Actions")),
        ("> Add Company</a>", f"> {td('Add Company')}</a>"),
        ("> Add User</a>", f"> {td('Add User')}</a>"),
        ("> View Invoices</a>", f"> {td('View Invoices')}</a>"),
        ("> View Reports</a>", f"> {td('View Reports')}</a>"),
        ("> Manage Regions</a>", f"> {td('Manage Regions')}</a>"),
        ("Billing Summary", td("Billing Summary")),
        ("Current subscription status", td("Current subscription status")),
        ('Manage &rarr;', f'{td("Manage")} &rarr;'),
        ("Platform Admin", td("Platform Admin")),
        ("Full access to all features", td("Full access to all features")),
        (">Active</span>", f">{tc('Active')}</span>"),
        ("Active Subscriptions</dt>", f"{td('Active Subscriptions')}</dt>"),
        ("Pending Invoices</dt>", f"{td('Pending Invoices')}</dt>"),
        ("Monthly Revenue</dt>", f"{td('Monthly Revenue')}</dt>"),
        (" USD</dd>", f" {td('USD')}</dd>"),
        ("Payment Method</dt>", f"{td('Payment Method')}</dt>"),
        (">Bank Transfer</dd>", f">{td('Bank Transfer')}</dd>"),
        (" pending</a>", f" {td('pending')}</a>"),
        ("All clear &#10003;", f"{td('All clear')} &#10003;"),
        ('id="healthTitle">User Health</h5>', f'id="healthTitle">{td("User Health")}</h5>'),
        ('onclick="showUsers()">Users</button>', f'onclick="showUsers()">{td("Users")}</button>'),
        ('onclick="showCompanies()">Companies</button>', f'onclick="showCompanies()">{td("Companies")}</button>'),
        ("Quick Insight", td("Quick Insight")),
    ]
    for old, new in pairs:
        text = text.replace(old, new)

    # Plan suffix in welcome meta
    text = re.sub(
        r"\{\{ user_plan\.name\|upper \}\} Plan",
        r'{% blocktrans trimmed with plan_name=user_plan.name|upper context "dashboard" %}{{ plan_name }} Plan{% endblocktrans %}',
        text,
    )

    # JS month names and chart labels via DASHBOARD_I18N bridge
    bridge = '''
<script>
(function () {
  var g = function (s) { return (typeof gettext === 'function') ? gettext(s) : s; };
  window.DASHBOARD_I18N = {
    monthNames: [
      '{% filter escapejs %}{% trans "January" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "February" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "March" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "April" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "May" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "June" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "July" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "August" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "September" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "October" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "November" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "December" context "dashboard" %}{% endfilter %}',
    ],
    daySun: '{% filter escapejs %}{% trans "Sun" context "dashboard" %}{% endfilter %}',
    dayMon: '{% filter escapejs %}{% trans "Mon" context "dashboard" %}{% endfilter %}',
    dayTue: '{% filter escapejs %}{% trans "Tue" context "dashboard" %}{% endfilter %}',
    dayWed: '{% filter escapejs %}{% trans "Wed" context "dashboard" %}{% endfilter %}',
    dayThu: '{% filter escapejs %}{% trans "Thu" context "dashboard" %}{% endfilter %}',
    dayFri: '{% filter escapejs %}{% trans "Fri" context "dashboard" %}{% endfilter %}',
    daySat: '{% filter escapejs %}{% trans "Sat" context "dashboard" %}{% endfilter %}',
    noCompaniesCertified: '{% filter escapejs %}{% trans "no companies certified" context "dashboard" %}{% endfilter %}',
    companyCertified: '{% filter escapejs %}{% trans "company certified" context "dashboard" %}{% endfilter %}',
    companiesCertified: '{% filter escapejs %}{% trans "companies certified" context "dashboard" %}{% endfilter %}',
    clickDayCertified: '{% filter escapejs %}{% trans "Click a day to see how many companies you certified that day." context "dashboard" %}{% endfilter %}',
    noSubsThisMonth: '{% filter escapejs %}{% trans "No subscriptions sold in this month yet." context "dashboard" %}{% endfilter %}',
    userHealth: '{% filter escapejs %}{% trans "User Health" context "dashboard" %}{% endfilter %}',
    companyHealth: '{% filter escapejs %}{% trans "Company Health" context "dashboard" %}{% endfilter %}',
    usersActiveInsight: '{% filter escapejs %}{% blocktrans trimmed with active=active_users total=total_users context "dashboard" %}<strong>{{ active }}</strong> of <strong>{{ total }}</strong> users are active.{% endblocktrans %}{% endfilter %}',
    companiesActiveInsight: '{% filter escapejs %}{% blocktrans trimmed with active=active_companies total=total_companies context "dashboard" %}<strong>{{ active }}</strong> of <strong>{{ total }}</strong> companies are active.{% endblocktrans %}{% endfilter %}',
    userActivityStable: '{% filter escapejs %}{% trans "User activity is stable." context "dashboard" %}{% endfilter %}',
    companyOpsStable: '{% filter escapejs %}{% trans "Company operations are stable." context "dashboard" %}{% endfilter %}',
    activeUsers: '{% filter escapejs %}{% trans "Active Users" context "dashboard" %}{% endfilter %}',
    inactiveUsers: '{% filter escapejs %}{% trans "Inactive Users" context "dashboard" %}{% endfilter %}',
    activeCompanies: '{% filter escapejs %}{% trans "Active Companies" context "dashboard" %}{% endfilter %}',
    inactiveCompanies: '{% filter escapejs %}{% trans "Inactive Companies" context "dashboard" %}{% endfilter %}',
  };
  Object.keys(window.DASHBOARD_I18N).forEach(function (k) {
    if (k === 'monthNames') {
      window.DASHBOARD_I18N[k] = window.DASHBOARD_I18N[k].map(g);
    } else {
      window.DASHBOARD_I18N[k] = g(window.DASHBOARD_I18N[k]);
    }
  });
})();
</script>
'''
    if "window.DASHBOARD_I18N" not in text:
        text = text.replace("{% if not is_consultant_dashboard %}\n<!-- ================= CHART SCRIPTS ================= -->", bridge + "\n{% if not is_consultant_dashboard %}\n<!-- ================= CHART SCRIPTS ================= -->")

    text = text.replace(
        'var monthNames = ["January","February","March","April","May","June","July","August","September","October","November","December"];',
        'var monthNames = window.DASHBOARD_I18N ? window.DASHBOARD_I18N.monthNames : ["January","February","March","April","May","June","July","August","September","October","November","December"];',
    )
    text = text.replace(
        '["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach',
        '[window.DASHBOARD_I18N.daySun,window.DASHBOARD_I18N.dayMon,window.DASHBOARD_I18N.dayTue,window.DASHBOARD_I18N.dayWed,window.DASHBOARD_I18N.dayThu,window.DASHBOARD_I18N.dayFri,window.DASHBOARD_I18N.daySat].forEach',
    )
    text = text.replace(
        '+ (n === 0 ? "no companies certified" : n + " compan" + (n === 1 ? "y" : "ies") + " certified")',
        '+ (n === 0 ? window.DASHBOARD_I18N.noCompaniesCertified : n + " " + (n === 1 ? window.DASHBOARD_I18N.companyCertified : window.DASHBOARD_I18N.companiesCertified))',
    )
    text = text.replace(
        "subList.innerHTML = '<div style=\"color:#94a3b8; font-size:.85rem;\">No subscriptions sold in this month yet.</div>';",
        "subList.innerHTML = '<div style=\"color:#94a3b8; font-size:.85rem;\">' + window.DASHBOARD_I18N.noSubsThisMonth + '</div>';",
    )
    text = text.replace(
        'dayDetail.innerHTML = "Click a day to see how many companies you certified that day.";',
        'dayDetail.innerHTML = window.DASHBOARD_I18N.clickDayCertified;',
    )
    text = text.replace(
        'document.getElementById("healthTitle").innerText = "User Health";',
        'document.getElementById("healthTitle").innerText = window.DASHBOARD_I18N.userHealth;',
    )
    text = text.replace(
        'document.getElementById("healthTitle").innerText = "Company Health";',
        'document.getElementById("healthTitle").innerText = window.DASHBOARD_I18N.companyHealth;',
    )
    text = text.replace(
        'document.getElementById("insightNote").innerText = "User activity is stable.";',
        'document.getElementById("insightNote").innerText = window.DASHBOARD_I18N.userActivityStable;',
    )
    text = text.replace(
        'document.getElementById("insightNote").innerText = "Company operations are stable.";',
        'document.getElementById("insightNote").innerText = window.DASHBOARD_I18N.companyOpsStable;',
    )
    text = text.replace(
        '["Active Users", "Inactive Users"]',
        '[window.DASHBOARD_I18N.activeUsers, window.DASHBOARD_I18N.inactiveUsers]',
    )
    text = text.replace(
        '["Active Companies", "Inactive Companies"]',
        '[window.DASHBOARD_I18N.activeCompanies, window.DASHBOARD_I18N.inactiveCompanies]',
    )

    path.write_text(text, encoding="utf-8")
    print(f"wrapped {path.name}")


def wrap_certifications(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    reps = [
        ('<i class="fas fa-certificate mr-1"></i> Certifications :', f'<i class="fas fa-certificate mr-1"></i> {td("Certifications")} :'),
        ('Review pending certification requests and manage the companies you\'ve already certified.', f'{{% blocktrans trimmed context "dashboard" %}}Review pending certification requests and manage the companies you\'ve already certified.{{% endblocktrans %}}'),
        ('<p class="mb-0">You haven\'t submitted any certification requests yet.</p>', f'<p class="mb-0">{td("You haven\'t submitted any certification requests yet.")}</p>'),
        ('Submit a company via <a href="{% url \'profile\' %}">your profile</a> or the', '{% blocktrans trimmed context "dashboard" %}Submit a company via{% endblocktrans %} <a href="{% url \'profile\' %}">{% trans "your profile" context "dashboard" %}</a> {% trans "or the" context "dashboard" %}'),
        ('<a href="{% url \'companies\' %}">Company Database</a> to request certification.', '<a href="{% url \'companies\' %}">{% trans "Company Database" context "dashboard" %}</a> {% trans "to request certification." context "dashboard" %}'),
        ('<div class="bu-section-title">Pending Review</div>', f'<div class="bu-section-title">{td("Pending Review")}</div>'),
        ('Assigned to consultant', '{% trans "Assigned to consultant" context "dashboard" %}'),
        ('Awaiting consultant assignment', td('Awaiting consultant assignment')),
        ('<span class="pill pill-pending">Pending</span>', f'<span class="pill pill-pending">{td("Pending")}</span>'),
        ('<div class="bu-section-title">Certified</div>', f'<div class="bu-section-title">{td("Certified")}</div>'),
        ('Certified {{ c.certified_at|date:"M j, Y" }}', '{% blocktrans trimmed with date=c.certified_at|date:"M j, Y" context "dashboard" %}Certified {{ date }}{% endblocktrans %}'),
        (' by {{ c.certified_by.first_name }}', ' {% trans "by" context "dashboard" %} {{ c.certified_by.first_name }}'),
        ('<span class="pill pill-certified">Certified</span>', f'<span class="pill pill-certified">{td("Certified")}</span>'),
        ('<div class="bu-section-title">Declined</div>', f'<div class="bu-section-title">{td("Declined")}</div>'),
        ('Declined {{ c.updated_at|date:"M j, Y" }}', '{% blocktrans trimmed with date=c.updated_at|date:"M j, Y" context "dashboard" %}Declined {{ date }}{% endblocktrans %}'),
        ('Update your company details and resubmit from', '{% trans "Update your company details and resubmit from" context "dashboard" %}'),
        ('<a href="{% url \'profile\' %}">your profile</a>.', '<a href="{% url \'profile\' %}">{% trans "your profile" context "dashboard" %}</a>.'),
        ('<span class="pill pill-rejected">Declined</span>', f'<span class="pill pill-rejected">{td("Declined")}</span>'),
        ('>Pending\n      {% if pending %}', '>' + td("Pending") + '\n      {% if pending %}'),
        ('My Certified Companies', td('My Certified Companies')),
        ('>Declined\n      {% if rejected %}', '>' + td("Declined") + '\n      {% if rejected %}'),
        ('<th>Company</th>', f'<th>{td("Company")}</th>'),
        ('<th>Requester</th>', f'<th>{td("Requester")}</th>'),
        ('<th>City</th>', f'<th>{tco("City / Municipality")}</th>'),
        ('<th>Submitted</th>', f'<th>{td("Submitted")}</th>'),
        ('<th class="text-center">Action</th>', f'<th class="text-center">{tc("Action")}</th>'),
        ('<i class="fas fa-eye mr-1"></i> View', f'<i class="fas fa-eye mr-1"></i> {tc("View")}'),
        ('title="Edit company details, then come back to approve"', f'title="{escjs("Edit company details, then come back to approve", "dashboard")}"'),
        ('<i class="fas fa-edit mr-1"></i> Edit', f'<i class="fas fa-edit mr-1"></i> {tc("Edit")}'),
        ('<i class="fas fa-check mr-1"></i> Approve', f'<i class="fas fa-check mr-1"></i> {td("Approve")}'),
        ('<i class="fas fa-times mr-1"></i> Decline', f'<i class="fas fa-times mr-1"></i> {td("Decline")}'),
        ('<p class="mb-0">No pending certification requests.</p>', f'<p class="mb-0">{td("No pending certification requests.")}</p>'),
        ('<p class="small mb-0">New requests routed to you will appear here.</p>', f'<p class="small mb-0">{td("New requests routed to you will appear here.")}</p>'),
        ('<th>Owner</th>', f'<th>{td("Owner")}</th>'),
        ('<th>Certified</th>', f'<th>{td("Certified")}</th>'),
        ('<span class="pill pill-inactive">Inactive</span>', f'<span class="pill pill-inactive">{tc("Inactive")}</span>'),
        ('<i class="fas fa-toggle-off mr-1"></i> Deactivate', f'<i class="fas fa-toggle-off mr-1"></i> {td("Deactivate")}'),
        ('<i class="fas fa-toggle-on mr-1"></i> Activate', f'<i class="fas fa-toggle-on mr-1"></i> {td("Activate")}'),
        ('<p class="mb-0">You haven\'t certified any companies yet.</p>', f'<p class="mb-0">{td("You haven\'t certified any companies yet.")}</p>'),
        ('<th>Decision date</th>', f'<th>{td("Decision date")}</th>'),
        ('<p class="mb-0">No declined requests.</p>', f'<p class="mb-0">{td("No declined requests.")}</p>'),
        ('<span id="cert-drawer-status" class="pill pill-pending">Pending</span>', f'<span id="cert-drawer-status" class="pill pill-pending">{td("Pending")}</span>'),
        ('<button type="button" id="cert-drawer-close-2" class="btn btn-sm btn-outline-secondary">Close</button>', f'<button type="button" id="cert-drawer-close-2" class="btn btn-sm btn-outline-secondary">{tc("Close")}</button>'),
    ]
    for old, new in reps:
        text = text.replace(old, new)

    # Submitted line in BU pending
    text = text.replace(
        'Submitted {{ c.created_at|date:"M j, Y" }} &middot;',
        '{% blocktrans trimmed with date=c.created_at|date:"M j, Y" context "dashboard" %}Submitted {{ date }}{% endblocktrans %} &middot;',
    )

    bridge = '''
<script>
(function () {
  var g = function (s) { return (typeof gettext === 'function') ? gettext(s) : s; };
  window.DASHBOARD_I18N = window.DASHBOARD_I18N || {};
  Object.assign(window.DASHBOARD_I18N, {
    actionFailed: '{% filter escapejs %}{% trans "Action failed." context "dashboard" %}{% endfilter %}',
    networkError: '{% filter escapejs %}{% trans "Network error. Please try again." context "common" %}{% endfilter %}',
    couldNotLoadCompany: '{% filter escapejs %}{% trans "Could not load company details." context "companies" %}{% endfilter %}',
    companyDefault: '{% filter escapejs %}{% trans "Company" context "dashboard" %}{% endfilter %}',
    legalForm: '{% filter escapejs %}{% trans "Legal Form" context "companies" %}{% endfilter %}',
    registrationId: '{% filter escapejs %}{% trans "Registration ID" context "companies" %}{% endfilter %}',
    yearEstablished: '{% filter escapejs %}{% trans "Year Established" context "companies" %}{% endfilter %}',
    employees: '{% filter escapejs %}{% trans "Employees" context "companies" %}{% endfilter %}',
    primaryLineOfBusiness: '{% filter escapejs %}{% trans "Primary Line of Business" context "dashboard" %}{% endfilter %}',
    naceCode: '{% filter escapejs %}{% trans "NACE Code" context "companies" %}{% endfilter %}',
    naicsCode: '{% filter escapejs %}{% trans "NAICS Code" context "companies" %}{% endfilter %}',
    keywords: '{% filter escapejs %}{% trans "Keywords" context "companies" %}{% endfilter %}',
    address: '{% filter escapejs %}{% trans "Address" context "companies" %}{% endfilter %}',
    contactPerson: '{% filter escapejs %}{% trans "Contact Person" context "companies" %}{% endfilter %}',
    phone: '{% filter escapejs %}{% trans "Phone" context "companies" %}{% endfilter %}',
    contactEmail: '{% filter escapejs %}{% trans "Contact Email" context "companies" %}{% endfilter %}',
    website: '{% filter escapejs %}{% trans "Website" context "companies" %}{% endfilter %}',
  });
  Object.keys(window.DASHBOARD_I18N).forEach(function (k) {
    if (typeof window.DASHBOARD_I18N[k] === 'string') {
      window.DASHBOARD_I18N[k] = g(window.DASHBOARD_I18N[k]);
    }
  });
})();
</script>
'''
    if "actionFailed" not in text:
        text = text.replace('<script>\ndocument.addEventListener("DOMContentLoaded", function () {', bridge + '\n<script>\ndocument.addEventListener("DOMContentLoaded", function () {\n  var i18n = window.DASHBOARD_I18N || {};')

    text = text.replace('var msg = (res.data && res.data.message) || "Action failed.";', 'var msg = (res.data && res.data.message) || i18n.actionFailed;')
    text = text.replace('showToast("Network error. Please try again.", "error");', 'showToast(i18n.networkError, "error");')
    text = text.replace('showToast("Could not load company details.", "error");', 'showToast(i18n.couldNotLoadCompany, "error");')
    text = text.replace('drawerName.textContent = c.name || "Company";', 'drawerName.textContent = c.name || i18n.companyDefault;')

    for label, key in [
        ("Legal Form", "legalForm"),
        ("Registration ID", "registrationId"),
        ("Year Established", "yearEstablished"),
        ("Employees", "employees"),
        ("Primary Line of Business", "primaryLineOfBusiness"),
        ("NACE Code", "naceCode"),
        ("NAICS Code", "naicsCode"),
        ("Keywords", "keywords"),
        ("Address", "address"),
        ("Contact Person", "contactPerson"),
        ("Phone", "phone"),
        ("Contact Email", "contactEmail"),
        ("Website", "website"),
    ]:
        text = text.replace(f'row("{label}",', f'row(i18n.{key},')

    path.write_text(text, encoding="utf-8")
    print(f"wrapped {path.name}")


def wrap_consultant_stats(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    reps = [
        ('Network <span>/ Consultant Users / {{ consultant.first_name }}', '{% trans "Network" context "dashboard" %} <span>/ {% trans "Consultant Users" context "dashboard" %} / {{ consultant.first_name }}'),
        ('/ Statistics</span>', '/ {% trans "Statistics" context "dashboard" %}</span>'),
        ('<label for="cs-from">From</label>', f'<label for="cs-from">{td("From")}</label>'),
        ('<label for="cs-to">To</label>', f'<label for="cs-to">{td("To")}</label>'),
        ('<i class="fas fa-filter mr-1"></i> Apply', f'<i class="fas fa-filter mr-1"></i> {td("Apply")}'),
        ('<div class="cs-kpi__label">Certifications</div>', f'<div class="cs-kpi__label">{td("Certifications")}</div>'),
        ('<div class="cs-kpi__label">Avg / day</div>', f'<div class="cs-kpi__label">{td("Avg / day")}</div>'),
        ('Target {{ target_certs_min }}–{{ target_certs_max }} per day', '{% blocktrans trimmed with min=target_certs_min max=target_certs_max context "dashboard" %}Target {{ min }}–{{ max }} per day{% endblocktrans %}'),
        ('<div class="cs-kpi__label">Subscriptions sold</div>', f'<div class="cs-kpi__label">{td("Subscriptions sold")}</div>'),
        ('Target {{ target_subs_month }} per month', '{% blocktrans trimmed with target=target_subs_month context "dashboard" %}Target {{ target }} per month{% endblocktrans %}'),
        ('<h3 class="cs-card__title">Certifications calendar</h3>', f'<h3 class="cs-card__title">{td("Certifications calendar")}</h3>'),
        ('Click a day to see how many companies this consultant certified that day.', td('Click a day to see how many companies this consultant certified that day.')),
        ('<h3 class="cs-card__title">Plans sold in range</h3>', f'<h3 class="cs-card__title">{td("Plans sold in range")}</h3>'),
    ]
    for old, new in reps:
        text = text.replace(old, new)

    bridge = '''
<script>
(function () {
  var g = function (s) { return (typeof gettext === 'function') ? gettext(s) : s; };
  window.DASHBOARD_I18N = window.DASHBOARD_I18N || {};
  Object.assign(window.DASHBOARD_I18N, {
    monthNames: [
      '{% filter escapejs %}{% trans "January" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "February" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "March" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "April" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "May" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "June" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "July" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "August" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "September" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "October" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "November" context "dashboard" %}{% endfilter %}',
      '{% filter escapejs %}{% trans "December" context "dashboard" %}{% endfilter %}',
    ],
    daySun: '{% filter escapejs %}{% trans "Sun" context "dashboard" %}{% endfilter %}',
    dayMon: '{% filter escapejs %}{% trans "Mon" context "dashboard" %}{% endfilter %}',
    dayTue: '{% filter escapejs %}{% trans "Tue" context "dashboard" %}{% endfilter %}',
    dayWed: '{% filter escapejs %}{% trans "Wed" context "dashboard" %}{% endfilter %}',
    dayThu: '{% filter escapejs %}{% trans "Thu" context "dashboard" %}{% endfilter %}',
    dayFri: '{% filter escapejs %}{% trans "Fri" context "dashboard" %}{% endfilter %}',
    daySat: '{% filter escapejs %}{% trans "Sat" context "dashboard" %}{% endfilter %}',
    noCompaniesCertified: '{% filter escapejs %}{% trans "no companies certified" context "dashboard" %}{% endfilter %}',
    companyCertified: '{% filter escapejs %}{% trans "company certified" context "dashboard" %}{% endfilter %}',
    companiesCertified: '{% filter escapejs %}{% trans "companies certified" context "dashboard" %}{% endfilter %}',
    clickDayConsultant: '{% filter escapejs %}{% trans "Click a day to see how many companies this consultant certified that day." context "dashboard" %}{% endfilter %}',
    acrossDays: '{% filter escapejs %}{% trans "Across" context "dashboard" %}{% endfilter %}',
    day: '{% filter escapejs %}{% trans "day" context "dashboard" %}{% endfilter %}',
    days: '{% filter escapejs %}{% trans "days" context "dashboard" %}{% endfilter %}',
    targetPerDay: '{% filter escapejs %}{% trans "Target" context "dashboard" %}{% endfilter %}',
    perDay: '{% filter escapejs %}{% trans "per day" context "dashboard" %}{% endfilter %}',
    meetingDailyTarget: '{% filter escapejs %}{% trans "Meeting daily target" context "dashboard" %}{% endfilter %}',
    belowDailyTarget: '{% filter escapejs %}{% trans "Below daily target" context "dashboard" %}{% endfilter %}',
    expectedInRange: '{% filter escapejs %}{% trans "Expected" context "dashboard" %}{% endfilter %}',
    inThisRange: '{% filter escapejs %}{% trans "in this range" context "dashboard" %}{% endfilter %}',
    targetPerMonth: '{% filter escapejs %}{% trans "target" context "dashboard" %}{% endfilter %}',
    metExpected: '{% filter escapejs %}{% trans "Met expected" context "dashboard" %}{% endfilter %}',
    noSubsInRange: '{% filter escapejs %}{% trans "No subscriptions sold in this range." context "dashboard" %}{% endfilter %}',
    toDateCantBeEarlier: '{% filter escapejs %}{% trans "The \'To\' date can\'t be earlier than the \'From\' date." context "dashboard" %}{% endfilter %}',
  });
  ['monthNames'].forEach(function (k) {
    window.DASHBOARD_I18N[k] = window.DASHBOARD_I18N[k].map(g);
  });
  Object.keys(window.DASHBOARD_I18N).forEach(function (k) {
    if (k !== 'monthNames' && typeof window.DASHBOARD_I18N[k] === 'string') {
      window.DASHBOARD_I18N[k] = g(window.DASHBOARD_I18N[k]);
    }
  });
})();
</script>
'''
    if "toDateCantBeEarlier" not in text:
        text = text.replace('<script>\n(function () {', bridge + '\n<script>\n(function () {\n  var i18n = window.DASHBOARD_I18N || {};')

    text = text.replace(
        'var monthNames = ["January","February","March","April","May","June","July","August","September","October","November","December"];',
        'var monthNames = i18n.monthNames;',
    )
    text = text.replace(
        '["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach',
        '[i18n.daySun,i18n.dayMon,i18n.dayTue,i18n.dayWed,i18n.dayThu,i18n.dayFri,i18n.daySat].forEach',
    )
    text = text.replace(
        '+ (n === 0 ? "no companies certified" : n + " compan" + (n === 1 ? "y" : "ies") + " certified")',
        '+ (n === 0 ? i18n.noCompaniesCertified : n + " " + (n === 1 ? i18n.companyCertified : i18n.companiesCertified))',
    )
    text = text.replace(
        'certsHint.textContent = "Across " + data.days_in_range + " day" + (data.days_in_range === 1 ? "" : "s");',
        'certsHint.textContent = i18n.acrossDays + " " + data.days_in_range + " " + (data.days_in_range === 1 ? i18n.day : i18n.days);',
    )
    text = text.replace(
        'var avgHintText = "Target " + TARGET_DAY_MIN + "–" + TARGET_DAY_MAX + " per day";',
        'var avgHintText = i18n.targetPerDay + " " + TARGET_DAY_MIN + "–" + TARGET_DAY_MAX + " " + i18n.perDay;',
    )
    text = text.replace('avgHintText = "✓ Meeting daily target";', 'avgHintText = "✓ " + i18n.meetingDailyTarget;')
    text = text.replace(
        'avgHintText = "Below daily target (" + TARGET_DAY_MIN + "–" + TARGET_DAY_MAX + ")";',
        'avgHintText = i18n.belowDailyTarget + " (" + TARGET_DAY_MIN + "–" + TARGET_DAY_MAX + ")";',
    )
    text = text.replace(
        'var subText = "Expected " + expectedSubs + " in this range (target " + TARGET_SUBS_MONTH + "/mo)";',
        'var subText = i18n.expectedInRange + " " + expectedSubs + " " + i18n.inThisRange + " (" + i18n.targetPerMonth + " " + TARGET_SUBS_MONTH + "/mo)";',
    )
    text = text.replace('subText = "✓ Met expected " + expectedSubs;', 'subText = "✓ " + i18n.metExpected + " " + expectedSubs;')
    text = text.replace(
        "planList.innerHTML = '<div style=\"color:#94a3b8; font-size:.85rem;\">No subscriptions sold in this range.</div>';",
        "planList.innerHTML = '<div style=\"color:#94a3b8; font-size:.85rem;\">' + i18n.noSubsInRange + '</div>';",
    )
    text = text.replace(
        'dayDetail.innerHTML = "Click a day to see how many companies this consultant certified that day.";',
        'dayDetail.innerHTML = i18n.clickDayConsultant;',
    )
    text = text.replace(
        'showToast("The \'To\' date can\'t be earlier than the \'From\' date.", "error");',
        'showToast(i18n.toDateCantBeEarlier, "error");',
    )
    text = text.replace(
        'alert("The \'To\' date can\'t be earlier than the \'From\' date.");',
        'alert(i18n.toDateCantBeEarlier);',
    )

    path.write_text(text, encoding="utf-8")
    print(f"wrapped {path.name}")


def wrap_regions_map(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    bridge = '''
<script>
(function () {
  var g = function (s) { return (typeof gettext === 'function') ? gettext(s) : s; };
  window.DASHBOARD_I18N = window.DASHBOARD_I18N || {};
  Object.assign(window.DASHBOARD_I18N, {
    consultant: '{% filter escapejs %}{% trans "consultant" context "dashboard" %}{% endfilter %}',
    consultants: '{% filter escapejs %}{% trans "consultants" context "dashboard" %}{% endfilter %}',
    more: '{% filter escapejs %}{% trans "more" context "dashboard" %}{% endfilter %}',
  });
  Object.keys(window.DASHBOARD_I18N).forEach(function (k) {
    if (['consultant','consultants','more'].indexOf(k) !== -1) {
      window.DASHBOARD_I18N[k] = g(window.DASHBOARD_I18N[k]);
    }
  });
})();
</script>
'''
    if "consultants" not in text or "window.DASHBOARD_I18N" not in text.split("regions-map")[1][:500]:
        text = text.replace('<script src="https://unpkg.com/leaflet', bridge + '\n<script src="https://unpkg.com/leaflet')

    text = text.replace(
        '"<span style=\'color:#6c757d\'>" + p.count + " consultant" +\n      (p.count === 1 ? "" : "s") + "</span><br><br>" +',
        '"<span style=\'color:#6c757d\'>" + p.count + " " + (p.count === 1 ? (window.DASHBOARD_I18N.consultant || "consultant") : (window.DASHBOARD_I18N.consultants || "consultants")) + "</span><br><br>" +',
    )
    text = text.replace(
        '? "<br><em>+ " + (p.consultants.length - 5) + " more</em>"',
        '? "<br><em>+ " + (p.consultants.length - 5) + " " + (window.DASHBOARD_I18N.more || "more") + "</em>"',
    )
    path.write_text(text, encoding="utf-8")
    print(f"wrapped {path.name}")


def main() -> None:
    wrap_profile(ROOT / "templates/profile/profile.html")
    wrap_index(ROOT / "templates/dashboard/index.html")
    wrap_certifications(ROOT / "templates/dashboard/certifications.html")
    wrap_consultant_stats(ROOT / "templates/dashboard/consultant_statistics.html")
    wrap_regions_map(ROOT / "templates/dashboard/regions_map.html")


if __name__ == "__main__":
    main()
