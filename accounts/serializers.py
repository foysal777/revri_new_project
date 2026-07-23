from rest_framework import serializers
from django.contrib.auth import get_user_model
from .utils import generate_otp, send_otp_email

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'password', 'userole']
        read_only_fields = ['id', 'userole', 'is_verified', 'otp']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['username'] = validated_data['email']
        user = User(**validated_data)
        user.set_password(password)
        user.is_verified = False
        user.otp = generate_otp()
        user.save()
        send_otp_email(user.email, user.otp)
        return user

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp   = serializers.CharField(max_length=4)


class LoginSerializer(serializers.Serializer):
    email     = serializers.EmailField()
    password  = serializers.CharField(write_only=True)



class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email        = serializers.EmailField()
    new_password = serializers.CharField(write_only=True, min_length=6)


class UserProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'profile_image', 'userole', 'is_verified', 'time_zone']
        read_only_fields = ['id', 'email', 'userole', 'is_verified']

    def validate_time_zone(self, value):
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(value)
        except Exception:
            raise serializers.ValidationError("Invalid time zone. Use an IANA time zone like 'Asia/Dhaka' or 'America/New_York'.")
        return value



class UserListSerializer(serializers.ModelSerializer):
    package = serializers.SerializerMethodField()
    ai_queries = serializers.SerializerMethodField()
    usage_level = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    join_date = serializers.DateTimeField(source='date_joined', format="%Y-%m-%d", read_only=True)
    last_active = serializers.DateTimeField(source='last_login', format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'package', 'join_date', 'ai_queries', 'usage_level', 'last_active', 'status']

    def get_package(self, obj):
        return getattr(obj, 'plantype', 'free').title()

    def get_ai_queries(self, obj):
        if hasattr(obj, 'queries_count'):
            return obj.queries_count
        return getattr(obj, 'sent_messages', getattr(obj.__class__, 'objects').none()).count()

    def get_usage_level(self, obj):
        count = self.get_ai_queries(obj)
        if count < 500:
            return "Low"
        elif count < 2000:
            return "Medium"
        elif count < 5000:
            return "High"
        else:
            return "Very High"

    def get_status(self, obj):
        return "active" if getattr(obj, 'is_active', False) else "inactive"


class ReportUserSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class UserAdminUpdateSerializer(serializers.ModelSerializer):
    profile_image = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'userole', 'plantype',
            'is_verified', 'is_active', 'time_zone', 'profile_image',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']