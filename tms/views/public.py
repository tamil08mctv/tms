from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, F, Exists, OuterRef, Prefetch, Min, Count
from django.core.cache import cache
from django.utils import timezone
from django.utils.timezone import localtime as dj_timezone  # ← Fixed dj_timezone
from django.db.models.functions import Coalesce
from django.contrib.postgres.search import TrigramSimilarity
from django.http import JsonResponse

from ..models import (
    Store, Product, Category, Lead, StoreBanner, SiteSettings,
    ProductSpecification, ProductImage, ProductVariant, ProductVariantImage, VariantValue
)
from ..forms import EnquiryForm

from datetime import date, timedelta
from collections import defaultdict
import re
import logging

public_logger = logging.getLogger('public')

def get_common_context():
    site_settings = SiteSettings.objects.first()
    return {
        'stores_all': Store.objects.filter(is_active=True).order_by('name'),
        'categories_all': Category.objects.all().order_by('name'),
        'site_settings': site_settings,
        'social_links': site_settings.social_links.all() if site_settings else [],
    }

def get_product_display_data(product):
    """
    Returns display-friendly data for product cards/listings.
    - For variant products: uses cheapest variant (prefers in-stock)
    - Images: variant image > variant first extra > product first
    - Now includes discount_percent for badge display in BOTH cases
    """
    has_variants = product.variants.exists()

    if has_variants:
        # Prefer in-stock variants first, then cheapest overall
        cheapest_in_stock = product.variants.filter(in_stock=True).order_by(
            Coalesce('offer_price', 'regular_price')
        ).first()

        cheapest = cheapest_in_stock or product.variants.order_by(
            Coalesce('offer_price', 'regular_price')
        ).first()

        if cheapest:
            price = cheapest.offer_price or cheapest.regular_price
            old_price = cheapest.regular_price if cheapest.offer_price else None

            # Image priority
            main_image = None
            if cheapest.image:
                main_image = cheapest.image.url
            elif cheapest.images.exists():
                main_image = cheapest.images.first().image.url
            elif product.images.exists():
                main_image = product.images.first().image.url

            return {
                'display_price': f"&#8377; {int(price):,}" if price else "Call for Price",
                'main_image': main_image or 'https://via.placeholder.com/300',
                'has_offer': bool(old_price and old_price > price),
                'old_price': old_price,
                'discount_percent': cheapest.discount_percent,  # ← FIXED: Use variant discount
                'in_stock': cheapest.in_stock,
                'has_variants': True,
                'variant_count': product.variants.count(),
            }

    # Non-variant product - FIXED: Now returns discount_percent
    price = product.offer_price or product.regular_price
    return {
        'display_price': f"&#8377{int(price):,}" if price else "Call for Price",
        'main_image': product.images.first().image.url if product.images.exists() else 'https://via.placeholder.com/300',
        'has_offer': bool(product.offer_price and product.offer_price < product.regular_price),
        'old_price': product.regular_price if product.offer_price else None,
        'discount_percent': product.discount_percent,  # ← This was missing → now added!
        'in_stock': product.in_stock,
        'has_variants': False,
    }


def home(request):
    cache_key = 'homepage_data'
    context = cache.get(cache_key)

    if not context:
        today = date.today()
        seven_days_ago = timezone.now() - timedelta(days=7)

        main_image_prefetch = Prefetch(
            'images',
            queryset=ProductImage.objects.filter(is_main=True).only('image'),
            to_attr='main_image_cached'
        )

        base_products = Product.objects.filter(store__is_active=True) \
            .select_related('store', 'category') \
            .prefetch_related(main_image_prefetch, 'variants__images') \
            .order_by('name')

        def prepare_section(qs):
            result = []
            for p in qs[:20]:
                data = get_product_display_data(p)
                result.append({
                    'product': p,
                    **data
                })
            return result

        context = {
            **get_common_context(),
            'stores': Store.objects.filter(is_active=True)[:8],
            'deals_of_day': prepare_section(base_products.filter(deal_end_date__gte=today)),
            'featured_products': prepare_section(base_products.filter(is_featured=True)),
            'best_sellers': prepare_section(base_products.filter(is_best_seller=True)),
            'limited_deals': prepare_section(base_products.filter(is_limited_deal=True)),
            'special_offers': prepare_section(base_products.filter(is_special_offer=True)),
            'new_arrivals': prepare_section(base_products.filter(
                Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago)
            ).distinct()),
            'categories_all': Category.objects.all().order_by('name')[:12],
            'all_store_banners': StoreBanner.objects.filter(
                is_active=True, store__is_active=True
            ).order_by('order', '-created_at'),
        }

        cache.set(cache_key, context, 300)

    return render(request, 'TMS/public/home.html', context)

