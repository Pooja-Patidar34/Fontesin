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


class ContinentChoices:
    """
    Continents a user can sit on. Keys match billing.utils.PLAN_REGIONS (which
    reads its map from CONTINENT_COUNTRIES below), so the continent stored on an
    account is the same token the geographic-scope code speaks — and the Pro
    plan's reach is exactly the country list of the continent picked at sign-up.
    """
    EUROPE = "europe"
    NORTH_AMERICA = "north_america"
    SOUTH_AMERICA = "south_america"
    AFRICA = "africa"
    ASIA = "asia"
    AUSTRALIA_OCEANIA = "australia_oceania"

    CHOICES = [
        (EUROPE, _("Europe")),
        (NORTH_AMERICA, _("North America")),
        (SOUTH_AMERICA, _("South America")),
        (AFRICA, _("Africa")),
        (ASIA, _("Asia")),
        (AUSTRALIA_OCEANIA, _("Australia / Oceania")),
    ]


# --------------------------- THE COUNTRY TABLE ---------------------------
# Every country the platform knows, grouped by the continent it belongs to:
# (ISO-3166-1 alpha-2 code, canonical ENGLISH name, international dial code).
#
# This is the single source of truth. Country dropdowns, the continent
# grouping, plan geographic scope, phone prefixes and flags are all derived
# from it below — nothing anywhere else may keep its own country list.
#
# 196 sovereign states: Africa 54, Asia 48, Europe 44, North America 24
# (23 sovereign + Greenland), South America 12, Australia / Oceania 14.
#
# The names are the CANONICAL ENGLISH spellings. Company.country is free text
# and may hold either the code or one of these names, so
# accounts.utils.country_matching matches against them directly — a translated
# label must never be stored or compared. Display translation happens once, in
# CountryChoices.CHOICES.
COUNTRIES_BY_CONTINENT = {
    ContinentChoices.AFRICA: (
        ("DZ", "Algeria", "+213"),
        ("AO", "Angola", "+244"),
        ("BJ", "Benin", "+229"),
        ("BW", "Botswana", "+267"),
        ("BF", "Burkina Faso", "+226"),
        ("BI", "Burundi", "+257"),
        ("CV", "Cabo Verde", "+238"),
        ("CM", "Cameroon", "+237"),
        ("CF", "Central African Republic", "+236"),
        ("TD", "Chad", "+235"),
        ("KM", "Comoros", "+269"),
        ("CG", "Republic of the Congo", "+242"),
        ("CD", "Democratic Republic of the Congo", "+243"),
        ("CI", "Ivory Coast", "+225"),
        ("DJ", "Djibouti", "+253"),
        ("EG", "Egypt", "+20"),
        ("GQ", "Equatorial Guinea", "+240"),
        ("ER", "Eritrea", "+291"),
        ("SZ", "Eswatini", "+268"),
        ("ET", "Ethiopia", "+251"),
        ("GA", "Gabon", "+241"),
        ("GM", "Gambia", "+220"),
        ("GH", "Ghana", "+233"),
        ("GN", "Guinea", "+224"),
        ("GW", "Guinea-Bissau", "+245"),
        ("KE", "Kenya", "+254"),
        ("LS", "Lesotho", "+266"),
        ("LR", "Liberia", "+231"),
        ("LY", "Libya", "+218"),
        ("MG", "Madagascar", "+261"),
        ("MW", "Malawi", "+265"),
        ("ML", "Mali", "+223"),
        ("MR", "Mauritania", "+222"),
        ("MU", "Mauritius", "+230"),
        ("MA", "Morocco", "+212"),
        ("MZ", "Mozambique", "+258"),
        ("NA", "Namibia", "+264"),
        ("NE", "Niger", "+227"),
        ("NG", "Nigeria", "+234"),
        ("RW", "Rwanda", "+250"),
        ("ST", "Sao Tome and Principe", "+239"),
        ("SN", "Senegal", "+221"),
        ("SC", "Seychelles", "+248"),
        ("SL", "Sierra Leone", "+232"),
        ("SO", "Somalia", "+252"),
        ("ZA", "South Africa", "+27"),
        ("SS", "South Sudan", "+211"),
        ("SD", "Sudan", "+249"),
        ("TZ", "Tanzania", "+255"),
        ("TG", "Togo", "+228"),
        ("TN", "Tunisia", "+216"),
        ("UG", "Uganda", "+256"),
        ("ZM", "Zambia", "+260"),
        ("ZW", "Zimbabwe", "+263"),
    ),
    ContinentChoices.ASIA: (
        ("AF", "Afghanistan", "+93"),
        ("AM", "Armenia", "+374"),
        ("AZ", "Azerbaijan", "+994"),
        ("BH", "Bahrain", "+973"),
        ("BD", "Bangladesh", "+880"),
        ("BT", "Bhutan", "+975"),
        ("BN", "Brunei", "+673"),
        ("KH", "Cambodia", "+855"),
        ("CN", "China", "+86"),
        ("CY", "Cyprus", "+357"),
        ("GE", "Georgia", "+995"),
        ("IN", "India", "+91"),
        ("ID", "Indonesia", "+62"),
        ("IR", "Iran", "+98"),
        ("IQ", "Iraq", "+964"),
        ("IL", "Israel", "+972"),
        ("JP", "Japan", "+81"),
        ("JO", "Jordan", "+962"),
        ("KZ", "Kazakhstan", "+7"),
        ("KW", "Kuwait", "+965"),
        ("KG", "Kyrgyzstan", "+996"),
        ("LA", "Laos", "+856"),
        ("LB", "Lebanon", "+961"),
        ("MY", "Malaysia", "+60"),
        ("MV", "Maldives", "+960"),
        ("MN", "Mongolia", "+976"),
        ("MM", "Myanmar", "+95"),
        ("NP", "Nepal", "+977"),
        ("KP", "North Korea", "+850"),
        ("OM", "Oman", "+968"),
        ("PK", "Pakistan", "+92"),
        ("PS", "Palestine", "+970"),
        ("PH", "Philippines", "+63"),
        ("QA", "Qatar", "+974"),
        ("SA", "Saudi Arabia", "+966"),
        ("SG", "Singapore", "+65"),
        ("KR", "South Korea", "+82"),
        ("LK", "Sri Lanka", "+94"),
        ("SY", "Syria", "+963"),
        ("TJ", "Tajikistan", "+992"),
        ("TH", "Thailand", "+66"),
        ("TL", "Timor-Leste", "+670"),
        ("TR", "Turkey", "+90"),
        ("TM", "Turkmenistan", "+993"),
        ("AE", "United Arab Emirates", "+971"),
        ("UZ", "Uzbekistan", "+998"),
        ("VN", "Vietnam", "+84"),
        ("YE", "Yemen", "+967"),
    ),
    ContinentChoices.EUROPE: (
        ("AL", "Albania", "+355"),
        ("AD", "Andorra", "+376"),
        ("AT", "Austria", "+43"),
        ("BY", "Belarus", "+375"),
        ("BE", "Belgium", "+32"),
        ("BA", "Bosnia and Herzegovina", "+387"),
        ("BG", "Bulgaria", "+359"),
        ("HR", "Croatia", "+385"),
        ("CZ", "Czech Republic", "+420"),
        ("DK", "Denmark", "+45"),
        ("EE", "Estonia", "+372"),
        ("FI", "Finland", "+358"),
        ("FR", "France", "+33"),
        ("DE", "Germany", "+49"),
        ("GR", "Greece", "+30"),
        ("HU", "Hungary", "+36"),
        ("IS", "Iceland", "+354"),
        ("IE", "Ireland", "+353"),
        ("IT", "Italy", "+39"),
        ("LV", "Latvia", "+371"),
        ("LI", "Liechtenstein", "+423"),
        ("LT", "Lithuania", "+370"),
        ("LU", "Luxembourg", "+352"),
        ("MT", "Malta", "+356"),
        ("MD", "Moldova", "+373"),
        ("MC", "Monaco", "+377"),
        ("ME", "Montenegro", "+382"),
        ("NL", "Netherlands", "+31"),
        ("MK", "North Macedonia", "+389"),
        ("NO", "Norway", "+47"),
        ("PL", "Poland", "+48"),
        ("PT", "Portugal", "+351"),
        ("RO", "Romania", "+40"),
        ("RU", "Russia", "+7"),
        ("SM", "San Marino", "+378"),
        ("RS", "Serbia", "+381"),
        ("SK", "Slovakia", "+421"),
        ("SI", "Slovenia", "+386"),
        ("ES", "Spain", "+34"),
        ("SE", "Sweden", "+46"),
        ("CH", "Switzerland", "+41"),
        ("UA", "Ukraine", "+380"),
        ("GB", "United Kingdom", "+44"),
        ("VA", "Vatican City", "+379"),
    ),
    ContinentChoices.NORTH_AMERICA: (
        ("AG", "Antigua and Barbuda", "+1268"),
        ("BS", "Bahamas", "+1242"),
        ("BB", "Barbados", "+1246"),
        ("BZ", "Belize", "+501"),
        ("CA", "Canada", "+1"),
        ("CR", "Costa Rica", "+506"),
        ("CU", "Cuba", "+53"),
        ("DM", "Dominica", "+1767"),
        ("DO", "Dominican Republic", "+1809"),
        ("SV", "El Salvador", "+503"),
        ("GL", "Greenland", "+299"),
        ("GD", "Grenada", "+1473"),
        ("GT", "Guatemala", "+502"),
        ("HT", "Haiti", "+509"),
        ("HN", "Honduras", "+504"),
        ("JM", "Jamaica", "+1876"),
        ("MX", "Mexico", "+52"),
        ("NI", "Nicaragua", "+505"),
        ("PA", "Panama", "+507"),
        ("KN", "Saint Kitts and Nevis", "+1869"),
        ("LC", "Saint Lucia", "+1758"),
        ("VC", "Saint Vincent and the Grenadines", "+1784"),
        ("TT", "Trinidad and Tobago", "+1868"),
        ("US", "United States", "+1"),
    ),
    ContinentChoices.SOUTH_AMERICA: (
        ("AR", "Argentina", "+54"),
        ("BO", "Bolivia", "+591"),
        ("BR", "Brazil", "+55"),
        ("CL", "Chile", "+56"),
        ("CO", "Colombia", "+57"),
        ("EC", "Ecuador", "+593"),
        ("GY", "Guyana", "+592"),
        ("PY", "Paraguay", "+595"),
        ("PE", "Peru", "+51"),
        ("SR", "Suriname", "+597"),
        ("UY", "Uruguay", "+598"),
        ("VE", "Venezuela", "+58"),
    ),
    ContinentChoices.AUSTRALIA_OCEANIA: (
        ("AU", "Australia", "+61"),
        ("FJ", "Fiji", "+679"),
        ("KI", "Kiribati", "+686"),
        ("MH", "Marshall Islands", "+692"),
        ("FM", "Micronesia", "+691"),
        ("NR", "Nauru", "+674"),
        ("NZ", "New Zealand", "+64"),
        ("PW", "Palau", "+680"),
        ("PG", "Papua New Guinea", "+675"),
        ("WS", "Samoa", "+685"),
        ("SB", "Solomon Islands", "+677"),
        ("TO", "Tonga", "+676"),
        ("TV", "Tuvalu", "+688"),
        ("VU", "Vanuatu", "+678"),
    ),
}


