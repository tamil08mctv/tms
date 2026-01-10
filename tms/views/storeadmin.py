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
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import JsonResponse
from django.db import ProgrammingError
from ..models import (
    Product, ProductImage, ProductSpecification,
    Category, VariantAttribute, ProductVariant, VariantValue,ProductVariantImage
)
from ..forms import (
   ProductForm, ProductSpecFormSet, VariantAttributeFormSet,
    ProductVariantFormSet, get_variant_value_formset, VariantSpecFormSet
)

# Fixed imports

from django.db.models import Q
from django.db.models.functions import Coalesce
import re
from django.contrib.postgres.search import TrigramSimilarity

# Logger for storeadmin actions
storeadmin_logger = logging.getLogger('storeadmin')

@login_required
def store_dashboard(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    user = request.user.username
    
    # Cache dashboard data (5min, per store)
    cache_key = f"dashboard_{store.id}"
    context = cache.get(cache_key)
    if not context:
        today = date.today()
        total_leads = Lead.objects.filter(store=store).count()
        today_leads = Lead.objects.filter(store=store, created_at__date=today).count()
        new_leads = Lead.objects.filter(store=store, status='new').count()
        converted = Lead.objects.filter(store=store, status='converted').count()
        
        recent_leads = Lead.objects.filter(store=store).select_related('product').order_by('-created_at')[:10]  # FIXED: prefetch
        recent_products = Product.objects.filter(store=store).select_related('category').order_by('-created_at')[:6]  # FIXED: prefetch
        
        context = {
            'store': store,
            'total_leads': total_leads,
            'today_leads': today_leads,
            'new_leads': new_leads,
            'converted': converted,
            'recent_leads': recent_leads,
            'recent_products': recent_products,
        }
        cache.set(cache_key, context, 300)  # 5min cache
        storeadmin_logger.info("Dashboard accessed (cache hit)", extra={'client_ip': client_ip, 'user': user})
    
    return render(request, 'TMS/storeadmin/dashboard.html', context)



@login_required
def store_products(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')

    store = request.user.storeadmin.store
    categories = Category.objects.filter(store=store).order_by('name')

    SpecFormSetFactory = inlineformset_factory(
        Product, ProductSpecification,
        fields=('name', 'value'), extra=3, can_delete=True
    )

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        spec_formset = SpecFormSetFactory(request.POST)

        if form.is_valid() and spec_formset.is_valid():
            product = form.save(commit=False)
            product.store = store
            product.call_for_price = 'call_for_price' in request.POST
            product.is_new_arrival = 'is_new_arrival' in request.POST
            product.is_best_seller = 'is_best_seller' in request.POST
            product.is_limited_deal = 'is_limited_deal' in request.POST
            product.is_special_offer = 'is_special_offer' in request.POST
            product.is_featured = 'is_featured' in request.POST
            product.in_stock = 'in_stock' in request.POST or True
            product.save()

            spec_formset.instance = product
            spec_formset.save()

            extra_images = request.FILES.getlist('extra_images')
            if extra_images:
                ProductImage.objects.filter(product=product).update(is_main=False)
                for i, img in enumerate(extra_images):
                    image_obj = ProductImage.objects.create(product=product, image=img)
                    if i == 0:
                        image_obj.is_main = True
                        image_obj.save()

            messages.success(request, f"Product '{product.name}' added successfully!")
            return redirect('store_products')
    else:
        form = ProductForm()
        spec_formset = SpecFormSetFactory()
        form.fields['category'].queryset = categories

    today = date.today()
    products_qs = Product.objects.filter(store=store) \
        .select_related('category') \
        .prefetch_related(
            Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_main=True).only('image'),
                to_attr='main_image_cached'
            )
        ) \
        .only(
            'id', 'name', 'regular_price', 'offer_price', 'call_for_price',
            'is_best_seller', 'is_special_offer', 'is_limited_deal',
            'is_new_arrival', 'is_featured', 'category__name'
        ) \
        .order_by('name')

    original_q = request.GET.get('search', '').strip().lower()
    applied_filters = []

    if original_q:
        q = original_q
        price_match = re.search(r'(under|below|less than|upto|budget)\s*₹?([\d,]+)', q)
        if price_match:
            max_price = int(price_match.group(2).replace(',', ''))
            products_qs = products_qs.filter(
                Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price)
            )
            applied_filters.append(f"Under ₹{max_price:,}")
        elif q.replace(',', '').isdigit():
            number = int(q.replace(',', ''))
            max_price = number * 1000
            products_qs = products_qs.filter(
                Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price)
            )
            applied_filters.append(f"Under ₹{number:,}000")
        else:
            keyword_applied = False
            for words, field in [
                (['best', 'top', 'popular', 'premium', 'luxury', 'best seller'], 'is_best_seller'),
                (['new', 'new arrival', 'latest'], 'is_new_arrival'),
                (['featured', 'highlight'], 'is_featured'),
                (['offer', 'deal', 'discount', 'sale', 'clearance', 'limited deal', 'limited'], None),
            ]:
                if any(word in q for word in words):
                    if field:
                        products_qs = products_qs.filter(**{field: True})
                    else:
                        products_qs = products_qs.filter(
                            Q(is_special_offer=True) |
                            Q(is_limited_deal=True) |
                            Q(deal_end_date__gte=today)
                        )
                    applied_filters.append("Offers & Deals" if not field else field.replace('is_', '').replace('_', ' ').title())
                    keyword_applied = True

            if not keyword_applied:
                name_matches = products_qs.filter(name__icontains=q)
                if name_matches.exists():
                    products_qs = name_matches
                elif len(q) >= 3:
                    products_qs = Product.objects.filter(store=store) \
                        .annotate(similarity=TrigramSimilarity('name', q)) \
                        .filter(similarity__gt=0.15) \
                        .order_by('-similarity') \
                        .select_related('category') \
                        .prefetch_related(
                            Prefetch('images', queryset=ProductImage.objects.filter(is_main=True).only('image'), to_attr='main_image_cached')
                        )

    category_name = request.GET.get('category', '')
    if category_name:
        products_qs = products_qs.filter(category__name__iexact=category_name)

    paginator = Paginator(products_qs, 102)
    page_number = request.GET.get('page', 1)
    products = paginator.get_page(page_number)

    context = {
        'store': store,
        'products': products,
        'total_count': products.paginator.count,
        'categories': categories,
        'form': form,
        'spec_formset': spec_formset,
        'current_search': original_q,
        'current_category': category_name,
        'applied_filters': applied_filters,
    }
    return render(request, 'TMS/storeadmin/products.html', context)


