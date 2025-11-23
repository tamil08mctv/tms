# tms/views/storeadmin.py → FINAL FIXED VERSION
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Q, Count
from ..models import Lead, Product, Store
from ..forms import ProductForm
import csv
from datetime import datetime

@login_required
def store_dashboard(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('super_dashboard')
    
    store = request.user.storeadmin.store
    
    # FIX: Get all leads first, THEN slice
    all_leads = Lead.objects.filter(store=store).order_by('-created_at')
    recent_leads = all_leads[:10]  # ← Now safe to slice
    today_leads = all_leads.filter(created_at__date=datetime.today()).count()
    
    products = Product.objects.filter(store=store)[:8]
    
    stats = {
        'total_leads': all_leads.count(),
        'new_leads': all_leads.filter(status='new').count(),
        'converted': all_leads.filter(status='converted').count(),
        'today': today_leads
    }
    
    return render(request, 'TMS/storeadmin/dashboard.html', {
        'store': store,
        'leads': recent_leads,  # ← Pass sliced version
        'products': products,
        'stats': stats
    })

@login_required
def store_leads(request):
    if not hasattr(request.user, 'storeadmin'): return redirect('super_dashboard')
    store = request.user.storeadmin.store
    leads = Lead.objects.filter(store=store)
    
    status = request.GET.get('status')
    source = request.GET.get('source')
    search = request.GET.get('search')
    
    if status: leads = leads.filter(status=status)
    if source: leads = leads.filter(source=source)
    if search: leads = leads.filter(Q(customer_name__icontains=search) | Q(phone__icontains=search))
    
    return render(request, 'TMS/storeadmin/leads.html', {'leads': leads, 'store': store})

@login_required
def update_lead(request, lead_id, status):
    lead = get_object_or_404(Lead, id=lead_id, store=request.user.storeadmin.store)
    lead.status = status
    lead.save()
    return redirect('store_leads')

@login_required
def store_products(request):
    store = request.user.storeadmin.store
    products = Product.objects.filter(store=store)
    form = ProductForm(request.POST or None, request.FILES or None)
    
    if form.is_valid():
        product = form.save(commit=False)
        product.store = store
        product.save()
        return redirect('store_products')
    
    return render(request, 'TMS/storeadmin/products.html', {
        'products': products, 'form': form, 'store': store
    })

@login_required
def export_leads_csv(request):
    store = request.user.storeadmin.store
    leads = Lead.objects.filter(store=store)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{store.name}_leads_{datetime.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Name', 'Phone', 'Product', 'Status', 'Source', 'Message'])
    for lead in leads:
        writer.writerow([lead.created_at, lead.customer_name, lead.phone, 
                        lead.product.name if lead.product else '', lead.status, lead.source, lead.message])
    return response