def all_products(request):
    context = get_common_context()
    today = date.today()
    seven_days_ago = timezone.now() - timedelta(days=7)

    main_image_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(is_main=True).only('image'),
        to_attr='main_image_cached'
    )

    qs = Product.objects.filter(store__is_active=True) \
        .select_related('store', 'category') \
        .prefetch_related(main_image_prefetch, 'variants__images') \
        .order_by('name')

    original_q = request.GET.get('q', '').strip()
    q_lower = original_q.lower() if original_q else ''
    applied_filters = []
    search_terms = []
    sort_by_relevance = False

    normalized_q = ' '.join(re.sub(r'[^\w\s]', ' ', q_lower).split())

    if original_q:
        price_match = re.search(r'(under|below|less than|upto|budget)\s*&#8377;?([\d,]+)', q_lower)
        if price_match:
            max_price = int(price_match.group(2).replace(',', ''))
            qs = qs.filter(
                Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price) |
                Q(variants__offer_price__lte=max_price) | Q(variants__regular_price__lte=max_price)
            )
            applied_filters.append(f"Under &#8377; {max_price:,}")
        elif original_q.replace(',', '').isdigit():
            number = int(original_q.replace(',', ''))
            max_price = number * 10
            qs = qs.filter(
                Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price) |
                Q(variants__offer_price__lte=max_price) | Q(variants__regular_price__lte=max_price)
            )
            applied_filters.append(f"Under &#8377; {number:,}000")
        else:
            if normalized_q:
                base_search = (
                    Q(name__icontains=normalized_q) |
                    Q(short_desc__icontains=normalized_q) |
                    Q(category__name__icontains=normalized_q) |
                    Q(store__name__icontains=normalized_q)
                )
                spec_subquery = ProductSpecification.objects.filter(
                    product=OuterRef('pk')
                ).filter(
                    Q(name__icontains=normalized_q) | Q(value__icontains=normalized_q)
                )
                qs = qs.filter(base_search | Exists(spec_subquery))

                if not qs.exists():
                    qs = Product.objects.filter(store__is_active=True) \
                        .select_related('store', 'category') \
                        .prefetch_related(main_image_prefetch, 'variants__images') \
                        .annotate(
                            name_sim=TrigramSimilarity('name', normalized_q),
                            desc_sim=TrigramSimilarity('short_desc', normalized_q),
                            similarity=F('name_sim') + F('desc_sim') * 0.6
                        ) \
                        .filter(similarity__gt=0.06) \
                        .order_by('-similarity', 'name')
                    search_terms.append(normalized_q.title())

        if any(word in q_lower for word in ['best', 'top', 'popular', 'premium', 'good', 'high quality', 'luxury']):
            sort_by_relevance = True

        if any(word in q_lower for word in ['offer', 'deal', 'discount', 'sale', 'on offer', 'clearance']):
            qs = qs.filter(
                Q(is_special_offer=True) |
                Q(is_limited_deal=True) |
                Q(deal_end_date__gte=today)
            )
            applied_filters.append("Offers & Deals")
            sort_by_relevance = True

    filter_type = request.GET.get('filter')
    if filter_type:
        if filter_type == 'deals':
            qs = qs.filter(deal_end_date__gte=today)
            applied_filters.append("Flash Deals")
        elif filter_type == 'bestselling':
            qs = qs.filter(is_best_seller=True)
            applied_filters.append("Best Sellers")
        elif filter_type == 'limited':
            qs = qs.filter(is_limited_deal=True)
            applied_filters.append("Limited Deals")
        elif filter_type == 'special':
            qs = qs.filter(is_special_offer=True)
            applied_filters.append("Special Offers")
        elif filter_type == 'new':
            qs = qs.filter(Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago))
            applied_filters.append("New Arrivals")
        elif filter_type == 'featured':
            qs = qs.filter(is_featured=True)
            applied_filters.append("Featured Products")
        elif filter_type == 'other':
            special_flags = (
                Q(is_best_seller=True) |
                Q(deal_end_date__gte=today) |
                Q(is_limited_deal=True) |
                Q(is_special_offer=True) |
                Q(is_featured=True) |
                Q(is_new_arrival=True)
            )
            qs = qs.exclude(special_flags)
            applied_filters.append("Other Products")

    if request.GET.get('category'):
        qs = qs.filter(category__slug=request.GET['category'])
        applied_filters.append(f"Category: {request.GET['category']}")
    if request.GET.get('store'):
        qs = qs.filter(store__slug=request.GET['store'])
        applied_filters.append(f"Store: {request.GET['store']}")

    sort = request.GET.get('sort')
    if sort == 'price_low':
        qs = qs.annotate(
            effective_price=Coalesce(
                Min('variants__offer_price', filter=Q(variants__offer_price__isnull=False)),
                Min('variants__regular_price'),
                'offer_price',
                'regular_price'
            )
        ).order_by('effective_price', 'name')
        applied_filters.append("Price: Low to High")
    elif sort == 'price_high':
        qs = qs.annotate(
            effective_price=Coalesce(
                Min('variants__offer_price', filter=Q(variants__offer_price__isnull=False)),
                Min('variants__regular_price'),
                'offer_price',
                'regular_price'
            )
        ).order_by('-effective_price', 'name')
        applied_filters.append("Price: High to Low")
    elif sort == 'newest':
        qs = qs.order_by('-created_at', 'name')
        applied_filters.append("Newest First")
    else:
        if sort_by_relevance:
            qs = qs.order_by(
                '-is_best_seller',
                '-is_featured',
                '-is_special_offer',
                '-is_limited_deal',
                F('deal_end_date').desc(nulls_last=True),
                'name'
            )
        else:
            qs = qs.order_by('name')

    PAGE_SIZE = 50
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    products_display = []
    for p in page_obj:
        data = get_product_display_data(p)
        products_display.append({
            'product': p,
            **data
        })

    context.update({
        'products_display': products_display,
        'page_obj': page_obj,
        'paginator': paginator,
        'query': original_q,
        'applied_filters': applied_filters,
        'search_terms': search_terms,
        'filter_type': request.GET.get('filter') or '',
        'current_category': Category.objects.filter(slug=request.GET.get('category')).first(),
        'current_store': Store.objects.filter(slug=request.GET.get('store')).first(),
        'today': today,
        'categories_all': Category.objects.all().order_by('name'),
        'stores_all': Store.objects.filter(is_active=True),
    })

    return render(request, 'TMS/public/allproducts.html', context)

