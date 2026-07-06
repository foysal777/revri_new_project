from enum import Enum

class AI_VOICE_TYPE(Enum):
    PROFESSIONAL = 'professional'
    FRIENDLY = 'friendly'
    FORMAL = 'formal'
    CASUAL = 'casual'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]
    


class ResponseLenth(Enum):
    SHORT = 'short'
    MEDIUM = 'medium'
    LONG = 'long'

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]