from django.utils.translation import gettext_lazy as _


class CompanyClassificationChoices:
    MANUFACTURING = "manufacturing"
    IT_SERVICES = "it_services"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    RETAIL = "retail"
    EDUCATION = "education"
    MARKETING = "marketing"
    INDUSTRY = "industry"

    CHOICES = [
        (MANUFACTURING, _("Manufacturing")),
        (IT_SERVICES, _("IT Services")),
        (HEALTHCARE, _("Healthcare")),
        (FINANCE, _("Finance")),
        (RETAIL, _("Retail")),
        (EDUCATION, _("Education")),
        (MARKETING, _("Marketing")),
        (INDUSTRY, _("Industry")),
    ]


class CompanyEntityTypeChoices:
    """Legal entity type — distinct from `classification` (which is industry).

    Stored as the short suffix (e.g. "inc", "pvt_ltd") so future label edits
    don't require a data migration.
    """
    INC = "inc"
    LLC = "llc"
    LTD = "ltd"
    PVT_LTD = "pvt_ltd"
    LLP = "llp"
    CORP = "corp"
    GMBH = "gmbh"
    AG = "ag"
    SA = "sa"
    SARL = "sarl"
    BV = "bv"
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    PARTNERSHIP = "partnership"
    NON_PROFIT = "non_profit"
    OTHER = "other"

    CHOICES = [
        (INC, _("Inc. (Incorporated)")),
        (LLC, _("LLC (Limited Liability Company)")),
        (LTD, _("Ltd. (Limited)")),
        (PVT_LTD, _("Pvt. Ltd. (Private Limited)")),
        (LLP, _("LLP (Limited Liability Partnership)")),
        (CORP, _("Corp. (Corporation)")),
        (GMBH, _("GmbH")),
        (AG, _("AG")),
        (SA, _("S.A.")),
        (SARL, _("S.A.R.L.")),
        (BV, _("B.V.")),
        (SOLE_PROPRIETORSHIP, _("Sole Proprietorship")),
        (PARTNERSHIP, _("Partnership")),
        (NON_PROFIT, _("Non-Profit")),
        (OTHER, _("Other")),
    ]


class EmployeeCountRangeChoices:
    """Headcount buckets shown in the company onboarding form."""
    UP_TO_10 = "up_to_10"
    UP_TO_50 = "up_to_50"
    UP_TO_100 = "up_to_100"
    UP_TO_1000 = "up_to_1000"
    OVER_1000 = "over_1000"

    CHOICES = [
        (UP_TO_10, _("Up to 10")),
        (UP_TO_50, _("Up to 50")),
        (UP_TO_100, _("Up to 100")),
        (UP_TO_1000, _("Up to 1,000")),
        (OVER_1000, _("Over 1,000")),
    ]


class CountryChoices:
    US = "US"
    DE = "DE"
    CZ = "CZ"
    GB = "GB"
    FR = "FR"
    NL = "NL"
    PL = "PL"
    AT = "AT"
    CH = "CH"
    SE = "SE"
    AE = "AE"
    SG = "SG"
    CA = "CA"
    AU = "AU"
    JP = "JP"
    BR = "BR"
    IN = "IN"
    MX = "MX"
    KR = "KR"

    CHOICES = [
        (US, _("United States")),
        (DE, _("Germany")),
        (CZ, _("Czech Republic")),
        (GB, _("United Kingdom")),
        (FR, _("France")),
        (NL, _("Netherlands")),
        (PL, _("Poland")),
        (AT, _("Austria")),
        (CH, _("Switzerland")),
        (SE, _("Sweden")),
        (AE, _("United Arab Emirates")),
        (SG, _("Singapore")),
        (CA, _("Canada")),
        (AU, _("Australia")),
        (JP, _("Japan")),
        (BR, _("Brazil")),
        (IN, _("India")),
        (MX, _("Mexico")),
        (KR, _("South Korea")),
    ]

    # Countries pinned to the top of search/dropdown UIs. These are the
    # operating markets right now — everything else still selectable but
    # appears below the divider.
    PINNED = ("US", "GB")


