# tms/admin.py → FINAL FIXED VERSION

from django.contrib import admin
from django.utils.text import slugify
from .models import Store, StoreAdmin, Category, SubCategory, Product, ProductImage, Lead, StoreBanner


# INLINE FOR StoreAdmin
class StoreAdminInline(admin.TabularInline):
    model = StoreAdmin
    extra = 1
    raw_id_fields = ('user',)


# INLINE FOR BANNERS - THIS IS THE MAGIC!
class StoreBannerInline(admin.TabularInline):
    model = StoreBanner
    extra = 1
    fields = ('image', 'caption', 'is_active')
    verbose_name = "Extra Banner"
    verbose_name_plural = "Extra Banners (for Home Page)"


@admin.register(Store)
class StoreAdminPanel(admin.ModelAdmin):
    list_display = ['name', 'city', 'whatsapp', 'is_active', 'created_at']
    search_fields = ['name', 'city']
    list_filter = ['is_active', 'city']
    inlines = [StoreAdminInline, StoreBannerInline]  # ← BANNERS HERE!
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    fields = ('image', 'is_main')


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'store']
    list_filter = ['store']
    inlines = [SubCategoryInline]
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category']
    list_filter = ['category']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'category', 'get_price_display', 'discount_percent', 'is_deal_active', 'is_featured']
    list_filter = ['store', 'category', 'price_style', 'deal_end_date', 'is_featured']
    search_fields = ['name', 'short_desc']
    inlines = [ProductImageInline]
    readonly_fields = ['discount_percent', 'views_count', 'enquiry_count']
    prepopulated_fields = {'slug': ('name',)}

    def get_price_display(self, obj):
        return obj.get_price_display()
    get_price_display.short_description = 'Price'

    def is_deal_active(self, obj):
        return obj.is_deal_active()
    is_deal_active.boolean = True


@admin.register(StoreBanner)
class StoreBannerAdmin(admin.ModelAdmin):
    list_display = ['store', 'is_active', 'created_at']
    list_filter = ['is_active', 'store']
    search_fields = ['store__name']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'phone', 'store', 'product', 'status', 'created_at']
    list_filter = ['store', 'status', 'created_at']
    search_fields = ['customer_name', 'phone']