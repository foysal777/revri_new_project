from django.contrib import admin
from .models import Plans

@admin.register(Plans)
class PlansAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'plantype', 'price', 'is_active', 'questions_per_month')
    list_filter = ('is_active', 'plantype', 'billing_cycle')
    search_fields = ('name', 'plantype')

from .models import UserSubscription
@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'status', 'start_date', 'stripe_subscription_id')
    list_filter = ('status', 'plan')
    search_fields = ('user__email', 'user__full_name', 'stripe_subscription_id')
