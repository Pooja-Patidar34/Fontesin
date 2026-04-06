from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render

from billing.models import Invoice


@login_required
def invoice_list(request):
    is_business_user = (
        request.user.role
        and request.user.role.code
        and request.user.role.code.lower() == "business_user"
    )

    if not request.user.is_superuser and not is_business_user:
        raise PermissionDenied()

    if request.user.is_superuser:
        qs = Invoice.objects.select_related(
            "subscription__user", "subscription__plan"
        ).order_by("-created_at")
    else:
        qs = Invoice.objects.filter(
            subscription__user=request.user
        ).select_related(
            "subscription__user", "subscription__plan"
        ).order_by("-created_at")

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(request, "dashboard/invoices.html", {
        "invoices": page_obj,
        "page_obj": page_obj,
        "active_menu": "invoices",
    })
