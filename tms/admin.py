# tms/admin.py → LIVE SLUG GENERATION WHILE TYPING (FLIPKART/MEESHO STYLE)
from django.contrib import admin
from django.utils.text import slugify
from .models import Store, StoreAdmin, Category, SubCategory, Product, ProductImage, Lead


# INLINE FOR StoreAdmin
class StoreAdminInline(admin.TabularInline):
    model = StoreAdmin
    extra = 1
    raw_id_fields = ('user',)


@admin.register(Store)
class StoreAdminPanel(admin.ModelAdmin):
    list_display = ['name', 'city', 'whatsapp', 'is_active', 'created_at']
    search_fields = ['name', 'city']
    list_filter = ['is_active', 'city']
    inlines = [StoreAdminInline]
    prepopulated_fields = {'slug': ('name',)}  # ← LIVE SLUG WHILE TYPING!


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
    prepopulated_fields = {'slug': ('name',)}  # ← LIVE SLUG FOR CATEGORY


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category']
    list_filter = ['category']
    prepopulated_fields = {'slug': ('name',)}  # ← LIVE SLUG FOR SUBCATEGORY


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'store', 'category', 'subcategory',
        'get_price_display', 'discount_percent',
        'is_deal_active', 'is_featured'
    ]
    list_filter = [
        'store', 'category', 'subcategory', 'price_style',
        'deal_end_date', 'is_featured', 'is_new'
    ]
    search_fields = ['name', 'short_desc']
    inlines = [ProductImageInline]
    readonly_fields = ['discount_percent', 'views_count', 'enquiry_count']
    
    # ← THIS IS THE MAGIC: LIVE SLUG WHILE TYPING PRODUCT NAME!
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        ('Basic Info', {
            'fields': ('store', 'category', 'subcategory', 'name', 'slug', 'short_desc', 'description')
        }),
        ('Pricing', {
            'fields': ('price_style', 'regular_price', 'offer_price', 'deal_end_date')
        }),
        ('Media', {
            'fields': ('video',)
        }),
        ('Status', {
            'fields': ('is_featured', 'is_new', 'in_stock')
        }),
    )

    def get_price_display(self, obj):
        return obj.get_price_display()
    get_price_display.short_description = 'Price Shown'

    def is_deal_active(self, obj):
        return obj.is_deal_active()
    is_deal_active.boolean = True
    is_deal_active.short_description = 'Deal Active'


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'phone', 'store', 'product', 'status', 'created_at']
    list_filter = ['store', 'status', 'source', 'created_at']
    search_fields = ['customer_name', 'phone', 'message']
    readonly_fields = ['created_at', 'uid']