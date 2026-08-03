"""Locale-invariant country matching for ORM queries and value resolution.

Company.country and User.target_region store ISO codes and/or canonical English
names — never translated UI labels. Display layers translate from ISO codes;
all business logic must use the helpers here instead of CountryChoices labels.
"""

from functools import lru_cache
from types import MappingProxyType

from django.db.models import Q

from accounts.constants import (
    COUNTRY_CODES,
    COUNTRY_ENGLISH_NAMES,
    COUNTRY_ENGLISH_NAME_TO_CODE,
    CountryChoices,
    SupportedLocale,
)

# Extra free-text spellings seen in Company.country (mapped by ISO code).
COUNTRY_ALIASES = {
    "US": ("USA", "United States of America", "U.S.", "U.S.A."),
    "GB": ("UK", "U.K.", "Great Britain"),
    "AE": ("UAE", "U.A.E."),
    "KR": ("Korea", "South Korea"),
    "CZ": ("Czechia",),
}

@lru_cache(maxsize=1)
def all_country_label_to_code():
    """Map any known country label (English, alias, or translated) → ISO code.

    Returned as an immutable view: lru_cache hands every caller the SAME object,
    so a stray `mapping[x] = y` anywhere would corrupt country resolution for the
    whole process. Callers only ever read (`.get()`), and the proxy keeps it that
    way — a mutation attempt raises TypeError at the call site instead of
    silently poisoning the cache."""
    mapping = dict(COUNTRY_ENGLISH_NAME_TO_CODE)
    for code, aliases in COUNTRY_ALIASES.items():
        for alias in aliases:
            mapping[alias.lower()] = code
    for code in COUNTRY_CODES:
        mapping[code.lower()] = code
    from django.utils import translation

    for code in COUNTRY_CODES:
        for lang in SupportedLocale.ALL:
            with translation.override(lang):
                label = dict(CountryChoices.CHOICES).get(code)
                if label:
                    mapping[str(label).lower()] = code
    return MappingProxyType(mapping)


def resolve_country_code(value):
    """Resolve a country string to an ISO-3166 alpha-2 code, or "" if unknown."""
    text = (value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if len(text) == 2 and upper in COUNTRY_CODES:
        return upper
    return all_country_label_to_code().get(text.lower(), "")


def canonical_country_name(value):
    """Return the canonical English country name for a code, name, alias, or label."""
    code = resolve_country_code(value)
    if code:
        return COUNTRY_ENGLISH_NAMES.get(code, code)
    # Unresolvable: hand back what the caller gave us, trimmed. `.strip()` on a
    # blank or None value already yields "", so no empty-check is needed.
    return (value or "").strip()


def country_match_q(country_code, field="country"):
    """Build a Q matching a stored country field against code + English name + aliases.

  Never use CountryChoices labels here — they are gettext_lazy and resolve to the
  active UI locale, while stored values are ISO codes and English names only."""
    code = (country_code or "").strip().upper()
    if not code:
        return Q(pk__in=[])

    variants = [code]
    english_name = COUNTRY_ENGLISH_NAMES.get(code)
    if english_name:
        variants.append(english_name)
    variants.extend(COUNTRY_ALIASES.get(code, ()))

    q = Q()
    for variant in variants:
        q |= Q(**{f"{field}__iexact": variant})
    return q
