#!/usr/bin/env python3
"""Safely wrap templates/dashboard/index.html for Phase 7 i18n."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "templates/dashboard/index.html.orig"
DST = ROOT / "templates/dashboard/index.html"


def td(s: str) -> str:
    return '{% trans "' + s + '" context "dashboard" %}'


def tc(s: str) -> str:
    return '{% trans "' + s + '" context "common" %}'


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    text = text.replace(
        '{% extends "base/base.html" %}\n{% block title %}Dashboard{% endblock %}',
        '{% extends "base/base.html" %}\n{% load i18n %}\n{% block title %}' + td("Dashboard") + '{% endblock %}',
    )

    replacements = [
        ('<div class="dash-welcome__label">Welcome Back</div>', f'<div class="dash-welcome__label">{td("Welcome Back")}</div>'),
        ('&middot; Last login: Today', f'&middot; {td("Last login: Today")}'),
        (
            '{{ user_plan.name|upper }} Plan',
            '{% blocktrans trimmed with plan_name=user_plan.name|upper context "dashboard" %}{{ plan_name }} Plan{% endblocktrans %}',
        ),
        ('<div class="dash-kpi__label">Certifications this month</div>', f'<div class="dash-kpi__label">{td("Certifications this month")}</div>'),
        ('{{ consultant_cert_today|default:"0" }} today', '{{ consultant_cert_today|default:"0" }} ' + td("today")),
        ('/ target {{ consultant_target_certs_min }}', '/ ' + td("target") + ' {{ consultant_target_certs_min }}'),
        ('<div class="dash-kpi__label">Subscriptions sold this month</div>', f'<div class="dash-kpi__label">{td("Subscriptions sold this month")}</div>'),
        (
            '{{ consultant_sub_total_month|default:"0" }} of {{ consultant_target_subs_month }} (monthly target)',
            '{{ consultant_sub_total_month|default:"0" }} ' + td("of") + ' {{ consultant_target_subs_month }} (' + td("monthly target") + ')',
        ),
        ('>Certifications</div>', '>' + td("Certifications") + '</div>',),
        ('>Subscriptions sold</div>', '>' + td("Subscriptions sold") + '</div>',),
        ('>By plan</div>', '>' + td("By plan") + '</div>',),
        ('No subscriptions sold in this month yet.', td("No subscriptions sold in this month yet.")),
        ('Click a day to see how many companies you certified that day.', td("Click a day to see how many companies you certified that day.")),
        ('<div class="dash-kpi__label">Total Companies</div>', f'<div class="dash-kpi__label">{td("Total Companies")}</div>'),
        ('+{{ new_companies_month|default:"0" }} this month', '+{{ new_companies_month|default:"0" }} ' + td("this month")),
        ('{{ active_companies }} active', '{{ active_companies }} ' + td("active")),
        ('<div class="dash-kpi__label">Active Subscriptions</div>', f'<div class="dash-kpi__label">{td("Active Subscriptions")}</div>'),
        ('+{{ new_subs_week|default:"0" }} this week', '+{{ new_subs_week|default:"0" }} ' + td("this week")),
        ('<div class="dash-kpi__label">Monthly Revenue</div>', f'<div class="dash-kpi__label">{td("Monthly Revenue")}</div>'),
        ('% vs last month', '% ' + td("vs last month")),
        ('<div class="dash-kpi__label">Active Companies</div>', f'<div class="dash-kpi__label">{td("Active Companies")}</div>'),
        ('{{ inactive_companies }} inactive', '{{ inactive_companies }} ' + td("inactive")),
        ('<div class="dash-kpi__label">Registered Users</div>', f'<div class="dash-kpi__label">{td("Registered Users")}</div>'),
        ('+{{ new_users_month|default:"0" }} this month', '+{{ new_users_month|default:"0" }} ' + td("this month")),
        ('{{ active_users }} active', '{{ active_users }} ' + td("active")),
        ('<div class="dash-kpi__label">Pending Invoices</div>', f'<div class="dash-kpi__label">{td("Pending Invoices")}</div>'),
        ('{{ overdue_invoices|default:"0" }} overdue', '{{ overdue_invoices|default:"0" }} ' + td("overdue")),
        ('<div class="dash-kpi__label">Active Regions</div>', f'<div class="dash-kpi__label">{td("Active Regions")}</div>'),
        ('Countries with companies', td("Countries with companies")),
        ('<div class="dash-kpi__label">Tenants</div>', f'<div class="dash-kpi__label">{td("Tenants")}</div>'),
        ('{{ active_tenants }} active', '{{ active_tenants }} ' + td("active")),
        ('<div class="dash-kpi__label">Pending Approvals</div>', f'<div class="dash-kpi__label">{td("Pending Approvals")}</div>'),
        ('Review now &rarr;', td("Review now") + ' &rarr;'),
        ('>Revenue Overview</h5>', '>' + td("Revenue Overview") + '</h5>'),
        ('Monthly subscription revenue (USD)', td("Monthly subscription revenue (USD)")),
        ('>Subscription Plans</h5>', '>' + td("Subscription Plans") + '</h5>'),
        ('Distribution by plan type', td("Distribution by plan type")),
        ('>Recent Companies</h5>', '>' + td("Recent Companies") + '</h5>'),
        ('Latest registered companies', td("Latest registered companies")),
        ('View All &rarr;', td("View All") + ' &rarr;'),
        ('<th>Company</th>', '<th>' + td("Company") + '</th>'),
        ('<th>Country</th>', '<th>' + tc("Country") + '</th>'),
        ('<th>Plan</th>', '<th>' + td("Plan") + '</th>'),
        ('<th>Status</th>', '<th>' + tc("Status") + '</th>'),
        ('&#10003; Verified', '&#10003; ' + td("Verified")),
        ('>Pending</span>', '>' + td("Pending") + '</span>'),
        ('No companies yet', td("No companies yet")),
        ('>Recent Activity</h5>', '>' + td("Recent Activity") + '</h5>'),
        ('Latest platform events', td("Latest platform events")),
        ('No recent activity', td("No recent activity")),
        ('>Regional Performance</h5>', '>' + td("Regional Performance") + '</h5>'),
        ('Companies by region', td("Companies by region")),
        ('>Industry Breakdown</h5>', '>' + td("Industry Breakdown") + '</h5>'),
        ('Companies by industry sector', td("Companies by industry sector")),
        ('>Quick Actions</h5>', '>' + td("Quick Actions") + '</h5>'),
        ('> Add Company</a>', '> ' + td("Add Company") + '</a>'),
        ('> Add User</a>', '> ' + td("Add User") + '</a>'),
        ('> View Invoices</a>', '> ' + td("View Invoices") + '</a>'),
        ('> View Reports</a>', '> ' + td("View Reports") + '</a>'),
        ('> Manage Regions</a>', '> ' + td("Manage Regions") + '</a>'),
        ('>Billing Summary</h5>', '>' + td("Billing Summary") + '</h5>'),
        ('Current subscription status', td("Current subscription status")),
        ('Manage &rarr;', td("Manage") + ' &rarr;'),
        ('>Platform Admin</div>', '>' + td("Platform Admin") + '</div>'),
        ('Full access to all features', td("Full access to all features")),
        ('>Active</span>', '>' + tc("Active") + '</span>'),
        ('<dt>Active Subscriptions</dt>', '<dt>' + td("Active Subscriptions") + '</dt>'),
        ('<dt>Pending Invoices</dt>', '<dt>' + td("Pending Invoices") + '</dt>'),
        ('<dt>Monthly Revenue</dt>', '<dt>' + td("Monthly Revenue") + '</dt>'),
        (' USD</dd>', ' ' + td("USD") + '</dd>'),
        ('<dt>Payment Method</dt>', '<dt>' + td("Payment Method") + '</dt>'),
        ('>Bank Transfer</dd>', '>' + td("Bank Transfer") + '</dd>'),
        (' pending</a>', ' ' + td("pending") + '</a>'),
        ('All clear &#10003;', td("All clear") + ' &#10003;'),
        ('id="healthTitle">User Health</h5>', 'id="healthTitle">' + td("User Health") + '</h5>'),
        ('onclick="showUsers()">Users</button>', 'onclick="showUsers()">' + td("Users") + '</button>'),
        ('onclick="showCompanies()">Companies</button>', 'onclick="showCompanies()">' + td("Companies") + '</button>'),
        ('>Quick Insight</div>', '>' + td("Quick Insight") + '</div>'),
        ('>Pending Approvals</span>', '>' + td("Pending Approvals") + '</span>'),
    ]
    for item in replacements:
        old, new = item[0], item[1]
        text = text.replace(old, new)

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
    userActivityStable: '{% filter escapejs %}{% trans "User activity is stable." context "dashboard" %}{% endfilter %}',
    companyOpsStable: '{% filter escapejs %}{% trans "Company operations are stable." context "dashboard" %}{% endfilter %}',
    activeUsers: '{% filter escapejs %}{% trans "Active Users" context "dashboard" %}{% endfilter %}',
    inactiveUsers: '{% filter escapejs %}{% trans "Inactive Users" context "dashboard" %}{% endfilter %}',
    activeCompanies: '{% filter escapejs %}{% trans "Active Companies" context "dashboard" %}{% endfilter %}',
    inactiveCompanies: '{% filter escapejs %}{% trans "Inactive Companies" context "dashboard" %}{% endfilter %}',
  };
  Object.keys(window.DASHBOARD_I18N).forEach(function (k) {
    if (k === 'monthNames') window.DASHBOARD_I18N[k] = window.DASHBOARD_I18N[k].map(g);
    else window.DASHBOARD_I18N[k] = g(window.DASHBOARD_I18N[k]);
  });
})();
</script>
'''
    anchor = '{% if not is_consultant_dashboard %}\n<!-- ================= CHART SCRIPTS ================= -->'
    text = text.replace(anchor, bridge + '\n' + anchor)

    text = text.replace(
        'var monthNames = ["January","February","March","April","May","June","July","August","September","October","November","December"];',
        'var monthNames = (window.DASHBOARD_I18N && window.DASHBOARD_I18N.monthNames) || ["January","February","March","April","May","June","July","August","September","October","November","December"];',
    )
    text = text.replace(
        '["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach(function (d) {',
        '[window.DASHBOARD_I18N.daySun,window.DASHBOARD_I18N.dayMon,window.DASHBOARD_I18N.dayTue,window.DASHBOARD_I18N.dayWed,window.DASHBOARD_I18N.dayThu,window.DASHBOARD_I18N.dayFri,window.DASHBOARD_I18N.daySat].forEach(function (d) {',
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
        '"<strong>{{ active_users }}</strong> of <strong>{{ total_users }}</strong> users are active.";',
        'window.DASHBOARD_I18N.usersActiveTpl || "<strong>{{ active_users }}</strong> of <strong>{{ total_users }}</strong> users are active.";',
    )
    # Use server-rendered blocktrans for insight templates
    insight_users = (
        '{% filter escapejs %}{% blocktrans trimmed with active=active_users total=total_users context "dashboard" %}'
        '<strong>{{ active }}</strong> of <strong>{{ total }}</strong> users are active.{% endblocktrans %}{% endfilter %}'
    )
    insight_companies = (
        '{% filter escapejs %}{% blocktrans trimmed with active=active_companies total=total_companies context "dashboard" %}'
        '<strong>{{ active }}</strong> of <strong>{{ total }}</strong> companies are active.{% endblocktrans %}{% endfilter %}'
    )
    text = text.replace(
        '"<strong>{{ active_users }}</strong> of <strong>{{ total_users }}</strong> users are active.";',
        '"' + insight_users + '";',
    )
    text = text.replace(
        '"<strong>{{ active_companies }}</strong> of <strong>{{ total_companies }}</strong> companies are active.";',
        '"' + insight_companies + '";',
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

    DST.write_text(text, encoding="utf-8")
    print("wrapped index.html safely")


if __name__ == "__main__":
    main()
