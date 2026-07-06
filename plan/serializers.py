from rest_framework import serializers
from .models import Plans

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plans
        fields = ['id', 'name', 'plantype', 'price', 'questions_per_month', 'stripe_price_id', 'billing_cycle', 'badge', 'is_active', 'features']
