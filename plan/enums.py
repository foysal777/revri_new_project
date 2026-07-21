from enum import Enum

class PlanType(Enum):
    FREE = 'free'
    CORE = 'core'
    BUILDER = 'builder'
    ANCHOR = 'anchor'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls] 