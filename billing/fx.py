"""
Foreign-exchange helpers — robust, always-free, no API keys.

Strategy
========
1. Cached rate (Django cache, 12h TTL) → no network call.
2. Primary:   fawazahmed0/currency-api on jsdelivr CDN.
3. Fallback:  same data on Cloudflare Pages mirror.
4. Fallback:  open.er-api.com (different provider).
5. Last resort: static `FX_FALLBACK_RATES` (currently USD→EUR ≈ 0.92).

Each network attempt has a short timeout, so total worst-case latency before
we hit the static fallback is ~6s. Successful results are cached so a single
slow request per 12h is the upper bound — every other render is instant.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.core.cache import cache


logger = logging.getLogger(__name__)


_CACHE_TTL_SECONDS = 12 * 60 * 60
_REQUEST_TIMEOUT = 2  # seconds; per-attempt

# Last-resort rates if every endpoint fails. Update if real-world drift gets
# meaningful (USD→EUR has hovered ~0.85–0.95 in recent years).
FX_FALLBACK_RATES = {
    ("USD", "EUR"): Decimal("0.92"),
}


def _try_fawazahmed(src: str, dst: str):
    """fawazahmed0/currency-api — free, no key, daily ECB-aligned data.

    Two host mirrors (jsdelivr + Cloudflare Pages) so a CDN outage on either
    side falls through cleanly. Lowercase ISO codes in URL; lowercase keys
    in JSON body.
    """
    src_l = src.lower()
    dst_l = dst.lower()
    hosts = [
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies",
        "https://latest.currency-api.pages.dev/v1/currencies",
    ]
    for host in hosts:
        url = f"{host}/{src_l}.json"
        try:
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            value = data.get(src_l, {}).get(dst_l)
            if value is not None:
                return Decimal(str(value))
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.info("fawazahmed FX %s→%s via %s failed: %s", src, dst, host, exc)
    return None


def _try_er_api(src: str, dst: str):
    """open.er-api.com — different provider, used as second fallback."""
    url = f"https://open.er-api.com/v6/latest/{src.upper()}"
    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") == "success":
            value = data.get("rates", {}).get(dst.upper())
            if value is not None:
                return Decimal(str(value))
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.info("open.er-api FX %s→%s failed: %s", src, dst, exc)
    return None


def get_rate(from_currency: str, to_currency: str) -> Decimal:
    """Return live exchange rate `from → to`, with cache + multi-source fallback.

    Identity (USD→USD) returns 1. Never raises — guarantees a usable Decimal
    by falling back to `FX_FALLBACK_RATES` if every network source fails.
    """
    src = from_currency.upper()
    dst = to_currency.upper()
    if src == dst:
        return Decimal("1")

    cache_key = f"fx:rate:{src}:{dst}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Decimal(cached)

    rate = _try_fawazahmed(src, dst) or _try_er_api(src, dst)

    if rate is None:
        fallback = FX_FALLBACK_RATES.get((src, dst))
        if fallback is None:
            logger.error("FX %s→%s unavailable from all sources, no static fallback configured", src, dst)
            return Decimal("1")  # safest no-op so callers don't crash
        logger.warning("FX %s→%s using static fallback %s — all live sources failed", src, dst, fallback)
        # Cache the fallback briefly so we don't pound the dead APIs every request.
        cache.set(cache_key, str(fallback), 5 * 60)
        return fallback

    cache.set(cache_key, str(rate), _CACHE_TTL_SECONDS)
    return rate


def convert(amount, from_currency: str, to_currency: str) -> Decimal:
    """Convert `amount` between currencies. Returns Decimal rounded to 2 dp."""
    if amount is None:
        return Decimal("0.00")
    src_amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    rate = get_rate(from_currency, to_currency)
    return (src_amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
