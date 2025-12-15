# tms/views/public.py → ULTIMATE AUTO-SEND + SIMILAR PRODUCTS

from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, F
from ..models import Store, Product, Category, Lead,StoreBanner
from ..forms import EnquiryForm
import urllib.parse
from datetime import date
from django.db.models import Count
from django.utils import timezone

# tms/views/public.py → FINAL FIXED HOME VIEW

from django.db.models import Prefetch

def get_common_context():
    return {
        'stores_all': Store.objects.filter(is_active=True),
        'categories_all': Category.objects.all().distinct(),
    }

def home(request):
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
        .prefetch_related('images')

    # SEARCH
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(
            Q(name__icontains=q) |
            Q(short_desc__icontains=q) |
            Q(store__name__icontains=q)
        )

    # FILTERS
    category_slug = request.GET.get('category')
    store_slug = request.GET.get('store')
    filter_type = request.GET.get('filter', '').lower()

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if store_slug:
        products = products.filter(store__slug=store_slug)

    # MAIN FILTER LOGIC
    if filter_type == 'deals':
        products = products.filter(deal_end_date__gte=today)
    elif filter_type == 'bestselling':
        products = products.filter(is_best_seller=True)
    elif filter_type == 'limited':
        products = products.filter(is_limited_deal=True)
    elif filter_type == 'special':
        products = products.filter(is_special_offer=True)
    elif filter_type == 'new':
        products = products.filter(
        Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago)
    )
    elif filter_type == 'featured':
        products = products.filter(is_featured=True)

    # SORT
    from django.db.models.functions import Coalesce
    products = products.annotate(effective_price=Coalesce('offer_price', 'regular_price'))
    sort = request.GET.get('sort')
    if sort == 'price_low':
        products = products.order_by('effective_price')
    elif sort == 'price_high':
        products = products.order_by('-effective_price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('name')

    # Pagination
    paginator = Paginator(products, 60)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)

    context.update({
        'products': products_page,
        'filter_type': filter_type,
        'current_category': Category.objects.filter(slug=category_slug).first() if category_slug else None,
        'current_store': Store.objects.filter(slug=store_slug).first() if store_slug else None,
        'categories_all': Category.objects.all(),
        'stores_all': Store.objects.filter(is_active=True),
        'seven_days_ago': seven_days_ago,
    })
    return render(request, 'TMS/public/allproducts.html', context)

# def all_products(request):
#     context = get_common_context()
#     today = date.today()
#     seven_days_ago = timezone.now() - timedelta(days=7)

#     products = Product.objects.filter(store__is_active=True)\
#         .select_related('store', 'category')\
#         .prefetch_related('images')

#     # SEARCH
#     q = request.GET.get('q', '').strip()
#     if q:
#         products = products.filter(
#             Q(name__icontains=q) |
#             Q(short_desc__icontains=q) |
#             Q(store__name__icontains=q)
#         )

#     # FILTERS
#     category_slug = request.GET.get('category')
#     store_slug = request.GET.get('store')
#     filter_type = request.GET.get('filter', '').lower()  # ← THIS IS CRITICAL

#     if category_slug:
#         products = products.filter(category__slug=category_slug)
#     if store_slug:
#         products = products.filter(store__slug=store_slug)

#     # MAIN FILTER LOGIC — FROM HOME PAGE LINKS
#     if filter_type == 'deals':
#         products = products.filter(deal_end_date__gte=today)
#     elif filter_type == 'bestselling':
#         products = products.filter(is_best_seller=True)
#     elif filter_type == 'limited':
#         products = products.filter(is_limited_deal=True)
#     elif filter_type == 'special':
#         products = products.filter(is_special_offer=True)
#     elif filter_type == 'new':
#         products = products.filter(created_at__gte=seven_days_ago)
#     elif filter_type == 'featured':
#         products = products.filter(is_featured=True)

  

#     # Default Sort
#     products = products.order_by('name')

#     # Pagination
#     paginator = Paginator(products, 60)
#     page = request.GET.get('page')
#     products_page = paginator.get_page(page)

#     # SEND FILTER TYPE TO TEMPLATE
#     context.update({
#         'products': products_page,
#         'filter_type': filter_type,  # ← THIS MAKES TITLE & BUTTONS WORK!
#         'current_category': Category.objects.filter(slug=category_slug).first() if category_slug else None,
#         'current_store': Store.objects.filter(slug=store_slug).first() if store_slug else None,
#         'categories_all': Category.objects.all(),
#         'stores_all': Store.objects.filter(is_active=True),
#         'seven_days_ago': seven_days_ago,
#     })
#     return render(request, 'TMS/public/allproducts.html', context)



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

    # ALL PRODUCTS FROM THIS STORE
    store_products = Product.objects.filter(store=store, store__is_active=True)\
        .select_related('category')\
        .prefetch_related('images')

    # PRE-COMPUTE ALL SECTIONS
    store_deals = store_products.filter(deal_end_date__gte=today)[:20]
    store_best_sellers = store_products.filter(is_best_seller=True)[:20]
    store_new_arrivals = store_products.filter(
    Q(is_new_arrival=True) | Q(created_at__gte=seven_days_ago)
    ).distinct()[:20]
    store_limited_deals = store_products.filter(is_limited_deal=True)[:20]
    store_special_offers = store_products.filter(is_special_offer=True)[:20]
    store_featured = store_products.filter(is_featured=True)[:20]

    # GET CATEGORIES THAT HAVE PRODUCTS IN THIS STORE
    store_categories = Category.objects.filter(
        product__store=store
    ).distinct()

    context.update({
        'store': store,
        
        # Correct names
        'store_deals': store_deals,
        'store_best_sellers': store_best_sellers,
        'store_new_arrivals': store_new_arrivals,
        'store_limited_deals': store_limited_deals,
        'store_special_offers': store_special_offers,
        'store_featured': store_featured,

        # Correct has_ variables
        'has_store_deals': store_deals.exists(),
        'has_store_best_sellers': store_best_sellers.exists(),
        'has_store_new_arrivals': store_new_arrivals.exists(),
        'has_store_limited_deals': store_limited_deals.exists(),
        'has_store_special_offers': store_special_offers.exists(),
        'has_store_featured': store_featured.exists(),  # ← THIS WAS WRONG BEFORE!

        # Only categories with products in this store
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
    # CHECK IF ALREADY ENQUIRED VIA SESSION (EVEN AFTER REFRESH!)
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
                source='whatsapp_form'
            )
            # MARK AS ENQUIRED IN SESSION — FORM WILL NEVER COME BACK!
            request.session[session_key] = True
            request.session.modified = True
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
    # If we came from a specific store (via ?store=slug), show only its categories
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
        # Normal behavior - show ALL categories
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