# Flattened view of the table: (code, English name, continent, dial code).
COUNTRIES = tuple(
    (code, name, continent, dial)
    for continent, rows in COUNTRIES_BY_CONTINENT.items()
    for code, name, dial in rows
)


class CountryChoices:
    """Country choices for model fields and dropdowns, built from COUNTRIES.

    Labels are lazily translated, so they follow the active UI locale. NEVER
    compare or store a label — resolve to an ISO code via
    accounts.utils.country_matching.resolve_country_code first.
    """

    # Alphabetical by English name: dropdowns render in this order, and the
    # sign-up form re-sorts by translated label within the picked continent.
    CHOICES = [
        (code, _(name))
        for code, name, _continent, _dial in sorted(COUNTRIES, key=lambda row: row[1])
    ]

    # Countries pinned to the top of search/dropdown UIs. These are the
    # operating markets right now — everything else still selectable but
    # appears below the divider.
    PINNED = ("US", "GB")


# Canonical English country names for ORM filters and legacy free-text matching.
# Company.country stores ISO codes and/or these English spellings — never
# translated UI labels. Display strings live in CountryChoices.CHOICES.
COUNTRY_ENGLISH_NAMES = {code: name for code, name, _c, _d in COUNTRIES}

COUNTRY_ENGLISH_NAME_TO_CODE = {
    name.lower(): code for code, name in COUNTRY_ENGLISH_NAMES.items()
}

