# tms/urls.py → FINAL VERSION (100% WORKING)
from django.urls import path
from django.contrib.auth import views as auth_views
from .views.public import *
from .views.storeadmin import *
from .views.superadmin import *
from .views.auth import login_redirect

urlpatterns = [
    # PUBLIC PAGES
    path('', home, name='home'),
    path('products/', all_products, name='all_products'),
    path('stores/', store_list, name='store_list'),
    path('store/<slug:slug>/', store_detail, name='store_detail'),
    path('store/<slug:store_slug>/products/', product_list, name='product_list'),
    path('store/<slug:store_slug>/product/<slug:product_slug>/', product_detail, name='product_detail'),

    # STORE ADMIN PANEL
    path('store-admin/', store_dashboard, name='store_dashboard'),
    path('store-admin/leads/', store_leads, name='store_leads'),
    path('store-admin/leads/update/<int:lead_id>/<str:status>/', update_lead),
    path('store-admin/products/', store_products, name='store_products'),
    path('store-admin/export/', export_leads_csv),

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