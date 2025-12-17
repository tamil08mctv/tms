# tms/urls.py → FINAL 100% CLEAN & WORKING VERSION
from django.urls import path
from django.contrib.auth import views as auth_views

# Import all views properly
from .views.public import (
    home, all_products, store_list, store_detail, 
    product_list, product_detail,
    categories_page,search_suggestions
)
from .views.storeadmin import (
    store_dashboard, store_products, edit_product, delete_product,
    store_banners, store_leads, update_lead_status, export_leads_csv,
    store_categories, edit_category, delete_category
)
from .views.superadmin import (
    super_dashboard, store_list_super, create_store, 
    edit_store, toggle_store, all_leads, export_all_leads,site_settings
)
from .views.auth import login_redirect

urlpatterns = [
    # ==================== PUBLIC PAGES ====================
    path('', home, name='home'),
    path('products/', all_products, name='all_products'),
    path('stores/', store_list, name='store_list'),
    path('store/<slug:slug>/', store_detail, name='store_detail'),
    path('store/<slug:store_slug>/products/', product_list, name='product_list'),
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

    # ==================== AUTH ====================
    path('login/', auth_views.LoginView.as_view(template_name='TMS/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('login-redirect/', login_redirect, name='login_redirect'),
]