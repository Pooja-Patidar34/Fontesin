"""Autocomplete endpoints for NACE and NAICS classification codes.

Used by the company onboarding/edit form to pick an industry code without
mistyping. Backed by the ``NaceCode`` and ``NaicsCode`` lookup tables
seeded via ``python manage.py seed_industry_codes``.
"""
from django.db.models import Q
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import NaceCode, NaicsCode


DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _parse_int(value, default, *, lower=1, upper=MAX_LIMIT):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, n))


def _serialize(node):
    parent = node.parent
    return {
        # UUID returned as a string so the company-modal picker can write
        # it straight into the hidden ModelChoiceField input. Without it
        # the picker would need a second round-trip to resolve code → id.
        "id": str(node.id),
        "code": node.code,
        "title": node.title,
        "level": node.level,
        "parent_code": parent.code if parent else None,
    }


def _search(model, query: str, level: str | None, parent_code: str | None, limit: int):
    qs = model.objects.filter(is_active=True).select_related("parent")

    if query:
        # Code matches as a prefix; title matches as a substring. Codes are
        # short and prefix matches feel correct ('62' shouldn't surface
        # rows where '62' appears mid-code).
        qs = qs.filter(Q(code__istartswith=query) | Q(title__icontains=query))

    if level is not None:
        level_int = _parse_int(level, default=None, lower=1, upper=6)
        if level_int is not None:
            qs = qs.filter(level=level_int)

    if parent_code:
        qs = qs.filter(parent__code=parent_code)

    return list(qs.order_by("code")[:limit])


class NaceCodeListAPIView(APIView):
    """Search NACE Rev.2 codes."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search NACE codes",
        description=(
            "Autocomplete search over NACE Rev.2 codes. Matches `code` as a "
            "prefix and `title` as a case-insensitive substring."
        ),
        parameters=[
            OpenApiParameter("q", description="Search term (code prefix or title substring).", required=False, type=str),
            OpenApiParameter("level", description="Restrict to a specific level (1–4).", required=False, type=int),
            OpenApiParameter("parent_code", description="Restrict to children of this NACE code.", required=False, type=str),
            OpenApiParameter("limit", description=f"Max rows to return (1–{MAX_LIMIT}, default {DEFAULT_LIMIT}).", required=False, type=int),
        ],
        responses={
            200: OpenApiResponse(description="List of matching codes."),
        },
        tags=["Industry codes"],
    )
    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        level = request.query_params.get("level")
        parent_code = (request.query_params.get("parent_code") or "").strip() or None
        limit = _parse_int(request.query_params.get("limit"), default=DEFAULT_LIMIT)

        results = _search(NaceCode, q, level, parent_code, limit)
        return Response(
            {"status": True, "data": [_serialize(r) for r in results]},
            status=status.HTTP_200_OK,
        )


class NaicsCodeListAPIView(APIView):
    """Search NAICS 2022 codes."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search NAICS codes",
        description=(
            "Autocomplete search over NAICS 2022 codes. Matches `code` as a "
            "prefix and `title` as a case-insensitive substring."
        ),
        parameters=[
            OpenApiParameter("q", description="Search term (code prefix or title substring).", required=False, type=str),
            OpenApiParameter("level", description="Restrict to a specific level (2–6, by digit count).", required=False, type=int),
            OpenApiParameter("parent_code", description="Restrict to children of this NAICS code.", required=False, type=str),
            OpenApiParameter("limit", description=f"Max rows to return (1–{MAX_LIMIT}, default {DEFAULT_LIMIT}).", required=False, type=int),
        ],
        responses={
            200: OpenApiResponse(description="List of matching codes."),
        },
        tags=["Industry codes"],
    )
    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        level = request.query_params.get("level")
        parent_code = (request.query_params.get("parent_code") or "").strip() or None
        limit = _parse_int(request.query_params.get("limit"), default=DEFAULT_LIMIT)

        results = _search(NaicsCode, q, level, parent_code, limit)
        return Response(
            {"status": True, "data": [_serialize(r) for r in results]},
            status=status.HTTP_200_OK,
        )
