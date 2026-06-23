#!/usr/bin/env python3
"""Apply Phase 5 i18n wrapping to large company templates (HTML labels)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CTX = "companies"
COMMON = "common"

# (pattern, replacement) — pattern is raw HTML text to wrap once
HTML_REPLACEMENTS = [
    ('{% extends "base/base.html" %}\n{% block title %}Companies{% endblock %}',
     '{% extends "base/base.html" %}\n{% load i18n %}\n{% block title %}{% trans "Companies" context "companies" %}{% endblock %}'),
    ('<h3 class="font-weight-bold mb-0" style="margin:0; padding:0; font-size:1.1rem; flex:0 0 auto;">\n        Companies\n      </h3>',
     '<h3 class="font-weight-bold mb-0" style="margin:0; padding:0; font-size:1.1rem; flex:0 0 auto;">\n        {% trans "Companies" context "companies" %}\n      </h3>'),
    ('placeholder="Search companies…"', 'placeholder="{% trans "Search companies…" context "companies" %}"'),
    ('title="Clear search"', 'title="{% trans "Clear search" context "common" %}"'),
    ('<span class="searchable-select__label">All Tenants</span>',
     '<span class="searchable-select__label">{% trans "All Tenants" context "companies" %}</span>'),
    ('placeholder="Search tenants…"', 'placeholder="{% trans "Search tenants…" context "companies" %}"'),
    ('role="option">All Tenants</div>',
     'role="option">{% trans "All Tenants" context "companies" %}</div>'),
    ('No matches.', '{% trans "No matches." context "common" %}'),
    ('<i class="fas fa-file-csv mr-1"></i> Import CSV',
     '<i class="fas fa-file-csv mr-1"></i> {% trans "Import CSV" context "companies" %}'),
    ('<i class="fas fa-plus mr-1"></i> Add Company',
     '<i class="fas fa-plus mr-1"></i> {% trans "Add Company" context "companies" %}'),
    ('<label class="small">Country <span class="text-danger">*</span></label>',
     '<label class="small">{% trans "Country" context "companies" %} <span class="text-danger">*</span></label>'),
    ('<option value="">-- Select country --</option>',
     '<option value="">{% trans "-- Select country --" context "companies" %}</option>'),
    ('label="── Primary markets ──"', 'label="{% trans "── Primary markets ──" context "companies" %}"'),
    ('label="── Other countries ──"', 'label="{% trans "── Other countries ──" context "companies" %}"'),
    ('<label class="small">State / Region</label>',
     '<label class="small">{% trans "State / Region" context "companies" %}</label>'),
    ('placeholder="e.g. Tex…"', 'placeholder="{% trans "e.g. Tex…" context "companies" %}"'),
    ('<label class="small">City</label>', '<label class="small">{% trans "City" context "companies" %}</label>'),
    ('placeholder="e.g. San Fr…"', 'placeholder="{% trans "e.g. San Fr…" context "companies" %}"'),
    ('<label class="small">Company Name</label>',
     '<label class="small">{% trans "Company Name" context "companies" %}</label>'),
    ('placeholder="e.g. Euro…"', 'placeholder="{% trans "e.g. Euro…" context "companies" %}"'),
    ('<label class="small">Company Type (Legal Form)</label>',
     '<label class="small">{% trans "Company Type (Legal Form)" context "companies" %}</label>'),
    ('<option value="">Any</option>', '<option value="">{% trans "Any" context "common" %}</option>'),
    ('Pick a country to see legal forms.', '{% trans "Pick a country to see legal forms." context "companies" %}'),
    ('<label class="small">Field of Activity</label>',
     '<label class="small">{% trans "Field of Activity" context "companies" %}</label>'),
    ('<label class="small">Industry Code (NACE / NAICS)</label>',
     '<label class="small">{% trans "Industry Code (NACE / NAICS)" context "companies" %}</label>'),
    ('placeholder="e.g. J62, 541511, software"',
     'placeholder="{% trans "e.g. J62, 541511, software" context "companies" %}"'),
    ('Matches code prefix or activity keyword on either system.',
     '{% trans "Matches code prefix or activity keyword on either system." context "companies" %}'),
    ('<label class="small">Keywords</label>', '<label class="small">{% trans "Keywords" context "companies" %}</label>'),
    ('placeholder="words to match"', 'placeholder="{% trans "words to match" context "companies" %}"'),
    ('Matches name, website &amp; registration ID.',
     '{% trans "Matches name, website & registration ID." context "companies" %}'),
    ('<i class="fas fa-filter mr-1"></i> Apply', '<i class="fas fa-filter mr-1"></i> {% trans "Apply" context "common" %}'),
    ('class="btn btn-sm btn-outline-secondary">Clear</a>',
     'class="btn btn-sm btn-outline-secondary">{% trans "Clear" context "common" %}</a>'),
    ('<i class="far fa-star mr-1"></i> Save', '<i class="far fa-star mr-1"></i> {% trans "Save" context "common" %}'),
    ('<th>Company Name</th>', '<th>{% trans "Company Name" context "companies" %}</th>'),
    ('<th>Tenant</th>', '<th>{% trans "Tenant" context "companies" %}</th>'),
    ('<th>Industry</th>', '<th>{% trans "Industry" context "companies" %}</th>'),
    ('<th>Location</th>', '<th>{% trans "Location" context "companies" %}</th>'),
    ('<th>Status</th>', '<th>{% trans "Status" context "companies" %}</th>'),
    ('<th class="text-right pr-4">Action</th>',
     '<th class="text-right pr-4">{% trans "Action" context "common" %}</th>'),
    ('<h5 class="modal-title font-weight-bold mb-0">Company</h5>',
     '<h5 class="modal-title font-weight-bold mb-0">{% trans "Company" context "companies" %}</h5>'),
    ('Certified by <strong id="company-certified-by-name"></strong>',
     '{% trans "Certified by" context "companies" %} <strong id="company-certified-by-name"></strong>'),
    ('<div class="section-title">Basic Info</div>',
     '<div class="section-title">{% trans "Basic Info" context "companies" %}</div>'),
    ('<label>Company Name <span class="text-danger">*</span></label>',
     '<label>{% trans "Company Name" context "companies" %} <span class="text-danger">*</span></label>'),
    ('<label>Legal Form <span class="text-danger">*</span></label>',
     '<label>{% trans "Legal Form" context "companies" %} <span class="text-danger">*</span></label>'),
    ('<label>Registration Number / Company ID</label>',
     '<label>{% trans "Registration Number / Company ID" context "companies" %}</label>'),
    ('<label>Year of Establishment</label>',
     '<label>{% trans "Year of Establishment" context "companies" %}</label>'),
    ('<label>Number of Employees</label>',
     '<label>{% trans "Number of Employees" context "companies" %}</label>'),
    ('<div class="section-title">Address</div>',
     '<div class="section-title">{% trans "Address" context "companies" %}</div>'),
    ('<label>Country <span class="text-danger">*</span></label>',
     '<label>{% trans "Country" context "companies" %} <span class="text-danger">*</span></label>'),
    ('<label>State</label>', '<label>{% trans "State" context "companies" %}</label>'),
    ('<label>Region</label>', '<label>{% trans "Region" context "companies" %}</label>'),
    ('<label>City / Municipality <span class="text-danger">*</span></label>',
     '<label>{% trans "City / Municipality" context "companies" %} <span class="text-danger">*</span></label>'),
    ('<label>District</label>', '<label>{% trans "District" context "companies" %}</label>'),
    ('<label>Postal Code</label>', '<label>{% trans "Postal Code" context "companies" %}</label>'),
    ('<label>Street</label>', '<label>{% trans "Street" context "companies" %}</label>'),
    ('<label>House Number</label>', '<label>{% trans "House Number" context "companies" %}</label>'),
    ('<div class="section-title">Business Activity</div>',
     '<div class="section-title">{% trans "Business Activity" context "companies" %}</div>'),
    ('<label>Primary Line of Business <span class="text-danger">*</span></label>',
     '<label>{% trans "Primary Line of Business" context "companies" %} <span class="text-danger">*</span></label>'),
    ('<label for="nace-picker-search">NACE Code <small class="text-muted">(EU classification)</small></label>',
     '<label for="nace-picker-search">{% trans "NACE Code" context "companies" %} <small class="text-muted">{% trans "(EU classification)" context "companies" %}</small></label>'),
    ('placeholder="Start typing a code or activity, e.g. J62 or \'software\'"',
     'placeholder="{% trans "Start typing a code or activity, e.g. J62 or software" context "companies" %}"'),
    ('aria-label="Clear NACE code"', 'aria-label="{% trans "Clear NACE code" context "companies" %}"'),
    ('title="Clear"', 'title="{% trans "Clear" context "common" %}"'),
    ('<label for="naics-picker-search">NAICS Code <small class="text-muted">(US, optional)</small></label>',
     '<label for="naics-picker-search">{% trans "NAICS Code" context "companies" %} <small class="text-muted">{% trans "(US, optional)" context "companies" %}</small></label>'),
    ('placeholder="Start typing a code or activity, e.g. 541511"',
     'placeholder="{% trans "Start typing a code or activity, e.g. 541511" context "companies" %}"'),
    ('aria-label="Clear NAICS code"', 'aria-label="{% trans "Clear NAICS code" context "companies" %}"'),
    ('Words other users will type to find this company.',
     '{% trans "Words other users will type to find this company." context "companies" %}'),
    ('<div class="section-title">Contact Person</div>',
     '<div class="section-title">{% trans "Contact Person" context "companies" %}</div>'),
    ('<label>First Name</label>', '<label>{% trans "First Name" context "companies" %}</label>'),
    ('<label>Last Name</label>', '<label>{% trans "Last Name" context "companies" %}</label>'),
    ('Maintained by the certifying consultant.',
     '{% trans "Maintained by the certifying consultant." context "companies" %}'),
    ('<label>Contact Email <span class="text-danger">*</span></label>',
     '<label>{% trans "Contact Email" context "companies" %} <span class="text-danger">*</span></label>'),
    ('<label>Phone</label>', '<label>{% trans "Phone" context "companies" %}</label>'),
    ('<div class="section-title">Certifying Consultant</div>',
     '<div class="section-title">{% trans "Certifying Consultant" context "companies" %}</div>'),
    ('A consultant will be assigned when your certification request is reviewed.',
     '{% trans "A consultant will be assigned when your certification request is reviewed." context "companies" %}'),
    ('Their name and contact details will appear here automatically and are',
     '{% trans "Their name and contact details will appear here automatically and are" context "companies" %}'),
    ('maintained by them &mdash; not editable from your account.',
     '{% trans "maintained by them — not editable from your account." context "companies" %}'),
    ('<label>Name</label>', '<label>{% trans "Name" context "companies" %}</label>'),
    ('placeholder="Not yet assigned"', 'placeholder="{% trans "Not yet assigned" context "companies" %}"'),
    ('<label>Email</label>', '<label>{% trans "Email" context "companies" %}</label>'),
    ('<label>Website</label>', '<label>{% trans "Website" context "companies" %}</label>'),
    ('<div class="section-title">Branding</div>',
     '<div class="section-title">{% trans "Branding" context "companies" %}</div>'),
    ('<label>Company Logo</label>', '<label>{% trans "Company Logo" context "companies" %}</label>'),
    ('PNG, JPG, SVG, WEBP or GIF (max 5 MB). Shown in the company overview.',
     '{% trans "PNG, JPG, SVG, WEBP or GIF (max 5 MB). Shown in the company overview." context "companies" %}'),
    ('<i class="fas fa-plus mr-1"></i> Create Company',
     '<i class="fas fa-plus mr-1"></i> {% trans "Create Company" context "companies" %}'),
    ('<i class="fas fa-certificate mr-1"></i> Request Certification',
     '<i class="fas fa-certificate mr-1"></i> {% trans "Request Certification" context "companies" %}'),
    ('<label>Tenant <span class="text-danger">*</span></label>',
     '<label>{% trans "Tenant" context "companies" %} <span class="text-danger">*</span></label>'),
]

MODAL_REPLACEMENTS = [
    ('{% comment %}\n  Reusable "Add Company" modal',
     '{% load i18n %}\n{% comment %}\n  Reusable "Add Company" modal'),
] + [r for r in HTML_REPLACEMENTS if 'extends' not in r[0]]

IMPORT_REPLACEMENTS = [
    ('{% comment %}\nBulk CSV import modal',
     '{% load i18n %}\n{% comment %}\nBulk CSV import modal'),
    ('<h5 class="modal-title font-weight-bold mb-0">Bulk Import Companies</h5>',
     '<h5 class="modal-title font-weight-bold mb-0">{% trans "Bulk Import Companies" context "companies.import" %}</h5>'),
    ('aria-label="Close"', 'aria-label="{% trans "Close" context "common" %}"'),
    ('<a href="{% url \'company-import-sample\' %}" download>Download sample CSV</a>',
     '<a href="{% url \'company-import-sample\' %}" download>{% trans "Download sample CSV" context "companies.import" %}</a>'),
    ('Not sure of the format?', '{% trans "Not sure of the format?" context "companies.import" %}'),
    ('<label for="import-tenant" class="small font-weight-bold">Target tenant</label>',
     '<label for="import-tenant" class="small font-weight-bold">{% trans "Target tenant" context "companies.import" %}</label>'),
    ('<option value="">Choose a tenant…</option>',
     '<option value="">{% trans "Choose a tenant…" context "companies.import" %}</option>'),
    ('Every company in the CSV will be created under this tenant.',
     '{% trans "Every company in the CSV will be created under this tenant." context "companies.import" %}'),
    ('<label for="import-csv-file" class="small font-weight-bold">CSV file</label>',
     '<label for="import-csv-file" class="small font-weight-bold">{% trans "CSV file" context "companies.import" %}</label>'),
    ('Large uploads (≥1 GB) may take several minutes. Don\'t close this tab until the upload finishes.',
     '{% trans "Large uploads (≥1 GB) may take several minutes. Don\'t close this tab until the upload finishes." context "companies.import" %}'),
    ('<strong>Importing:</strong>', '<strong>{% trans "Importing:" context "companies.import" %}</strong>'),
    ('<strong>Total:</strong>', '<strong>{% trans "Total:" context "companies.import" %}</strong>'),
    ('<strong>Processed:</strong>', '<strong>{% trans "Processed:" context "companies.import" %}</strong>'),
    ('<strong>Inserted:</strong>', '<strong>{% trans "Inserted:" context "companies.import" %}</strong>'),
    ('<strong>Skipped:</strong>', '<strong>{% trans "Skipped:" context "companies.import" %}</strong>'),
    ('<strong>Failed:</strong>', '<strong>{% trans "Failed:" context "companies.import" %}</strong>'),
    ('You can safely close this window — the import will keep running on the server.',
     '{% trans "You can safely close this window — the import will keep running on the server." context "companies.import" %}'),
    ('Download error report', '{% trans "Download error report" context "companies.import" %}'),
    ('data-dismiss="modal" data-bs-dismiss="modal">Close</button>',
     'data-dismiss="modal" data-bs-dismiss="modal">{% trans "Close" context "common" %}</button>'),
    ('id="import-submit-btn">Upload &amp; Import</button>',
     'id="import-submit-btn">{% trans "Upload & Import" context "companies.import" %}</button>'),
]


def apply_replacements(path: Path, replacements: list[tuple[str, str]]) -> int:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        if old not in text:
            continue
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
    return sum(1 for o, n in replacements if o in original)


def inject_js_i18n_block(path: Path, marker: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if "COMPANY_I18N" in text:
        return
    idx = text.find(marker)
    if idx == -1:
        return
    text = text[:idx] + block + "\n" + text[idx:]
    path.write_text(text, encoding="utf-8")


COMPANIES_JS_I18N = '''<script>
(function () {
  window.COMPANY_I18N = {
    selectState: '{% filter escapejs %}{% trans "Select State" context "companies" %}{% endfilter %}',
    addCompany: '{% filter escapejs %}{% trans "Add Company" context "companies" %}{% endfilter %}',
    createCompany: '{% filter escapejs %}{% trans "Create Company" context "companies" %}{% endfilter %}',
    requestCertification: '{% filter escapejs %}{% trans "Request Certification" context "companies" %}{% endfilter %}',
    companyDetails: '{% filter escapejs %}{% trans "Company Details" context "companies" %}{% endfilter %}',
    editCompany: '{% filter escapejs %}{% trans "Edit Company" context "companies" %}{% endfilter %}',
    save: '{% filter escapejs %}{% trans "Save" context "common" %}{% endfilter %}',
    certifiedBy: '{% filter escapejs %}{% trans "Certified by" context "companies" %}{% endfilter %}',
    on: '{% filter escapejs %}{% trans "on" context "common" %}{% endfilter %}',
    basicInfo: '{% filter escapejs %}{% trans "Basic Info" context "companies" %}{% endfilter %}',
    address: '{% filter escapejs %}{% trans "Address" context "companies" %}{% endfilter %}',
    contact: '{% filter escapejs %}{% trans "Contact" context "companies" %}{% endfilter %}',
    certifyingConsultant: '{% filter escapejs %}{% trans "Certifying Consultant" context "companies" %}{% endfilter %}',
    status: '{% filter escapejs %}{% trans "Status" context "companies" %}{% endfilter %}',
    legalForm: '{% filter escapejs %}{% trans "Legal Form" context "companies" %}{% endfilter %}',
    registrationNo: '{% filter escapejs %}{% trans "Registration No." context "companies" %}{% endfilter %}',
    yearOfEstablishment: '{% filter escapejs %}{% trans "Year of Establishment" context "companies" %}{% endfilter %}',
    numberOfEmployees: '{% filter escapejs %}{% trans "Number of Employees" context "companies" %}{% endfilter %}',
    naceCode: '{% filter escapejs %}{% trans "NACE Code" context "companies" %}{% endfilter %}',
    naicsCode: '{% filter escapejs %}{% trans "NAICS Code" context "companies" %}{% endfilter %}',
    keywords: '{% filter escapejs %}{% trans "Keywords" context "companies" %}{% endfilter %}',
    houseNumber: '{% filter escapejs %}{% trans "House Number" context "companies" %}{% endfilter %}',
    district: '{% filter escapejs %}{% trans "District" context "companies" %}{% endfilter %}',
    region: '{% filter escapejs %}{% trans "Region" context "companies" %}{% endfilter %}',
    cityState: '{% filter escapejs %}{% trans "City / State" context "companies" %}{% endfilter %}',
    postalCode: '{% filter escapejs %}{% trans "Postal Code" context "companies" %}{% endfilter %}',
    contactPerson: '{% filter escapejs %}{% trans "Contact Person" context "companies" %}{% endfilter %}',
    contactEmail: '{% filter escapejs %}{% trans "Contact Email" context "companies" %}{% endfilter %}',
    phone: '{% filter escapejs %}{% trans "Phone" context "companies" %}{% endfilter %}',
    website: '{% filter escapejs %}{% trans "Website" context "companies" %}{% endfilter %}',
    certification: '{% filter escapejs %}{% trans "Certification" context "companies" %}{% endfilter %}',
    active: '{% filter escapejs %}{% trans "Active" context "companies" %}{% endfilter %}',
    yes: '{% filter escapejs %}{% trans "Yes" context "common" %}{% endfilter %}',
    no: '{% filter escapejs %}{% trans "No" context "common" %}{% endfilter %}',
    any: '{% filter escapejs %}{% trans "Any" context "common" %}{% endfilter %}',
    noPresetCountry: '{% filter escapejs %}{% trans "No preset for this country — showing all legal forms." context "companies" %}{% endfilter %}',
    pickCountryNarrow: '{% filter escapejs %}{% trans "Pick a country to narrow the list, or filter globally." context "companies" %}{% endfilter %}',
    noMatchesFor: '{% filter escapejs %}{% trans "No matches for" context "companies" %}{% endfilter %}',
    startTyping: '{% filter escapejs %}{% trans "Start typing." context "companies" %}{% endfilter %}',
    certSubmitted: '{% filter escapejs %}{% trans "Certification request submitted. A consultant will review your company shortly." context "companies" %}{% endfilter %}',
    couldNotSave: '{% filter escapejs %}{% trans "Could not save company. Please check the form." context "companies" %}{% endfilter %}',
    networkError: '{% filter escapejs %}{% trans "Network error. Please try again." context "common" %}{% endfilter %}',
    companyLogo: '{% filter escapejs %}{% trans "Company" context "companies" %}{% endfilter %}',
    uploadImport: '{% filter escapejs %}{% trans "Upload & Import" context "companies.import" %}{% endfilter %}',
    uploading: '{% filter escapejs %}{% trans "Uploading…" context "companies.import" %}{% endfilter %}',
    chooseTenant: '{% filter escapejs %}{% trans "Please choose a target tenant." context "companies.import" %}{% endfilter %}',
    chooseCsv: '{% filter escapejs %}{% trans "Please choose a CSV file." context "companies.import" %}{% endfilter %}',
    mustBeCsv: '{% filter escapejs %}{% trans "File must be a .csv" context "companies.import" %}{% endfilter %}',
    uploadFailed: '{% filter escapejs %}{% trans "Upload failed" context "companies.import" %}{% endfilter %}',
    importComplete: '{% filter escapejs %}{% trans "Import complete." context "companies.import" %}{% endfilter %}',
    inserted: '{% filter escapejs %}{% trans "Inserted:" context "companies.import" %}{% endfilter %}',
    skippedDuplicates: '{% filter escapejs %}{% trans "Skipped (duplicates):" context "companies.import" %}{% endfilter %}',
    failed: '{% filter escapejs %}{% trans "Failed:" context "companies.import" %}{% endfilter %}',
    importFailed: '{% filter escapejs %}{% trans "Import failed." context "companies.import" %}{% endfilter %}',
    noDetails: '{% filter escapejs %}{% trans "(no details)" context "companies.import" %}{% endfilter %}',
    noResults: '{% filter escapejs %}{% trans "No results" context "companies" %}{% endfilter %}',
  };
  var g = (typeof gettext === "function") ? gettext : function (s) { return s; };
  Object.keys(window.COMPANY_I18N).forEach(function (k) {
    window.COMPANY_I18N[k] = g(window.COMPANY_I18N[k]);
  });
})();
</script>
'''

JS_SUBSTITUTIONS = [
    ("'<option value=\"\">Select State</option>'", "COMPANY_I18N.selectState"),
    ('title.innerText = "Add Company"', "title.innerText = COMPANY_I18N.addCompany"),
    ("saveBtn.innerHTML = '<i class=\"fas fa-plus mr-1\"></i> Create Company'",
     "saveBtn.innerHTML = '<i class=\"fas fa-plus mr-1\"></i> ' + COMPANY_I18N.createCompany"),
    ("saveBtn.innerHTML = '<i class=\"fas fa-certificate mr-1\"></i> Request Certification'",
     "saveBtn.innerHTML = '<i class=\"fas fa-certificate mr-1\"></i> ' + COMPANY_I18N.requestCertification"),
    ('title.innerText = mode === "view" ? "Company Details" : "Edit Company"',
     'title.innerText = mode === "view" ? COMPANY_I18N.companyDetails : COMPANY_I18N.editCompany'),
    ("saveBtn.innerHTML = '<i class=\"fas fa-save mr-1\"></i> Save'",
     "saveBtn.innerHTML = '<i class=\"fas fa-save mr-1\"></i> ' + COMPANY_I18N.save"),
    ('(c.name || "Company") + " logo"', '(c.name || COMPANY_I18N.companyLogo) + " logo"'),
    ('html += heading("Basic Info")', 'html += heading(COMPANY_I18N.basicInfo)'),
    ('html += row("Legal Form", c.entity_type)', 'html += row(COMPANY_I18N.legalForm, c.entity_type)'),
    ('html += row("Registration No.", c.registration_id)', 'html += row(COMPANY_I18N.registrationNo, c.registration_id)'),
    ('html += row("Year of Establishment", c.year_established)', 'html += row(COMPANY_I18N.yearOfEstablishment, c.year_established)'),
    ('html += row("Number of Employees", c.employee_count_range)', 'html += row(COMPANY_I18N.numberOfEmployees, c.employee_count_range)'),
    ('html += row("NACE Code", c.nace_code_display)', 'html += row(COMPANY_I18N.naceCode, c.nace_code_display)'),
    ('html += row("NAICS Code", naicsDisplay)', 'html += row(COMPANY_I18N.naicsCode, naicsDisplay)'),
    ('html += row("Keywords", c.keywords)', 'html += row(COMPANY_I18N.keywords, c.keywords)'),
    ('html += heading("Address")', 'html += heading(COMPANY_I18N.address)'),
    ('html += row("Address", address)', 'html += row(COMPANY_I18N.address, address)'),
    ('html += row("House Number", c.house_number)', 'html += row(COMPANY_I18N.houseNumber, c.house_number)'),
    ('html += row("District", c.district)', 'html += row(COMPANY_I18N.district, c.district)'),
    ('html += row("Region", c.region)', 'html += row(COMPANY_I18N.region, c.region)'),
    ('html += row("City / State", loc)', 'html += row(COMPANY_I18N.cityState, loc)'),
    ('html += row("Postal Code", c.postal_code)', 'html += row(COMPANY_I18N.postalCode, c.postal_code)'),
    ('html += heading("Contact")', 'html += heading(COMPANY_I18N.contact)'),
    ('html += row("Contact Person", contactName)', 'html += row(COMPANY_I18N.contactPerson, contactName)'),
    ('html += row("Contact Email", c.contact_email)', 'html += row(COMPANY_I18N.contactEmail, c.contact_email)'),
    ('html += row("Phone", c.phone)', 'html += row(COMPANY_I18N.phone, c.phone)'),
    ('html += row("Website", c.website)', 'html += row(COMPANY_I18N.website, c.website)'),
    ('html += heading("Certifying Consultant")', 'html += heading(COMPANY_I18N.certifyingConsultant)'),
    ('html += row("Name", c.certifying_consultant.full_name)', 'html += row(COMPANY_I18N.legalForm.replace("Legal Form","Name") || "Name", c.certifying_consultant.full_name)'),
]

# Fix the botched name row - use explicit key
JS_SUBSTITUTIONS = [s for s in JS_SUBSTITUTIONS if 'legalForm.replace' not in s[1]]
JS_SUBSTITUTIONS.append(
    ('html += row("Name", c.certifying_consultant.full_name)',
     'html += row(COMPANY_I18N.contactPerson.split(" ")[0] === COMPANY_I18N.contactPerson ? "Name" : "Name", c.certifying_consultant.full_name)')
)
# Simpler: add name key to I18N block - I'll patch script manually after

def patch_js(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    subs = [
        ("entitySel.innerHTML = '<option value=\"\">Any</option>';",
         "entitySel.innerHTML = '<option value=\"\">' + COMPANY_I18N.any + '</option>';"),
        ("? 'No preset for this country — showing all legal forms.'",
         "? COMPANY_I18N.noPresetCountry"),
        (": 'Pick a country to narrow the list, or filter globally.'",
         ": COMPANY_I18N.pickCountryNarrow"),
        ('(query ? \'No matches for "\' + esc(query) + \'".\' : \'Start typing.\')',
         "(query ? COMPANY_I18N.noMatchesFor + ' \"' + esc(query) + '\".': COMPANY_I18N.startTyping)"),
        ('"Certification request submitted. A consultant will review your company shortly."',
         "COMPANY_I18N.certSubmitted"),
        ('"Could not save company. Please check the form."', "COMPANY_I18N.couldNotSave"),
        ('showToast("Network error. Please try again.", "error")',
         'showToast(COMPANY_I18N.networkError, "error")'),
        ('title.innerText = "Edit Company"', 'title.innerText = COMPANY_I18N.editCompany'),
        ('$("#import-submit-btn").textContent = "Upload & Import"',
         '$("#import-submit-btn").textContent = COMPANY_I18N.uploadImport'),
        ('$("#import-submit-btn").textContent = "Uploading…"',
         '$("#import-submit-btn").textContent = COMPANY_I18N.uploading'),
        ('showError("Please choose a target tenant.")', 'showError(COMPANY_I18N.chooseTenant)'),
        ('showError("Please choose a CSV file.")', 'showError(COMPANY_I18N.chooseCsv)'),
        ('showError("File must be a .csv")', 'showError(COMPANY_I18N.mustBeCsv)'),
        ('let msg = "Upload failed (HTTP " + resp.status + ")"',
         'let msg = COMPANY_I18N.uploadFailed + " (HTTP " + resp.status + ")"'),
        ('.catch((err) => showError(err.message || "Upload failed"))',
         '.catch((err) => showError(err.message || COMPANY_I18N.uploadFailed))'),
        ("'<strong>Import complete.</strong> '",
         "'<strong>' + COMPANY_I18N.importComplete + '</strong> '"),
        ("'<br>Inserted: <strong>'", "'<br>' + COMPANY_I18N.inserted + ' <strong>'"),
        ("' &nbsp; Skipped (duplicates): <strong>'",
         "' &nbsp; ' + COMPANY_I18N.skippedDuplicates + ' <strong>'"),
        ("' &nbsp; Failed: <strong>'", "' &nbsp; ' + COMPANY_I18N.failed + ' <strong>'"),
        ("'<strong>Import failed.</strong> '",
         "'<strong>' + COMPANY_I18N.importFailed + '</strong> '"),
        ('(j.error_message ? j.error_message.replace(/</g, "&lt;") : "(no details)")',
         '(j.error_message ? j.error_message.replace(/</g, "&lt;") : COMPANY_I18N.noDetails)'),
        ('html += heading("Status")', 'html += heading(COMPANY_I18N.status)'),
        ('html += row("Certification", c.certification_status)',
         'html += row(COMPANY_I18N.certification, c.certification_status)'),
        ('html += row("Active", c.is_active ? "Yes" : "No")',
         'html += row(COMPANY_I18N.active, c.is_active ? COMPANY_I18N.yes : COMPANY_I18N.no)'),
        ('html += row("Name", c.certifying_consultant.full_name)',
         'html += row("Name", c.certifying_consultant.full_name)'),  # keep - add name to I18N manually
    ]
    for old, new in subs:
        if old in text and new not in text:
            text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    companies = ROOT / "templates/dashboard/companies.html"
    modal = ROOT / "templates/dashboard/_company_create_modal.html"
    imp = ROOT / "templates/dashboard/_company_import_modal.html"

    n = apply_replacements(companies, HTML_REPLACEMENTS)
    print(f"companies.html: {n} HTML patterns applied")
    n2 = apply_replacements(modal, MODAL_REPLACEMENTS)
    print(f"_company_create_modal.html: {n2} patterns applied")
    n3 = apply_replacements(imp, IMPORT_REPLACEMENTS)
    print(f"_company_import_modal.html: {n3} patterns applied")

    inject_js_i18n_block(companies, "<!-- ================= JS", COMPANIES_JS_I18N)
    inject_js_i18n_block(modal, "<script>\n// --- Country / State", COMPANIES_JS_I18N)
    inject_js_i18n_block(imp, "<script>\n(function () {", COMPANIES_JS_I18N)

    patch_js(companies)
    patch_js(modal)
    patch_js(imp)
    print("JS patches applied")


if __name__ == "__main__":
    main()
