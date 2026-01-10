from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import redirect
from .models import (
    Store, StoreAdmin, Category, Product, ProductImage,
    Lead, StoreBanner, ProductSpecification, SiteSettings, SocialLink,
    VariantAttribute, ProductVariant, VariantValue, ProductVariantImage, VariantSpecification
)

# ======================= INLINES =======================

class StoreAdminInline(admin.TabularInline):
    model = StoreAdmin
    extra = 1
    raw_id_fields = ('user',)

class StoreBannerInline(admin.TabularInline):
    model = StoreBanner
    extra = 1
    fields = ('image_desktop', 'image_tablet', 'image_mobile', 'link', 'caption', 'is_active', 'order')

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 2
    fields = ('image', 'image_preview', 'is_main', 'sort_order')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px; border-radius:8px; object-fit:cover;" />',
                obj.image.url
            )
        return "(No image)"
    image_preview.short_description = "Preview"

class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 3
    fields = ('name', 'value')

# Variant Inlines - FULLY NESTED
class VariantValueInline(admin.TabularInline):
    model = VariantValue
    extra = 2
    fields = ('attribute', 'value')

class VariantSpecificationInline(admin.TabularInline):
    model = VariantSpecification
    extra = 3
    fields = ('name', 'value')

class ProductVariantImageInline(admin.TabularInline):
    model = ProductVariantImage
    extra = 3
    fields = ('image', 'is_main', 'sort_order')
    readonly_fields = ('image',)  # Optional: make image preview if needed

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('regular_price', 'offer_price', 'in_stock', 'image')
    inlines = [
        VariantValueInline,          # Values like Color: Red
        VariantSpecificationInline,  # Specs like Weight: 15kg
        ProductVariantImageInline    # Additional images per variant
    ]

class VariantAttributeInline(admin.TabularInline):
    model = VariantAttribute
    extra = 1
    fields = ('name',)

# ======================= ADMIN CLASSES =======================

@admin.register(Store)
class StoreAdminPanel(admin.ModelAdmin):
    list_display = ('name', 'city', 'whatsapp', 'is_active', 'created_at')
    search_fields = ('name', 'city', 'whatsapp')
    list_filter = ('is_active', 'city')
    inlines = (StoreAdminInline, StoreBannerInline)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'get_product_count')
    list_filter = ('store',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

    def get_product_count(self, obj):
        return obj.products.count()
    get_product_count.short_description = "Products"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'store', 'category', 'admin_price', 'discount_percent',
        'call_for_price', 'in_stock', 'is_best_seller', 'is_limited_deal',
        'is_special_offer', 'is_featured', 'views_count'
    )
    list_filter = (
        'store', 'category', 'call_for_price', 'in_stock', 'is_best_seller',
        'is_limited_deal', 'is_special_offer', 'is_featured', 'deal_end_date'
    )
    search_fields = ('name', 'short_desc', 'description')
    readonly_fields = ('discount_percent', 'views_count', 'enquiry_count')
    prepopulated_fields = {'slug': ('name',)}

    inlines = (
        ProductImageInline,
        ProductSpecificationInline,
        VariantAttributeInline,       # ← Variant Types (Color, Size)
        ProductVariantInline          # ← Full variants with values, specs, images
    )

    fieldsets = (
        ('Basic Info', {
            'fields': ('store', 'category', 'name', 'slug', 'short_desc', 'description')
        }),
        ('Pricing', {
            'fields': ('regular_price', 'offer_price', 'deal_end_date', 'call_for_price')
        }),
        ('Status & Badges', {
            'fields': (
                'in_stock', 'is_featured', 'is_best_seller',
                'is_limited_deal', 'is_special_offer', 'is_new_arrival'
            )
        }),
        ('Statistics', {
            'fields': ('views_count', 'enquiry_count', 'discount_percent'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('video',),
            'description': "Upload product video (optional)"
        }),
    )

    def admin_price(self, obj):
        if obj.call_for_price:
            return "Call for Best Price"
        price = obj.offer_price or obj.regular_price
        return f"₹{price}" if price is not None else "—"
    admin_price.short_description = "Price"

@admin.register(StoreBanner)
class StoreBannerAdmin(admin.ModelAdmin):
    list_display = ('store', 'caption', 'is_active', 'order', 'created_at')
    list_filter = ('store', 'is_active')
    search_fields = ('store__name', 'caption')

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'phone', 'store', 'product', 'status', 'created_at')
    list_filter = ('store', 'status', 'created_at')
    search_fields = ('customer_name', 'phone', 'city')
    readonly_fields = ('created_at',)

@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'value')
    list_filter = ('product__store',)
    search_fields = ('name', 'value', 'product__name')

class SocialLinkInline(admin.TabularInline):
    model = SocialLink
    extra = 1
    fields = ('platform', 'url', 'order')

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'phone', 'email')
    inlines = [SocialLinkInline]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        if not SiteSettings.objects.exists():
            return redirect('admin:tms_sitesettings_add')
        return super().changelist_view(request, extra_context=extra_context)