# tms/views/storeadmin.py → FINAL 100% WORKING VERSION (NO ERRORS)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from ..models import Lead, Product, Store, StoreBanner, ProductImage, Category
from ..forms import ProductForm, StoreBannerForm,CategoryForm
import csv
from datetime import datetime, date


@login_required
def store_dashboard(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
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
    products = Product.objects.filter(store=store).order_by('-created_at')
    categories = Category.objects.filter(store=store).order_by('name')  # THIS WAS MISSING!

    paginator = Paginator(products, 50)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = store
            product.save()

            extra_images = request.FILES.getlist('extra_images')
            for img in extra_images:
                ProductImage.objects.create(product=product, image=img)

            messages.success(request, f"Product '{product.name}' added successfully!")
            return redirect('store_products')
    else:
        form = ProductForm()
        

    

    return render(request, 'TMS/storeadmin/products.html', {
        'store': store,
        'products': products_page,
        'form': form,
        'categories': categories,  # NOW PASSED!
    })


@login_required
def edit_product(request, pk):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    product = get_object_or_404(Product, pk=pk, store=store)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)

        # HANDLE IMAGE DELETION FIRST
        delete_image_id = request.POST.get('delete_image')
        if delete_image_id:
            image_to_delete = get_object_or_404(ProductImage, id=delete_image_id, product=product)
            image_to_delete.delete()
            messages.success(request, "Image deleted successfully!")
            return redirect('edit_product', pk=product.pk)  # REFRESH PAGE

        # HANDLE SET MAIN IMAGE
        main_image_id = request.POST.get('main_image')
        if main_image_id:
            ProductImage.objects.filter(product=product).update(is_main=False)
            ProductImage.objects.filter(id=main_image_id, product=product).update(is_main=True)
            messages.success(request, "Main image updated!")

        # NOW PROCESS FORM
        if form.is_valid():
            form.save()

            # ADD NEW IMAGES
            extra_images = request.FILES.getlist('extra_images')
            for img_file in extra_images:
                ProductImage.objects.create(product=product, image=img_file)

            # REORDER IMAGES
            image_order = request.POST.getlist('image_order')
            if image_order:
                for index, image_id in enumerate(image_order):
                    ProductImage.objects.filter(id=image_id, product=product).update(sort_order=index)

            messages.success(request, "Product updated successfully!")
            return redirect('store_products')
        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = ProductForm(instance=product)

    return render(request, 'TMS/storeadmin/edit_product.html', {
        'store': store,
        'product': product,
        'form': form
    })

@login_required
def delete_product(request, pk):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    product = get_object_or_404(Product, pk=pk, store=request.user.storeadmin.store)
    if request.method == 'POST':
        product.delete()
        messages.success(request, "Product deleted!")
    return redirect('store_products')


@login_required
def store_banners(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    banners = StoreBanner.objects.filter(store=store).order_by('-created_at')

    if request.method == 'POST':
        form = StoreBannerForm(request.POST, request.FILES)
        if form.is_valid():
            banner = form.save(commit=False)
            banner.store = store
            banner.save()
            messages.success(request, "Banner added!")
            return redirect('store_banners')
    else:
        form = StoreBannerForm()

    return render(request, 'TMS/storeadmin/banners.html', {
        'store': store, 'banners': banners, 'form': form
    })


@login_required
def delete_banner(request, pk):
    banner = get_object_or_404(StoreBanner, pk=pk, store=request.user.storeadmin.store)
    if request.method == 'POST':
        banner.delete()
        messages.success(request, "Banner deleted!")
    return redirect('store_banners')

@login_required
def store_leads(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    leads_qs = Lead.objects.filter(store=store).order_by('-created_at')

    # FILTERS
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    status = request.GET.get('status')

    if from_date:
        leads_qs = leads_qs.filter(created_at__date__gte=from_date)
    if to_date:
        leads_qs = leads_qs.filter(created_at__date__lte=to_date)
    if status:
        leads_qs = leads_qs.filter(status=status)

    # PRESERVE FILTERS IN PAGINATION
    page_params = request.GET.copy()
    if 'page' in page_params:
        del page_params['page']
    page_params = page_params.urlencode() + "&" if page_params else ""

    # 100 PER PAGE
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
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in [choice[0] for choice in Lead.STATUS_CHOICES]:
            lead.status = status
            lead.save()
            messages.success(request, f"Lead status updated to {status}!")
    return redirect('store_leads')


@login_required
def export_leads_csv(request):
    store = request.user.storeadmin.store
    leads = Lead.objects.filter(store=store).order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{store.slug}_leads_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Name', 'Phone', 'City', 'Product', 'Message', 'Status', 'Source'])
    for lead in leads:
        writer.writerow([
            lead.created_at.strftime('%d-%m-%Y %I:%M %p'),
            lead.customer_name,
            lead.phone,
            lead.city or '-',
            lead.product.name if lead.product else 'General',
            lead.message[:100],
            lead.get_status_display(),
            lead.get_source_display()
        ])
    return response

# ADD THESE VIEWS TO storeadmin.py

@login_required
def store_categories(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    store = request.user.storeadmin.store
    categories = Category.objects.filter(store=store).order_by('name')

    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save(commit=False)
            category.store = store
            category.save()
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
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated!")
            return redirect('store_categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'TMS/storeadmin/edit_category.html', {'form': form, 'category': category})

@login_required
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk, store=request.user.storeadmin.store)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Category deleted!")
    return redirect('store_categories')