def store_list(request):
    context = get_common_context()
    stores = Store.objects.filter(is_active=True)
    query = request.GET.get('q')
    city = request.GET.get('city')
    
    if query:
        stores = stores.filter(Q(name__icontains=query) | Q(city__icontains=query))
    if city:
        stores = stores.filter(city__iexact=city)
    
    context.update({
        'stores': Paginator(stores, 20).get_page(request.GET.get('page')),
        'cities': Store.objects.values_list('city', flat=True).distinct(),
        'query': query,
        'selected_city': city
    })
    return render(request, 'TMS/public/storelist.html', context)

def store_detail(request, slug):
    context = get_common_context()
    store = get_object_or_404(Store, slug=slug, is_active=True)

    today = date.today()
    seven_days_ago = timezone.now() - timedelta(days=7)

    main_image_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(is_main=True).only('image'),
        to_attr='main_image_cached'
    )

    store_products = Product.objects.filter(store=store) \
        .select_related('category') \
        .prefetch_related(main_image_prefetch, 'variants__images')

    def prepare_section(qs):
        result = []
        for p in qs[:20]:
            data = get_product_display_data(p)
            result.append({
                'product': p,
                **data
            })
        return result

    store_deals = prepare_section(store_products.filter(deal_end_date__gte=today))
    store_best_sellers = prepare_section(store_products.filter(is_best_seller=True))
    store_new_arrivals = prepare_section(store_products.filter(
        Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago)
    ).distinct())
    store_limited_deals = prepare_section(store_products.filter(is_limited_deal=True))
    store_special_offers = prepare_section(store_products.filter(is_special_offer=True))
    store_featured = prepare_section(store_products.filter(is_featured=True))

    store_categories = Category.objects.filter(
        product__store=store
    ).distinct()

    context.update({
        'store': store,
        'store_deals': store_deals,
        'store_best_sellers': store_best_sellers,
        'store_new_arrivals': store_new_arrivals,
        'store_limited_deals': store_limited_deals,
        'store_special_offers': store_special_offers,
        'store_featured': store_featured,
        'has_store_deals': bool(store_deals),
        'has_store_best_sellers': bool(store_best_sellers),
        'has_store_new_arrivals': bool(store_new_arrivals),
        'has_store_limited_deals': bool(store_limited_deals),
        'has_store_special_offers': bool(store_special_offers),
        'has_store_featured': bool(store_featured),
        'store_categories': store_categories,
    })

    return render(request, 'TMS/public/storedetail.html', context)

