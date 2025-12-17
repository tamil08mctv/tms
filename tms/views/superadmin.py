# tms/views/superadmin.py → FINAL VERSION WITH PROFESSIONAL LOGGING

import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Count, Q
import csv
from datetime import date
from ..models import Store, Lead, StoreAdmin, User, SiteSettings, SocialLink
from ..forms import StoreForm, StoreUpdateForm, SiteSettingsForm, SocialLinkFormSet

# Logger for superadmin actions
superadmin_logger = logging.getLogger('superadmin')

def superuser_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_superuser, login_url='/')(view_func))

from django.core.paginator import Paginator

@superuser_required
def store_list_super(request):
    superadmin_logger.info(f"Superuser {request.user.username} accessed store list")
    
    store_list = Store.objects.prefetch_related('store_admins__user').all().order_by('-id')
    paginator = Paginator(store_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'TMS/superadmin/store_list.html', {
        'stores': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'paginator': paginator,
        'page_obj': page_obj,
    })

@superuser_required
def super_dashboard(request):
    superadmin_logger.info(f"Superuser {request.user.username} accessed dashboard")
    
    context = {
        'total_stores': Store.objects.count(),
        'total_leads': Lead.objects.count(),
        'converted': Lead.objects.filter(status='converted').count(),
        'pending': Lead.objects.filter(status='new').count(),
        'top_stores': Store.objects.annotate(lead_count=Count('leads')).order_by('-lead_count')[:6],
        'recent_leads': Lead.objects.select_related('store').order_by('-created_at')[:15],
    }
    return render(request, 'TMS/superadmin/dashboard.html', context)

@superuser_required
def create_store(request):
    superadmin_logger.info(f"Superuser {request.user.username} accessed create store page")
    
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.created_by = request.user
            store.save()

            username = form.cleaned_data['admin_username']
            password = form.cleaned_data['admin_password']
            if username and password:
                user = User.objects.create_user(username=username, password=password)
                StoreAdmin.objects.create(user=user, store=store)

            superadmin_logger.info(f"Superuser {request.user.username} CREATED store: '{store.name}' ({store.city}) | Admin: {username}")
            messages.success(request, f"Store '{store.name}' created successfully!")
            return redirect('store_list_super')
    else:
        form = StoreForm()

    return render(request, 'TMS/superadmin/createstore.html', {
        'form': form,
        'store': None
    })

@superuser_required
def edit_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    superadmin_logger.info(f"Superuser {request.user.username} accessed edit store: '{store.name}' ({store.city})")
    
    if request.method == 'POST':
        form = StoreUpdateForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()
            superadmin_logger.info(f"Superuser {request.user.username} UPDATED store: '{store.name}' ({store.city})")
            messages.success(request, f"Store '{store.name}' updated successfully!")
            return redirect('store_list_super')
    else:
        form = StoreUpdateForm(instance=store)

    return render(request, 'TMS/superadmin/createstore.html', {
        'form': form,
        'store': store
    })

@superuser_required
def toggle_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    old_status = "Active" if store.is_active else "Inactive"
    store.is_active = not store.is_active
    store.save()
    
    superadmin_logger.info(f"Superuser {request.user.username} toggled store status: '{store.name}' | {old_status} → {'Active' if store.is_active else 'Inactive'}")
    messages.success(request, f"Store '{store.name}' has been {'activated' if store.is_active else 'disabled'}")
    return redirect('store_list_super')

@superuser_required
def all_leads(request):
    superadmin_logger.info(f"Superuser {request.user.username} accessed all leads page")
    
    leads = Lead.objects.select_related('store', 'product').order_by('-created_at')
    stores = Store.objects.all()

    store_filter = request.GET.get('store')
    status_filter = request.GET.get('status')
    search = request.GET.get('q')

    if store_filter:
        leads = leads.filter(store_id=store_filter)
    if status_filter:
        leads = leads.filter(status=status_filter)
    if search:
        leads = leads.filter(
            Q(customer_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(store__name__icontains=search)
        )

    context = {
        'leads': leads,
        'stores': stores,
        'current_store': store_filter,
        'current_status': status_filter,
    }
    return render(request, 'TMS/superadmin/allleads.html', context)

@superuser_required
def export_all_leads(request):
    superadmin_logger.info(f"Superuser {request.user.username} exported all leads CSV")
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tms_all_leads.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Store', 'Customer', 'Phone', 'Product', 'Status', 'Source'])
    
    for lead in Lead.objects.all().order_by('-created_at'):
        writer.writerow([
            lead.created_at.strftime('%d-%m-%Y %H:%M'),
            lead.store.name,
            lead.customer_name,
            lead.phone,
            lead.product.name if lead.product else 'General',
            lead.get_status_display(),
            lead.get_source_display()
        ])
    
    return response

def logout_view(request):
    if request.user.is_authenticated:
        superadmin_logger.info(f"Superuser {request.user.username} logged out")
    logout(request)
    return redirect('home')

@superuser_required
def site_settings(request):
    superadmin_logger.info(f"Superuser {request.user.username} accessed site settings")
    
    settings, created = SiteSettings.objects.get_or_create(pk=1)

    if request.method == 'POST':
        superadmin_logger.info(f"Superuser {request.user.username} submitted site settings form")
        
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings)
        formset = SocialLinkFormSet(request.POST, instance=settings)

        if form.is_valid() and formset.is_valid():
            saved_settings = form.save()
            formset.instance = saved_settings
            formset.save()
            
            superadmin_logger.info(f"Superuser {request.user.username} SUCCESSFULLY updated site settings & social links")
            messages.success(request, "Site settings and social links updated successfully!")
            return redirect('site_settings')
        else:
            superadmin_logger.warning(f"Superuser {request.user.username} site settings validation FAILED")
            if not form.is_valid():
                superadmin_logger.warning(f"Main form errors: {form.errors}")
            if not formset.is_valid():
                superadmin_logger.warning(f"Formset errors: {formset.errors}")
            messages.error(request, "Please fix the errors below.")
    else:
        form = SiteSettingsForm(instance=settings)
        formset = SocialLinkFormSet(instance=settings)

    return render(request, 'TMS/superadmin/site_settings.html', {
        'form': form,
        'formset': formset,
        'site_settings': settings,
    })