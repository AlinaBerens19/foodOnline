from django.http import HttpResponse
from django.shortcuts import redirect, render
from accounts import views


def home(request):
    return render(request, 'home.html')
