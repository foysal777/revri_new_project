from rest_framework import serializers
from .models import Product, UploadThumbnail


class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = ['id', 'name', 'product_type', 'link', 'description', 'is_published', 'product_price', 'product_image', 'created_at']
        read_only_fields = ['id', 'created_at']


class UploadThumbnailSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadThumbnail
        fields = ['id', 'title', 'image', 'expirey_date', 'is_active', 'active_count', 'created_at']
        read_only_fields = ['id', 'active_count', 'created_at']