def product_detail(request, store_slug, product_slug):
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    username = request.user.username if request.user.is_authenticated else 'guest'

    context = get_common_context()
    form = EnquiryForm()

    product = get_object_or_404(
        Product.objects.prefetch_related(
            'specifications',
            Prefetch('images', queryset=ProductImage.objects.order_by('sort_order', 'id')),
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.prefetch_related(
                    Prefetch('values', queryset=VariantValue.objects.select_related('attribute')),
                    Prefetch('images', queryset=ProductVariantImage.objects.order_by('sort_order', 'id')),
                    'specifications'
                )
            ),
            'variant_attributes'
        ),
        slug=product_slug,
        store__slug=store_slug,
        store__is_active=True
    )

    Product.objects.filter(pk=product.pk).update(views_count=F('views_count') + 1)
    product.refresh_from_db()

    public_logger.info("PRODUCT VIEW", extra={
        'client_ip': client_ip,
        'user': username,
        'product': product.name,
        'product_id': product.id,
        'store': product.store.name,
        'store_city': product.store.city,
    })

    # Variant specs data
    variant_specs_data = {}
    if product.variants.exists():
        for variant in product.variants.all():
            specs = variant.specifications.all().values('name', 'value')
            variant_specs_data[str(variant.id)] = list(specs)

    variants_data = []
    default_variant_dict = None

    if product.variants.exists():
        # Prefer in-stock cheapest variant
        cheapest_variant = (
            product.variants
            .filter(in_stock=True)
            .annotate(effective_price=Coalesce('offer_price', 'regular_price'))
            .order_by('effective_price')
            .first()
        ) or product.variants.first()

        if cheapest_variant:
            values = {v.attribute.name: v.value for v in cheapest_variant.values.all()}
            images = [img.image.url for img in cheapest_variant.images.all()] or \
                     [img.image.url for img in product.images.all()]

            main_image = (
                cheapest_variant.image.url if cheapest_variant.image else
                (cheapest_variant.images.first().image.url if cheapest_variant.images.exists() else
                 (product.images.first().image.url if product.images.exists() else None))
            )

            # FIXED: Added discount_percent to context!
            default_variant_dict = {
                'id': str(cheapest_variant.id),
                'title': cheapest_variant.get_display_title(),
                'regular_price': float(cheapest_variant.regular_price),
                'offer_price': float(cheapest_variant.offer_price) if cheapest_variant.offer_price else None,
                'in_stock': cheapest_variant.in_stock,
                'main_image': main_image,
                'images': images,
                'values': values,
                'discount_percent': cheapest_variant.discount_percent,  # ← THIS WAS MISSING!
            }

        # All variants data
        for variant in product.variants.all():
            values = {v.attribute.name: v.value for v in variant.values.all()}
            images = [img.image.url for img in variant.images.all()] or \
                     [img.image.url for img in product.images.all()]

            main_image = (
                variant.image.url if variant.image else
                (variant.images.first().image.url if variant.images.exists() else
                 (product.images.first().image.url if product.images.exists() else None))
            )

            variants_data.append({
                'id': str(variant.id),
                'title': variant.get_display_title(),
                'regular_price': float(variant.regular_price),
                'offer_price': float(variant.offer_price) if variant.offer_price else None,
                'in_stock': variant.in_stock,
                'main_image': main_image,
                'images': images,
                'values': values,
            })

    else:
        # Non-variant product
        images = [img.image.url for img in product.images.all()]
        main_image = product.images.first().image.url if product.images.exists() else None

        variants_data.append({
            'id': 'none',
            'title': 'Standard',
            'regular_price': float(product.regular_price) if product.regular_price else None,
            'offer_price': float(product.offer_price) if product.offer_price else None,
            'in_stock': product.in_stock,
            'main_image': main_image,
            'images': images,
            'values': {},
        })

        default_variant_dict = {
            'id': 'none',
            'main_image': main_image,
            'offer_price': product.offer_price,
            'regular_price': product.regular_price,
            'in_stock': product.in_stock,
            'discount_percent': product.discount_percent,  # ← Added here too!
        }

    # Grouping variants
    grouped_variants = defaultdict(list)
    variant_to_values = {}
    if product.variants.exists():
        all_attrs = set()
        for v in variants_data:
            all_attrs.update(v['values'].keys())

        for attr in all_attrs:
            seen = set()
            items = []
            for v in variants_data:
                if attr in v['values']:
                    val = v['values'][attr]
                    if val not in seen:
                        seen.add(val)
                        items.append({
                            'value': val,
                            'variant_id': v['id'],
                            'price': v['offer_price'] or v['regular_price'],
                            'old_price': v['regular_price'],
                            'has_offer': bool(v['offer_price']),
                            'stock': v['in_stock'],
                            'main_image': v['main_image'],
                            'images': v['images'],
                            'is_default': v['id'] == default_variant_dict['id'] if default_variant_dict else False
                        })
            if items:
                grouped_variants[attr] = items

        for v in variants_data:
            variant_to_values[v['id']] = v['values']

    # Similar products
    similar = Product.objects.filter(store__is_active=True)\
                   .exclude(id=product.id)\
                   .prefetch_related('images', 'variants__images')[:15]

    if not similar.exists():
        similar = Product.objects.filter(is_featured=True)\
                       .prefetch_related('images', 'variants__images')[:15]

    similar_display = []
    for p in similar:
        data = get_product_display_data(p)
        similar_display.append({'product': p, **data})

    # WhatsApp setup
    phone_raw = product.store.whatsapp or "919629828969"
    clean_phone = ''.join(filter(str.isdigit, phone_raw))
    phone = "91" + clean_phone if len(clean_phone) == 10 else clean_phone
    if not phone.startswith("91"):
        phone = "919629828969"

    default_title = default_variant_dict.get('title', 'Standard') if default_variant_dict else "Standard"
    default_price = (
        default_variant_dict.get('offer_price') or default_variant_dict.get('regular_price')
        if default_variant_dict else (product.offer_price or product.regular_price)
    )

    message = (
        f"Hi {product.store.name}!%0A%0A"
        f"I am interested in:%0A%0A"
        f"*{product.name}*%0A"
        f"Variant: {default_title}%0A"
        f"Price:  &#8377; {int(default_price):,}%0A"
        f"Store: {product.store.name}, {product.store.city}%0A"
        f"Link: {request.build_absolute_uri()}"
    )
    whatsapp_url = f"https://wa.me/{phone}?text={message}"

    # Handle POST (enquiry form)
    if request.method == "POST":
        form = EnquiryForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('website'):
                public_logger.warning("SPAM ATTEMPT DETECTED")
                return JsonResponse({'success': False, 'message': 'Spam detected. Please try again.'})

            phone_input = form.cleaned_data['phone'].strip()
            customer_name = form.cleaned_data['customer_name']
            city = form.cleaned_data['city']
            selected_variant_id = request.POST.get('variant_id')  # ← from hidden input
            # Anti-duplicate check (last 24 hours)
            twenty_four_hours_ago = timezone.now() - timedelta(hours=12)
            duplicate = Lead.objects.filter(
                product=product,
                phone=phone_input,
                created_at__gte=twenty_four_hours_ago
            ).exists()

            if duplicate:
                return JsonResponse({
                    'success': False,
                    'already': True,
                    'message': 'You have already enquired for this product today. Try again tomorrow!',
                    'whatsapp_url': whatsapp_url
                })

            # ── IMPROVED: Determine display name reliably ──────────────────────
            selected_variant = None
            selected_variant_id = request.POST.get('variant_id')

            if selected_variant_id and product.variants.exists():
                try:
                    selected_variant = product.variants.get(id=selected_variant_id)
                except ProductVariant.DoesNotExist:
                    selected_variant = None

            # Always build a clean, human-readable name
            if selected_variant:
                variant_title = selected_variant.get_display_title()
                display_name = f"{product.name} - {variant_title}".strip()
            else:
                display_name = product.name.strip()

       
            if not display_name:
                display_name = "Product Enquiry"

            # Create the lead with proper display name
            lead = Lead.objects.create(
                store=product.store,
                product=product,
                product_display_name=display_name,          # ← this is now always correct
                customer_name=customer_name,
                phone=phone_input,
                city=city,
                source='website_form'
            )

            public_logger.info("NEW LEAD CREATED", extra={
                'client_ip': client_ip,
                'user': username,
                'customer_name': customer_name,
                'phone': phone_input,
                'city': city or 'Not provided',
                'product': display_name,
                'product_id': product.id,
                'variant_id': selected_variant.id if selected_variant else None,
                'store': product.store.name,
                'store_city': product.store.city,
                'time_ist': timezone.localtime(lead.created_at).strftime('%d %b %Y %I:%M %p')
            })

            # WhatsApp message – use the same display name
            variant_title = selected_variant.get_display_title() if selected_variant else "Standard"
            variant_price = (
                selected_variant.offer_price or selected_variant.regular_price
                if selected_variant else (product.offer_price or product.regular_price)
            )

            final_message = (
                f"Hi {product.store.name}!%0A%0A"
                f"I am interested in:%0A%0A"
                f"*{display_name}*%0A"           # ← using the same clean name
                f"Price: &#8377;{int(variant_price):,}%0A"
                f"Store: {product.store.name}, {product.store.city}%0A"
                f"Link: {request.build_absolute_uri()}"
            )

            final_whatsapp_url = f"https://wa.me/{phone}?text={final_message}"

            return JsonResponse({
                'success': True,
                'message': 'Enquiry sent successfully!',
                'whatsapp_url': final_whatsapp_url
            })

        else:
            public_logger.warning("INVALID ENQUIRY FORM")
            return JsonResponse({'success': False, 'message': 'Invalid form data. Please check your inputs.'})
    # Final context
    context.update({
        'product': product,
        'images': product.images.all(),
        'variants_data': variants_data,
        'default_variant': default_variant_dict,
        'has_variants': product.variants.exists(),
        'variant_specs_data': variant_specs_data,
        'grouped_variants': dict(grouped_variants),
        'variant_to_values': variant_to_values,
        'similar_display': similar_display,
        'form': form,
        'whatsapp_url': whatsapp_url,
        'phone_raw': phone,
        'already_enquired': False,
    })

    return render(request, 'TMS/public/productdetail.html', context)


