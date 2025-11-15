# myApp/admin.py
from django.contrib import admin
from .models import UserProfile, Product, Customer, Bill, BillItem, Payment

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['bill_number', 'customer', 'date', 'total_amount', 'payment_status', 'created_by']
    list_filter = ['date', 'payment_status', 'created_by']
    search_fields = ['bill_number', 'customer__name']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'date', 'payment_method', 'received_by']
    list_filter = ['date', 'payment_method', 'received_by']
    search_fields = ['customer__name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'market_price', 'current_stock', 'last_updated', 'updated_by']