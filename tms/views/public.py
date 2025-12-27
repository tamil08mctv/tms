from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, F, Exists, OuterRef, Prefetch
from django.core.cache import cache
from ..models import Store, Product, Category, Lead, StoreBanner, SiteSettings, ProductSpecification, ProductImage
from ..forms import EnquiryForm
from datetime import date, timedelta
from django.db.models import Count
from django.utils import timezone
from django.db.models.functions import Coalesce
import re
import logging
from django.utils import timezone as dj_timezone
from django.utils.timezone import localtime

from django.contrib.postgres.search import TrigramSimilarity
from django.http import JsonResponse

public_logger = logging.getLogger('public')

def get_common_context():
    site_settings = SiteSettings.objects.first()
    return {
        'stores_all': Store.objects.filter(is_active=True).order_by('name'),
        'categories_all': Category.objects.all().order_by('name'),
        'site_settings': site_settings,
        'social_links': site_settings.social_links.all() if site_settings else [],
    }

def home(request):
    # CACHE HOMEPAGE FOR 5 MINUTES
    cache_key = 'homepage_data'
    context = cache.get(cache_key)

    if not context:
        today = date.today()
        seven_days_ago = timezone.now() - timedelta(days=7)

        # PREFETCH ONLY MAIN IMAGE
        main_image_prefetch = Prefetch(
            'images',
            queryset=ProductImage.objects.filter(is_main=True).only('image'),
            to_attr='main_image'
        )

        # BASE QUERY — ONE TIME ONLY
        base_products = Product.objects.filter(store__is_active=True) \
            .select_related('store', 'category') \
            .prefetch_related(main_image_prefetch).order_by('name')

        # ALL SECTIONS FROM ONE BASE QUERY
        deals_of_day = base_products.filter(deal_end_date__gte=today)[:20]
        featured_products = base_products.filter(is_featured=True)[:20]
        best_sellers = base_products.filter(is_best_seller=True)[:20]
        limited_deals = base_products.filter(is_limited_deal=True)[:20]
        special_offers = base_products.filter(is_special_offer=True)[:20]
        new_arrivals = base_products.filter(
            Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago)
        ).distinct()[:20]

        # BANNERS
        all_store_banners = StoreBanner.objects.filter(
            is_active=True,
            store__is_active=True
        ).order_by('order', '-created_at')

        context = {
            **get_common_context(),
            'stores': Store.objects.filter(is_active=True)[:8],
            'deals_of_day': deals_of_day,
            'featured_products': featured_products,
            'best_sellers': best_sellers,
            'limited_deals': limited_deals,
            'special_offers': special_offers,
            'new_arrivals': new_arrivals,
            'categories_all': Category.objects.all().order_by('name')[:12],
            'all_store_banners': all_store_banners,

            'has_deals': deals_of_day.exists(),
            'has_featured': featured_products.exists(),
            'has_best_sellers': best_sellers.exists(),
            'has_limited_deals': limited_deals.exists(),
            'has_special_offers': special_offers.exists(),
            'has_new_arrivals': new_arrivals.exists(),
        }

        # Cache for 5 minutes
        cache.set(cache_key, context, 300)

    return render(request, 'TMS/public/home.html', context)


# def all_products(request):
#     context = get_common_context()
#     today = date.today()
#     seven_days_ago = timezone.now() - timedelta(days=7)

#     main_image_prefetch = Prefetch(
#     'images',
#     queryset=ProductImage.objects.filter(is_main=True).only('image'),
#     to_attr='main_image'
#     )


#     products = Product.objects.filter(store__is_active=True) \
#     .select_related('store', 'category') \
#     .prefetch_related(main_image_prefetch, 'specifications') \
#     .only(
#         'id', 'name', 'slug', 'short_desc', 'regular_price', 'offer_price',
#         'call_for_price', 'is_best_seller', 'is_special_offer', 'is_limited_deal',
#         'deal_end_date', 'is_new_arrival', 'is_featured', 'created_at',
#         'store__name', 'store__slug', 'category__name', 'category__slug'
#     )


#     original_q = request.GET.get('q', '').strip()
#     q = original_q.lower() if original_q else ''

#     applied_filters = []
#     search_terms = []
#     sort_by_relevance = False

