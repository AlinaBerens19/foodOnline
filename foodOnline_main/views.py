from django.http import HttpResponse
from django.shortcuts import redirect, render
from accounts import views
from vendor.models import Vendor
from marketplace.views import cart


def home(request):
    vendors = Vendor.objects.filter(is_approved=True, user__is_active=True)[:8]
    context = {
        'vendors': vendors,
    }
    return render(request, 'home.html', context)
