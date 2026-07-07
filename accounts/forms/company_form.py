from django.utils.translation import gettext_lazy as _
import datetime
import re
import uuid

from django import forms
from accounts.models import Company, NaceCode, NaicsCode, Tenant
from accounts.constants import (
    CountryChoices,
    COUNTRY_ENGLISH_NAME_TO_CODE,
    EmployeeCountRangeChoices,
    PHONE_RULES,
    COUNTRY_STATES,
)

COUNTRY_LABELS = dict(CountryChoices.CHOICES)

# General phone/fax shape (length/digits bounds validated separately, per-country for phone).
PHONE_CHARSET_RE = re.compile(r"^[\d+\-\s()]{7,25}$")

# City: letters, spaces, hyphens, apostrophes, and periods (for abbreviations like "St. Louis");
# must start with a letter; 2-60 chars. No digits or other special characters.
CITY_NAME_RE = re.compile(r"^[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F\s'\-.]{1,59}$")

# Company Name: letters (incl. accented), digits, spaces and & ' . , - ( ); must contain at least one letter; 2-100 chars.
COMPANY_NAME_RE = re.compile(r"^(?=.*[A-Za-z\u00C0-\u024F])[A-Za-z\u00C0-\u024F0-9&'.,\-()\s]{2,100}$")

# Registration ID: alphanumerics and - / . _ ; 2-100 chars; at least one alphanumeric.
REGISTRATION_ID_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z0-9\-/._]{2,100}$")

# Canonical English names → ISO codes (never translated CountryChoices labels).
COUNTRY_NAME_TO_CODE = COUNTRY_ENGLISH_NAME_TO_CODE

# Strict website URL:
#   - http/https only
#   - domain with TLD (2+ letters)
#   - optional port
#   - optional path using URL-safe chars only (alphanumerics, - . _ ~ /)
#   - optional query using alphanumerics and - . _ ~ & =
# Rejects characters like $ ( ) + : ! * , ; ' ? # % which allowed Django's default
# URLValidator to accept obvious garbage trailers.
WEBSITE_URL_RE = re.compile(
    r"^https?://"
    r"[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)*"
    r"\.[a-z]{2,}"
    r"(?::\d{1,5})?"
    r"(?:/[A-Za-z0-9\-._~/]*)?"
    r"(?:\?[A-Za-z0-9\-._~&=]*)?"
    r"/?$",
    re.IGNORECASE,
)

# Fax: digits with optional + - ( ) and whitespace; 7-25 chars overall; 5-15 raw digits.
FAX_RE = re.compile(r"^[\d+\-\s()]{7,25}$")

# Address line: letters (incl. accented), digits, spaces and the explicit allowlist , . - / #
# Must contain at least one alphanumeric; 3-120 chars.
# Rejects unusual symbols like ! @ $ % ^ & * ' ( ) { } [ ] < > " ; : ? = + _ |
ADDRESS_LINE_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z\u00C0-\u024F0-9\s,./#\-]{3,120}$")

# Postal code: alphanumerics with optional spaces/hyphens (US/UK/CA/etc.); 3-12 chars.
POSTAL_CODE_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z0-9\s\-]{3,12}$")

# House number: digits with optional letter suffix and / - (e.g. "221B", "12/3", "5-A"); 1-15 chars.
HOUSE_NUMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/ ]{0,14}$")

# Region / District / Keywords: letters, digits, spaces and the symbols , . - / & ' ; 1-120 chars.
REGION_DISTRICT_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-zÀ-ɏ0-9\s,./&'\-]{1,120}$")

# Industry code (NACE / ISIC / NAICS): digits, letters, optional dot — 1-20 chars.
INDUSTRY_CODE_RE = re.compile(r"^[A-Za-z0-9.\-]{1,20}$")

# Allowed logo extensions.
LOGO_ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")
# 5 MB upper bound on logo upload size.
LOGO_MAX_BYTES = 5 * 1024 * 1024


