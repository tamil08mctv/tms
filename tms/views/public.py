# tms/views/public.py → ULTIMATE AUTO-SEND + SIMILAR PRODUCTS

from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, F
from ..models import Store, Product, Category, SubCategory, Lead
from ..forms import EnquiryForm
import urllib.parse
from datetime import date

def get_common_context():
    return {
        'stores_all': Store.objects.filter(is_active=True),
        'categories_all': Category.objects.all().distinct(),
    }

def all_products(request):
    context = get_common_context()
    products = Product.objects.filter(store__is_active=True).select_related('store', 'category')
    
    search = request.GET.get('q')
    category = request.GET.get('category')
    city = request.GET.get('city')
    price = request.GET.get('price')
    
    if search:
        products = products.filter(Q(name__icontains=search) | Q(short_desc__icontains=search))
    if category:
        products = products.filter(category__slug=category)
    if city:
        products = products.filter(store__city__iexact=city)
    if price == 'low':
        products = products.order_by('starting_price')
    elif price == 'high':
        products = products.order_by('-starting_price')
    else:
        products = products.order_by('-created_at')
    
    paginator = Paginator(products, 24)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    context.update({
        'products': products_page,
        'categories': Category.objects.all(),
        'cities': Store.objects.values_list('city', flat=True).distinct(),
        'current_category': category,
        'search_query': search
    })
    return render(request, 'TMS/public/allproducts.html', context)


def home(request):
    context = get_common_context()
    today = date.today()
    deals = Product.objects.filter(
        price_style='deal',
        deal_end_date__gte=today,
        store__is_active=True
    )[:20]

    context.update({
        'stores': Store.objects.filter(is_active=True)[:8],
        'deals_of_day': deals,
        'featured_products': Product.objects.filter(is_featured=True)[:20],
    })
    return render(request, 'TMS/public/home.html', context)

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
        price_style='deal',
        deal_end_date__gte=date.today()
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

def product_detail(request, store_slug, product_slug):
    context = get_common_context()
    product = get_object_or_404(Product, slug=product_slug, store__slug=store_slug, store__is_active=True)
    
    # View count
    Product.objects.filter(pk=product.pk).update(views_count=F('views_count') + 1)
    product.refresh_from_db()
    
    images = product.images.all()
    
    # 🔥 SIMILAR PRODUCTS BY CATEGORY (PERFECT!)
    if product.category:
        similar_same_category = Product.objects.filter(
            category=product.category,
            store__is_active=True
        ).exclude(id=product.id)[:6]
    else:
        similar_same_category = []
    
    # If no same category products, show popular products
    # Similar products
    similar = Product.objects.filter(subcategory=product.subcategory, store__is_active=True).exclude(id=product.id)[:8]
    if not similar:
        similar = Product.objects.filter(category=product.category, store__is_active=True).exclude(id=product.id)[:8]
    if not similar:
        similar = Product.objects.filter(is_featured=True)[:8]
    
    # PHONE CLEANING
    phone_raw = product.store.whatsapp
    clean_phone = ''.join(filter(str.isdigit, phone_raw))
    if len(clean_phone) == 10:
        phone = "91" + clean_phone
    elif clean_phone.startswith("91") and len(clean_phone) == 12:
        phone = clean_phone
    else:
        phone = "919629828969"

    # PERFECT MESSAGE
    message = f"""Hi {product.store.name}!

I'm very interested in:

*{product.name}*
Price: {product.get_price_display()}
Category: {product.category.name if product.category else 'General'}
Store: {product.store.name}, {product.store.city}
Link: {request.build_absolute_uri()}"""

    # WHATSAPP URLS
    web_whatsapp = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
    mobile_whatsapp = f"whatsapp://send?phone={phone}&text={urllib.parse.quote(message)}"
    
    # DETECT DEVICE
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(x in user_agent for x in ['android', 'iphone', 'ipad', 'mobile'])
    is_android = 'android' in user_agent

    form = EnquiryForm(request.POST or None)
    if form.is_valid():
        Lead.objects.create(
            store=product.store,
            product=product,
            source='whatsapp_form',
            **form.cleaned_data
        )
        if is_android:
            return redirect(mobile_whatsapp)
        else:
            return redirect(web_whatsapp)

    context.update({
        'product': product,
        'images': images,
        'similar': similar,
        'whatsapp_url': web_whatsapp,
        'mobile_whatsapp': mobile_whatsapp,
        'form': form,
        'is_mobile': is_mobile,
        'is_android': is_android,
        'similar_category_count': len(similar_same_category)
    })
    return render(request, 'TMS/public/productdetail.html', context)