from enum import Enum

class ProductType(Enum):
    RESOURCE = 'resource'
    CONSULTANCY = 'consultancy'
    ECOMMERCE = 'ecommerce'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]
    