def categories_page(request):
    store_slug = request.GET.get('store')

    if store_slug:
        store = get_object_or_404(Store, slug=store_slug, is_active=True)
        categories_qs = Category.objects.filter(
            product__store=store
        ).annotate(
            product_count=Count('product')
        ).distinct().order_by('name')

        paginator = Paginator(categories_qs, 60)
        page_number = request.GET.get('page')
        categories = paginator.get_page(page_number)

        context = {
            'categories': categories,
            'store': store,
            'page_obj': categories,
            'paginator': paginator,
            'is_paginated': categories.has_other_pages(),
        }
    else:
        categories_qs = Category.objects.annotate(
            product_count=Count('product')
        ).order_by('name')

        paginator = Paginator(categories_qs, 60)
        page_number = request.GET.get('page')
        categories = paginator.get_page(page_number)

        context = {
            'categories': categories,
            'page_obj': categories,
            'paginator': paginator,
            'is_paginated': categories.has_other_pages(),
        }

    return render(request, 'TMS/public/categories.html', context)

def search_suggestions(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 1:
        return JsonResponse({'products': [], 'categories': [], 'stores': [], 'specs': []})

    normalized_q = re.sub(r'\s+', ' ', q.lower())
    normalized_q = re.sub(r'[^\w\s]', ' ', normalized_q)
    normalized_q = ' '.join(normalized_q.split())

    main_image_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(is_main=True).only('image'),
        to_attr='main_image_cached'
    )

    products = Product.objects.filter(
        Q(name__icontains=normalized_q) | Q(short_desc__icontains=normalized_q),
        store__is_active=True
    ).select_related('store').prefetch_related(main_image_prefetch, 'variants')[:10]

    categories = Category.objects.filter(name__icontains=normalized_q)[:6]

    stores = Store.objects.filter(
        Q(name__icontains=normalized_q) | Q(city__icontains=normalized_q),
        is_active=True
    )[:6]

    specs = ProductSpecification.objects.filter(
        Q(name__icontains=normalized_q) | Q(value__icontains=normalized_q)
    ).values('value', 'name').annotate(count=Count('id')).order_by('-count')[:10]

    spec_suggestions = []
    seen = set()
    for s in specs:
        term = f"{s['value']} {s['name']}".strip()
        if term.lower() not in seen:
            spec_suggestions.append(term)
            seen.add(term.lower())
        if len(spec_suggestions) >= 8:
            break

    data = {
        'products': [
            {
                'name': p.name,
                'price_display': get_product_display_data(p)['display_price'],
                'image': get_product_display_data(p)['main_image'],
                'store': p.store.name,
            } for p in products
        ],
        'categories': [{'name': c.name} for c in categories],
        'stores': [{'name': f"{s.name} - {s.city}"} for s in stores],
        'specs': spec_suggestions,
    }
    return JsonResponse(data)