#     # Normalize query
#     normalized_q = re.sub(r'\s+', ' ', q)
#     normalized_q = re.sub(r'[^\w\s]', ' ', normalized_q)
#     normalized_q = ' '.join(normalized_q.split()).lower()

#     main_image_prefetch = Prefetch(
#         'images',
#         queryset=ProductImage.objects.filter(is_main=True).only('image'),
#         to_attr='main_image'
#     )

#     # 1. PRICE FILTERS
#     price_match = re.search(r'(under|below|less than|upto|budget)\s*₹?([\d,]+)', q)
#     if price_match:
#         max_price = int(price_match.group(2).replace(',', ''))
#         products = products.filter(effective_price__lte=max_price)
#         applied_filters.append(f"Under ₹{max_price:,}")

#     # 2. PURE NUMBER → Budget search
#     elif q.replace(',', '').isdigit():
#         number = int(q.replace(',', ''))
#         max_price = number * 1000
#         products = products.filter(effective_price__lte=max_price)
#         applied_filters.append(f"Under ₹{number:,}000")
#         search_terms.append(original_q)

#     else:
#         if normalized_q:
#             # First: Try normal icontains search (fast & accurate)
#             base_search = (
#                 Q(name__icontains=normalized_q) |
#                 Q(short_desc__icontains=normalized_q) |
#                 Q(category__name__icontains=normalized_q) |
#                 Q(store__name__icontains=normalized_q)
#             )

#             spec_subquery = ProductSpecification.objects.filter(
#                 product=OuterRef('pk')
#             ).filter(
#                 Q(name__icontains=normalized_q) | Q(value__icontains=normalized_q)
#             )

#             products = products.filter(base_search | Exists(spec_subquery))

#             # If no results → fall back to trigram with very low threshold
#             if not products.exists():
#                 products = (
#                     Product.objects
#                     .filter(store__is_active=True)
#                     .select_related('store', 'category')
#                     .prefetch_related(main_image_prefetch, 'specifications')

#                     .annotate(
#                         name_sim=TrigramSimilarity('name', normalized_q),
#                         desc_sim=TrigramSimilarity('short_desc', normalized_q),
#                         similarity=F('name_sim') + F('desc_sim') * 0.7
#                     )
#                     .filter(similarity__gt=0.05)
#                     .order_by('-similarity')
#                 )

#             search_terms.append(normalized_q.title())

#     # Quality & Offer words
#     if any(word in q for word in ['best', 'top', 'popular', 'premium', 'good', 'high quality', 'luxury']):
#         sort_by_relevance = True

#     if any(word in q for word in ['offer', 'deal', 'discount', 'sale', 'on offer', 'clearance']):
#         products = products.filter(
#             Q(is_special_offer=True) |
#             Q(is_limited_deal=True) |
#             Q(deal_end_date__gte=today)
#         )
#         applied_filters.append("Offers & Deals")
#         sort_by_relevance = True

#     # MANUAL FILTERS
#     filter_type = request.GET.get('filter')
#     category_slug = request.GET.get('category')
#     store_slug = request.GET.get('store')

#     if filter_type:
#         if filter_type == 'deals':
#             products = products.filter(deal_end_date__gte=today)
#         elif filter_type == 'bestselling':
#             products = products.filter(is_best_seller=True)
#         elif filter_type == 'limited':
#             products = products.filter(is_limited_deal=True)
#         elif filter_type == 'special':
#             products = products.filter(is_special_offer=True)
#         elif filter_type == 'new':
#             products = products.filter(Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago))
#         elif filter_type == 'featured':
#             products = products.filter(is_featured=True)
#         elif filter_type == 'other':
#             products = products.exclude(
#                 Q(is_best_seller=True) |
#                 Q(deal_end_date__gte=today) |
#                 Q(is_limited_deal=True) |
#                 Q(is_special_offer=True) |
#                 Q(is_featured=True) |
#                 Q(is_new_arrival=True)|Q(created_at__gte=seven_days_ago)
#             )

#     if category_slug:
#         products = products.filter(category__slug=category_slug)
#     if store_slug:
#         products = products.filter(store__slug=store_slug)

