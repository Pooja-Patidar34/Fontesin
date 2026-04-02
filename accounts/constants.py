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
