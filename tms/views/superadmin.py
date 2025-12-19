# tms/views/superadmin.py → FINAL 100% WORKING VERSION (WITH all_leads!)

import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Count, Q
import csv
from django.utils import timezone
from datetime import datetime
from dateutil.relativedelta import relativedelta

from ..models import Store, Lead, StoreAdmin, User, SiteSettings, SocialLink
from ..forms import StoreForm, StoreUpdateForm, SiteSettingsForm, SocialLinkFormSet

superadmin_logger = logging.getLogger('superadmin')

def superuser_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_superuser, login_url='/')(view_func))

from django.core.paginator import Paginator

@superuser_required
def store_list_super(request):
    
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
    
    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - relativedelta(months=1))
    last_month_end = this_month_start - timezone.timedelta(seconds=1)

    this_month_leads = Lead.objects.filter(created_at__gte=this_month_start).count()
    this_month_converted = Lead.objects.filter(created_at__gte=this_month_start, status='converted').count()

    last_month_leads = Lead.objects.filter(created_at__range=[last_month_start, last_month_end]).count()
    last_month_converted = Lead.objects.filter(created_at__range=[last_month_start, last_month_end], status='converted').count()

    leads_growth = round(((this_month_leads - last_month_leads) / last_month_leads * 100), 1) if last_month_leads else 100
    converted_growth = round(((this_month_converted - last_month_converted) / last_month_converted * 100), 1) if last_month_converted else 100

    context = {
        'total_stores': Store.objects.count(),
        'total_leads': Lead.objects.count(),
        'converted': Lead.objects.filter(status='converted').count(),
        'pending': Lead.objects.filter(status='new').count(),

        'this_month_leads': this_month_leads,
        'leads_growth': leads_growth,
        'this_month_converted': this_month_converted,
        'converted_growth': converted_growth,

        'top_stores': Store.objects.annotate(lead_count=Count('leads')).order_by('-lead_count')[:6],
        'recent_leads': Lead.objects.select_related('store', 'product').order_by('-created_at')[:15],
    }
    return render(request, 'TMS/superadmin/dashboard.html', context)

@superuser_required
def create_store(request):
    
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

            superadmin_logger.info(f"Superuser {request.user.username} CREATED store: '{store.name}' ({store.city})")
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
    
    if request.method == 'POST':
        form = StoreUpdateForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()
            superadmin_logger.info(f"Superuser {request.user.username} UPDATED store: '{store.name}'")
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
    
    superadmin_logger.info(f"Superuser {request.user.username} toggled store: '{store.name}' → {'Active' if store.is_active else 'Inactive'}")
    messages.success(request, f"Store '{store.name}' is now {'activated' if store.is_active else 'deactivated'}")
    return redirect('store_list_super')

# ← THIS WAS MISSING! ADD THIS FUNCTION
@superuser_required
def all_leads(request):
    
    leads = Lead.objects.select_related('store', 'product').order_by('-created_at')
    stores = Store.objects.all()

    store_filter = request.GET.get('store')
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    status_filter = request.GET.get('status')

    if store_filter:
        leads = leads.filter(store_id=store_filter)
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d')
            leads = leads.filter(created_at__date__gte=from_dt.date())
        except:
            pass
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d')
            leads = leads.filter(created_at__date__lte=to_dt.date())
        except:
            pass
    if status_filter:
        leads = leads.filter(status=status_filter)

    context = {
        'leads': leads,
        'stores': stores,
        'current_store': store_filter,
        'from_date': from_date,
        'to_date': to_date,
        'current_status': status_filter,
    }
    return render(request, 'TMS/superadmin/allleads.html', context)

@superuser_required
def export_all_leads(request):
    superadmin_logger.info(f"Superuser {request.user.username} exported filtered leads CSV")
    
    leads = Lead.objects.select_related('store', 'product').order_by('-created_at')
    
    store_filter = request.GET.get('store')
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')
    status_filter = request.GET.get('status')

    if store_filter:
        leads = leads.filter(store_id=store_filter)
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d')
            leads = leads.filter(created_at__date__gte=from_dt.date())
        except:
            pass
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d')
            leads = leads.filter(created_at__date__lte=to_dt.date())
        except:
            pass
    if status_filter:
        leads = leads.filter(status=status_filter)

    response = HttpResponse(content_type='text/csv')
    filename = "tms_all_leads"
    if from_date or to_date:
        filename += f"_{from_date or 'start'}_to_{to_date or 'end'}"
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Store', 'Customer', 'Phone', 'Product', 'Status', 'Source'])

    for lead in leads:
        writer.writerow([
            lead.created_at.strftime('%d-%m-%Y %H:%M'),
            lead.store.name,
            lead.customer_name,
            lead.phone,
            lead.product.name if lead.product else 'General',
            lead.get_status_display(),
            lead.source
        ])

    return response

@superuser_required
def site_settings(request):
    
    settings, created = SiteSettings.objects.get_or_create(pk=1)

    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings)
        formset = SocialLinkFormSet(request.POST, instance=settings)

        if form.is_valid() and formset.is_valid():
            saved_settings = form.save()
            formset.instance = saved_settings
            formset.save()
            messages.success(request, "Site settings and social links updated successfully!")
            superadmin_logger.info(f"Superuser {request.user.username} updated site settings")
    
            return redirect('site_settings')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = SiteSettingsForm(instance=settings)
        formset = SocialLinkFormSet(instance=settings)

    return render(request, 'TMS/superadmin/site_settings.html', {
        'form': form,
        'formset': formset,
        'site_settings': settings,
    })

def logout_view(request):
    if request.user.is_authenticated:
        superadmin_logger.info(f"User {request.user.username} logged out")
    logout(request)
    messages.success(request, "You have been logged out successfully!")
    return redirect('login')