#     # SORTING
#     sort = request.GET.get('sort')
#     if sort == 'price_low':
#         products = products.order_by('effective_price')
#     elif sort == 'price_high':
#         products = products.order_by('-effective_price')
#     elif sort == 'newest':
#         products = products.order_by('-created_at')
#     else:
#         if sort_by_relevance:
#             products = products.order_by(
#                 '-is_best_seller',
#                 '-is_featured',
#                 '-is_special_offer',
#                 '-is_limited_deal',
#                 F('deal_end_date').desc(nulls_last=True),
#                 'name'
#             )
#         else:
#             products = products.order_by('name')

#     # Pagination
#     paginator = Paginator(products,50)
#     page = request.GET.get('page')
#     products_page = paginator.get_page(page)

#     context.update({
#         'products': products_page,
#         'query': original_q,
#         'applied_filters': applied_filters,
#         'search_terms': search_terms,
#         'filter_type': filter_type or '',
#         'current_category': Category.objects.filter(slug=category_slug).first() if category_slug else None,
#         'current_store': Store.objects.filter(slug=store_slug).first() if store_slug else None,
#         'categories_all': Category.objects.all(),
#         'stores_all': Store.objects.filter(is_active=True),
#         'today': today
#     })
#     return render(request, 'TMS/public/allproducts.html', context)


def all_products(request):
    context = get_common_context()
    today = date.today()
    seven_days_ago = timezone.now() - timedelta(days=7)

    main_image_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(is_main=True).only('image'),
        to_attr='main_image'
    )

    qs = Product.objects.filter(store__is_active=True) \
        .select_related('store', 'category') \
        .prefetch_related(main_image_prefetch) \
        .only(
            'id', 'name', 'slug', 'short_desc', 'regular_price', 'offer_price',
            'is_best_seller', 'is_special_offer', 'is_limited_deal',
            'deal_end_date', 'is_new_arrival', 'is_featured', 'created_at',
            'store__name', 'store__slug', 'category__name', 'category__slug'
        ).order_by('name')

    original_q = request.GET.get('q', '').strip()
    q_lower = original_q.lower() if original_q else ''
    applied_filters = []
    search_terms = []
    sort_by_relevance = False

    # Normalize query
    normalized_q = ' '.join(re.sub(r'[^\w\s]', ' ', q_lower).split())

    if original_q:
        # PRICE FILTERS
        price_match = re.search(r'(under|below|less than|upto|budget)\s*₹?([\d,]+)', q_lower)
        if price_match:
            max_price = int(price_match.group(2).replace(',', ''))
            qs = qs.filter(Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price))
            applied_filters.append(f"Under ₹{max_price:,}")
        elif original_q.replace(',', '').isdigit():
            number = int(original_q.replace(',', ''))
            max_price = number * 1000
            qs = qs.filter(Q(offer_price__lte=max_price) | Q(regular_price__lte=max_price))
            applied_filters.append(f"Under ₹{number:,}000")
        else:
            if normalized_q:
                base_search = (
                    Q(name__icontains=normalized_q) |
                    Q(short_desc__icontains=normalized_q) |
                    Q(category__name__icontains=normalized_q) |
                    Q(store__name__icontains=normalized_q)
                )
                spec_subquery = ProductSpecification.objects.filter(product=OuterRef('pk')).filter(
    Q(name__icontains=normalized_q) | Q(value__icontains=normalized_q)
)
                qs = qs.filter(base_search | Exists(spec_subquery))

                # Trigram fallback if no results
                if not qs.exists():
                    qs = Product.objects.filter(store__is_active=True) \
                        .select_related('store', 'category') \
                        .prefetch_related(main_image_prefetch) \
                        .annotate(
                            name_sim=TrigramSimilarity('name', normalized_q),
                            desc_sim=TrigramSimilarity('short_desc', normalized_q),
                            similarity=F('name_sim') + F('desc_sim') * 0.7
                        ) \
                        .filter(similarity__gt=0.05) \
                        .order_by('-similarity','name')
                    
                    search_terms.append(normalized_q.title())


        # Detect quality/offer words
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

    # MANUAL FILTERS
    filter_type = request.GET.get('filter')
    if filter_type == 'deals':
        qs = qs.filter(deal_end_date__gte=today)
    elif filter_type == 'bestselling':
        qs = qs.filter(is_best_seller=True)
    elif filter_type == 'limited':
        qs = qs.filter(is_limited_deal=True)
    elif filter_type == 'special':
        qs = qs.filter(is_special_offer=True)
    elif filter_type == 'new':
        qs = qs.filter(Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago))
    elif filter_type == 'featured':
        qs = qs.filter(is_featured=True)

    if request.GET.get('category'):
        qs = qs.filter(category__slug=request.GET['category'])
    if request.GET.get('store'):
        qs = qs.filter(store__slug=request.GET['store'])

    # SORTING
    sort = request.GET.get('sort')
    if sort == 'price_low':
        qs = qs.order_by(Coalesce('offer_price', 'regular_price'), 'name')
    elif sort == 'price_high':
        qs = qs.order_by(Coalesce('-offer_price', '-regular_price'), 'name')
    elif sort == 'newest':
        qs = qs.order_by('-created_at', 'name')
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
    

    # PAGINATION — FLIPKART STYLE
    PAGE_SIZE = 50  # Change to 10 for testing
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context.update({
        'products': page_obj,
        'query': original_q,
        'applied_filters': applied_filters,
        'search_terms': search_terms,
        'filter_type': filter_type or '',
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

    # FIXED: Added to_attr='main_image' so template can use p.main_image.0.image.url
    main_image_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(is_main=True).only('image'),
        to_attr='main_image'
    )

    store_products = Product.objects.filter(store=store, store__is_active=True)\
        .select_related('category')\
        .prefetch_related(main_image_prefetch)

    store_deals = store_products.filter(deal_end_date__gte=today)[:20]
    store_best_sellers = store_products.filter(is_best_seller=True)[:20]
    store_new_arrivals = store_products.filter(
        Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago)
    ).distinct()[:20]
    store_limited_deals = store_products.filter(is_limited_deal=True)[:20]
    store_special_offers = store_products.filter(is_special_offer=True)[:20]
    store_featured = store_products.filter(is_featured=True)[:20]

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
        'has_store_deals': store_deals.exists(),
        'has_store_best_sellers': store_best_sellers.exists(),
        'has_store_new_arrivals': store_new_arrivals.exists(),
        'has_store_limited_deals': store_limited_deals.exists(),
        'has_store_special_offers': store_special_offers.exists(),
        'has_store_featured': store_featured.exists(),
        'store_categories': store_categories,
    })
    
    return render(request, 'TMS/public/storedetail.html', context)


