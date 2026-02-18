from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import UserRole, Permission

def admin_login(request):
    if request.user.is_authenticated:
        return redirect("admin:dashboard")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Invalid credentials")
            return render(request, "auth/login.html")

        if not user.is_active:
            messages.error(request, "Your account is inactive")
            return render(request, "auth/login.html")

        if user.is_superuser:
            login(request, user)
            return redirect("admin:dashboard")

        try:
            user_role = UserRole.objects.select_related("role").get(user=user)
            if user_role.role.name == "tenant_admin":
                login(request, user)
                return redirect("admin:dashboard")
        except UserRole.DoesNotExist:
            pass

        messages.error(
            request,
            "You are not allowed to access the admin panel"
        )

    return render(request, "auth/login.html")


def admin_logout(request):
    logout(request)
    return redirect("admin:login")