# Canonical English country names for ORM filters and legacy free-text matching.
# Company.country stores ISO codes and/or these English spellings — never
# translated UI labels. Display strings live in CountryChoices.CHOICES.
COUNTRY_ENGLISH_NAMES = {
    "US": "United States",
    "DE": "Germany",
    "CZ": "Czech Republic",
    "GB": "United Kingdom",
    "FR": "France",
    "NL": "Netherlands",
    "PL": "Poland",
    "AT": "Austria",
    "CH": "Switzerland",
    "SE": "Sweden",
    "AE": "United Arab Emirates",
    "SG": "Singapore",
    "CA": "Canada",
    "AU": "Australia",
    "JP": "Japan",
    "BR": "Brazil",
    "IN": "India",
    "MX": "Mexico",
    "KR": "South Korea",
}

COUNTRY_ENGLISH_NAME_TO_CODE = {
    name.lower(): code for code, name in COUNTRY_ENGLISH_NAMES.items()
}

# ISO codes valid for ORM validation — never build this from translated CHOICES.
COUNTRY_CODES = frozenset(COUNTRY_ENGLISH_NAMES.keys())

# Fail at import time if the two country lists drift apart. COUNTRY_CODES is
# what ORM validation and resolve_country_code() trust, so a country added to
# CountryChoices.CHOICES but not here would be selectable in the UI yet
# rejected as invalid on save (and vice versa).
assert COUNTRY_CODES == {code for code, _label in CountryChoices.CHOICES}, (
    "COUNTRY_ENGLISH_NAMES and CountryChoices.CHOICES have drifted: "
    f"only in CHOICES={sorted({c for c, _l in CountryChoices.CHOICES} - COUNTRY_CODES)}, "
    f"only in COUNTRY_ENGLISH_NAMES={sorted(COUNTRY_CODES - {c for c, _l in CountryChoices.CHOICES})}. "
    "Add the country to both."
)


# ISO-3166-1 alpha-2 → emoji flag (regional indicator pairs). The browser
# renders these via the OS font; no image assets to ship.
COUNTRY_FLAGS = {
    "US": "🇺🇸", "GB": "🇬🇧", "DE": "🇩🇪", "CZ": "🇨🇿", "FR": "🇫🇷",
    "NL": "🇳🇱", "PL": "🇵🇱", "AT": "🇦🇹", "CH": "🇨🇭", "SE": "🇸🇪",
    "AE": "🇦🇪", "SG": "🇸🇬", "CA": "🇨🇦", "AU": "🇦🇺", "JP": "🇯🇵",
    "BR": "🇧🇷", "IN": "🇮🇳", "MX": "🇲🇽", "KR": "🇰🇷",
}


# Legal-form (entity type) options per country. The Company filter UI swaps
# this list when the user picks a country. Keys are existing
# CompanyEntityTypeChoices values where possible; new country-specific values
# are added as strings (no DB migration — `entity_type` is a free CharField
# with choices, but Django doesn't enforce choices at the DB layer).
LEGAL_FORMS_BY_COUNTRY = {
    "US": [
        ("sole_proprietorship", _("Sole Proprietorship")),
        ("partnership", _("Partnership (General)")),
        ("lp",          _("Partnership (Limited / LP)")),
        ("llp",         _("Partnership (Limited Liability / LLP)")),
        ("llc",         _("Limited Liability Company (LLC)")),
        ("c_corp",      _("Corporation (C Corp)")),
        ("s_corp",      _("Corporation (S Corp)")),
        ("non_profit",  _("Nonprofit Organization")),
    ],
    "GB": [
        ("sole_trader", _("Sole Trader")),
        ("partnership", _("Partnership")),
        ("llp",         _("Limited Liability Partnership (LLP)")),
        ("ltd",         _("Private Limited Company (Ltd)")),
        ("plc",         _("Public Limited Company (PLC)")),
        ("social_enterprise", _("Social Enterprise")),
        ("cic",         _("Community Interest Company (CIC)")),
        ("cooperative", _("Cooperative")),
    ],
}


