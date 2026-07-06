from enum import Enum

class RepetedType(Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]