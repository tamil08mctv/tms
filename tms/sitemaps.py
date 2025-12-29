# tms/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Store, Category

class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Product.objects.filter(store__is_active=True)

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return f"/store/{obj.store.slug}/product/{obj.slug}/"


class StoreSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Store.objects.filter(is_active=True)

    def location(self, obj):
        return f"/store/{obj.slug}/"


class CategorySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return reverse('all_products') + f"?category={obj.slug}"


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1.0

    def items(self):
        return ['home', 'all_products', 'store_list', 'categories_page']

    def location(self, item):
        return reverse(item)