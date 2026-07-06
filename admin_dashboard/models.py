from django.db import models
from common.basemodel import BaseModel
from .enums import ProductType


class Product(BaseModel):
    name = models.CharField(max_length=255)
    product_type = models.CharField(max_length=50, choices=ProductType.choices, default=ProductType.RESOURCE.value)
    link = models.URLField(max_length=500, null=True, blank=True)
    description = models.TextField()
    is_published = models.BooleanField(default=True)
    product_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product_image = models.FileField(upload_to='products/')


    def __str__(self):
        return f"{self.name} ({self.product_type})"
    


class UploadThumbnail(BaseModel):
    title = models.CharField(max_length=255, null=True, blank=True)
    image = models.FileField(upload_to='thumbnails/')
    expirey_date = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    active_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Thumbnail {self.id}"

