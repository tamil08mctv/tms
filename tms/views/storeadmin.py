# tms/views/storeadmin.py → FINAL VERSION WITH PROFESSIONAL LOGGING
import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from ..models import Lead, Product, Store, StoreBanner, ProductImage, Category, ProductSpecification
from ..forms import ProductForm, StoreBannerForm, CategoryForm
import csv
from datetime import datetime, date
from django.forms import inlineformset_factory

# Logger for storeadmin actions
storeadmin_logger = logging.getLogger('storeadmin')

@login_required
def store_dashboard(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    storeadmin_logger.info(f"Dashboard accessed | Store: {store.name} | User: {request.user.username} | IP: {client_ip}")
    
    today = date.today()

    total_leads = Lead.objects.filter(store=store).count()
    today_leads = Lead.objects.filter(store=store, created_at__date=today).count()
    new_leads = Lead.objects.filter(store=store, status='new').count()
    converted = Lead.objects.filter(store=store, status='converted').count()
    
    recent_leads = Lead.objects.filter(store=store).order_by('-created_at')[:10]
    recent_products = Product.objects.filter(store=store).order_by('-created_at')[:6]

    context = {
        'store': store,
        'total_leads': total_leads,
        'today_leads': today_leads,
        'new_leads': new_leads,
        'converted': converted,
        'recent_leads': recent_leads,
        'recent_products': recent_products,
    }
    return render(request, 'TMS/storeadmin/dashboard.html', context)


@login_required
def store_products(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    storeadmin_logger.info(f"Products page accessed | Store: {store.name} | User: {request.user.username} | IP: {client_ip}")

    products = Product.objects.filter(store=store).order_by('-created_at')
    categories = Category.objects.filter(store=store).order_by('name')

    paginator = Paginator(products, 50)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)

    ProductSpecFormSet = inlineformset_factory(
        Product, ProductSpecification,
        fields=('name', 'value'),
        extra=3,
        can_delete=True
    )
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        spec_formset = ProductSpecFormSet(request.POST)

        if form.is_valid() and spec_formset.is_valid():
            product = form.save(commit=False)
            product.store = store

            product.call_for_price = 'call_for_price' in request.POST
            product.is_limited_stock = 'is_limited_stock' in request.POST
            product.is_new_arrival = 'is_new_arrival' in request.POST
            product.save()

            spec_formset.instance = product
            spec_formset.save()

            extra_images = request.FILES.getlist('extra_images')
            for img in extra_images:
                ProductImage.objects.create(product=product, image=img)

            storeadmin_logger.info(f"Product ADDED: '{product.name}' | Store: {store.name} | User: {request.user.username} | IP: {client_ip}")
            messages.success(request, f"Product '{product.name}' added successfully!")
            return redirect('store_products')
    else:
        form = ProductForm()
        spec_formset = ProductSpecFormSet()
        
    return render(request, 'TMS/storeadmin/products.html', {
        'store': store,
        'products': products_page,
        'form': form,
        'categories': categories,
        'spec_formset': spec_formset,
    })


@login_required
def edit_product(request, pk):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    product = get_object_or_404(Product, pk=pk, store=store)
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    storeadmin_logger.info(f"Edit product accessed: '{product.name}' | Store: {store.name} | User: {request.user.username}")

    ProductSpecFormSet = inlineformset_factory(
        Product, ProductSpecification,
        fields=('name', 'value'),
        extra=1,
        can_delete=True
    )

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        spec_formset = ProductSpecFormSet(request.POST, instance=product)

        delete_image_id = request.POST.get('delete_image')
        if delete_image_id:
            image_to_delete = get_object_or_404(ProductImage, id=delete_image_id, product=product)
            image_to_delete.delete()
            storeadmin_logger.info(f"Image DELETED from product '{product.name}' | Store: {store.name} | User: {request.user.username}")
            messages.success(request, "Image deleted successfully!")
            return redirect('edit_product', pk=product.pk)

        main_image_id = request.POST.get('main_image')
        if main_image_id:
            ProductImage.objects.filter(product=product).update(is_main=False)
            ProductImage.objects.filter(id=main_image_id, product=product).update(is_main=True)
            storeadmin_logger.info(f"Main image updated for '{product.name}' | Store: {store.name} | User: {request.user.username}")
            messages.success(request, "Main image updated!")

        if form.is_valid() and spec_formset.is_valid():
            product.call_for_price = 'call_for_price' in request.POST
            product.is_limited_stock = 'is_limited_stock' in request.POST
            product.is_new_arrival = 'is_new_arrival' in request.POST
            product.is_best_seller = 'is_best_seller' in request.POST
            product.is_limited_deal = 'is_limited_deal' in request.POST
            product.is_special_offer = 'is_special_offer' in request.POST
     
            form.save()
            spec_formset.save()

            extra_images = request.FILES.getlist('extra_images')
            for img_file in extra_images:
                ProductImage.objects.create(product=product, image=img_file)

            image_order = request.POST.getlist('image_order')
            if image_order:
                for index, image_id in enumerate(image_order):
                    ProductImage.objects.filter(id=image_id, product=product).update(sort_order=index)

            storeadmin_logger.info(f"Product UPDATED: '{product.name}' | Store: {store.name} | User: {request.user.username} | IP: {client_ip}")
            messages.success(request, "Product updated successfully!")
            return redirect('store_products')
        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = ProductForm(instance=product)
        spec_formset = ProductSpecFormSet(instance=product)

    return render(request, 'TMS/storeadmin/edit_product.html', {
        'store': store,
        'product': product,
        'form': form,
        'spec_formset': spec_formset,
    })


@login_required
def delete_product(request, pk):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    product = get_object_or_404(Product, pk=pk, store=request.user.storeadmin.store)
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        storeadmin_logger.info(f"Product DELETED: '{product_name}' | Store: {product.store.name} | User: {request.user.username} | IP: {client_ip}")
        messages.success(request, f"Product '{product_name}' deleted!")
    return redirect('store_products')


@login_required
def store_banners(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    storeadmin_logger.info(f"Banners page accessed | Store: {store.name} | User: {request.user.username}")

    banners = StoreBanner.objects.filter(store=store).order_by('order', '-created_at')

    if request.method == 'POST' and 'add_banner' in request.POST:
        form = StoreBannerForm(request.POST, request.FILES)
        if form.is_valid():
            banner = form.save(commit=False)
            banner.store = store
            banner.save()
            storeadmin_logger.info(f"Banner ADDED | Store: {store.name} | User: {request.user.username}")
            messages.success(request, "Banner added successfully!")
            return redirect('store_banners')
    else:
        form = StoreBannerForm()

    edit_form = None
    edit_id = request.GET.get('edit')
    if edit_id:
        banner = get_object_or_404(StoreBanner, pk=edit_id, store=store)
        if request.method == 'POST' and 'update_banner' in request.POST:
            edit_form = StoreBannerForm(request.POST, request.FILES, instance=banner)
            if edit_form.is_valid():
                edit_form.save()
                storeadmin_logger.info(f"Banner UPDATED | Store: {store.name} | User: {request.user.username}")
                messages.success(request, "Banner updated!")
                return redirect('store_banners')
        else:
            edit_form = StoreBannerForm(instance=banner)

    if request.GET.get('toggle'):
        banner = get_object_or_404(StoreBanner, pk=request.GET['toggle'], store=store)
        old_status = "Active" if banner.is_active else "Inactive"
        banner.is_active = not banner.is_active
        banner.save()
        storeadmin_logger.info(f"Banner status toggled: {old_status} → {'Active' if banner.is_active else 'Inactive'} | Store: {store.name} | User: {request.user.username}")
        messages.success(request, "Status changed!")
        return redirect('store_banners')

    if request.method == 'POST' and 'delete_banner' in request.POST:
        banner = get_object_or_404(StoreBanner, pk=request.POST['delete_banner'], store=store)
        banner.delete()
        storeadmin_logger.info(f"Banner DELETED | Store: {store.name} | User: {request.user.username}")
        messages.success(request, "Banner deleted!")
        return redirect('store_banners')

    context = {
        'store': store,
        'banners': banners,
        'form': form,
        'edit_form': edit_form,
        'edit_id': edit_id,
    }
    return render(request, 'TMS/storeadmin/banners.html', context)


@login_required
def store_leads(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    storeadmin_logger.info(f"Leads page accessed | Store: {store.name} | User: {request.user.username} | IP: {client_ip}")

    leads_qs = Lead.objects.filter(store=store).order_by('-created_at')

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    status = request.GET.get('status')

    if from_date:
        leads_qs = leads_qs.filter(created_at__date__gte=from_date)
    if to_date:
        leads_qs = leads_qs.filter(created_at__date__lte=to_date)
    if status:
        leads_qs = leads_qs.filter(status=status)

    page_params = request.GET.copy()
    if 'page' in page_params:
        del page_params['page']
    page_params = page_params.urlencode() + "&" if page_params else ""

    paginator = Paginator(leads_qs, 100)
    page = request.GET.get('page')
    leads = paginator.get_page(page)

    return render(request, 'TMS/storeadmin/leads.html', {
        'store': store,
        'leads': leads,
        'lead_status_choices': Lead.STATUS_CHOICES,
        'page_params': page_params,
    })


@login_required
def update_lead_status(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id, store=request.user.storeadmin.store)
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    if request.method == 'POST':
        old_status = lead.get_status_display()
        status = request.POST.get('status')
        if status in [choice[0] for choice in Lead.STATUS_CHOICES]:
            lead.status = status
            lead.save()
            storeadmin_logger.info(f"Lead status updated: {old_status} → {lead.get_status_display()} | Lead ID: {lead.id} | Customer: {lead.customer_name} | Store: {lead.store.name} | User: {request.user.username}")
            messages.success(request, f"Lead status updated to {status}!")
    return redirect('store_leads')


@login_required
def export_leads_csv(request):
    store = request.user.storeadmin.store
    
    leads = Lead.objects.filter(store=store).order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{store.slug}_leads.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Name', 'Phone', 'City', 'Product', 'Status', 'Source'])
    for lead in leads:
        writer.writerow([
            lead.created_at.strftime('%d-%m-%Y %I:%M %p'),
            lead.customer_name,
            lead.phone,
            lead.city or '-',
            lead.product.name if lead.product else 'General',
            lead.get_status_display(),
            lead.source  # ← Fixed
        ])
    return response

@login_required
def store_categories(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    storeadmin_logger.info(f"Categories page accessed | Store: {store.name} | User: {request.user.username}")

    categories = Category.objects.filter(store=store).order_by('name')

    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save(commit=False)
            category.store = store
            category.save()
            storeadmin_logger.info(f"Category ADDED: '{category.name}' | Store: {store.name} | User: {request.user.username}")
            messages.success(request, f"Category '{category.name}' added!")
            return redirect('store_categories')
    else:
        form = CategoryForm()

    return render(request, 'TMS/storeadmin/categories.html', {
        'store': store,
        'categories': categories,
        'form': form
    })


@login_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk, store=request.user.storeadmin.store)
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    storeadmin_logger.info(f"Edit category accessed: '{category.name}' | Store: {category.store.name} | User: {request.user.username}")

    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            storeadmin_logger.info(f"Category UPDATED: '{category.name}' | Store: {category.store.name} | User: {request.user.username}")
            messages.success(request, "Category updated!")
            return redirect('store_categories')
    else:
        form = CategoryForm(instance=category)
    
    return render(request, 'TMS/storeadmin/edit_category.html', {'form': form, 'category': category})


@login_required
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk, store=request.user.storeadmin.store)
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        storeadmin_logger.info(f"Category DELETED: '{category_name}' | Store: {category.store.name} | User: {request.user.username} | IP: {client_ip}")
        messages.success(request, "Category deleted!")
    return redirect('store_categories')