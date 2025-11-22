# tms/views/public.py → FINAL FIXED VERSION
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, F
from ..models import Store, Product, ProductImage, Category, Lead
from ..forms import EnquiryForm
import urllib.parse

# COMMON DATA FOR NAVBAR
def get_common_context():
    return {
        'stores_all': Store.objects.filter(is_active=True),
        'categories_all': Category.objects.all().distinct()[:10],
    }

def home(request):
    context = get_common_context()
    context.update({
        'stores': Store.objects.filter(is_active=True)[:8],
        'featured_products': Product.objects.filter(is_featured=True)[:12],
        'popular_products': Product.objects.order_by('-views_count')[:6],
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
    products = Product.objects.filter(store=store)
    
    context.update({
        'store': store,
        'products': products,
        'featured': products.filter(is_featured=True)[:8],
        'categories': store.categories.all()
    })
    return render(request, 'TMS/public/storedetail.html', context)

def product_list(request, store_slug):
    context = get_common_context()
    store = get_object_or_404(Store, slug=store_slug)
    products = Product.objects.filter(store=store)
    
    # Add filters if needed later
    context.update({
        'store': store,
        'products': products,
        'categories': store.categories.all()
    })
    return render(request, 'TMS/public/productlist.html', context)

def product_detail(request, store_slug, product_slug):
    context = get_common_context()
    product = get_object_or_404(Product, slug=product_slug, store__slug=store_slug)
    
    # Increase view count
    Product.objects.filter(pk=product.pk).update(views_count=F('views_count') + 1)
    product.refresh_from_db()
    
    images = product.images.all()
    similar = Product.objects.filter(category=product.category).exclude(id=product.id)[:6]
    
    whatsapp_msg = f"Hi {product.store.name}! Interested in {product.name}\nPrice: {product.get_price_display()}\nLink: {request.build_absolute_uri()}"
    whatsapp_url = f"https://wa.me/{product.store.whatsapp}?text={urllib.parse.quote(whatsapp_msg)}"
    
    form = EnquiryForm(request.POST or None)
    if form.is_valid():
        Lead.objects.create(
            store=product.store,
            product=product,
            **form.cleaned_data,
            source='form'
        )
        return redirect(whatsapp_url)
    
    context.update({
        'product': product,
        'images': images,
        'similar': similar,
        'whatsapp_url': whatsapp_url,
        'form': form
    })
    return render(request, 'TMS/public/productdetail.html', context)