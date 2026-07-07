from enum import Enum

class ProductType(Enum):
    RESOURCE = 'resource'
    SERVICES = 'services'
    ASSESSMENT = 'assessment'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]
    
