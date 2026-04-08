from django.shortcuts import render

def region_us(request):
    return render(request, 'regions/region-us.html')

def region_de(request):
    return render(request, 'regions/region-de.html')

def region_cz(request):
    return render(request, 'regions/region-cz.html')

def region_ae(request):
    return render(request, 'regions/region-ae.html')

def region_jp(request):
    return render(request, 'regions/region-jp.html')