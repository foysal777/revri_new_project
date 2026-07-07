from django.contrib import admin
from .models import  Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id',  'name', 'product_type', 'is_published', 'product_price')
    search_fields = ('name', 'description')
    list_filter = ('product_type', 'is_published')
