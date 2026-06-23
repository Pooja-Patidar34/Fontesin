#!/usr/bin/env python3
"""Wrap templates/website/* for Phase 8 i18n."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "templates" / "website"

W = "website"
C = "common"


def tw(s: str) -> str:
    return f'{{% trans "{s}" context "{W}" %}}'


def tc(s: str) -> str:
    return f'{{% trans "{s}" context "{C}" %}}'


def t_auth(s: str) -> str:
    return f'{{% trans "{s}" context "auth.login" %}}'


def base_header(text: str) -> str:
    if "{% load static i18n %}" in text:
        return text
    text = text.replace("{% load static %}", "{% load static i18n %}")
    text = text.replace('lang="en"', 'lang="{{ LANGUAGE_CODE }}"')
    return text


def nav_footer(text: str) -> str:
    reps = [
        ('aria-label="Menu"', f'aria-label="{tw("Menu")}"'),
        (">Home</a>", f">{tw('Home')}</a>"),
        (">Home</a>", f">{tw('Home')}</a>"),
        (">World Map</a>", f">{tw('World Map')}</a>"),
        (">About</a>", f">{tw('About')}</a>"),
        (">About Us</a>", f">{tw('About Us')}</a>"),
        (">Careers</a>", f">{tw('Careers')}</a>"),
        (">Contact</a>", f">{tw('Contact')}</a>"),
        (">Log In</a>", f">{t_auth('Log In')}</a>"),
        (">Get Started</a>", f">{tw('Get Started')}</a>"),
        (">United States</a>", f">{tw('United States')}</a>"),
        (">Germany</a>", f">{tw('Germany')}</a>"),
        (">Czech Republic</a>", f">{tw('Czech Republic')}</a>"),
        (">UAE</a>", f">{tw('UAE')}</a>"),
        (">Japan</a>", f">{tw('Japan')}</a>"),
        ('<p class="footer__heading">Platform</p>', f'<p class="footer__heading">{tw("Platform")}</p>'),
        ('<p class="footer__heading">Company</p>', f'<p class="footer__heading">{tw("Company")}</p>'),
        ('<p class="footer__heading">Regions</p>', f'<p class="footer__heading">{tw("Regions")}</p>'),
        ('<h4>Platform</h4>', f'<h4>{tw("Platform")}</h4>'),
        ('<h4>Company</h4>', f'<h4>{tw("Company")}</h4>'),
        (
            "A deep-tech global business infrastructure platform connecting companies, professionals, and markets across languages, borders, and systems.",
            tw(
                "A deep-tech global business infrastructure platform connecting companies, professionals, and markets across languages, borders, and systems."
            ),
        ),
        ("© 2026 FONTES Inc. All rights reserved.", tw("© 2026 FONTES Inc. All rights reserved.")),
        ("&copy; 2026 FONTES Inc. All rights reserved.", tw("© 2026 FONTES Inc. All rights reserved.")),
        ("Design by Memento Mori Digital LLC", tw("Design by Memento Mori Digital LLC")),
        ("Global Business Intelligence Platform", tw("Global Business Intelligence Platform")),
    ]
    for old, new in reps:
        text = text.replace(old, new)
    return text


def pwa_block() -> str:
    return f"""<script>
(function () {{
  window.PWA_I18N = {{
    notificationBody: '{{% filter escapejs %}}{tw("You have a new notification")}{{% endfilter %}}',
    open: '{{% filter escapejs %}}{tw("Open")}{{% endfilter %}}',
    dismiss: '{{% filter escapejs %}}{tw("Dismiss")}{{% endfilter %}}',
  }};
}})();
</script>
<script>
  if ("serviceWorker" in navigator) {{
    window.addEventListener("load", function() {{
      navigator.serviceWorker.register("{{% static 'adminlte/js/sw.js' %}}")
        .then(function(reg) {{
          function sendStrings() {{
            var sw = reg.active || navigator.serviceWorker.controller;
            if (sw && window.PWA_I18N) {{
              sw.postMessage({{ type: "PWA_STRINGS", strings: window.PWA_I18N }});
            }}
          }}
          sendStrings();
          navigator.serviceWorker.addEventListener("controllerchange", sendStrings);
        }})
        .catch(function(err) {{ console.warn("[PWA] SW registration failed:", err); }});
    }});
  }}
