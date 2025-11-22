# tms/admin.py → FINAL WITH INLINE IMAGES
from django.contrib import admin
from .models import Store, StoreAdmin, Category, Product, ProductImage, Lead


# INLINE IMAGES — ADMIN CAN ADD 100 IMAGES EASILY!
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'is_main')


@admin.register(Store)
class StoreAdminPanel(admin.ModelAdmin):
    list_display = ['name', 'city', 'whatsapp', 'is_active']
    search_fields = ['name', 'city']
    list_filter = ['is_active', 'city']


@admin.register(StoreAdmin)
class StoreAdminUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'store']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'store']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'price_style', 'is_featured', 'created_at']
    list_filter = ['store', 'price_style', 'is_featured']
    search_fields = ['name']
    inlines = [ProductImageInline]  # THIS IS THE MAGIC!


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'phone', 'store', 'status', 'created_at']
    list_filter = ['store', 'status', 'source']
    search_fields = ['customer_name', 'phone']