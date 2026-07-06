from django.core.exceptions import ValidationError
from django.db import models
from common.basemodel import BaseModel
from accounts.models import User
from notifiation.enums import RepetedType
from plan.enums import PlanType
# Create your models here.



class Notification(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    select_audience = models.JSONField(default=list, blank=True)
    title = models.CharField(max_length=255)
    notification_banner = models.FileField(upload_to='notification_banners/', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_read = models.BooleanField(default=False)

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.description}"

    def clean(self):
        super().clean()
        valid_values = [choice[0] for choice in PlanType.choices()]
        invalid = [value for value in self.select_audience if value not in valid_values]
        if invalid:
            raise ValidationError({'select_audience': f"Invalid plan type(s): {invalid}. Valid values are: {valid_values}."})
    


class Email(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emails')
    # Store the timezone the user supplied when creating the scheduled email.
    # This allows the scheduler to convert the stored local date/time correctly
    # even if the User.profile.time_zone is empty.
    user_time_zone = models.CharField(max_length=64, null=True, blank=True)
    set_date = models.DateField(null=True, blank=True)
    set_time = models.TimeField(null=True, blank=True)
    select_audience = models.JSONField(default=list, blank=True)
    is_repeated = models.BooleanField(default=False)
    repeated_type = models.CharField(max_length=20, choices=RepetedType.choices(), null=True, blank=True)
    describe_email = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)


    def __str__(self):
        return f"Email for {self.user.username}: {self.describe_email}"

    def clean(self):
        super().clean()
        valid_values = [choice[0] for choice in PlanType.choices()]
        invalid = [value for value in self.select_audience if value not in valid_values]
        if invalid:
            raise ValidationError({'select_audience': f"Invalid plan type(s): {invalid}. Valid values are: {valid_values}."})