import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction

@login_required
def edit_product(request, pk):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')

    store = request.user.storeadmin.store
    product = get_object_or_404(Product, pk=pk, store=store)

    logger = logging.getLogger('storeadmin')
    has_variants = product.variant_attributes.exists()

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, has_variants=has_variants)
        spec_formset = ProductSpecFormSet(request.POST, instance=product)
        attr_formset = VariantAttributeFormSet(request.POST, instance=product, prefix='attr')
        variant_formset = ProductVariantFormSet(request.POST, request.FILES, instance=product, prefix='variant')

        # Delete individual variant image
        if 'delete_variant_image' in request.POST:
            img_id = request.POST['delete_variant_image']
            img = get_object_or_404(ProductVariantImage, pk=img_id, variant__product=product)
            variant = img.variant
            was_main = img.is_main
            main_image_name = img.image.name if was_main and img.image else None
            img.delete()
            if was_main and variant.image and variant.image.name == main_image_name:
                variant.image = None
                variant.save()
            messages.success(request, "Variant image deleted.")
            return redirect('edit_product', pk=pk)

        # Set main variant image
        if 'set_main_variant_image' in request.POST:
            img_id = request.POST['set_main_variant_image']
            img = get_object_or_404(ProductVariantImage, pk=img_id, variant__product=product)
            variant = img.variant
            ProductVariantImage.objects.filter(variant=variant).exclude(pk=img.pk).update(is_main=False)
            img.is_main = True
            img.save()
            variant.image = img.image
            variant.save()
            messages.success(request, "Main variant image updated.")
            return redirect('edit_product', pk=pk)

        # Delete selected variant images (multi-select)
        if 'delete_selected_variant_images' in request.POST:
            selected_ids = request.POST.getlist('selected_variant_images')
            if selected_ids:
                images = ProductVariantImage.objects.filter(id__in=selected_ids, variant__product=product)
                main_deleted = images.filter(is_main=True).exists()
                images.delete()
                if main_deleted:
                    for variant_id in set(images.values_list('variant_id', flat=True)):
                        remaining = ProductVariantImage.objects.filter(variant_id=variant_id).first()
                        if remaining:
                            remaining.is_main = True
                            remaining.save()
                            try:
                                variant = ProductVariant.objects.get(id=variant_id)
                                variant.image = remaining.image
                                variant.save()
                            except ProductVariant.DoesNotExist:
                                pass
                messages.success(request, "Selected variant images deleted.")
            return redirect('edit_product', pk=pk)

        # Save variant types only
        if 'save_attributes' in request.POST:
            if attr_formset.is_valid():
                attr_formset.save()
                messages.success(request, "Variant types saved successfully!")
            else:
                messages.error(request, "Error saving variant types.")
            return redirect('edit_product', pk=pk)

        # Full save
        if form.is_valid() and spec_formset.is_valid() and attr_formset.is_valid() and variant_formset.is_valid():
            try:
                with transaction.atomic():
                    # Video
                    if 'video' in request.FILES:
                        if product.video:
                            product.video.delete(save=False)
                        product.video = request.FILES['video']

                    # Booleans
                    product.call_for_price = 'call_for_price' in request.POST
                    product.is_new_arrival = 'is_new_arrival' in request.POST
                    product.is_best_seller = 'is_best_seller' in request.POST
                    product.is_limited_deal = 'is_limited_deal' in request.POST
                    product.is_special_offer = 'is_special_offer' in request.POST
                    product.is_featured = 'is_featured' in request.POST
                    product.in_stock = 'in_stock' in request.POST

                    # Pricing
                    if not has_variants:
                        product.regular_price = form.cleaned_data['regular_price']
                        product.offer_price = form.cleaned_data.get('offer_price')
                        product.deal_end_date = form.cleaned_data.get('deal_end_date')
                    else:
                        product.regular_price = None
                        product.offer_price = None
                        product.deal_end_date = None

                    product.save()

                    spec_formset.save()
                    attr_formset.save()

                    # Save variants
                    variants = variant_formset.save(commit=False)
                    for v in variants:
                        v.product = product
                        v.save()

                    # Nested formsets
                    for vform in variant_formset:
                        if vform.instance.pk and not vform.cleaned_data.get('DELETE', False):
                            prefix = vform.prefix
                            value_fs = get_variant_value_formset(product=product, extra=3)(
                                request.POST, instance=vform.instance, prefix=f'value-{prefix}'
                            )
                            if value_fs.is_valid():
                                value_fs.save()

                            spec_fs = VariantSpecFormSet(
                                request.POST, instance=vform.instance, prefix=f'spec-{prefix}'
                            )
                            if spec_fs.is_valid():
                                spec_fs.save()

                    # Upload variant images – first becomes main if none exists
                    for field_name, files in request.FILES.lists():
                        if not field_name.startswith('variant_extra_images_'):
                            continue

                        variant_id_str = field_name.split('_')[-1]
                        if variant_id_str.startswith('new_'):
                            continue

                        try:
                            variant_id = int(variant_id_str)
                            variant = ProductVariant.objects.get(pk=variant_id, product=product)

                            has_main = ProductVariantImage.objects.filter(variant=variant, is_main=True).exists()
                            for idx, file in enumerate(files):
                                img = ProductVariantImage.objects.create(variant=variant, image=file)
                                if idx == 0 and not has_main:
                                    img.is_main = True
                                    img.save()
                                    variant.image = img.image
                                    variant.save()

                            if len(files) > 0:
                                logger.info(f"Uploaded {len(files)} images to variant {variant_id}")
                        except (ValueError, ProductVariant.DoesNotExist):
                            logger.warning(f"Skipping upload for variant {variant_id_str}")
                        except Exception as e:
                            logger.error(f"Upload error for variant {variant_id_str}: {e}")

                    # Main product extra images (non-variant only)
                    if not has_variants and 'extra_images' in request.FILES:
                        files = request.FILES.getlist('extra_images')
                        has_main = product.images.filter(is_main=True).exists()
                        for i, f in enumerate(files):
                            img = ProductImage.objects.create(product=product, image=f)
                            if not has_main and i == 0:
                                img.is_main = True
                                img.save()

                    messages.success(request, "Product and all variants saved successfully!")
                    return redirect('edit_product', pk=pk)

            except Exception as e:
                logger.error(f"Full save failed: {e}", exc_info=True)
                messages.error(request, f"Error saving product: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form.")

    # GET / failed POST
    form = ProductForm(instance=product, has_variants=has_variants)
    form.fields['category'].queryset = Category.objects.filter(store=store)

    spec_formset = ProductSpecFormSet(instance=product)
    attr_formset = VariantAttributeFormSet(instance=product, prefix='attr')
    variant_formset = ProductVariantFormSet(instance=product, prefix='variant')

    for vform in variant_formset:
        if vform.instance.pk:
            vform.nested_values = get_variant_value_formset(product=product, extra=0)(
                instance=vform.instance, prefix=f'value-{vform.prefix}'
            )
            vform.nested_specs = VariantSpecFormSet(
                instance=vform.instance, prefix=f'spec-{vform.prefix}'
            )

    context = {
        'product': product,
        'form': form,
        'spec_formset': spec_formset,
        'attr_formset': attr_formset,
        'variant_formset': variant_formset,
        'has_variants': has_variants,
    }

    return render(request, 'TMS/storeadmin/edit_product.html', context)

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