</script>"""


def replace_sw_registration(text: str) -> str:
    text = re.sub(
        r'<script>\s*if \("serviceWorker" in navigator\).*?</script>',
        pwa_block(),
        text,
        flags=re.DOTALL,
    )
    return text


def wrap_index(text: str) -> str:
    text = base_header(text)
    text = text.replace(
        "<title>FONTESIN – Global Business Infrastructure Platform</title>",
        f"<title>FONTESIN – {tw('Global Business Infrastructure Platform')}</title>",
    )
    text = text.replace(
        'content="FONTESIN is a deep-tech global business infrastructure platform connecting companies, professionals, and markets across borders."',
        f'content="{tw("FONTESIN is a deep-tech global business infrastructure platform connecting companies, professionals, and markets across borders.")}"',
    )
    text = text.replace('href="manifest.json"', 'href="{% static \'adminlte/manifest.json\' %}"')
    reps = [
        ("Pre-MVP · Now Onboarding Partners", tw("Pre-MVP · Now Onboarding Partners")),
        ("Global Business<br/><em>Infrastructure</em><br/>Platform", f"{tw('Global Business')}<br/><em>{tw('Infrastructure')}</em><br/>{tw('Platform')}"),
        (
            "FONTESIN is a deep-tech communication and certification platform connecting companies, professionals, and markets across languages, borders, and systems.",
            tw(
                "FONTESIN is a deep-tech communication and certification platform connecting companies, professionals, and markets across languages, borders, and systems."
            ),
        ),
        ("Get Started Free", tw("Get Started Free")),
        ("Explore World Map", tw("Explore World Map")),
        ("Countries Mapped", tw("Countries Mapped")),
        ("Active Regions", tw("Active Regions")),
        ("Pioneer Members", tw("Pioneer Members")),
        ("License Tiers", tw("License Tiers")),
        ("Platform Capabilities", tw("Platform Capabilities")),
        ("Built for Global Business Operations", tw("Built for Global Business Operations")),
        (
            "FONTESIN provides a structured, verified, and scalable infrastructure for companies and professionals operating across international markets.",
            tw(
                "FONTESIN provides a structured, verified, and scalable infrastructure for companies and professionals operating across international markets."
            ),
        ),
        ("Global Region Control", tw("Global Region Control")),
        (
            "Interactive world map with live region status — Active, Planned, and Inactive markets. Direct entry point for investors, franchisees, and partners.",
            tw(
                "Interactive world map with live region status — Active, Planned, and Inactive markets. Direct entry point for investors, franchisees, and partners."
            ),
        ),
        ("Company Database", tw("Company Database")),
        (
            "Searchable, tenant-isolated company registry with legal form classification, NACE codes, certifications, and verified business profiles.",
            tw(
                "Searchable, tenant-isolated company registry with legal form classification, NACE codes, certifications, and verified business profiles."
            ),
        ),
        ("Trust & Certification", tw("Trust & Certification")),
        (
            "Blockchain-anchored certification system providing verified badges, transparent audit trails, and institutional-grade data validation.",
            tw(
                "Blockchain-anchored certification system providing verified badges, transparent audit trails, and institutional-grade data validation."
            ),
        ),
        ("Partnership Network", tw("Partnership Network")),
        (
            "Structured partnership requests, mutual visibility after acceptance, and direct 1:1 messaging within a secure, role-based environment.",
            tw(
                "Structured partnership requests, mutual visibility after acceptance, and direct 1:1 messaging within a secure, role-based environment."
            ),
        ),
        ("Tenant-Based Security", tw("Tenant-Based Security")),
        (
            "Every country operates as an isolated data tenant. Licenses define access rights. No cross-tenant data leakage — ever.",
            tw(
                "Every country operates as an isolated data tenant. Licenses define access rights. No cross-tenant data leakage — ever."
            ),
        ),
        ("AI-Powered Matching", tw("AI-Powered Matching")),
        (
            "Intelligent algorithms match companies, consultants, and franchise opportunities based on sector, region, and business profile.",
            tw(
                "Intelligent algorithms match companies, consultants, and franchise opportunities based on sector, region, and business profile."
            ),
        ),
        ("Region Control Layer", tw("Region Control Layer")),
        ("Live Global Expansion Map", tw("Live Global Expansion Map")),
        (
            'The world map is not a visualization — it is our regional control layer. A live interface for global rollout, licensing, and franchise activation.',
            tw(
                "The world map is not a visualization — it is our regional control layer. A live interface for global rollout, licensing, and franchise activation."
            ),
        ),
        ("Active Region", tw("Active Region")),
        ("Planned Expansion", tw("Planned Expansion")),
        ("Not Yet Available", tw("Not Yet Available")),
        ("Open Full Interactive Map", tw("Open Full Interactive Map")),
        ("Explore Our Active Markets", tw("Explore Our Active Markets")),
        (
            "Click any region to view detailed economic data, legal business forms, credit ratings, and franchise availability.",
            tw(
                "Click any region to view detailed economic data, legal business forms, credit ratings, and franchise availability."
            ),
        ),
        ('<span class="status-badge status-badge--active">Active</span>', f'<span class="status-badge status-badge--active">{tw("Active")}</span>'),
        (
            '<span class="status-badge status-badge--planned">Planned – Year 2</span>',
            f'<span class="status-badge status-badge--planned">{tw("Planned – Year 2")}</span>',
        ),
        (
            '<span class="status-badge status-badge--planned">Planned – Year 3</span>',
            f'<span class="status-badge status-badge--planned">{tw("Planned – Year 3")}</span>',
        ),
        ("United Arab Emirates", tw("United Arab Emirates")),
        (
            "More regions coming soon.<br/>View full map for expansion timeline.",
            f'{tw("More regions coming soon.")}<br/>{tw("View full map for expansion timeline.")}',
        ),
        ("View All Regions", tw("View All Regions")),
        ("Access Model", tw("Access Model")),
        ("Choose Your License", tw("Choose Your License")),
        (
            "From free exploration to full global access — FONTESIN scales with your ambitions.",
            tw("From free exploration to full global access — FONTESIN scales with your ambitions."),
        ),
        ("Read-only company name index. Max 1 saved selection. No active tenant.", tw("Read-only company name index. Max 1 saved selection. No active tenant.")),
        (
            "Full access to one country tenant. Unlimited saved selections. Company details visible.",
            tw("Full access to one country tenant. Unlimited saved selections. Company details visible."),
        ),
        (
            "Access to defined regions. One active country tenant per session. Advanced filters.",
            tw("Access to defined regions. One active country tenant per session. Advanced filters."),
        ),
        (
            "Access to all countries. One active country tenant per session. Full platform capabilities.",
            tw("Access to all countries. One active country tenant per session. Full platform capabilities."),
        ),
        ("Start for Free", tw("Start for Free")),
        ("Join the Movement", tw("Join the Movement")),
        ("Become a Pioneer Member", tw("Become a Pioneer Member")),
        (
            "We are building a global micro-community of 200 visionaries, experts, and pioneers shaping the future of digital business collaboration.",
            tw(
                "We are building a global micro-community of 200 visionaries, experts, and pioneers shaping the future of digital business collaboration."
            ),
        ),
        ("Apply for Pioneer Status", tw("Apply for Pioneer Status")),
        ("Learn About Us", tw("Learn About Us")),
    ]
    for old, new in reps:
        text = text.replace(old, new)
    text = nav_footer(text)
    text = replace_sw_registration(text)
    return text


def wrap_upgrade(text: str) -> str:
    text = base_header(text)
    text = text.replace("<title>Upgrade Required – FONTESIN</title>", f"<title>{tw('Upgrade Required')} – FONTESIN</title>")
    text = nav_footer(text)
    reps = [
        ("Upgrade Your Plan", tw("Upgrade Your Plan")),
        (
            """<p>
      This feature is not available on your current plan.
      Upgrade to
      {% if required_plan %}
        <strong>{{ required_plan|upper }}</strong> or higher
      {% else %}
        a higher plan
      {% endif %}
      to unlock this feature.
    </p>""",
            """<p>
      {% blocktrans context "website" %}This feature is not available on your current plan. Upgrade to{% endblocktrans %}
      {% if required_plan %}
        <strong>{{ required_plan|upper }}</strong> {% trans "or higher" context "website" %}
      {% else %}
        {% trans "a higher plan" context "website" %}
      {% endif %}
      {% trans "to unlock this feature." context "website" %}
    </p>""",
        ),
        (
            'Your current plan: <strong>{{ current_plan.name|default:"No Plan" }}</strong>',
            '{% blocktrans with plan_name=current_plan.name|default:_("No Plan") context "website" %}Your current plan: <strong>{{ plan_name }}</strong>{% endblocktrans %}',
        ),
        ("View Plans &amp; Upgrade &rarr;", tw("View Plans & Upgrade") + " &rarr;"),
        ("&larr; Go Back", "&larr; " + tw("Go Back")),
        ("No Plan", tw("No Plan")),
    ]
    for old, new in reps:
        text = text.replace(old, new)
    return text


def wrap_world_map_partial(text: str) -> str:
    text = base_header(text)
    text = text.replace(
        "'<p style=\"color:#253D51;padding:40px;text-align:center;\">Map loading...</p>'",
        f"'<p style=\"color:#253D51;padding:40px;text-align:center;\">{tw('Map loading...')}</p>'",
    )
    text = text.replace(
        "const statusLabel = info.status === 'active' ? '● Active' : `◌ Planned – Year ${info.year}`;",
        f"const statusLabel = info.status === 'active' ? '● {tw('Active')}' : `◌ {tw('Planned – Year')} ${{info.year}}`;",
    )
    text = text.replace(
        "<div style=\"font-size:.7rem;color:rgba(199,204,209,.6);margin-top:4px;\">Click for details →</div>",
        f"<div style=\"font-size:.7rem;color:rgba(199,204,209,.6);margin-top:4px;\">{tw('Click for details →')}</div>",
    )
    return text


def wrap_contact(text: str) -> str:
    text = base_header(text)
    text = text.replace("<title>Contact – FONTESIN</title>", f"<title>{tw('Contact')} – FONTESIN</title>")
    text = text.replace(
        'content="Get in touch with FONTESIN. Contact us for franchise inquiries, partnerships, investor relations, or general questions."',
        f'content="{tw("Get in touch with FONTESIN. Contact us for franchise inquiries, partnerships, investor relations, or general questions.")}"',
    )
    text = nav_footer(text)
    text = replace_sw_registration(text)

  # Fix contact form JS with WEBSITE_I18N
    website_i18n = f"""<script>
