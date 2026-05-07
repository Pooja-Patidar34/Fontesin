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