class CompanyForm(forms.ModelForm):

    # Company.country on the model is a plain CharField with no `choices`, so
    # Django auto-generates a forms.CharField (free-text). Declare an explicit
    # ChoiceField here to render the country dropdown and gate validation on
    # the ISO codes we recognize. The widget id matches the JS in
    # companies.html that rebuilds the State dropdown on country change.
    country = forms.ChoiceField(
        required=True,
        choices=[("", _("Select Country"))] + list(CountryChoices.CHOICES),
        widget=forms.Select(attrs={
            "class": "form-control",
            "id": "id_country",
            "autocomplete": "country",
        }),
    )

    # Industry classification — picked via the autocomplete widget in
    # companies.html, which writes the selected NaceCode/NaicsCode UUID
    # into these hidden inputs. ModelChoiceField validates the UUID
    # against the lookup table. Both optional; NACE is the canonical
    # default per the dashboard onboarding flow.
    nace_code = forms.ModelChoiceField(
        queryset=NaceCode.objects.filter(is_active=True),
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_nace_code"}),
    )
    naics_code = forms.ModelChoiceField(
        queryset=NaicsCode.objects.filter(is_active=True),
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_naics_code"}),
    )

    class Meta:
        model = Company
        fields = [
            # ---- Tenant / Identity ----
            "tenant",
            "name",
            "registration_id",
            "classification",
            "entity_type",

            # ---- Address ----
            "address_line1",
            "address_line2",
            "house_number",
            "district",
            "region",
            "city",
            "state",
            "postal_code",
            "country",
            "latitude",
            "longitude",

            # ---- Business attributes ----
            "year_established",
            "nace_code",
            "naics_code",
            "industry_code",
            "keywords",
            "employee_count_range",

            # ---- Contact ----
            "contact_first_name",
            "contact_last_name",
            "phone",
            "phone_secondary",
            "fax",
            "website",
            "contact_email",

            # ---- Branding ----
            "logo",

            # ---- Status ----
            "is_active",
        ]

        widgets = {
            # Identity
            "tenant": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "minlength": "2",
                "maxlength": "100",
                "pattern": r"(?=.*[A-Za-z\u00C0-\u024F])[A-Za-z\u00C0-\u024F0-9&'.,\-()\s]{2,100}",
                "title": "2-100 characters. Letters, digits, spaces, and & ' . , - ( ) only. Must contain at least one letter.",
                "required": True,
            }),
            "registration_id": forms.TextInput(attrs={
                "class": "form-control",
                "minlength": "2",
                "maxlength": "100",
                "pattern": r"(?=.*[A-Za-z0-9])[A-Za-z0-9\-/._]{2,100}",
                "title": "Letters, digits and the symbols - / . _ only (2-100 characters).",
            }),
            "classification": forms.Select(attrs={"class": "form-control"}),
            "entity_type": forms.Select(attrs={"class": "form-control"}),

            # Address
            "address_line1": forms.TextInput(attrs={
                "class": "form-control",
                "minlength": "3",
                "maxlength": "120",
                "pattern": r"(?=.*[A-Za-z0-9])[A-Za-z\u00C0-\u024F0-9\s,./#\-]{3,120}",
                "placeholder": "e.g. Baker Street",
                "title": "3-120 characters. Letters, digits, spaces and the symbols , . - / # only. Other special characters are not allowed.",
                "autocomplete": "address-line1",
            }),
            "house_number": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "15",
                "pattern": r"[A-Za-z0-9][A-Za-z0-9\-/ ]{0,14}",
                "placeholder": "e.g. 221B",
                "title": "Letters, digits and the symbols - / and spaces (1-15 characters).",
            }),
            "district": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "120",
                "placeholder": "e.g. Westminster",
            }),
            "region": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "120",
                "placeholder": "e.g. Greater London",
            }),
            "address_line2": forms.TextInput(attrs={
                "class": "form-control",
                "minlength": "3",
                "maxlength": "120",
                "pattern": r"(?=.*[A-Za-z0-9])[A-Za-z\u00C0-\u024F0-9\s,./#\-]{3,120}",
                "placeholder": "Apt, suite, unit (optional)",
                "title": "3-120 characters. Letters, digits, spaces and the symbols , . - / # only. Other special characters are not allowed.",
                "autocomplete": "address-line2",
            }),
            "city": forms.TextInput(attrs={
                "class": "form-control",
                "id": "id_city",
                "minlength": "2",
                "maxlength": "60",
                "pattern": r"[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F\s'\-.]{1,59}",
                "placeholder": "e.g. New York",
                "title": "City must be 2-60 letters (letters, spaces, hyphens, apostrophes and periods only). Numbers and special characters are not allowed.",
                "autocomplete": "address-level2",
            }),
            "state": forms.Select(attrs={
                "class": "form-control",
                "id": "id_state",
                "autocomplete": "address-level1",
            }),
            "postal_code": forms.TextInput(attrs={
                "class": "form-control",
                "minlength": "3",
                "maxlength": "12",
                "pattern": r"(?=.*[A-Za-z0-9])[A-Za-z0-9\s\-]{3,12}",
                "placeholder": "e.g. 10001 or SW1A 1AA",
                "title": "3-12 characters. Letters, digits, spaces and hyphens only. Must contain at least one letter or digit.",
                "autocomplete": "postal-code",
            }),
            "latitude": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.00000001"}
            ),
            "longitude": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.00000001"}
            ),

            # Contact
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "id": "id_phone",
                "maxlength": "25",
                "pattern": r"[\d+\-\s()]{7,25}",
                "placeholder": "+1 212 555 0100",
                "title": "Digits and + - ( ) spaces only. Length is validated against the selected country.",
                "inputmode": "tel",
                "data-phone-validate": "1",
            }),
            "phone_secondary": forms.TextInput(attrs={
                "class": "form-control",
                "id": "id_phone_secondary",
                "maxlength": "25",
                "pattern": r"[\d+\-\s()]{7,25}",
                "placeholder": "+1 212 555 0100",
                "title": "Digits and + - ( ) spaces only. Length is validated against the selected country.",
                "inputmode": "tel",
                "data-phone-validate": "1",
            }),
            "fax": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "25",
                "pattern": r"[\d+\-\s()]{7,25}",
                "placeholder": "+1 212 555 0199",
                "title": "Fax may only contain digits and the symbols + - ( ) and spaces (7-25 characters).",
                "inputmode": "tel",
            }),
            "website": forms.URLInput(attrs={
                "class": "form-control",
                "maxlength": "500",
                "placeholder": "https://example.com",
                "title": "Enter a valid URL like https://example.com (letters, digits, and . - _ / only in the path).",
            }),
            "contact_email": forms.EmailInput(attrs={
                "class": "form-control",
                "maxlength": "254",
                "placeholder": "contact@example.com",
                "autocomplete": "email",
            }),
            "contact_first_name": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "80",
                "placeholder": "First name",
                "autocomplete": "given-name",
            }),
            "contact_last_name": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "80",
                "placeholder": "Last name",
                "autocomplete": "family-name",
            }),

            # Business attributes
            "year_established": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1500",
                # `max` is enforced server-side against current year; render as
                # a generous upper bound so the browser widget stays usable on
                # New Year's Eve without a deploy.
                "max": str(datetime.date.today().year),
                "step": "1",
                "placeholder": "e.g. 2014",
            }),
            "industry_code": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "20",
                "pattern": r"[A-Za-z0-9.\-]{1,20}",
                "placeholder": "NACE / ISIC code",
                "title": "1-20 characters. Letters, digits, dots and hyphens only.",
            }),
            "keywords": forms.TextInput(attrs={
                "class": "form-control",
                "maxlength": "500",
                "placeholder": "comma-separated search keywords",
            }),
            "employee_count_range": forms.Select(attrs={"class": "form-control"}),

            # Branding
            "logo": forms.ClearableFileInput(attrs={
                "class": "form-control-file",
                "accept": ",".join(LOGO_ALLOWED_EXTENSIONS),
            }),

            # Status
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Replace Django's default "---------" placeholder with a clearer prompt.
        self.fields["tenant"].empty_label = "Select Tenant"

        # NACE/NAICS picker forgiveness: the JS picker writes a UUID into
        # the hidden input on selection, but a user who just types a code
        # like "J62" or "541511" and hits Save (without clicking a
        # dropdown row) would otherwise submit an empty FK. Resolve any
        # non-UUID value as a code lookup here, BEFORE ModelChoiceField
        # validates the field (which requires a valid UUID). Anything
        # that's neither a UUID nor a known code is passed through and
        # the field's own validator surfaces a clear error.
        if self.data:
            try:
                data = self.data.copy()  # QueryDict from request.POST → mutable
            except AttributeError:
                data = dict(self.data)
            for field_name, model in (("nace_code", NaceCode), ("naics_code", NaicsCode)):
                raw = (data.get(field_name) or "").strip()
                if not raw:
                    continue
                try:
                    uuid.UUID(raw)
                    continue  # already a UUID, leave alone
                except (ValueError, AttributeError, TypeError):
                    pass
                match = model.objects.filter(code__iexact=raw, is_active=True).first()
                if match is not None:
                    data[field_name] = str(match.id)
            self.data = data

        # Address fields and classification are blank=True on the model (so
        # the DB column is nullable), but the admin Add/Edit Company UI
        # treats them as required. Force them required at the form layer;
        # the model column stays nullable so legacy / API-only writes can
        # still leave them empty.
        for required_field in ("city", "state", "country", "classification"):
            self.fields[required_field].required = True

        # Drop the implicit "---------" blank option from classification so
        # the dropdown can't be submitted unselected.
        self.fields["classification"].choices = [
            choice for choice in self.fields["classification"].choices if choice[0]
        ]

        if not user:
            return

        # Business Users may not edit the contact-person fields (First Name,
        # Last Name, Contact Email) on companies they DON'T own — at that
        # point those fields belong to the company's certifying consultant
        # / owner. The BU's OWN company stays editable so they can keep
        # their own contact info up to date.
        #
        # Contact fields are also editable on the Add Company form (no saved
        # instance yet) so the BU can give an initial contact when filing
        # the request; once saved + handed off to a consultant, only the
        # owner BU and the consultant can change it. tenant_id is the
        # reliable "already saved" signal because Company.id defaults to
        # uuid4 even for unsaved instances.
        #
        # Because `disabled = True` is enforced server-side (Django ignores
        # submitted values for disabled fields and keeps the initial value),
        # a hand-crafted POST from a non-owner BU can't slip contact-field
        # changes past us either.
        role_code = (user.role.code or "").lower() if getattr(user, "role", None) else ""
        instance_is_saved = bool(self.instance and self.instance.tenant_id)
        is_business_user = not user.is_superuser and role_code == "business_user"
        is_owner = bool(
            self.instance
            and getattr(self.instance, "owner_user_id", None) == user.id
        )
        if is_business_user and instance_is_saved and not is_owner:
            for fld in ("contact_first_name", "contact_last_name", "contact_email"):
                if fld in self.fields:
                    self.fields[fld].disabled = True
                    self.fields[fld].widget.attrs["readonly"] = "readonly"
                    self.fields[fld].widget.attrs["title"] = (
                        "Only the company owner or the certifying consultant "
                        "can edit these fields."
                    )

        if user.is_superuser:
            # Superuser can select any tenant
            self.fields["tenant"].queryset = Tenant.objects.all()

        else:
            # Non-superusers see a hidden tenant field. The queryset is
            # normally locked to the user's own tenant, but when editing an
            # existing company that was linked cross-tenant (registration
            # lets users pick companies from any tenant), we must also
            # include the instance's current tenant — otherwise the hidden
            # field posts a value that isn't in the queryset and Django
            # raises "Select a valid choice" on save.
            tenant_ids = {user.tenant_id} if user.tenant_id else set()
            if self.instance and self.instance.pk and self.instance.tenant_id:
                tenant_ids.add(self.instance.tenant_id)

            self.fields["tenant"].queryset = Tenant.objects.filter(
                id__in=tenant_ids
            )
            # Company.id has default=uuid.uuid4, so `self.instance.pk` is truthy
            # even for unsaved instances. Use tenant_id as the real "existing row"
            # signal — it's only populated once the company has been saved.
            self.fields["tenant"].initial = (
                self.instance.tenant if self.instance and self.instance.tenant_id else user.tenant
            )
            self.fields["tenant"].widget = forms.HiddenInput()
            # The view assigns the tenant for non-superusers (request.user.tenant,
            # with a default-tenant fallback), so the form shouldn't block when
            # the hidden field is empty — e.g. a consultant who has no tenant
            # assigned. Without this, "Add Company" failed with the unhelpful
            # "Tenant: This field is required." for tenant-less users.
            self.fields["tenant"].required = False

    def clean_name(self):
        # Collapse runs of whitespace ("Acme  Corp" -> "Acme Corp") so the
        # uniqueness check below can't be slipped past with extra spaces.
        name = re.sub(r"\s+", " ", (self.cleaned_data.get("name") or "").strip())
        if not name:
            raise forms.ValidationError(_("Company name is required and cannot be only spaces."))
        if len(name) < 2:
            raise forms.ValidationError(_("Company name must be at least 2 characters."))
        if len(name) > 100:
            raise forms.ValidationError(_("Company name must be 100 characters or fewer."))
        if not COMPANY_NAME_RE.match(name):
            raise forms.ValidationError(
                _("Company name may only contain letters, digits, spaces, and the symbols & ' . , - ( ), and must contain at least one letter.")
            )

        # Strict global same-name guard: applies to both create and edit.
        # On edit, exclude the current row so saving without renaming works.
        # tenant_id is the reliable "already saved" signal here — Company.id
        # has a uuid4 default, so .pk is truthy even on unsaved instances.
        duplicates = Company.objects.filter(name__iexact=name)
        if self.instance and self.instance.tenant_id:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(
                _("A company with this name already exists. Please choose a different name.")
            )
        return name

    def clean_registration_id(self):
        reg = (self.cleaned_data.get("registration_id") or "").strip()
        if not reg:
            # Optional field: whitespace-only collapses to empty and is allowed.
            return ""
        if len(reg) < 2:
            raise forms.ValidationError(_("Registration ID must be at least 2 characters."))
        if len(reg) > 100:
            raise forms.ValidationError(_("Registration ID must be 100 characters or fewer."))
        if not REGISTRATION_ID_RE.match(reg):
            raise forms.ValidationError(
                _("Registration ID may only contain letters, digits, and the symbols - / . _ , and must contain at least one letter or digit.")
            )

        # Globally unique (case-insensitive). Registration IDs are real-world
        # legal identifiers and must not repeat across tenants. Soft-deleted
        # companies are excluded via ActiveManager so a re-registration of a
        # previously deleted company can reuse its number. tenant_id is the
        # reliable "already saved" signal here — Company.id has a uuid4
        # default, so .pk is truthy even on unsaved instances.
        duplicates = Company.objects.filter(registration_id__iexact=reg)
        if self.instance and self.instance.tenant_id:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(
                _("A company with this Registration ID already exists. Registration IDs must be unique.")
            )
        return reg

    def clean(self):
        # Soft duplicate check on (name, country). Catches the most common
        # collision — same legal-language name registered twice in the same
        # country — before submitting to the DB. Different countries are
        # allowed (e.g. "Apple Inc." in US vs UK are distinct entities), and
        # the registration_id constraint is the hard backstop for legal
        # identity. Case-insensitive on both fields. Skips the check on
        # update (only flags new rows that conflict with someone else).
        cleaned = super().clean()
        name = (cleaned.get("name") or "").strip()
        country = (cleaned.get("country") or "").strip()
        state = (cleaned.get("state") or "").strip()

        # Country/state pairing — the State dropdown is populated client-side
        # from COUNTRY_STATES[country], so any value outside that list is a
        # tampered request or stale data, not a typo.
        if country:
            valid_states = COUNTRY_STATES.get(country, [])
            if not state:
                self.add_error("state", forms.ValidationError(_("State is required.")))
            elif valid_states and state not in valid_states:
                self.add_error(
                    "state",
                    forms.ValidationError(_("Please select a valid state for the chosen country.")),
                )
        elif state:
            self.add_error("country", forms.ValidationError(_("Country is required.")))

        if name and country:
            country_label = COUNTRY_LABELS.get(country, country)
            qs = Company.objects.filter(name__iexact=name, country__iexact=country)
            if self.instance and self.instance.tenant_id:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    "name",
                    forms.ValidationError(
                        _("A company named '%(name)s' already exists in %(country)s. "
                          "If this is a different legal entity, please provide a Registration ID to distinguish it.")
                        % {"name": name, "country": country_label}
                    ),
                )
        return cleaned

    def _clean_address_line(self, field_name, label):
        value = (self.cleaned_data.get(field_name) or "").strip()
        if not value:
            return value
        if len(value) < 3:
            raise forms.ValidationError(_("%(label)s must be at least 3 characters.") % {"label": label})
        if len(value) > 120:
            raise forms.ValidationError(_("%(label)s must be 120 characters or fewer.") % {"label": label})
        if not ADDRESS_LINE_RE.match(value):
            raise forms.ValidationError(
                _("%(label)s may only contain letters, digits, spaces and the symbols , . - / #. "
                  "Other special characters (such as ! @ $ %% ^ * {{ }} [ ] < >) are not allowed.")
                % {"label": label}
            )
        return value

    def clean_address_line1(self):
        return self._clean_address_line("address_line1", _("Address Line 1"))

    def clean_address_line2(self):
        return self._clean_address_line("address_line2", _("Address Line 2"))

    def clean_postal_code(self):
        postal = (self.cleaned_data.get("postal_code") or "").strip()
        if not postal:
            return postal
        if len(postal) < 3:
            raise forms.ValidationError(_("Postal code must be at least 3 characters."))
        if len(postal) > 12:
            raise forms.ValidationError(_("Postal code must be 12 characters or fewer."))
        if not POSTAL_CODE_RE.match(postal):
            raise forms.ValidationError(
                _("Postal code may only contain letters, digits, spaces and hyphens, and must contain at least one letter or digit.")
            )
        return postal

    def clean_city(self):
        city = (self.cleaned_data.get("city") or "").strip()
        if not city:
            return city
        if len(city) < 2:
            raise forms.ValidationError(_("City must be at least 2 characters."))
        if len(city) > 60:
            raise forms.ValidationError(_("City must be 60 characters or fewer."))
        if not CITY_NAME_RE.match(city):
            raise forms.ValidationError(
                _("City may only contain letters, spaces, hyphens, apostrophes and periods. Numbers and special characters are not allowed.")
            )
        return city

    def clean_state(self):
        # State is a free-text CharField on the model; we constrain it to one
        # of COUNTRY_STATES[country] in clean() once the country is also
        # available. Just normalize whitespace here.
        return (self.cleaned_data.get("state") or "").strip()

    def clean_country(self):
        # Country is a model ChoiceField (CountryChoices), so Django's built-in
        # TypedChoiceField validation already rejects values outside the list.
        # Just normalize and uppercase the ISO code so downstream lookups work.
        country = (self.cleaned_data.get("country") or "").strip()
        return country.upper() if country else country

    def _clean_phone_field(self, field_name, label):
        value = (self.cleaned_data.get(field_name) or "").strip()
        if not value:
            return value
        if not PHONE_CHARSET_RE.match(value):
            raise forms.ValidationError(
                _("%(label)s may only contain digits and the symbols + - ( ) and spaces (7-25 characters).")
                % {"label": label}
            )

        digits = re.sub(r"\D", "", value)
        # If the caller prepended a country code (e.g. +91 98xxxxxxxx), strip the trailing
        # country-code prefix so we compare the subscriber number against PHONE_RULES.
        raw_country = (self.cleaned_data.get("country") or "").strip()
        # Country may be an ISO code ("IN") or a free-text name ("India") — resolve either.
        country_code = raw_country.upper() if len(raw_country) == 2 else COUNTRY_NAME_TO_CODE.get(raw_country.lower(), "")
        rule = PHONE_RULES.get(country_code)

        if rule:
            min_len, max_len = rule
            # Allow up to 4 leading country-code digits when the value starts with '+'.
            candidates = [digits]
            if value.lstrip().startswith("+"):
                for cc_len in (1, 2, 3, 4):
                    if len(digits) > cc_len:
                        candidates.append(digits[cc_len:])
            if not any(min_len <= len(c) <= max_len for c in candidates):
                raise forms.ValidationError(
                    _("%(label)s must be %(min)s-%(max)s digits for the selected country.")
                    % {"label": label, "min": min_len, "max": max_len}
                )
        else:
            # No country selected or unknown: fall back to a generic 5-15 digit bound.
            if not (5 <= len(digits) <= 15):
                raise forms.ValidationError(
                    _("%(label)s must contain 5-15 digits.") % {"label": label}
                )
        return value

    def clean_phone(self):
        return self._clean_phone_field("phone", _("Phone"))

    def clean_phone_secondary(self):
        return self._clean_phone_field("phone_secondary", _("Secondary phone"))

    def clean_fax(self):
        fax = (self.cleaned_data.get("fax") or "").strip()
        if not fax:
            return fax
        if not FAX_RE.match(fax):
            raise forms.ValidationError(
                _("Fax may only contain digits and the symbols + - ( ) and spaces (7-25 characters).")
            )
        digits = re.sub(r"\D", "", fax)
        if not (5 <= len(digits) <= 15):
            raise forms.ValidationError(_("Fax number must contain 5-15 digits."))
        return fax

    def _clean_text_field(self, field_name, label, regex, max_len=120):
        value = (self.cleaned_data.get(field_name) or "").strip()
        if not value:
            return value
        if len(value) > max_len:
            raise forms.ValidationError(
                _("%(label)s must be %(max)s characters or fewer.") % {"label": label, "max": max_len}
            )
        if not regex.match(value):
            raise forms.ValidationError(
                _("%(label)s contains invalid characters.") % {"label": label}
            )
        return value

    def clean_house_number(self):
        return self._clean_text_field("house_number", _("House number"), HOUSE_NUMBER_RE, max_len=15)

    def clean_district(self):
        return self._clean_text_field("district", _("District"), REGION_DISTRICT_RE, max_len=120)

    def clean_region(self):
        return self._clean_text_field("region", _("Region"), REGION_DISTRICT_RE, max_len=120)

    def clean_industry_code(self):
        code = (self.cleaned_data.get("industry_code") or "").strip()
        if not code:
            return code
        if not INDUSTRY_CODE_RE.match(code):
            raise forms.ValidationError(
                _("Industry code may only contain letters, digits, dots and hyphens (1-20 characters).")
            )
        return code

    def clean_keywords(self):
        keywords = (self.cleaned_data.get("keywords") or "").strip()
        if not keywords:
            return keywords
        if len(keywords) > 500:
            raise forms.ValidationError(_("Keywords must be 500 characters or fewer."))
        return keywords

    def clean_year_established(self):
        year = self.cleaned_data.get("year_established")
        if year in (None, ""):
            return None
        current_year = datetime.date.today().year
        if year < 1500 or year > current_year:
            raise forms.ValidationError(
                _("Year of establishment must be between 1500 and %(year)s.")
                % {"year": current_year}
            )
        return year

    def _clean_contact_name(self, field):
        value = (self.cleaned_data.get(field) or "").strip()
        if not value:
            return ""
        if len(value) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters."))
        if len(value) > 80:
            raise forms.ValidationError(_("Name must be 80 characters or fewer."))
        if not re.match(r"^[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ\s'\-.]{1,79}$", value):
            raise forms.ValidationError(
                _("Use letters, spaces, hyphens, apostrophes, or dots only.")
            )
        return value

    def clean_contact_first_name(self):
        return self._clean_contact_name("contact_first_name")

    def clean_contact_last_name(self):
        return self._clean_contact_name("contact_last_name")

    def clean_contact_email(self):
        # EmailField already validates the format; we just normalize the case
        # of the domain portion and strip surrounding whitespace.
        email = (self.cleaned_data.get("contact_email") or "").strip()
        if not email:
            return email
        if "@" in email:
            local, _, domain = email.partition("@")
            email = f"{local}@{domain.lower()}"
        return email

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        # Only validate when a new file was uploaded this request — preserving
        # the existing file (FieldFile) on edits without re-uploading.
        if not logo or not hasattr(logo, "name") or not hasattr(logo, "size"):
            return logo
        # `size` is only present on freshly-uploaded files; existing FieldFile
        # instances have it too but it equals the stored file size. Guard the
        # extension/size check to UploadedFile so we don't re-reject the
        # already-saved logo on update.
        name = (logo.name or "").lower()
        if not name.endswith(LOGO_ALLOWED_EXTENSIONS):
            raise forms.ValidationError(
                _("Logo must be one of: %(exts)s")
                % {"exts": ", ".join(LOGO_ALLOWED_EXTENSIONS)}
            )
        if getattr(logo, "size", 0) > LOGO_MAX_BYTES:
            raise forms.ValidationError(_("Logo file must be 5 MB or smaller."))
        return logo

    def clean_website(self):
        website = (self.cleaned_data.get("website") or "").strip()
        if not website:
            return website
        if len(website) > 500:
            raise forms.ValidationError(_("Website URL must be 500 characters or fewer."))
        if not WEBSITE_URL_RE.match(website):
            raise forms.ValidationError(
                _("Enter a valid website URL like https://example.com. "
                  "Only letters, digits, and - . _ / are allowed in the path.")
            )
        return website