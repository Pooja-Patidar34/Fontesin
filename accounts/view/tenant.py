# accounts/views/tenants.py  (or views.py)
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from accounts.models import Tenant


@login_required
def tenant_list(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Not allowed")

    tenants = Tenant.objects.all()
    return render(request, "dashboard/tenants.html", {"tenants": tenants})
