# tms/views/superadmin.py
from itertools import count
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.http import HttpResponse
from ..models import Store, Lead, StoreAdmin
from ..forms import StoreForm
import csv

@login_required
def super_dashboard(request):
    if not request.user.is_superuser:
        return redirect('store_dashboard')
    
    stores = Store.objects.all()
    leads = Lead.objects.all().order_by('-created_at')[:20]
    top_stores = Store.objects.annotate(lead_count=count('leads')).order_by('-lead_count')[:5]
    
    context = {
        'total_stores': stores.count(),
        'total_leads': Lead.objects.count(),
        'converted': Lead.objects.filter(status='converted').count(),
        'stores': stores,
        'leads': leads,
        'top_stores': top_stores
    }
    return render(request, 'TMS/superadmin/dashboard.html', context)

@login_required
def create_store(request):
    if not request.user.is_superuser:
        return redirect('super_dashboard')
    
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.created_by = request.user
            store.save()
            
            username = form.cleaned_data['admin_username']
            password = form.cleaned_data['admin_password']
            user = User.objects.create_user(username=username, password=password)
            StoreAdmin.objects.create(user=user, store=store)
            return redirect('super_dashboard')
    else:
        form = StoreForm()
    
    return render(request, 'TMS/superadmin/createstore.html', {'form': form})

@login_required
def all_leads(request):
    if not request.user.is_superuser:
        return redirect('super_dashboard')
    
    leads = Lead.objects.all().order_by('-created_at')
    stores = Store.objects.all()
    
    store_filter = request.GET.get('store')
    if store_filter:
        leads = leads.filter(store_id=store_filter)
    
    return render(request, 'TMS/superadmin/allleads.html', {'leads': leads, 'stores': stores})