# ISO codes valid for ORM validation — never build this from translated CHOICES.
COUNTRY_CODES = frozenset(COUNTRY_ENGLISH_NAMES.keys())

# International dial code per country, e.g. "IN" -> "+91". Drives the phone
# prefix box on the sign-up form.
COUNTRY_DIAL_CODES = {code: dial for code, _n, _c, dial in COUNTRIES}

# Continent -> the country codes on it, in table order. This is also the Pro
# plan's reach (billing.utils.PLAN_REGIONS reads it): a Pro user who signed up
# in Asia sees the companies of every Asian country in this list.
CONTINENT_COUNTRIES = {
    continent: [code for code, _n, _d in rows]
    for continent, rows in COUNTRIES_BY_CONTINENT.items()
}

# Reverse index: ISO country code -> continent key.
COUNTRY_CONTINENT = {code: continent for code, _n, continent, _d in COUNTRIES}

CONTINENT_CODES = frozenset(CONTINENT_COUNTRIES.keys())

# What the sign-up dropdown renders: continents that actually have a country
# behind them (all of them today — the guard is here so an emptied continent is
# never offered as a dead end).
CONTINENT_CHOICES_WITH_COUNTRIES = [
    (code, label)
    for code, label in ContinentChoices.CHOICES
    if CONTINENT_COUNTRIES.get(code)
]

