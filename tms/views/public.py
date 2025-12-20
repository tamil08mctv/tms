# tms/views/public.py → FINAL: FLIPKART/AMAZON LEVEL TYPO TOLERANCE + 10 LAKH+ READY

from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, F, Exists, OuterRef
from ..models import Store, Product, Category, Lead, StoreBanner, SiteSettings, ProductSpecification
from ..forms import EnquiryForm
import urllib.parse
from datetime import date
from django.db.models import Count
from django.utils import timezone
from django.db.models.functions import Coalesce
import re
import logging

# NEW: For advanced typo tolerance (Flipkart-like)
from django.contrib.postgres.search import TrigramSimilarity

from django.db.models import Prefetch

# Logger for public actions
public_logger = logging.getLogger('public')

def get_common_context():
    site_settings = SiteSettings.objects.first()
    return {
        'stores_all': Store.objects.filter(is_active=True),
        'categories_all': Category.objects.all().distinct(),
        'site_settings': site_settings,
        'social_links': site_settings.social_links.all() if site_settings else [],
    }

def home(request):
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    user = request.user.username if request.user.is_authenticated else 'Anonymous'
    public_logger.info(f"Home page accessed | IP: {client_ip} | User: {user}")

    context = get_common_context()
    today = date.today()
    seven_days_ago = timezone.now() - timedelta(days=7)

    # DEALS OF THE DAY
    deals = Product.objects.filter(
        deal_end_date__gte=today,
        store__is_active=True
    ).select_related('store', 'category').prefetch_related('images')[:30]

    # FEATURED PRODUCTS
    featured = Product.objects.filter(
        is_featured=True,
        store__is_active=True
    ).select_related('store', 'category').prefetch_related('images')[:20]

    # BEST SELLERS
    best_sellers = Product.objects.filter(
        is_best_seller=True,
        store__is_active=True
    ).select_related('store', 'category').prefetch_related('images')[:20]

    # LIMITED DEALS (URGENCY)
    limited_deals = Product.objects.filter(
        is_limited_deal=True,
        store__is_active=True
    ).select_related('store', 'category').prefetch_related('images')[:20]

    # SPECIAL OFFERS
    special_offers = Product.objects.filter(
        is_special_offer=True,
        store__is_active=True
    ).select_related('store', 'category').prefetch_related('images')[:20]

    # NEW ARRIVALS (LAST 7 DAYS)
    new_arrivals = Product.objects.filter(
        Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago),
        store__is_active=True
    ).select_related('store', 'category').distinct().prefetch_related('images')[:20]

    # BANNERS
    all_store_banners = StoreBanner.objects.filter(
        is_active=True,
        store__is_active=True
    ).order_by('order', '-created_at')
    
    context.update({
        'stores': Store.objects.filter(is_active=True)[:8],
        'deals_of_day': deals,
        'featured_products': featured,
        'best_sellers': best_sellers,
        'limited_deals': limited_deals,
        'special_offers': special_offers,
        'new_arrivals': new_arrivals,
        'categories_all': Category.objects.all()[:12],
        'all_store_banners': all_store_banners,

        # FOR CONDITIONAL DISPLAY IN TEMPLATE
        'has_deals': deals.exists(),
        'has_featured': featured.exists(),
        'has_best_sellers': best_sellers.exists(),
        'has_limited_deals': limited_deals.exists(),
        'has_special_offers': special_offers.exists(),
        'has_new_arrivals': new_arrivals.exists(),
    })
    return render(request, 'TMS/public/home.html', context)

