"""Clean serializer for Email notifications."""
import datetime

from django.conf import settings
from rest_framework import serializers
from zoneinfo import ZoneInfo
from . import models


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for read-only notifications."""
    class Meta:
        model = models.Notification
        fields = ['id', 'user', 'title', 'notification_banner', 'select_audience', 
                  'description', 'is_read', 'is_deleted', 'created_at']
        read_only_fields = ['id', 'user', 'is_read', 'is_deleted', 'created_at']


class UserDelNotificationSerializer(serializers.ModelSerializer):
    """Minimal notification serializer for deletion."""
    class Meta:
        model = models.Notification
        fields = ['id', 'title']


class EmailSerializer(serializers.ModelSerializer):
    """Serializer for scheduled emails with timezone support."""
    user_email = serializers.SerializerMethodField()
    user_time_zone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = models.Email
        fields = [
            'id', 'user', 'user_email', 'set_date', 'set_time', 'user_time_zone',
            'select_audience', 'is_repeated', 'repeated_type', 'describe_email',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None
    
    def validate_select_audience(self, value):
        """Ensure select_audience contains only valid plan types."""
        from plan.enums import PlanType
        
        # Normalize to list
        if isinstance(value, dict):
            value = list(value.values())
        elif not isinstance(value, list):
            value = [value]
        
        # Validate each value
        valid_choices = {choice[0] for choice in PlanType.choices()}
        invalid = [item for item in value if item not in valid_choices]
        
        if invalid:
            raise serializers.ValidationError(
                f"Invalid plan types: {invalid}. Valid: {valid_choices}"
            )
        
        return value
    
    def validate_set_date(self, value):
        """Ensure set_date is provided."""
        if not value:
            raise serializers.ValidationError('set_date is required.')
        return value
    
    def validate_set_time(self, value):
        """Ensure set_time is provided."""
        if value is None:
            raise serializers.ValidationError('set_time is required.')
        return value
    
    def validate_user_time_zone(self, value):
        """Validate timezone is a valid IANA name."""
        if not value:
            return value
        
        try:
            ZoneInfo(value)
            return value
        except Exception:
            raise serializers.ValidationError(
                f"Invalid timezone '{value}'. Use IANA format like 'Asia/Dhaka'."
            )
    
    def to_representation(self, obj):
        """Return local date/time (as stored) to frontend."""
        data = super().to_representation(obj)
        if obj.set_date and obj.set_time:
            # Return as stored (local values, not UTC)
            data['set_date'] = obj.set_date.isoformat()
            data['set_time'] = obj.set_time.replace(microsecond=0).isoformat()
        return data
