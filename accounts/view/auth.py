from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages

def admin_login(request):
    if request.user.is_authenticated:
        return redirect("admin:dashboard")

    

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Invalid credentials")
        elif not user.is_staff:
            messages.error(request, "You are not allowed to access admin panel")
        else:
            login(request, user)
            return redirect("admin:dashboard")

    return render(request, "auth/login.html")



def admin_logout(request):
    logout(request)
    return redirect("admin:login")