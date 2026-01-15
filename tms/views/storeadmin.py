# tms/views/storeadmin.py → FINAL VERSION WITH PROFESSIONAL LOGGING
import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from ..models import Lead, Product, Store, StoreBanner, ProductImage, Category, ProductSpecification
from ..forms import ProductForm, ProductSpecFormSet, VariantAttributeFormSet,StoreBannerForm,CategoryForm,ProductVariantForm, get_variant_value_formset, VariantSpecFormSet
import csv
from datetime import datetime, date
from django.forms import inlineformset_factory
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import JsonResponse
from django.db.models import Min, Q
from django.db import ProgrammingError
from ..models import (
    Product, ProductImage, ProductSpecification,
    Category, VariantAttribute, ProductVariant, VariantValue,ProductVariantImage
)
from ..forms import (
   ProductForm, ProductSpecFormSet, VariantAttributeFormSet,
    get_variant_value_formset, VariantSpecFormSet
)
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

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


# 1. Products List + Simple Add
@login_required
def store_products(request):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')

    store = request.user.storeadmin.store
    categories = Category.objects.filter(store=store).order_by('name')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        spec_formset = ProductSpecFormSet(request.POST, prefix='spec')

        if form.is_valid() and spec_formset.is_valid():
            try:
                with transaction.atomic():
                    product = form.save(commit=False)
                    product.store = store
                    for field in ['call_for_price', 'is_new_arrival', 'is_best_seller',
                                  'is_limited_deal', 'is_special_offer', 'is_featured', 'in_stock']:
                        setattr(product, field, field in request.POST)
                    product.save()

                    spec_formset.instance = product
                    spec_formset.save()

                    files = request.FILES.getlist('extra_images')
                    if files:
                        for i, f in enumerate(files):
                            img = ProductImage.objects.create(product=product, image=f)
                            if i == 0:
                                img.is_main = True
                                img.save()

                    if 'video' in request.FILES:
                        product.video = request.FILES['video']
                        product.save()

                messages.success(request, f"Product '{product.name}' added successfully!")
                return redirect('store_products')
            except Exception as e:
                storeadmin_logger.error(f"Error adding product: {e}", exc_info=True)
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = ProductForm()
        spec_formset = ProductSpecFormSet(prefix='spec')
        form.fields['category'].queryset = categories

    today = date.today()
    products_qs = Product.objects.filter(store=store) \
        .select_related('category') \
        .prefetch_related(
            Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_main=True).only('image'),
                to_attr='main_image_cached'
            ),
            'variants'  # For variable products
        ) \
        .annotate(
            min_variant_price=Min('variants__offer_price', filter=Q(variants__offer_price__isnull=False)) or
                             Min('variants__regular_price')
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
        price_match = re.search(r'(under|below|less than|upto|budget)\s*&#8377;?([\d,]+)', q)
        if price_match:
            max_price = int(price_match.group(2).replace(',', ''))
            products_qs = products_qs.filter(
                Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price) |
                Q(min_variant_price__lte=max_price)
            )
            applied_filters.append(f"Under &#8377;{max_price:,}")
        elif q.replace(',', '').isdigit():
            number = int(q.replace(',', ''))
            max_price = number * 1000
            products_qs = products_qs.filter(
                Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price) |
                Q(min_variant_price__lte=max_price)
            )
            applied_filters.append(f"Under &#8377{number:,}000")
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
                            Prefetch('images', queryset=ProductImage.objects.filter(is_main=True).only('image'), to_attr='main_image_cached'),
                            'variants'
                        )

    category_name = request.GET.get('category', '')
    if category_name:
        products_qs = products_qs.filter(category__name__iexact=category_name)

    paginator = Paginator(products_qs, 20)
    page_number = request.GET.get('page', 1)
    products = paginator.get_page(page_number)

    # Add dynamic properties for template
    for p in products:
        p.has_variants = p.variant_attributes.exists()
        if p.has_variants:
            min_price = p.variants.aggregate(min_price=Min('offer_price') or Min('regular_price'))['min_price']
            p.display_price = f"From &#8377; {int(min_price):,}" if min_price else "Price on variants"
        else:
            p.display_price = f"&#8377; {int(p.offer_price or p.regular_price):,}" if p.regular_price else "Call for Price"

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