# A country can only sit on one continent. The table is keyed BY continent, so
# a duplicated row is the one mistake the structure cannot catch on its own —
# and it would silently give two continents overlapping Pro scopes.
_COUNTRY_CODE_LIST = [code for code, _n, _c, _d in COUNTRIES]
assert len(_COUNTRY_CODE_LIST) == len(COUNTRY_CODES), (
    "A country appears twice in COUNTRIES_BY_CONTINENT: "
    + str(sorted({c for c in _COUNTRY_CODE_LIST if _COUNTRY_CODE_LIST.count(c) > 1}))
)

assert set(CONTINENT_COUNTRIES) == {c for c, _label in ContinentChoices.CHOICES}, (
    "COUNTRIES_BY_CONTINENT and ContinentChoices.CHOICES have drifted."
)


def continent_for_country(country_code):
    """Return the continent key for an ISO alpha-2 country code, or None."""
    if not country_code:
        return None
    return COUNTRY_CONTINENT.get(country_code.strip().upper())


def flag_for_country(country_code):
    """ISO-3166-1 alpha-2 -> emoji flag, from the regional-indicator pair.

    Derived rather than hand-listed: every row in the table gets a flag for
    free, and a country can never be added without one. The browser renders it
    with the OS font — no image assets to ship."""
    code = (country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code)


COUNTRY_FLAGS = {code: flag_for_country(code) for code in COUNTRY_ENGLISH_NAMES}


# National (subscriber) phone-number length per country, plus the format hint
# shown under the sign-up phone field: code -> (min digits, max digits, hint).
# Digits are counted AFTER the dial code is stripped.
#
# Only the markets we actively operate in are pinned to an exact length. Every
# other country falls back to DEFAULT_PHONE_RULE, which accepts anything in the
# ITU-plausible range — a wrong-but-strict rule locks real users out of sign-up,
# while a loose one only lets a typo through to a field the user can correct.
# Add a row here as a market becomes operational.
COUNTRY_PHONE_RULES = {
    "US": (10, 10, "(XXX) XXX-XXXX"),
    "CA": (10, 10, "(XXX) XXX-XXXX"),
    "GB": (10, 10, "XXXX XXX XXXX"),
    "DE": (10, 11, "XXX XXXXXXXX"),
    "FR": (9, 9, "X XX XX XX XX"),
    "NL": (9, 9, "XX XXX XXXX"),
    "PL": (9, 9, "XXX XXX XXX"),
    "AT": (10, 11, "XXX XXXXXXX"),
    "CH": (9, 9, "XX XXX XX XX"),
    "SE": (9, 10, "XX XXX XXXX"),
    "CZ": (9, 9, "XXX XXX XXX"),
    "AE": (9, 9, "XX XXX XXXX"),
    "SG": (8, 8, "XXXX XXXX"),
    "AU": (9, 9, "XXX XXX XXX"),
    "JP": (10, 10, "XX XXXX XXXX"),
    "BR": (10, 11, "XX XXXXX XXXX"),
    "IN": (10, 10, "XXXXX XXXXX"),
    "MX": (10, 10, "XX XXXX XXXX"),
    "KR": (10, 11, "XX XXXX XXXX"),
}

