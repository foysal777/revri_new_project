from enum import Enum

class UserRole(Enum):
    ADMIN = "admin"
    NORMAL = "normal"

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]