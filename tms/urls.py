# tms/urls.py → FINAL VERSION (100% WORKING)
from django import views
from django.urls import path
from django.contrib.auth import views as auth_views
from .views.public import *
from .views.storeadmin import *
from .views.superadmin import *
from .views.auth import login_redirect
from tms.views import storeadmin

urlpatterns = [
    # PUBLIC PAGES
    path('', home, name='home'),
    path('products/', all_products, name='all_products'),
    path('stores/', store_list, name='store_list'),
    path('store/<slug:slug>/', store_detail, name='store_detail'),
    path('store/<slug:store_slug>/products/', product_list, name='product_list'),
    path('store/<slug:store_slug>/product/<slug:product_slug>/', product_detail, name='product_detail'),
    path('deals/', deals_view, name='deals'),      
    path('featured/', featured_view, name='featured'),

    # STORE ADMIN PANEL
    path('store-admin/', storeadmin.store_dashboard, name='store_dashboard'),
    path('store-admin/products/', storeadmin.store_products, name='store_products'),
    path('store-admin/products/edit/<int:pk>/', storeadmin.edit_product, name='edit_product'),
    path('store-admin/products/delete/<int:pk>/', storeadmin.delete_product, name='delete_product'),
    path('store-admin/banners/', storeadmin.store_banners, name='store_banners'),
    path('store-admin/banners/delete/<int:pk>/', storeadmin.delete_banner, name='delete_banner'),
    path('store-admin/leads/', storeadmin.store_leads, name='store_leads'),
    path('store-admin/leads/update/<int:lead_id>/', storeadmin.update_lead_status, name='update_lead_status'),
    path('store-admin/export-leads/', storeadmin.export_leads_csv, name='export_leads_csv'),
   
    path('store-admin/categories/', storeadmin.store_categories, name='store_categories'),
    path('store-admin/categories/edit/<int:pk>/', storeadmin.edit_category, name='edit_category'),
    path('store-admin/categories/delete/<int:pk>/', storeadmin.delete_category, name='delete_category'),



    # SUPER ADMIN PANEL — FULL CONTROL
    path('super-admin/', super_dashboard, name='super_dashboard'),
    path('super-admin/stores/', store_list_super, name='store_list_super'),           # NEW
    path('super-admin/create-store/', create_store, name='create_store'),
    path('super-admin/edit-store/<int:pk>/', edit_store, name='edit_store'),          # NEW
    path('super-admin/toggle-store/<int:pk>/', toggle_store, name='toggle_store'),    # NEW
    path('super-admin/all-leads/', all_leads, name='all_leads'),
    path('super-admin/export-all/', export_all_leads, name='export_all_leads'),

    # AUTH
    path('login/', auth_views.LoginView.as_view(template_name='TMS/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('login-redirect/', login_redirect, name='login_redirect'),
]