# Primary administrative subdivisions per country (states / provinces /
# regions / prefectures / emirates / cantons). Keyed by ISO-3166-1 alpha-2
# matching CountryChoices, so a country dropdown change can index into this
# directly client-side. Names are stored as the canonical English form;
# server-side validation only checks set membership against this map for
# the selected country code.
COUNTRY_STATES = {
    "US": [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
        "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
        "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
        "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
        "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
        "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
        "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
        "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
        "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
    ],
    "CA": [
        "Alberta", "British Columbia", "Manitoba", "New Brunswick",
        "Newfoundland and Labrador", "Northwest Territories", "Nova Scotia",
        "Nunavut", "Ontario", "Prince Edward Island", "Quebec", "Saskatchewan",
        "Yukon",
    ],
    "GB": ["England", "Northern Ireland", "Scotland", "Wales"],
    "DE": [
        "Baden-Württemberg", "Bavaria", "Berlin", "Brandenburg", "Bremen",
        "Hamburg", "Hesse", "Lower Saxony", "Mecklenburg-Vorpommern",
        "North Rhine-Westphalia", "Rhineland-Palatinate", "Saarland",
        "Saxony", "Saxony-Anhalt", "Schleswig-Holstein", "Thuringia",
    ],
    "FR": [
        "Auvergne-Rhône-Alpes", "Bourgogne-Franche-Comté", "Brittany",
        "Centre-Val de Loire", "Corsica", "Grand Est", "Hauts-de-France",
        "Île-de-France", "Normandy", "Nouvelle-Aquitaine", "Occitanie",
        "Pays de la Loire", "Provence-Alpes-Côte d'Azur",
    ],
    "NL": [
        "Drenthe", "Flevoland", "Friesland", "Gelderland", "Groningen",
        "Limburg", "North Brabant", "North Holland", "Overijssel",
        "South Holland", "Utrecht", "Zeeland",
    ],
    "PL": [
        "Greater Poland", "Kuyavian-Pomeranian", "Lesser Poland", "Lower Silesian",
        "Lublin", "Lubusz", "Łódź", "Masovian", "Opole", "Podlaskie",
        "Pomeranian", "Silesian", "Subcarpathian", "Świętokrzyskie",
        "Warmian-Masurian", "West Pomeranian",
    ],
    "AT": [
        "Burgenland", "Carinthia", "Lower Austria", "Salzburg", "Styria",
        "Tyrol", "Upper Austria", "Vienna", "Vorarlberg",
    ],
    "CH": [
        "Aargau", "Appenzell Ausserrhoden", "Appenzell Innerrhoden",
        "Basel-Landschaft", "Basel-Stadt", "Bern", "Fribourg", "Geneva",
        "Glarus", "Graubünden", "Jura", "Lucerne", "Neuchâtel", "Nidwalden",
        "Obwalden", "Schaffhausen", "Schwyz", "Solothurn", "St. Gallen",
        "Thurgau", "Ticino", "Uri", "Valais", "Vaud", "Zug", "Zürich",
    ],
    "SE": [
        "Blekinge", "Dalarna", "Gävleborg", "Gotland", "Halland", "Jämtland",
        "Jönköping", "Kalmar", "Kronoberg", "Norrbotten", "Örebro",
        "Östergötland", "Skåne", "Södermanland", "Stockholm", "Uppsala",
        "Värmland", "Västerbotten", "Västernorrland", "Västmanland",
        "Västra Götaland",
    ],
    "CZ": [
        "Central Bohemian", "Hradec Králové", "Karlovy Vary", "Liberec",
        "Moravian-Silesian", "Olomouc", "Pardubice", "Pilsen", "Prague",
        "South Bohemian", "South Moravian", "Ústí nad Labem", "Vysočina", "Zlín",
    ],
    "AE": [
        "Abu Dhabi", "Ajman", "Dubai", "Fujairah", "Ras Al Khaimah",
        "Sharjah", "Umm Al Quwain",
    ],
    "SG": [
        "Central Region", "East Region", "North Region", "North-East Region",
        "West Region",
    ],
    "AU": [
        "Australian Capital Territory", "New South Wales", "Northern Territory",
        "Queensland", "South Australia", "Tasmania", "Victoria",
        "Western Australia",
    ],
    "JP": [
        "Aichi", "Akita", "Aomori", "Chiba", "Ehime", "Fukui", "Fukuoka",
        "Fukushima", "Gifu", "Gunma", "Hiroshima", "Hokkaido", "Hyogo",
        "Ibaraki", "Ishikawa", "Iwate", "Kagawa", "Kagoshima", "Kanagawa",
        "Kochi", "Kumamoto", "Kyoto", "Mie", "Miyagi", "Miyazaki", "Nagano",
        "Nagasaki", "Nara", "Niigata", "Oita", "Okayama", "Okinawa", "Osaka",
        "Saga", "Saitama", "Shiga", "Shimane", "Shizuoka", "Tochigi",
        "Tokushima", "Tokyo", "Tottori", "Toyama", "Wakayama", "Yamagata",
        "Yamaguchi", "Yamanashi",
    ],
    "BR": [
        "Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará",
        "Distrito Federal", "Espírito Santo", "Goiás", "Maranhão",
        "Mato Grosso", "Mato Grosso do Sul", "Minas Gerais", "Pará",
        "Paraíba", "Paraná", "Pernambuco", "Piauí", "Rio de Janeiro",
        "Rio Grande do Norte", "Rio Grande do Sul", "Rondônia", "Roraima",
        "Santa Catarina", "São Paulo", "Sergipe", "Tocantins",
    ],
    "IN": [
        "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh",
        "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
        "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat",
        "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand",
        "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh",
        "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
        "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
        "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    ],
    "MX": [
        "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
        "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila", "Colima",
        "Durango", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "México",
        "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla",
        "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora",
        "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
    ],
    "KR": [
        "Busan", "Daegu", "Daejeon", "Gangwon", "Gwangju", "Gyeonggi",
        "Incheon", "Jeju", "North Chungcheong", "North Gyeongsang",
        "North Jeolla", "Sejong", "Seoul", "South Chungcheong",
        "South Gyeongsang", "South Jeolla", "Ulsan",
    ],
}


# National subscriber-number length bounds per country (excluding country dialing code).
# Used to validate phone/fax input against the selected country.
PHONE_RULES = {
    "US": (10, 10), "CA": (10, 10), "GB": (10, 10),
    "DE": (10, 11), "FR": (9, 9),   "NL": (9, 9),
    "PL": (9, 9),   "AT": (10, 11), "CH": (9, 9),
    "SE": (9, 10),  "CZ": (9, 9),   "AE": (9, 9),
    "SG": (8, 8),   "AU": (9, 9),   "JP": (10, 10),
    "BR": (10, 11), "IN": (10, 10), "MX": (10, 10),
    "KR": (10, 11),
}


class SupportedLocale:
    EN = "en"
    DE = "de"
    ES = "es"
    FR = "fr"

    CHOICES = [
        (EN, _("English")),
        (DE, _("German")),
        (ES, _("Spanish")),
        (FR, _("French")),
    ]

    ALL = frozenset({EN, DE, ES, FR})


class LanguageChoices(SupportedLocale):
    """Backward-compatible alias for SupportedLocale."""


# ---------------------------------------------------------------------------
# Franchise hierarchy (MVP)
#
# The franchise tree is layered onto the existing `Tenant` model: a Tenant row
# with a non-null `franchise_level` IS a franchise node; a row with a null
# level is a plain org-partition (legacy behaviour, unchanged). These choice
# classes back the new franchise fields on Tenant plus the FranchiseApplication
# and ConsultantAssignment models. See accounts/models.py.
# ---------------------------------------------------------------------------


class FranchiseLevel:
    """The four franchise tiers, ordered from broadest to narrowest.

    Not every region uses every tier (spec §1): a Master may sit directly above
    a Regional or a Micro if the intermediate tiers don't exist yet. `RANK`
    encodes depth so validation can require a child to be strictly deeper than
    its parent without forcing adjacent tiers.
    """
    MASTER = "MASTER"
    NATIONAL = "NATIONAL"
    REGIONAL = "REGIONAL"
    MICRO = "MICRO"

    CHOICES = [
        (MASTER, _("Master Franchise")),
        (NATIONAL, _("National Sub-Franchise")),
        (REGIONAL, _("Regional Sub-Franchise")),
        (MICRO, _("Micro-Franchise")),
    ]

    # Depth rank — a child node must have a strictly greater rank than its
    # parent. Gaps are allowed (simplified MVP tree, spec §4 note).
    RANK = {
        MASTER: 1,
        NATIONAL: 2,
        REGIONAL: 3,
        MICRO: 4,
    }


class FranchiseUnitStatus:
    """Lifecycle of a franchise unit (spec §9.2).

    A unit gains full access rights ONLY in ACTIVE. Everything before that is a
    gate (contract → payment → activation); everything after is a wind-down.
    """
    PENDING_CONTRACT = "PENDING_CONTRACT"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    EXPIRED = "EXPIRED"

    CHOICES = [
        (PENDING_CONTRACT, _("Pending Contract")),
        (PENDING_PAYMENT, _("Pending Payment")),
        (ACTIVE, _("Active")),
        (SUSPENDED, _("Suspended")),
        (TERMINATED, _("Terminated")),
        (EXPIRED, _("Expired")),
    ]


class FranchiseApplicationStatus:
    """Lifecycle of a franchise application / approval request (spec §9.1)."""
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    CHOICES = [
        (DRAFT, _("Draft")),
        (SUBMITTED, _("Submitted")),
        (PENDING_REVIEW, _("Pending Review")),
        (APPROVED, _("Approved")),
        (REJECTED, _("Rejected")),
        (CANCELLED, _("Cancelled")),
    ]

    # Statuses that still occupy the reviewer's queue.
    OPEN = frozenset({SUBMITTED, PENDING_REVIEW})


class ConsultantType:
    """A consultant's relationship to a franchise node (spec §8.3).

    A Micro-Franchise owner IS a consultant with local exclusivity; a standard
    consultant works a territory without exclusivity and can't block it.
    """
    MICRO_FRANCHISE_OWNER = "MICRO_FRANCHISE_OWNER"
    STANDARD_CONSULTANT = "STANDARD_CONSULTANT"

    CHOICES = [
        (MICRO_FRANCHISE_OWNER, _("Micro-Franchise Owner")),
        (STANDARD_CONSULTANT, _("Standard Consultant")),
    ]


class ConsultantAssignmentStatus:
    """Lifecycle of a consultant's assignment to a franchise node (spec §12.3)."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"

    CHOICES = [
        (PENDING, _("Pending")),
        (ACTIVE, _("Active")),
        (SUSPENDED, _("Suspended")),
        (TERMINATED, _("Terminated")),
    ]


class FranchiseFeeStatus:
    """Franchise-fee payment state (spec §8.1 `franchise_fee_status`)."""
    UNPAID = "UNPAID"
    PAID = "PAID"
    WAIVED = "WAIVED"

    CHOICES = [
        (UNPAID, _("Unpaid")),
        (PAID, _("Paid")),
        (WAIVED, _("Waived")),
    ]


class ContractStatus:
    """Franchise-contract signature state (spec §8.1 `contract_status`)."""
    PENDING = "PENDING"
    SIGNED = "SIGNED"

    CHOICES = [
        (PENDING, _("Pending")),
        (SIGNED, _("Signed")),
    ]
