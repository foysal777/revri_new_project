from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import filters, status
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .serializers import (
    RegisterSerializer, VerifyOTPSerializer, LoginSerializer,
    ResendOTPSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,
    UserProfileSerializer, UserListSerializer, ReportUserSerializer
)
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import generate_otp, send_otp_email
from .enums import UserRole
from common.responses import success_response, created_response, error_response
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import UserReport, UserBlock
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404


User = get_user_model()

# ─────────────────────────────────────────────
#  Registration View
# ─────────────────────────────────────────────
@extend_schema(
    request=RegisterSerializer,
    responses={201: OpenApiResponse(description="User registered successfully. OTP sent to email.")},
    tags=['Accounts - Authentication'],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return created_response(message="User registered successfully. OTP sent to email.")
    return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
#  Verify OTP View
# ─────────────────────────────────────────────
@extend_schema(
    request=VerifyOTPSerializer,
    responses={200: OpenApiResponse(description="OTP verified successfully.")},
    tags=['Accounts - Authentication'],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_view(request):
    serializer = VerifyOTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        otp   = serializer.validated_data['otp']
        try:
            user = User.objects.get(email=email)
            if user.otp == otp:
                user.is_verified = True
                user.otp = None
                user.save()
                return success_response(message="OTP verified successfully.")
            return error_response(message="Invalid OTP", status_code=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return error_response(message="User not found", status_code=status.HTTP_404_NOT_FOUND)
    return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
#  Login View
# ─────────────────────────────────────────────
@extend_schema(
    request=LoginSerializer,
    responses={200: OpenApiResponse(description="Login successful")},
    tags=['Accounts - Authentication'],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email     = serializer.validated_data['email']
        password  = serializer.validated_data['password']
        # accept either `role_type` (current serializer) or legacy `userole_type`
        role_type = serializer.validated_data.get('role_type') or serializer.validated_data.get('userole_type')

        user = authenticate(request, username=email, password=password)
        if user is None:
            return error_response(message="Invalid email or password", status_code=status.HTTP_401_UNAUTHORIZED)

        if not user.is_verified:
            return error_response(
                message="Email is not verified. Please verify your OTP.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )


        refresh = RefreshToken.for_user(user)
        data = {
            'refresh':  str(refresh),
            'access':   str(refresh.access_token),
            'userole':     user.userole,
            'user_id':  user.id,
        }
        return success_response(data=data, message="Login successful")
    return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
#  Resend OTP View
# ─────────────────────────────────────────────
@extend_schema(
    request=ResendOTPSerializer,
    responses={200: OpenApiResponse(description="A new OTP has been sent to your email.")},
    tags=['Accounts - Authentication'],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp_view(request):
    serializer = ResendOTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            user.otp = generate_otp()
            user.save()
            send_otp_email(user.email, user.otp)
            return success_response(message="A new OTP has been sent to your email.")
        except User.DoesNotExist:
            return error_response(message="User not found", status_code=status.HTTP_404_NOT_FOUND)
    return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
#  Forgot Password View
# ─────────────────────────────────────────────
@extend_schema(
    request=ForgotPasswordSerializer,
    responses={200: OpenApiResponse(description="OTP sent to email for password reset.")},
    tags=['Accounts - Authentication'],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_view(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            user.otp = generate_otp()
            user.save()
            send_otp_email(user.email, user.otp)
            return success_response(message="OTP sent to email for password reset.")
        except User.DoesNotExist:
            return error_response(message="User not found", status_code=status.HTTP_404_NOT_FOUND)
    return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
#  Reset Password View
# ─────────────────────────────────────────────
@extend_schema(
    request=ResetPasswordSerializer,
    responses={200: OpenApiResponse(description="Password reset successfully.")},
    tags=['Accounts - Authentication'],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_view(request):
    serializer = ResetPasswordSerializer(data=request.data)
    if serializer.is_valid():
        email        = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.otp = None
            user.is_verified = True
            user.save()
            return success_response(message="Password reset successfully.")
        except User.DoesNotExist:
            return error_response(message="User not found", status_code=status.HTTP_404_NOT_FOUND)
    return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
#  User Profile View
# ─────────────────────────────────────────────
@extend_schema(
    methods=['GET'],
    responses={200: UserProfileSerializer},
    description="Retrieve details of the currently authenticated user and their pricing plan details.",
    tags=['User Profile']
)
@extend_schema(
    methods=['PATCH'],
    request={'multipart/form-data': UserProfileSerializer},
    responses={200: UserProfileSerializer},
    description="Update the current user's profile details and upload a profile image.",
    tags=['User Profile']
)
@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def user_profile_view(request):
    user = request.user

    if request.method == 'GET':
        serializer = UserProfileSerializer(user, context={'request': request})
        return success_response(data=serializer.data, message="User profile retrieved successfully.")

    elif request.method == 'PATCH':
        serializer = UserProfileSerializer(user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return success_response(data=serializer.data, message="Profile updated successfully.")
        return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


from common.pagination import StandardResultsSetPagination


class AdminUserList(generics.ListAPIView):
    serializer_class = UserListSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.AllowAny] # Use IsAuthenticated if required by admin
    search_fields = ['email', 'full_name']
    
    def get_queryset(self):
        # Annotate with sent_messages count so we can filter by it
        from django.db.models import Count
        queryset = User.objects.annotate(queries_count=Count('sent_messages')).all()
        
        filter_param = self.request.query_params.get('filter', None)
        
        if filter_param == 'free':
            queryset = queryset.filter(plantype='free')
        elif filter_param == 'paid':
            queryset = queryset.exclude(plantype='free')
        elif filter_param == 'high_usage':
            queryset = queryset.filter(queries_count__gte=2000)
            
        return queryset.order_by('-date_joined')


import urllib.request
import json
import os

@extend_schema(
    responses={200: OpenApiResponse(description="Google Login successful")},
    tags=['Accounts - Authentication'],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def google_login_view(request):
    id_token_str = request.data.get('id_token')
    if not id_token_str:
        return error_response(message="id_token is required", status_code=status.HTTP_400_BAD_REQUEST)
    
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token_str}"
        with urllib.request.urlopen(url) as response:
            token_info = json.loads(response.read().decode())
        
        client_id = os.getenv('OAUTH_CLIENT_ID')
        if token_info.get('aud') != client_id:
            return error_response(message="Invalid client ID", status_code=status.HTTP_400_BAD_REQUEST)
        
        email = token_info.get('email')
        if not email:
            return error_response(message="Email not found in token", status_code=status.HTTP_400_BAD_REQUEST)
        
        user, created = User.objects.get_or_create(email=email)
        if created:
            user.full_name = token_info.get('name', '')
            user.is_verified = True
            user.set_unusable_password()
            user.save()
            
        refresh = RefreshToken.for_user(user)
        data = {
            'refresh':  str(refresh),
            'access':   str(refresh.access_token),
            'userole':  user.userole if hasattr(user, 'userole') else '',
            'user_id':  user.id,
        }
        return success_response(data=data, message="Google login successful")
        
    except urllib.error.HTTPError:
        return error_response(message="Invalid Google ID token", status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return error_response(message=f"Error verifying token: {str(e)}", status_code=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=ReportUserSerializer,
    responses={201: OpenApiResponse(description="User reported successfully.")},
    tags=['Accounts - Actions'],
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_user_view(request, id):
    reported_user = get_object_or_404(User, id=id)
    serializer = ReportUserSerializer(data=request.data)
    if serializer.is_valid():
        reason = serializer.validated_data['reason']
        UserReport.objects.create(
            reporter=request.user,
            reported_user=reported_user,
            reason=reason
        )
        
        # Notify admin
        admin_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@example.com')
        if hasattr(settings, 'ADMIN_EMAIL'):
            admin_email = settings.ADMIN_EMAIL
        elif hasattr(settings, 'ADMINS') and settings.ADMINS:
            admin_email = settings.ADMINS[0][1]
            
        send_mail(
            subject=f"User Report Alert: {reported_user.email}",
            message=f"User {request.user.email} reported {reported_user.email}.\nReason: {reason}\nPlease check the admin dashboard.",
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost'),
            recipient_list=[admin_email],
            fail_silently=True,
        )
        return success_response(message="User reported successfully.", status_code=status.HTTP_201_CREATED)
    return error_response(message="Validation Error", errors=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=None,
    responses={201: OpenApiResponse(description="User blocked successfully.")},
    tags=['Accounts - Actions'],
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def block_user_view(request, id):
    blocked_user = get_object_or_404(User, id=id)
    if request.user == blocked_user:
        return error_response(message="You cannot block yourself.", status_code=status.HTTP_400_BAD_REQUEST)
        
    UserBlock.objects.get_or_create(
        blocker=request.user,
        blocked_user=blocked_user
    )
    
    # Notify admin
    admin_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@example.com')
    if hasattr(settings, 'ADMIN_EMAIL'):
        admin_email = settings.ADMIN_EMAIL
    elif hasattr(settings, 'ADMINS') and settings.ADMINS:
        admin_email = settings.ADMINS[0][1]
        
    send_mail(
        subject=f"User Block Alert: {blocked_user.email}",
        message=f"User {request.user.email} blocked {blocked_user.email}.\nPlease check the admin dashboard if further action is needed.",
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost'),
        recipient_list=[admin_email],
        fail_silently=True,
    )
    return success_response(message="User blocked successfully.", status_code=status.HTTP_201_CREATED)


@extend_schema(
    responses={200: OpenApiResponse(description="User account overview retrieved successfully.")},
    tags=['User Profile']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_overview_view(request):
    user = request.user
    
    # 1. Role: Map userole database value to display value
    role_mapping = {
        'admin': 'Admin',
        'normal': 'Normal'
    }
    role_display = role_mapping.get(getattr(user, 'userole', None), 'N/A')
    
    # 2. Verified: Yes / No
    verified_display = 'Yes' if getattr(user, 'is_verified', False) else 'No'
    
    # 3. Plan & Queries limit:
    from plan.models import UserSubscription, Plans
    
    active_sub = UserSubscription.objects.filter(user=user, status='active').order_by('-start_date').first()
    if active_sub and active_sub.plan:
        plan_display = active_sub.plan.name
        limit = active_sub.plan.questions_per_month
    else:
        plantype = getattr(user, 'plantype', None)
        db_plan = Plans.objects.filter(plantype=plantype, is_active=True).order_by('-updated_at').first()
        if db_plan:
            plan_display = db_plan.name
            limit = db_plan.questions_per_month
        else:
            if plantype:
                plan_display = plantype.title()
                LIMIT_MAPPING = {
                    'free': 5,
                    'core': 30,
                    'builder': 75,
                    'anchor': -1,
                }
                limit = LIMIT_MAPPING.get(plantype, None)
            else:
                plan_display = 'None'
                limit = None

    if plan_display == 'None' or not plan_display:
        plan_display = 'None'
        limit_display = '—'
    else:
        if limit == -1:
            limit_display = 'Unlimited'
        elif limit is None:
            limit_display = '—'
        else:
            from chatsystem.models import Message
            from django.utils import timezone
            import datetime
            
            now = timezone.now()
            start_of_month = datetime.datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
            sent_count = Message.objects.filter(
                sender=user,
                is_deleted=False,
                created_at__gte=start_of_month
            ).count()
            
            remaining = max(0, limit - sent_count)
            limit_display = f"{remaining}/{limit}"
            
    data = {
        'role': role_display,
        'verified': verified_display,
        'plan': plan_display,
        'queries_limit': limit_display
    }
    
    return success_response(data=data, message="Account overview retrieved successfully.")