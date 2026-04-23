class CompanyClassificationChoices:
    MANUFACTURING = "manufacturing"
    IT_SERVICES = "it_services"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    RETAIL = "retail"
    EDUCATION = "education"

    CHOICES = [
        (MANUFACTURING, "Manufacturing"),
        (IT_SERVICES, "IT Services"),
        (HEALTHCARE, "Healthcare"),
        (FINANCE, "Finance"),
        (RETAIL, "Retail"),
        (EDUCATION, "Education"),
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
        (US, "United States"),
        (DE, "Germany"),
        (CZ, "Czech Republic"),
        (GB, "United Kingdom"),
        (FR, "France"),
        (NL, "Netherlands"),
        (PL, "Poland"),
        (AT, "Austria"),
        (CH, "Switzerland"),
        (SE, "Sweden"),
        (AE, "United Arab Emirates"),
        (SG, "Singapore"),
        (CA, "Canada"),
        (AU, "Australia"),
        (JP, "Japan"),
        (BR, "Brazil"),
        (IN, "India"),
        (MX, "Mexico"),
        (KR, "South Korea"),
    ]


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


class LanguageChoices:
    EN = "en"
    DE = "de"
    CS = "cs"
    FR = "fr"
    AR = "ar"
    JA = "ja"
    ES = "es"
    PT = "pt"

    CHOICES = [
        (EN, "English"),
        (DE, "German"),
        (CS, "Czech"),
        (FR, "French"),
        (AR, "Arabic"),
        (JA, "Japanese"),
        (ES, "Spanish"),
        (PT, "Portuguese"),
    ]
