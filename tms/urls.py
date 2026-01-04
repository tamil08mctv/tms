# tms/urls.py â†’ FINAL WITH ADMIN PATHS

from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from .sitemaps import ProductSitemap, StoreSitemap, CategorySitemap, StaticViewSitemap

# Import all views properly
from .views.public import (
    home, all_products, store_list, store_detail, 
    product_detail,
    categories_page,search_suggestions
)
from .views.storeadmin import (
    store_dashboard, store_products, edit_product, delete_product,
    store_banners, store_leads, update_lead_status, export_leads_csv,
    store_categories, edit_category, delete_category
)
from .views.superadmin import (
    super_dashboard, store_list_super, create_store, 
    edit_store, toggle_store, export_all_leads,site_settings, all_leads,
    manage_store_admins, create_store_admin, edit_store_admin, toggle_store_admin, delete_store_admin,delete_store # â† NEW
)
from .views.auth import login_redirect

sitemaps = {
    'products': ProductSitemap,
    'stores': StoreSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
}

urlpatterns = [
    # ==================== PUBLIC PAGES ====================
    path('', home, name='home'),
    path('products/', all_products, name='all_products'),
    path('stores/', store_list, name='store_list'),
    path('store/<slug:slug>/', store_detail, name='store_detail'),
  
    path('store/<slug:store_slug>/product/<slug:product_slug>/', product_detail, name='product_detail'),
    path('categories/', categories_page, name='categories_page'),
 
    path('store/<slug:slug>/categories/', categories_page, name='store_categories'),
    path('search-suggestions/', search_suggestions, name='search_suggestions'),

    # ==================== STORE ADMIN PANEL ====================
    path('store-admin/', store_dashboard, name='store_dashboard'),
    path('store-admin/products/', store_products, name='store_products'),
    path('store-admin/products/edit/<int:pk>/', edit_product, name='edit_product'),
    path('store-admin/products/delete/<int:pk>/', delete_product, name='delete_product'),
    path('store-admin/banners/', store_banners, name='store_banners'),
    path('store-admin/leads/', store_leads, name='store_leads'),
    path('store-admin/leads/update/<int:lead_id>/', update_lead_status, name='update_lead_status'),
    path('store-admin/export-leads/', export_leads_csv, name='export_leads_csv'),
    path('store-admin/categories/', store_categories, name='store_categories'),
    path('store-admin/categories/edit/<int:pk>/', edit_category, name='edit_category'),
    path('store-admin/categories/delete/<int:pk>/', delete_category, name='delete_category'),

    # ==================== SUPER ADMIN PANEL ====================
    path('super-admin/', super_dashboard, name='super_dashboard'),
    path('super-admin/stores/', store_list_super, name='store_list_super'),
    path('super-admin/create-store/', create_store, name='create_store'),
    path('super-admin/edit-store/<int:pk>/', edit_store, name='edit_store'),
    path('super-admin/toggle-store/<int:pk>/', toggle_store, name='toggle_store'),
    path('super-admin/all-leads/', all_leads, name='all_leads'),
    path('super-admin/export-all/', export_all_leads, name='export_all_leads'),
    path('site-settings/', site_settings, name='site_settings'),

    # NEW: Admin Management Paths
    path('super-admin/store/<int:pk>/admins/', manage_store_admins, name='manage_store_admins'),
    path('super-admin/store/<int:pk>/admins/create/', create_store_admin, name='create_store_admin'),
    path('super-admin/store/<int:pk>/admins/edit/<int:admin_pk>/', edit_store_admin, name='edit_store_admin'),
    path('super-admin/store/<int:pk>/admins/toggle/<int:admin_pk>/', toggle_store_admin, name='toggle_store_admin'),
    path('super-admin/store/<int:pk>/admins/delete/<int:admin_pk>/', delete_store_admin, name='delete_store_admin'),
    path('super-admin/delete-store/<int:pk>/', delete_store, name='delete_store'),

    # ==================== AUTH ====================
    path('login/', auth_views.LoginView.as_view(template_name='TMS/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
    template_name='TMS/login.html',
    next_page='login'  # â† This forces redirect to /login/ URL
), name='logout'),
    path('login-redirect/', login_redirect, name='login_redirect'),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
]