# 2. Edit Basic Product Info
@login_required
def edit_product(request, pk):
    if not hasattr(request.user, 'storeadmin'):
        return redirect('login')

    store = request.user.storeadmin.store
    product = get_object_or_404(Product, pk=pk, store=store)
    has_variants = product.variant_attributes.exists()

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, has_variants=has_variants)
        spec_formset = ProductSpecFormSet(request.POST, instance=product, prefix='spec')

        if form.is_valid() and spec_formset.is_valid():
            try:
                with transaction.atomic():
                    product = form.save(commit=False)

                    # Handle boolean flags properly
                    for field in ['call_for_price', 'is_new_arrival', 'is_best_seller',
                                  'is_limited_deal', 'is_special_offer', 'is_featured', 'in_stock']:
                        setattr(product, field, field in request.POST)

                    # Only save pricing fields when NO variants
                    if not has_variants:
                        product.regular_price = form.cleaned_data.get('regular_price')
                        product.offer_price = form.cleaned_data.get('offer_price')
                        product.deal_end_date = form.cleaned_data.get('deal_end_date')
                    else:
                        # When variants exist → clear top-level pricing
                        product.regular_price = None
                        product.offer_price = None
                        product.deal_end_date = None

                    # Handle video replacement
                    if 'video' in request.FILES:
                        if product.video:
                            product.video.delete(save=False)
                        product.video = request.FILES['video']

                    product.save()
                    spec_formset.save()

                    # Handle extra images (non-variant case)
                    if not has_variants and 'extra_images' in request.FILES:
                        files = request.FILES.getlist('extra_images')
                        has_main = product.images.filter(is_main=True).exists()
                        for i, f in enumerate(files):
                            img = ProductImage.objects.create(product=product, image=f)
                            if i == 0 and not has_main:
                                img.is_main = True
                                img.save()

                    # Handle multi-delete
                    if 'delete_selected_images' in request.POST:
                        selected_ids = request.POST.getlist('selected_images')
                        if selected_ids:
                            ProductImage.objects.filter(product=product, id__in=selected_ids).delete()
                            messages.success(request, f"{len(selected_ids)} image(s) deleted!")

                    # Handle set main image
                    if 'set_main_image' in request.POST:
                        img_id = request.POST.get('set_main_image')
                        try:
                            img = ProductImage.objects.get(product=product, id=img_id)
                            product.images.update(is_main=False)
                            img.is_main = True
                            img.save()
                            messages.success(request, "Main image updated!")
                        except ProductImage.DoesNotExist:
                            messages.error(request, "Image not found.")

                messages.success(request, "Product updated successfully!")
                return redirect(f"{reverse('edit_product', kwargs={'pk': pk})}?t={timezone.now().timestamp()}")

            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Please correct the form errors below.")

    else:
        form = ProductForm(instance=product, has_variants=has_variants)
        spec_formset = ProductSpecFormSet(instance=product, prefix='spec')
        form.fields['category'].queryset = Category.objects.filter(store=store)

    context = {
        'product': product,
        'form': form,
        'spec_formset': spec_formset,
        'has_variants': has_variants,
    }
    return render(request, 'TMS/storeadmin/edit_product.html', context)

# 3. Manage Variants (Types + List)
@login_required
def manage_variants(request, product_id):
    product = get_object_or_404(Product, id=product_id, store=request.user.storeadmin.store)

    if request.method == 'POST':
        attr_formset = VariantAttributeFormSet(request.POST, instance=product, prefix='attr')

        if 'save_types' in request.POST:
            if attr_formset.is_valid():
                attr_formset.save()
                messages.success(request, "Variant types saved successfully!")
            else:
                messages.error(request, "Please correct variant type errors.")

        # Handle variant deletion
        elif 'delete_selected_variants' in request.POST or 'delete_variant' in request.POST:
            selected_ids = request.POST.getlist('selected_variants') if 'delete_selected_variants' in request.POST else [request.POST.get('delete_variant')]
            if selected_ids and any(selected_ids):
                deleted_count = ProductVariant.objects.filter(
                    product=product, id__in=selected_ids
                ).delete()[0]  # [0] returns number of deleted objects
                messages.success(request, f"{deleted_count} variant(s) deleted successfully!")
            else:
                messages.warning(request, "No variants selected for deletion.")

        elif 'generate_variants' in request.POST:
            if attr_formset.is_valid():
                attr_formset.save()

                # Collect values from textareas
                attributes = product.variant_attributes.all()
                value_dict = {}

                for attr in attributes:
                    field_name = f'values_{attr_formset.prefix}-{attr.id}' if attr.id else f'values_attr-{attr.pk or "new"}'
                    values_text = request.POST.get(field_name, '').strip()
                    if values_text:
                        value_dict[attr] = [v.strip() for v in values_text.split('\n') if v.strip()]

                if not value_dict:
                    messages.warning(request, "No values entered for any type.")
                    return redirect('manage_variants', product_id=product_id)

                # Generate all combinations (Cartesian product)
                from itertools import product
                attr_list = list(value_dict.keys())
                value_combos = product(*(value_dict[attr] for attr in attr_list))

                created_count = 0
                for combo in value_combos:
                    variant = ProductVariant.objects.create(product=product)
                    for attr, val in zip(attr_list, combo):
                        VariantValue.objects.create(
                            variant=variant,
                            attribute=attr,
                            value=val
                        )
                    created_count += 1

                messages.success(request, f"Successfully generated {created_count} new variants!")
            else:
                messages.error(request, "Please save valid variant types first.")

        return redirect('manage_variants', product_id=product_id)

    attr_formset = VariantAttributeFormSet(instance=product, prefix='attr')

    context = {
        'product': product,
        'attr_formset': attr_formset,
        'variants': product.variants.all().order_by('created_at'),
    }
    return render(request, 'TMS/storeadmin/manage_variants.html', context)

