import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from . import models
from zoneinfo import ZoneInfo


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Notification
        fields = ['id', 'user', 'title', 'notification_banner',  'select_audience', 'description', 'is_read', 'is_deleted', 'created_at']
        read_only_fields = ['id', 'user', 'is_read', 'is_deleted', 'created_at']

class UserDelNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Notification
        fields = ['id', 'title']


class EmailSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    user_time_zone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    class Meta:
        model = models.Email
        fields = ['id', 'user', 'user_email', 'set_date', 'set_time', 'user_time_zone', 'select_audience', 'is_repeated', 'repeated_type', 'describe_email', 'is_active', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None
    
    def validate_select_audience(self, value):
        """
        Ensure select_audience is always a list of plan type strings.
        Also validate that all values are valid PlanType choices.
        """
        from plan.enums import PlanType
        
        # Convert dict to list if needed (extract values)
        if isinstance(value, dict):
            value = list(value.values())
        
        # Ensure it's a list
        if not isinstance(value, list):
            value = [value]
        
        # Validate each value
        valid_choices = {choice[0] for choice in PlanType.choices()}
        for item in value:
            if item not in valid_choices:
                raise serializers.ValidationError(
                    f"'{item}' is not a valid plan type. Choose from: {', '.join(valid_choices)}"
                )
        
        return value
    
    def _get_user_timezone(self, user_time_zone=None):
        if user_time_zone:
            tz_name = user_time_zone
        else:
            request = self.context.get('request') if self.context else None
            tz_name = None
            if request and hasattr(request, 'user') and request.user and getattr(request.user, 'time_zone', None):
                tz_name = request.user.time_zone
            tz_name = tz_name or getattr(settings, 'USER_TIME_ZONE', 'UTC')

        try:
            return ZoneInfo(tz_name)
        except Exception:
            raise serializers.ValidationError(
                {'user_time_zone': f"Invalid time zone '{tz_name}'. Use an IANA name like 'Asia/Dhaka'."}
            )
    def validate(self, data):
        """Ensure set_date is provided when creating/updating an email."""
        if not data.get('set_date'):
            raise serializers.ValidationError(
                {'set_date': 'set_date is required. Please provide a date for when to send the email.'}
            )
        if not data.get('set_time'):
            raise serializers.ValidationError(
                {'set_time': 'set_time is required. Please provide a time for when to send the email.'}
            )

        # Accept an optional `user_time_zone` in input but do NOT convert
        # the provided `set_date`/`set_time` here. We store the date/time
        # as the user's local values in the DB and convert to UTC when the
        # scheduler runs. Keep `user_time_zone` in `data` so it's saved
        # on the Email record (new `user_time_zone` model field).
        # If not provided, the task will fall back to user.profile or
        # settings.USER_TIME_ZONE.

        return data

    def create(self, validated_data):
        """Ensure user_time_zone is saved to the Email record."""
        email = models.Email.objects.create(**validated_data)
        return email

    def to_representation(self, obj):
        data = super().to_representation(obj)
        # `set_date` and `set_time` are stored as the user's local values.
        # Represent them directly (ISO strings) so the frontend sees the
        # local date/time the user supplied.
        if obj.set_date and obj.set_time:
            data['set_date'] = obj.set_date.isoformat()
            data['set_time'] = obj.set_time.replace(microsecond=0).isoformat()
        return data