def all_products(request):
    context = get_common_context()
    today = date.today()
    seven_days_ago = timezone.now() - timedelta(days=7)

    products = Product.objects.filter(store__is_active=True)\
        .select_related('store', 'category')\
        .prefetch_related('images', 'specifications')\
        .annotate(effective_price=Coalesce('offer_price', 'regular_price'))

    original_q = request.GET.get('q', '').strip()
    q = original_q.lower() if original_q else ''

    applied_filters = []
    search_terms = []
    sort_by_relevance = False

    # Normalize query
    normalized_q = re.sub(r'\s+', ' ', q)
    normalized_q = re.sub(r'[^\w\s]', ' ', normalized_q)
    normalized_q = ' '.join(normalized_q.split()).lower()

    # 1. PRICE FILTERS
    price_match = re.search(r'(under|below|less than|upto|budget)\s*₹?([\d,]+)', q)
    if price_match:
        max_price = int(price_match.group(2).replace(',', ''))
        products = products.filter(effective_price__lte=max_price)
        applied_filters.append(f"Under ₹{max_price:,}")

    # 2. PURE NUMBER → Budget search
    elif q.replace(',', '').isdigit():
        number = int(q.replace(',', ''))
        max_price = number * 1000
        products = products.filter(effective_price__lte=max_price)
        applied_filters.append(f"Under ₹{number:,}000")
        search_terms.append(original_q)

    else:
        if normalized_q:
            # First: Try normal icontains search (fast & accurate)
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

            products = products.filter(base_search | Exists(spec_subquery))

            # If no results → fall back to trigram with very low threshold
            if not products.exists():
                products = (
                    Product.objects
                    .filter(store__is_active=True)
                    .select_related('store', 'category')
                    .prefetch_related('images', 'specifications')
                    .annotate(
                        name_sim=TrigramSimilarity('name', normalized_q),
                        desc_sim=TrigramSimilarity('short_desc', normalized_q),
                        similarity=F('name_sim') + F('desc_sim') * 0.7
                    )
                    .filter(similarity__gt=0.05)
                    .order_by('-similarity')
                )

            search_terms.append(normalized_q.title())

    # Quality & Offer words
    if any(word in q for word in ['best', 'top', 'popular', 'premium', 'good', 'high quality', 'luxury']):
        sort_by_relevance = True

    if any(word in q for word in ['offer', 'deal', 'discount', 'sale', 'on offer', 'clearance']):
        products = products.filter(
            Q(is_special_offer=True) |
            Q(is_limited_deal=True) |
            Q(deal_end_date__gte=today)
        )
        applied_filters.append("Offers & Deals")
        sort_by_relevance = True

    # MANUAL FILTERS
    filter_type = request.GET.get('filter')
    category_slug = request.GET.get('category')
    store_slug = request.GET.get('store')

    if filter_type:
        if filter_type == 'deals':
            products = products.filter(deal_end_date__gte=today)
        elif filter_type == 'bestselling':
            products = products.filter(is_best_seller=True)
        elif filter_type == 'limited':
            products = products.filter(is_limited_deal=True)
        elif filter_type == 'special':
            products = products.filter(is_special_offer=True)
        elif filter_type == 'new':
            products = products.filter(Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago))
        elif filter_type == 'featured':
            products = products.filter(is_featured=True)

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if store_slug:
        products = products.filter(store__slug=store_slug)

    # SORTING
    sort = request.GET.get('sort')
    if sort == 'price_low':
        products = products.order_by('effective_price')
    elif sort == 'price_high':
        products = products.order_by('-effective_price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:
        if sort_by_relevance:
            products = products.order_by(
                '-is_best_seller',
                '-is_featured',
                '-is_special_offer',
                '-is_limited_deal',
                F('deal_end_date').desc(nulls_last=True),
                'name'
            )
        else:
            products = products.order_by('name')

    # Pagination
    paginator = Paginator(products, 100)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)

    context.update({
        'products': products_page,
        'query': original_q,
        'applied_filters': applied_filters,
        'search_terms': search_terms,
        'filter_type': filter_type or '',
        'current_category': Category.objects.filter(slug=category_slug).first() if category_slug else None,
        'current_store': Store.objects.filter(slug=store_slug).first() if store_slug else None,
        'categories_all': Category.objects.all(),
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
        'stores': Paginator(stores, 12).get_page(request.GET.get('page')),
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

    store_products = Product.objects.filter(store=store, store__is_active=True)\
        .select_related('category')\
        .prefetch_related('images')

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


def product_list(request, store_slug):
    context = get_common_context()
    store = get_object_or_404(Store, slug=store_slug)
    products = Product.objects.filter(store=store)
    
    context.update({
        'store': store,
        'products': products,
        'categories': store.categories.all()
    })
    return render(request, 'TMS/public/productlist.html', context)


from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

def product_detail(request, store_slug, product_slug):
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    user = request.user.username if request.user.is_authenticated else 'Anonymous'
   
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
    message = f"Hi {product.store.name}!%0A%0AI am interested in:%0A%0A*{product.name}*%0APrice: {product.get_price_display()}%0AStore: {product.store.name}, {product.store.city}%0ALink: {request.build_absolute_uri()}"
    whatsapp_url = f"https://wa.me/{phone}?text={message}"
    
    session_key = f"enquired_{product.id}"
    already_enquired_via_session = request.session.get(session_key, False)
    form = EnquiryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone_input = form.cleaned_data['phone'].strip()
        name = form.cleaned_data['customer_name'].strip()
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        duplicate = Lead.objects.filter(
            product=product,
            phone=phone_input,
            created_at__gte=twenty_four_hours_ago
        ).exists()
        if duplicate or already_enquired_via_session:
            return JsonResponse({
                'success': False,
                'already': True,
                'name': name,
                'whatsapp_url': whatsapp_url
            })
        else:
            Lead.objects.create(
                store=product.store,
                product=product,
                customer_name=name,
                phone=phone_input,
                city=form.cleaned_data['city'],
                source='website_form'
            )
            request.session[session_key] = True
            request.session.modified = True

            public_logger.info(f"NEW LEAD | Name: {name} | Phone: {phone_input} | Product: {product.name} | Store: {product.store.name} | IP: {client_ip}")
            return JsonResponse({
                'success': True,
                'name': name,
                'whatsapp_url': whatsapp_url
            })
    context.update({
        'product': product,
        'images': images,
        'similar': similar,
        'form': form,
        'whatsapp_url': whatsapp_url,
        'already_enquired': already_enquired_via_session,
    })
    return render(request, 'TMS/public/productdetail.html', context)


def categories_page(request):
    store_slug = request.GET.get('store')
    
    if store_slug:
        store = get_object_or_404(Store, slug=store_slug, is_active=True)
        categories_list = Category.objects.filter(
            product__store=store
        ).annotate(
            product_count=Count('product')
        ).distinct().order_by('name')
        
        context = {
            'categories': categories_list,
            'store': store,
            'page_obj': None,
            'is_paginated': False,
        }
        return render(request, 'TMS/public/categories.html', context)
    
    else:
        categories_list = Category.objects.annotate(
            product_count=Count('product')
        ).order_by('name')

        paginator = Paginator(categories_list, 36)
        page_number = request.GET.get('page')
        categories = paginator.get_page(page_number)

        return render(request, 'TMS/public/categories.html', {
            'categories': categories,
            'page_obj': categories,
            'paginator': paginator,
            'is_paginated': categories.has_other_pages(),
        })
    

def search_suggestions(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 1:
        return JsonResponse({'products': [], 'categories': [], 'stores': [], 'specs': []})

    normalized_q = re.sub(r'\s+', ' ', q.lower())
    normalized_q = re.sub(r'[^\w\s]', ' ', normalized_q)
    normalized_q = ' '.join(normalized_q.split())

    products = Product.objects.filter(
        Q(name__icontains=normalized_q) | Q(short_desc__icontains=normalized_q),
        store__is_active=True
    ).select_related('store').prefetch_related('images')[:10]

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
                'image': p.images.first().image.url if p.images.exists() else '/static/TMS/images/no-image.jpg',
                'store': p.store.name,
            } for p in products
        ],
        'categories': [{'name': c.name} for c in categories],
        'stores': [{'name': f"{s.name} - {s.city}"} for s in stores],
        'specs': spec_suggestions,
    }
    return JsonResponse(data)