# 4. Edit / Add Single Variant (with populated dropdowns)@login_required
@login_required
def edit_variant(request, product_id, variant_id=0):
    product = get_object_or_404(Product, id=product_id, store=request.user.storeadmin.store)

    if variant_id == 0:
        variant = None
    else:
        variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

    if request.method == 'POST':
        form = ProductVariantForm(request.POST, request.FILES, instance=variant) if variant else ProductVariantForm(request.POST, request.FILES)

        value_formset = get_variant_value_formset(product=product)(
            request.POST, instance=variant or ProductVariant(), prefix='val'
        )
        spec_formset = VariantSpecFormSet(
            request.POST, instance=variant or ProductVariant(), prefix='vspec'
        )

        if all([form.is_valid(), value_formset.is_valid(), spec_formset.is_valid()]):
            try:
                with transaction.atomic():
                    if not variant:
                        variant = form.save(commit=False)
                        variant.product = product
                    variant = form.save()

                    value_formset.instance = variant
                    value_formset.save()

                    spec_formset.instance = variant
                    spec_formset.save()

                    # Handle new main image (single file)
                    if 'image' in request.FILES:
                        variant.image = request.FILES['image']
                        variant.save(update_fields=['image'])

                    # Handle extra images
                    files = request.FILES.getlist('extra_images')
                    if files:
                        has_main = variant.images.filter(is_main=True).exists()
                        for i, f in enumerate(files):
                            img = ProductVariantImage.objects.create(variant=variant, image=f)
                            if i == 0 and not has_main:
                                img.is_main = True
                                img.save()
                                variant.image = img.image
                                variant.save(update_fields=['image'])

                    # Handle deletes
                    deleted = False

                    if 'delete_selected_images' in request.POST:
                        selected_ids = request.POST.getlist('selected_images')
                        if selected_ids:
                            ProductVariantImage.objects.filter(
                                variant=variant, id__in=selected_ids
                            ).delete()
                            deleted = True
                            messages.success(request, f"{len(selected_ids)} image(s) deleted!")

                    if 'delete_image' in request.POST:
                        img_id = request.POST.get('delete_image')
                        if img_id:
                            try:
                                img = ProductVariantImage.objects.get(variant=variant, id=img_id)
                                img.delete()
                                deleted = True
                                messages.success(request, "Image deleted!")
                            except ProductVariantImage.DoesNotExist:
                                messages.error(request, "Image not found.")

                    if deleted:
                        if variant.image and not variant.images.filter(image=variant.image).exists():
                            variant.image = None
                            variant.save(update_fields=['image'])

                    if deleted and not variant.images.filter(is_main=True).exists() and variant.images.exists():
                        first_img = variant.images.first()
                        first_img.is_main = True
                        first_img.save()
                        variant.image = first_img.image
                        variant.save(update_fields=['image'])

                messages.success(request, "Variant updated successfully!")
                return redirect('edit_variant', product_id=product.id, variant_id=variant.id)

            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Please correct the form errors.")

    else:
        form = ProductVariantForm(instance=variant) if variant else ProductVariantForm()
        value_formset = get_variant_value_formset(product=product)(
            instance=variant or ProductVariant(), prefix='val'
        )
        spec_formset = VariantSpecFormSet(
            instance=variant or ProductVariant(), prefix='vspec'
        )

    context = {
        'variant': variant,
        'product': product,
        'form': form,
        'value_formset': value_formset,
        'spec_formset': spec_formset,
        'is_new': variant is None,
    }
    return render(request, 'TMS/storeadmin/edit_variant.html', context)

# 5. Delete Product
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

    # Base query - select_related for product
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

    # Search - now also searches in product_display_name
    if search:
        leads_qs = leads_qs.filter(
            Q(customer_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(city__icontains=search) |
            Q(product__name__icontains=search) |
            Q(product_display_name__icontains=search)
        )

    # Preserve query params for pagination & export
    page_params = request.GET.copy()
    if 'page' in page_params:
        del page_params['page']
    page_params_str = page_params.urlencode()

    # Pagination - 100 leads per page
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

            # Clear dashboard cache
            cache.delete(f"dashboard_{lead.store.id}")

            storeadmin_logger.info(
                f"Lead status updated: {old_status} → {lead.get_status_display()} | "
                f"Lead ID: {lead.id} | Customer: {lead.customer_name} | "
                f"Product: {lead.product_display_name or 'N/A'} | "
                f"Store: {lead.store.name} | User: {request.user.username}"
            )

            messages.success(request, f"Lead status updated to {lead.get_status_display()}!")

    return redirect('store_leads')


@login_required
def export_leads_csv(request):
    store = request.user.storeadmin.store

    leads = Lead.objects.filter(store=store).order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{store.slug}_leads_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Date (IST)',
        'Customer Name',
        'Phone',
        'City',
        'Product (with Variant if any)',
        'Status',
        'Source',
        'Notes'
    ])

    for lead in leads:
        writer.writerow([
            lead.created_at_ist(),
            lead.customer_name,
            lead.phone,
            lead.city or '-',
            lead.product_display_name or (lead.product.name if lead.product else 'General Enquiry'),
            lead.get_status_display(),
            lead.source,
            lead.notes or '-'
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