from django.shortcuts import render

def home(request):
    return render(request, 'website/index.html')

def about(request):
    return render(request, 'website/about.html')

def worldmap(request):
    return render(request, 'website/worldmap.html')

def career(request):
    return render(request, 'website/career.html')

def contact(request):
    return render(request, 'website/contact.html')

def membership(request):
    return render(request, 'website/membership.html')