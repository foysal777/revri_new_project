from django.db import models
from pytz import timezone
from accounts.models import User
from common.basemodel import BaseModel
from . import enums

# Create your models here.


class AISetting(BaseModel):

    ai_restriction = models.TextField(blank=True, default="")
    response_style = models.CharField(choices=enums.AI_VOICE_TYPE.choices, default=enums.AI_VOICE_TYPE.FORMAL.value, max_length=50)

    # Query statistics
    total_query_count = models.BigIntegerField(default=0)
    today_query_count = models.IntegerField(default=0)
    # date for which `today_query_count` is valid
    today_date = models.DateField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    @classmethod
    def get_active(cls):
        obj = cls.objects.filter(is_active=True).order_by('-updated_at').first()
        if not obj:
            # Ensure at least one configuration exists
            obj = cls.objects.create(ai_restriction="", response_style=enums.AI_VOICE_TYPE.FORMAL.value)
        return obj

    def increment_query_counts(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.today_date != today:
            self.today_date = today
            self.today_query_count = 0
        self.today_query_count = (self.today_query_count or 0) + 1
        self.total_query_count = (self.total_query_count or 0) + 1
        self.save(update_fields=['today_date', 'today_query_count', 'total_query_count'])

    def __str__(self):
        return f"AI System Settings (Last Updated: {self.updated_at.strftime('%Y-%m-%d')})"


class KnowledgePDF(BaseModel):

    file = models.FileField(upload_to='knowledge_pdfs/')
    is_active = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_active:
            KnowledgePDF.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f"{self.file.name} ({status})"


class BlockedKeyword(BaseModel):

    word = models.CharField(max_length=100, unique=True, db_index=True)

    def __str__(self):
        return self.word


class UserQueryLog(BaseModel):

    query_text = models.TextField()
    response_text = models.TextField(blank=True, null=True)
    is_blocked = models.BooleanField(default=False)

    @classmethod
    def get_today_query_count(cls):

        today = timezone.now().date()
        return cls.objects.filter(updated_at__date=today).count()

    def __str__(self):
        status = "Blocked" if self.is_blocked else "Success"
        return f"Query on {self.updated_at.strftime('%Y-%m-%d %H:%M')} - Status: {status}"




class ChatRoom(BaseModel):
    name = models.CharField(max_length=255)
    human = models.ForeignKey(User, on_delete=models.CASCADE, related_name='human_chatrooms')
    ai_response = models.TextField(blank=True, null=True)

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    



class Message(BaseModel):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')

    message = models.TextField(default="")

    ai_response = models.TextField(blank=True, null=True, default="1")

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.sender.email} in {self.room.name}"
    