from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

def product_detail(request, store_slug, product_slug):
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
   
    context = get_common_context()
    
    product = get_object_or_404(
        Product.objects.prefetch_related('specifications', 'images'),
        slug=product_slug, 
        store__slug=store_slug, 
        store__is_active=True
    )
    Product.objects.filter(pk=product.pk).update(views_count=F('views_count') + 1)
    product.refresh_from_db()
    
    images = product.images.all()
    similar = Product.objects.filter(store__is_active=True).exclude(id=product.id)[:15]
    if not similar.exists():
        similar = Product.objects.filter(is_featured=True)[:15]
    
    phone_raw = product.store.whatsapp or "919629828969"
    clean_phone = ''.join(filter(str.isdigit, phone_raw))
    phone = "91" + clean_phone if len(clean_phone) == 10 else clean_phone
    if not phone.startswith("91"): phone = "919629828969"
    message = f"Hi {product.store.name}!%0A%0AI am interested in:%0A%0A*{product.name}*%0APrice: ₹{product.offer_price or product.regular_price}%0AStore: {product.store.name}, {product.store.city}%0ALink: {request.build_absolute_uri()}"
    whatsapp_url = f"https://wa.me/{phone}?text={message}"
    
    # Check if user already enquired in last 24 hours (by IP + phone if POST, else just show form)
    already_enquired = False
    if request.method == "POST":
        form = EnquiryForm(request.POST)
        if form.is_valid():
            phone_input = form.cleaned_data['phone'].strip()
            twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
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
            else:
                Lead.objects.create(
                    store=product.store,
                    product=product,
                    customer_name=form.cleaned_data['customer_name'],
                    phone=phone_input,
                    city=form.cleaned_data['city'],
                    source='website_form'
                )
                
                public_logger.info("NEW LEAD", extra={
                        'client_ip': client_ip,
                        'customer_name': form.cleaned_data['customer_name'],  # ← Changed from 'name' to 'customer_name'
                        'phone': phone_input,
                        'product': product.name,
                        'store': product.store.name,
                        'time_ist': dj_timezone.localtime(dj_timezone.now()).strftime('%d %b %Y %I:%M %p')
                    })
                
                return JsonResponse({
                    'success': True,
                    'message': 'Enquiry sent successfully!',
                    'whatsapp_url': whatsapp_url
                })
    else:
        form = EnquiryForm()
    
    context.update({
        'product': product,
        'images': images,
        'similar': similar,
        'form': form,
        'whatsapp_url': whatsapp_url,
        'already_enquired': already_enquired,  # Always False on GET
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
        
        # ADD PAGINATION FOR STORE TOO
        paginator = Paginator(categories_qs, 60)  # Same as global
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


# def search_suggestions(request):
#     q = request.GET.get('q', '').strip()
#     if len(q) < 1:
#         return JsonResponse({'products': [], 'categories': [], 'stores': [], 'specs': []})

#     normalized_q = re.sub(r'\s+', ' ', q.lower())
#     normalized_q = re.sub(r'[^\w\s]', ' ', normalized_q)
#     normalized_q = ' '.join(normalized_q.split())

#     products = Product.objects.filter(
#         Q(name__icontains=normalized_q) | Q(short_desc__icontains=normalized_q),
#         store__is_active=True
#     ).select_related('store').prefetch_related('images')[:10]

#     categories = Category.objects.filter(name__icontains=normalized_q)[:6]

#     stores = Store.objects.filter(
#         Q(name__icontains=normalized_q) | Q(city__icontains=normalized_q),
#         is_active=True
#     )[:6]

#     specs = ProductSpecification.objects.filter(
#         Q(name__icontains=normalized_q) | Q(value__icontains=normalized_q)
#     ).values('value', 'name').annotate(count=Count('id')).order_by('-count')[:10]

#     spec_suggestions = []
#     seen = set()
#     for s in specs:
#         term = f"{s['value']} {s['name']}".strip()
#         if term.lower() not in seen:
#             spec_suggestions.append(term)
#             seen.add(term.lower())
#         if len(spec_suggestions) >= 8:
#             break

#     data = {
#         'products': [
#             {
#                 'name': p.name,
#                 'price_display': f"₹{int(p.offer_price or p.regular_price):,}",
#                 'image': p.images.first().image.url if p.images.exists() else '/static/TMS/images/no-image.jpg',
#                 'store': p.store.name,
#             } for p in products
#         ],
#         'categories': [{'name': c.name} for c in categories],
#         'stores': [{'name': f"{s.name} - {s.city}"} for s in stores],
#         'specs': spec_suggestions,
#     }
#     return JsonResponse(data)


def search_suggestions(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 1:
        return JsonResponse({'products': [], 'categories': [], 'stores': [], 'specs': []})

    normalized_q = re.sub(r'\s+', ' ', q.lower())
    normalized_q = re.sub(r'[^\w\s]', ' ', normalized_q)
    normalized_q = ' '.join(normalized_q.split())

    # ADD MAIN IMAGE PREFETCH HERE
    main_image_prefetch = Prefetch(
        'images',
        queryset=ProductImage.objects.filter(is_main=True).only('image'),
        to_attr='main_image'
    )

    products = Product.objects.filter(
        Q(name__icontains=normalized_q) | Q(short_desc__icontains=normalized_q),
        store__is_active=True
    ).select_related('store').prefetch_related(main_image_prefetch)[:10]

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
                'price_display': f"₹{int(p.offer_price or p.regular_price):,}",
                # FIXED: Now uses prefetched main_image
                'image': p.main_image[0].image.url if hasattr(p, 'main_image') and p.main_image else '/static/TMS/images/no-image.jpg',
                'store': p.store.name,
            } for p in products
        ],
        'categories': [{'name': c.name} for c in categories],
        'stores': [{'name': f"{s.name} - {s.city}"} for s in stores],
        'specs': spec_suggestions,
    }
    return JsonResponse(data)