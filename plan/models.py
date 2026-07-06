from django.db import models
from common.basemodel import BaseModel
from .enums import PlanType
# Create your models here.

class Plans(BaseModel):
    name = models.CharField(max_length=255)
    plantype = models.CharField(max_length=50, choices=PlanType.choices(), default=PlanType.FREE.value)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    questions_per_month = models.IntegerField(default=5, help_text="-1 for unlimited")
    stripe_price_id = models.CharField(max_length=255, blank=True, null=True)
    billing_cycle = models.CharField(max_length=50, default='Monthly')
    badge = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def default_features():
        return ["Feature 1", "Feature 2", "Feature 3"]
        
    features = models.JSONField(default=default_features, help_text='List of features for this plan')

    def __str__(self):
        return self.name


class UserSubscription(BaseModel):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plans, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscribers')
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, default='active') # active, cancelled, etc.
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        plan_name = self.plan.name if self.plan else "Unknown Plan"
        return f"{self.user.email} - {plan_name} ({self.status})"
