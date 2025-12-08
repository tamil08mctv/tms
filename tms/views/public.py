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
        created_at__gte=seven_days_ago,
        store__is_active=True
    ).select_related('store', 'category').prefetch_related('images')[:20]

    # BANNERS
    banners = StoreBanner.objects.filter(is_active=True).order_by('-created_at')
    if not banners.exists():
        banners = Store.objects.filter(is_active=True, banner__isnull=False)

    context.update({
        'stores': Store.objects.filter(is_active=True)[:8],
        'deals_of_day': deals,
        'featured_products': featured,
        'best_sellers': best_sellers,
        'limited_deals': limited_deals,
        'special_offers': special_offers,
        'new_arrivals': new_arrivals,
        'categories_all': Category.objects.all()[:12],
        'all_store_banners': banners,

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
    filter_type = request.GET.get('filter')

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if store_slug:
        products = products.filter(store__slug=store_slug)

    # TYPE FILTER
    if filter_type == 'bestselling':
        products = products.filter(is_best_seller=True)
    elif filter_type == 'limited':
        products = products.filter(is_limited_deal=True)
    elif filter_type == 'special':
        products = products.filter(is_special_offer=True)
    elif filter_type == 'deals':
        products = products.filter(deal_end_date__gte=today)
    elif filter_type == 'new':
        seven_days_ago = timezone.now() - timedelta(days=7)
        products = products.filter(created_at__gte=seven_days_ago)

    # SORTING
    sort = request.GET.get('sort', '')
    if sort == 'price_low':
        products = products.order_by('offer_price', '-created_at')
    elif sort == 'price_high':
        products = products.order_by('-offer_price', '-created_at')
    elif sort == 'new':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('-created_at')

    # PAGINATION — THIS LINE WAS WRONG!
    paginator = Paginator(products, 25)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)   # CORRECT LINE!

    current_category = Category.objects.filter(slug=category_slug).first() if category_slug else None
    current_store = Store.objects.filter(slug=store_slug).first() if store_slug else None

    context.update({
        'products': products_page,
        'current_category': current_category,
        'current_store': current_store,
        'categories_all': Category.objects.all(),
        'stores_all': Store.objects.filter(is_active=True),
        'seven_days_ago': seven_days_ago,
    })
    return render(request, 'TMS/public/allproducts.html', context)

# def all_products(request):
#     context = get_common_context()
#     today = date.today()

#     products = Product.objects.filter(store__is_active=True).select_related('store', 'category').prefetch_related('images').order_by('name')

#     # GET PARAMETERS
#     q = request.GET.get('q', '').strip()
#     category_slug = request.GET.get('category')
#     sort = request.GET.get('sort')  # new, price_low, price_high

#     # FILTERS
#     if q:
#         products = products.filter(Q(name__icontains=q) | Q(short_desc__icontains=q) | Q(store__name__icontains=q))
#     if category_slug:
#         products = products.filter(category__slug=category_slug)

#     # SORTING — FIXED!
#     if sort == 'price_low':
#         products = products.order_by('offer_price', '-created_at')
#     elif sort == 'price_high':
#         products = products.order_by('-offer_price', '-created_at')
#     elif sort == 'new':
#         products = products.order_by('-created_at')
#     else:
#         products = products.order_by('-created_at')  # default

#     # PAGINATION
#     paginator = Paginator(products, 24)
#     page = request.GET.get('page')
#     products_page = paginator.get_page(page)

#     # Current category object for title
#     current_category = None
#     if category_slug:
#         try:
#             current_category = Category.objects.get(slug=category_slug)
#         except:
#             pass

#     context.update({
#         'products': products_page,
#         'categories': Category.objects.all(),
#         'current_category': current_category,
#         'categories_all': Category.objects.all()[:20],
#     })
#     return render(request, 'TMS/public/allproducts.html', context)


# def home(request):
#     context = get_common_context()
#     today = date.today()
#     deals = Product.objects.filter(
#         price_style='deal',
#         deal_end_date__gte=today,
#         store__is_active=True
#     )[:20]

#     context.update({
#         'stores': Store.objects.filter(is_active=True)[:8],
#         'deals_of_day': deals,
#         'featured_products': Product.objects.filter(is_featured=True)[:20],
#     })
#     return render(request, 'TMS/public/home.html', context)

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
    
    # PRE-FETCH DEALS & FEATURED FOR THIS STORE ONLY
    store_deals = store.products.filter(
        deal_end_date__gte=date.today(),
    )
    featured_store = store.products.filter(is_featured=True)

    context.update({
        'store': store,
        'store_deals': store_deals,
        'featured_store': featured_store,
        'products': store.products.all(),  # fallback
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
    product = get_object_or_404(Product, slug=product_slug, store__slug=store_slug, store__is_active=True)
  
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



from django.core.paginator import Paginator

def deals_view(request):
    today = date.today()
    deals = Product.objects.filter(
        deal_end_date__gte=today,
        store__is_active=True
    ).select_related('store').prefetch_related('images').order_by('-created_at')

    paginator = Paginator(deals, 40)  # 40 per page
    page = request.GET.get('page')
    products = paginator.get_page(page)

    context = get_common_context()
    context.update({
        'products': products,
        'page_title': 'Deals of the Day',
    })
    return render(request, 'TMS/public/deals.html', context)


def featured_view(request):
    featured = Product.objects.filter(
        is_featured=True,
        store__is_active=True
    ).select_related('store').prefetch_related('images').order_by('-created_at')

    paginator = Paginator(featured, 40)
    page = request.GET.get('page')
    products = paginator.get_page(page)

    context = get_common_context()
    context.update({
        'products': products,
        'page_title': 'Featured Products',
    })
    return render(request, 'TMS/public/featured.html', context)

def categories_page(request):
    categories_list = Category.objects.annotate(
        product_count=Count('product')  # 'product' is default reverse name
    ).order_by('name')

    paginator = Paginator(categories_list, 36)  # 24 per page
    page_number = request.GET.get('page')
    categories = paginator.get_page(page_number)

    return render(request, 'TMS/public/categories.html', {
        'categories': categories,
        'page_obj': categories,
        'paginator': paginator,
        'is_paginated': categories.has_other_pages(),
    })