(function () {{
  var g = function (s) {{ return (typeof gettext === 'function') ? gettext(s) : s; }};
  window.WEBSITE_I18N = {{
    firstNameRequired: '{{% filter escapejs %}}{tw("Please enter your first name.")}{{% endfilter %}}',
    lastNameRequired: '{{% filter escapejs %}}{tw("Please enter your last name.")}{{% endfilter %}}',
    emailRequired: '{{% filter escapejs %}}{tw("Please enter your email address.")}{{% endfilter %}}',
    subjectRequired: '{{% filter escapejs %}}{tw("Please select a subject.")}{{% endfilter %}}',
    messageRequired: '{{% filter escapejs %}}{tw("Please enter your message.")}{{% endfilter %}}',
    emailInvalid: '{{% filter escapejs %}}{tw("Please enter a valid email address.")}{{% endfilter %}}',
    privacyRequired: '{{% filter escapejs %}}{tw("Please agree to the Privacy Policy before sending.")}{{% endfilter %}}',
  }};
  Object.keys(window.WEBSITE_I18N).forEach(function (k) {{
    window.WEBSITE_I18N[k] = g(window.WEBSITE_I18N[k]);
  }});
}})();
</script>"""

    text = text.replace(
        """    var REQUIRED = [
      { name: "first_name", msg: "Please enter your first name." },
      { name: "last_name",  msg: "Please enter your last name." },
      { name: "email",      msg: "Please enter your email address." },
      { name: "subject",    msg: "Please select a subject." },
      { name: "message",    msg: "Please enter your message." }
    ];""",
        """    var REQUIRED = [
      { name: "first_name", msg: window.WEBSITE_I18N.firstNameRequired },
      { name: "last_name",  msg: window.WEBSITE_I18N.lastNameRequired },
      { name: "email",      msg: window.WEBSITE_I18N.emailRequired },
      { name: "subject",    msg: window.WEBSITE_I18N.subjectRequired },
      { name: "message",    msg: window.WEBSITE_I18N.messageRequired }
    ];""",
    )
    text = text.replace(
        'showError(email, "Please enter a valid email address.");',
        'showError(email, window.WEBSITE_I18N.emailInvalid);',
    )
    text = text.replace(
        'showError(privacy, "Please agree to the Privacy Policy before sending.");',
        'showError(privacy, window.WEBSITE_I18N.privacyRequired);',
    )
    text = text.replace("<style>\n  .cf-invalid", website_i18n + "\n<style>\n  .cf-invalid")

    reps = [
        ("<span>Contact</span>", f"<span>{tw('Contact')}</span>"),
        ("<h1>Get In Touch</h1>", f"<h1>{tw('Get In Touch')}</h1>"),
        (
            "Whether you are an investor, franchise partner, consultant, or simply curious — we would love to hear from you.",
            tw("Whether you are an investor, franchise partner, consultant, or simply curious — we would love to hear from you."),
        ),
        ("<h3 style=\"margin-bottom:28px;\">Contact Information</h3>", f'<h3 style="margin-bottom:28px;">{tw("Contact Information")}</h3>'),
        ("<div class=\"contact-info__label\">Headquarters</div>", f'<div class="contact-info__label">{tw("Headquarters")}</div>'),
        ("<div class=\"contact-info__label\">Phone</div>", f'<div class="contact-info__label">{tw("Phone")}</div>'),
        ("<div class=\"contact-info__label\">Email</div>", f'<div class="contact-info__label">{tc("Email")}</div>'),
        ("<div class=\"contact-info__label\">Website</div>", f'<div class="contact-info__label">{tw("Website")}</div>'),
        ("<div class=\"contact-info__label\">Office Hours</div>", f'<div class="contact-info__label">{tw("Office Hours")}</div>'),
        ("Monday – Friday<br/>9:00 AM – 6:00 PM EST", f'{tw("Monday – Friday")}<br/>{tw("9:00 AM – 6:00 PM EST")}'),
        ("<h3 style=\"margin-bottom:28px;\">Send Us a Message</h3>", f'<h3 style="margin-bottom:28px;">{tw("Send Us a Message")}</h3>'),
        ('<label class="form-label">First Name *</label>', f'<label class="form-label">{tw("First Name")} *</label>'),
        ('<label class="form-label">Last Name *</label>', f'<label class="form-label">{tw("Last Name")} *</label>'),
        ('<label class="form-label">Email Address *</label>', f'<label class="form-label">{tw("Email Address")} *</label>'),
        ('<label class="form-label">Phone Number</label>', f'<label class="form-label">{tw("Phone Number")}</label>'),
        ('<label class="form-label">Company Name</label>', f'<label class="form-label">{tw("Company Name")}</label>'),
        ('<label class="form-label">Subject *</label>', f'<label class="form-label">{tc("Subject")} *</label>'),
        ('<option value="">Select a topic...</option>', f'<option value="">{tw("Select a topic...")}</option>'),
        ("<option>Franchise Inquiry</option>", f"<option>{tw('Franchise Inquiry')}</option>"),
        ("<option>Partnership Request</option>", f"<option>{tw('Partnership Request')}</option>"),
        ("<option>Investor Relations</option>", f"<option>{tw('Investor Relations')}</option>"),
        ("<option>Consultant Application</option>", f"<option>{tw('Consultant Application')}</option>"),
        ("<option>Technical Support</option>", f"<option>{tw('Technical Support')}</option>"),
        ("<option>General Inquiry</option>", f"<option>{tw('General Inquiry')}</option>"),
        ("<option>Press &amp; Media</option>", f"<option>{tw('Press & Media')}</option>"),
        ('<label class="form-label">Message *</label>', f'<label class="form-label">{tw("Message")} *</label>'),
        (
            '<label for="privacy">I agree to the processing of my personal data in accordance with FONTESIN\'s Privacy Policy. *</label>',
            f'<label for="privacy">{tw("I agree to the processing of my personal data in accordance with FONTESIN\'s Privacy Policy.")} *</label>',
        ),
        ('>Send Message</button>', f'>{tw("Send Message")}</button>'),
        ('<h3 style="margin-bottom:20px;">Our Location</h3>', f'<h3 style="margin-bottom:20px;">{tw("Our Location")}</h3>'),
        ('<h3 style="margin-bottom:28px;text-align:center;">Specific Inquiries</h3>', f'<h3 style="margin-bottom:28px;text-align:center;">{tw("Specific Inquiries")}</h3>'),
        ("<h4 class=\"card__title\">Franchise &amp; Partners</h4>", f'<h4 class="card__title">{tw("Franchise & Partners")}</h4>'),
        (
            "Interested in becoming a Master Franchise or regional partner?",
            tw("Interested in becoming a Master Franchise or regional partner?"),
        ),
        ("<h4 class=\"card__title\">Investor Relations</h4>", f'<h4 class="card__title">{tw("Investor Relations")}</h4>'),
        (
            "Looking for investment opportunities or financial information?",
            tw("Looking for investment opportunities or financial information?"),
        ),
        ("<h4 class=\"card__title\">Press &amp; Media</h4>", f'<h4 class="card__title">{tw("Press & Media")}</h4>'),
        ("Media inquiries, press releases, and interview requests.", tw("Media inquiries, press releases, and interview requests.")),
        ("FONTESIN Headquarters · One World Trade Center, New York", tw("FONTESIN Headquarters · One World Trade Center, New York")),
    ]
    for old, new in reps:
        text = text.replace(old, new)
    return text


WRAPPERS = {
    "index.html": wrap_index,
    "upgrade_required.html": wrap_upgrade,
    "_world_map.html": wrap_world_map_partial,
    "contact.html": wrap_contact,
}


def main() -> None:
    for name, fn in WRAPPERS.items():
        path = WEBSITE / name
        original = path.read_text(encoding="utf-8")
        path.write_text(fn(original), encoding="utf-8")
        print(f"wrapped {name}")


if __name__ == "__main__":
    main()