DEFAULT_PHONE_RULE = (7, 15, "")


def phone_rule_for_country(country_code):
    """(min digits, max digits, format hint) for a country, with a safe default."""
    return COUNTRY_PHONE_RULES.get(
        (country_code or "").strip().upper(), DEFAULT_PHONE_RULE
    )


def country_phone_map():
    """Per-country phone data for the sign-up form's JS.

    code -> {"dial", "min", "max", "name", "format"}. Built for all 196
    countries so the prefix box and the digit-count check work the moment a
    country is picked, whatever continent it sits on. `name` is the canonical
    English name — it is only used inside an error message the caller
    translates, never for matching."""
    out = {}
    for code, name, _continent, dial in COUNTRIES:
        min_len, max_len, fmt = phone_rule_for_country(code)
        out[code] = {
            "dial": dial,
            "min": min_len,
            "max": max_len,
            "name": name,
            "format": fmt,
        }
    return out


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


# Hand-curated subdivisions for the operating markets, in the canonical ENGLISH
# form ("Bavaria", not "Bayern"). These are the spellings already stored in
# Company.state and User.state_region, so they must keep winning over the
# generated ISO data below — swapping them for the ISO/local spelling would
# invalidate every stored value and quietly shrink each Basic-plan user's
# directory to nothing.
#
# Keyed by ISO-3166-1 alpha-2 matching CountryChoices, so a country dropdown
# change can index into this directly client-side. Server-side validation only
# checks set membership for the selected country code.
CURATED_COUNTRY_STATES = {
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


# Every country's subdivisions: the generated ISO 3166-2 lists, with the curated
# markets layered on top.
#
# The generated half is a committed file produced by
# `python manage.py generate_country_subdivisions` (which needs the
# generation-only `pycountry` dependency); the app itself imports nothing extra.
# Its names are the ISO spellings, usually the local ones — that is fine for the
# countries it serves, because nothing was ever stored for them, so the ISO
# spelling becomes the canonical one on first use. Where a curated list exists
# it wins outright: see CURATED_COUNTRY_STATES above for why.
#
# A handful of countries (city-states and microstates) have no ISO subdivisions
# at all and no curated list; they keep the free-text State box, which is the
# honest answer for a country that genuinely has no states.
from accounts.data.country_subdivisions import (  # noqa: E402  (data, not a cycle)
    COUNTRY_SUBDIVISIONS as _ISO_COUNTRY_SUBDIVISIONS,
)

COUNTRY_STATES = {
    **{
        code: names
        for code, names in _ISO_COUNTRY_SUBDIVISIONS.items()
        if code in COUNTRY_CODES
    },
    **CURATED_COUNTRY_STATES,
}


# National subscriber-number length bounds per country (excluding country
# dialing code), used to validate phone/fax input against the selected country.
#
# Derived from COUNTRY_PHONE_RULES rather than kept as a second list: the two
# held the same 19 markets and would have drifted the first time one was
# edited. Callers that also want the format hint should use
# phone_rule_for_country(), which additionally supplies DEFAULT_PHONE_RULE for
# countries with no pinned entry — this map deliberately stays sparse, because
# company_form.py treats a missing key as "unknown country, apply the generic
# 5-15 digit bound".
PHONE_RULES = {
    code: (min_len, max_len)
    for code, (min_len, max_len, _hint) in COUNTRY_PHONE_RULES.items()
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