from django.http import JsonResponse

@login_required
def store_banners(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')
    
    store = request.user.storeadmin.store
    
    # AJAX Requests
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.POST.get('action')

        # Toggle
        if action == 'toggle':
            banner_id = request.POST.get('banner_id')
            banner = get_object_or_404(StoreBanner, pk=banner_id, store=store)
            banner.is_active = not banner.is_active
            banner.save()
            return JsonResponse({
                'success': True,
                'is_active': banner.is_active,
                'text': 'ACTIVE' if banner.is_active else 'INACTIVE',
                'btn_class': 'btn-success' if banner.is_active else 'btn-secondary'
            })

        # Add
        if action == 'add':
            form = StoreBannerForm(request.POST, request.FILES)
            if form.is_valid():
                banner = form.save(commit=False)
                banner.store = store
                banner.save()
                return JsonResponse({'success': True, 'banner_id': banner.id})
            return JsonResponse({'success': False, 'errors': form.errors})

        # Update
        if action == 'update':
            banner_id = request.POST.get('banner_id')
            banner = get_object_or_404(StoreBanner, pk=banner_id, store=store)
            form = StoreBannerForm(request.POST, request.FILES, instance=banner)
            if form.is_valid():
                form.save()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'errors': form.errors})

        # Delete
        if action == 'delete':
            banner_id = request.POST.get('banner_id')
            banner = get_object_or_404(StoreBanner, pk=banner_id, store=store)
            banner.delete()
            return JsonResponse({'success': True})

    # Normal Render
    banners_qs = StoreBanner.objects.filter(store=store).order_by('order', '-created_at')
    paginator = Paginator(banners_qs, 12)
    banners = paginator.get_page(request.GET.get('page', 1))

    form = StoreBannerForm()

    edit_form = None
    edit_id = request.GET.get('edit')
    if edit_id:
        banner = get_object_or_404(StoreBanner, pk=edit_id, store=store)
        edit_form = StoreBannerForm(instance=banner)

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
    
    # Base query with select_related for performance
    leads_qs = Lead.objects.filter(store=store)\
        .select_related('product')\
        .order_by('-created_at')

    # Filters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    status = request.GET.get('status')
    search = request.GET.get('search', '').strip()

    if from_date:
        leads_qs = leads_qs.filter(created_at__date__gte=from_date)
    if to_date:
        leads_qs = leads_qs.filter(created_at__date__lte=to_date)
    if status:
        leads_qs = leads_qs.filter(status=status)

    # Server-side search
    if search:
        leads_qs = leads_qs.filter(
            Q(customer_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(city__icontains=search) |
            Q(product__name__icontains=search)
        )

    # Preserve query params for pagination & export
    page_params = request.GET.copy()
    if 'page' in page_params:
        del page_params['page']
    page_params_str = page_params.urlencode()

    # Pagination - 100 per page
    paginator = Paginator(leads_qs, 100)
    page = request.GET.get('page')
    leads = paginator.get_page(page)

    context = {
        'store': store,
        'leads': leads,
        'lead_status_choices': Lead.STATUS_CHOICES,
        'page_params': page_params_str + "&" if page_params_str else "",
    }
    
    return render(request, 'TMS/storeadmin/leads.html', context)

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

            # ← ADD THIS LINE: Clear dashboard cache instantly
            cache.delete(f"dashboard_{lead.store.id}")
            storeadmin_logger.info(f"Lead status updated: {old_status} to {lead.get_status_display()} | Lead ID: {lead.id} | Customer: {lead.customer_name} | Store: {lead.store.name} | User: {request.user.username}")
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
    
    # Base query
    categories_qs = Category.objects.filter(store=store).order_by('name')

    # Search
    original_q = request.GET.get('search', '').strip()
    q = original_q.lower() if original_q else ''

    if q:
        # Normalize
        normalized_q = re.sub(r'\s+', ' ', q)
        normalized_q = re.sub(r'[^\w\s]', ' ', normalized_q)
        normalized_q = ' '.join(normalized_q.split()).lower()

        # First: fast icontains
        categories_qs = categories_qs.filter(name__icontains=normalized_q)

        # If no results → trigram fallback
        if not categories_qs.exists():
            categories_qs = Category.objects.filter(store=store)\
                .annotate(similarity=TrigramSimilarity('name', normalized_q))\
                .filter(similarity__gt=0.15)\
                .order_by('-similarity')

    # Pagination - 24 per page (perfect for grid)
    paginator = Paginator(categories_qs, 60)
    page_number = request.GET.get('page', 1)
    categories = paginator.get_page(page_number)

    # Form for adding
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

    context = {
        'store': store,
        'categories': categories,
        'form': form,
        'current_search': original_q,
    }
    
    return render(request, 'TMS/storeadmin/categories.html', context)

@login_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk, store=request.user.storeadmin.store)
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    
  
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
    
    # Count products in this category
    product_count = category.product_set.count()
    
    if request.method == 'POST':
        if product_count > 0:
            messages.error(
                request, 
                f"Cannot delete '{category.name}'! It has {product_count} product(s). "
                "Please move all products to another category first."
            )
        else:
            category_name = category.name
            category.delete()
            storeadmin_logger.info(
                f"Category DELETED: '{category_name}' | Store: {category.store.name} | "
                f"User: {request.user.username} | IP: {client_ip}"
            )
            messages.success(request, f"Category '{category_name}' deleted successfully!")
        
        return redirect('store_categories')
    
    # GET request - should not reach here normally, but safe
    return redirect('store_categories')