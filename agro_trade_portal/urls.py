from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib import admin
from myApp import views

urlpatterns = [
    # Authentication
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.user_profile, name='profile'),
    path('lending/', views.customer_lending, name='customer_lending'),
    path('customer/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('search-customers/', views.search_customers, name='search_customers'),
    
    # Billing
    path('bills/', views.bill_list, name='bill_list'),
    path('bills/create/', views.create_bill, name='create_bill'),
    path('bills/<int:bill_id>/', views.bill_detail, name='bill_detail'),
    
    # Payments
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/receive/', views.receive_payment, name='receive_payment'),
    path('payments/success/', views.payment_success, name='payment_success'),
    
    # Reports
    path('reports/activity/', views.user_activity_report, name='activity_report'),
]