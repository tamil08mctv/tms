from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Count, Q
import csv
from datetime import date
from ..models import Store, Lead, StoreAdmin, User
from ..forms import StoreForm, StoreUpdateForm

def superuser_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_superuser, login_url='/')(view_func))

from django.core.paginator import Paginator

@superuser_required
def store_list_super(request):
    store_list = Store.objects.prefetch_related('store_admins__user').all().order_by('-id')
    paginator = Paginator(store_list, 20)  # 20 stores per page
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
def store_list_super(request):
    stores = Store.objects.prefetch_related('store_admins__user').all()
    return render(request, 'TMS/superadmin/store_list.html', {'stores': stores})
@superuser_required
def create_store(request):
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.created_by = request.user
            store.save()

            # Create admin only when creating new store
            username = form.cleaned_data['admin_username']
            password = form.cleaned_data['admin_password']
            if username and password:
                user = User.objects.create_user(username=username, password=password)
                StoreAdmin.objects.create(user=user, store=store)

            messages.success(request, f"Store '{store.name}' created successfully!")
            return redirect('store_list_super')
    else:
        form = StoreForm()  # Blank form

    return render(request, 'TMS/superadmin/createstore.html', {
        'form': form,
        'store': None  # Important: tells template it's create mode
    })

@superuser_required
def edit_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    if request.method == 'POST':
        form = StoreUpdateForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, f"Store '{store.name}' updated successfully!")
            return redirect('store_list_super')
    else:
        form = StoreUpdateForm(instance=store)

    return render(request, 'TMS/superadmin/createstore.html', {
        'form': form,
        'store': store  # Important: tells template it's edit mode
    })


@superuser_required
def toggle_store(request, pk):
    store = get_object_or_404(Store, pk=pk)
    store.is_active = not store.is_active
    store.save()
    status = "activated" if store.is_active else "disabled"
    messages.success(request, f"Store '{store.name}' has been {status}")
    return redirect('store_list_super')


@superuser_required
def all_leads(request):
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
@login_required
def export_all_leads(request):
    if not request.user.is_superuser:
        return redirect('super_dashboard')
    
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
    logout(request)
    return redirect('home')