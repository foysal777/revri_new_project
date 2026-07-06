from django.urls import path

from chatsystem import views as chatsystem_views

from admin_dashboard import views as admin_dashboard_views

from notifiation import views as notification_views

from accounts.views import (
    AdminUserList,
    register_view,
    verify_otp_view,
    login_view,
    resend_otp_view,
    forgot_password_view,
    reset_password_view,
    user_profile_view,
    google_login_view,
    report_user_view,
    block_user_view,
)
from plan import views as plan_views


urlpatterns = [

    path('chat-rooms-list/', chatsystem_views.ChatRoomList.as_view(), name='chat-room-list'),
    path('send-message/', chatsystem_views.MessageCreate.as_view(), name='send-message'),
    path('chat-details/<int:room_id>/', chatsystem_views.ChatDetails.as_view(), name='chat-details'),
    path('delete-message/<int:id>/', chatsystem_views.MessageDelete.as_view(), name='delete-message'),

    path('ai-settings/', chatsystem_views.AiSettingsView.as_view(), name='ai-settings'),

    path('knowledge-pdf-list/', chatsystem_views.KnowledgePDFListView.as_view(), name='knowledge-pdf-list'),
    path('knowledge-pdf-create/', chatsystem_views.KnowledgePDFCreateView.as_view(), name='knowledge-pdf-create'),
    path('knowledge-pdf-delete/<int:pk>/', chatsystem_views.KnowledgePDFDeleteView.as_view(), name='knowledge-pdf-delete'),

    path('block-query-list/', chatsystem_views.BlockedKeywordListView.as_view(), name='block-query-list'),
    path('block-query-create/', chatsystem_views.BlockedKeywordCreateView.as_view(), name='block-query-create'),
    path('block-query-delete/<int:pk>/', chatsystem_views.BlockedKeywordDeleteView.as_view(), name='block-query-delete'),

    path('user-query-log-list/', chatsystem_views.UserQueryLogListView.as_view(), name='user-query-log-list'),
    path('user-query-log-delete/<int:pk>/', chatsystem_views.UserQueryLogDeleteView.as_view(), name='user-query-log-delete'),


    path('admin-dashboard-stats/', admin_dashboard_views.AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('advanced-analytics/', admin_dashboard_views.AdvancedAnalyticsView.as_view(), name='advanced-analytics'),

    path('product-create/', admin_dashboard_views.ProductCreateView.as_view(), name='product-create'),
    path('product-list/', admin_dashboard_views.ProductListView.as_view(), name='product-list'),
    path('product-detail/<int:pk>/', admin_dashboard_views.ProductDetailView.as_view(), name='product-detail'),
    path('product-update-delete/<int:pk>/', admin_dashboard_views.ProductUpdateDeleteView.as_view(), name='product-update-delete'), 

    # Upload Thumbnail URLs
    path('thumbnail-create/', admin_dashboard_views.UploadThumbnailCreateView.as_view(), name='upload-thumbnail-create'),
    path('thumbnail-list/admin/', admin_dashboard_views.AdminThumbnailListView.as_view(), name='upload-thumbnail-list'),
    path('thumbnail-list/user/', admin_dashboard_views.UserThumbnailListView.as_view(), name='upload-thumbnail-list-user'),
    path('thumbnail-detail/<int:pk>/', admin_dashboard_views.UploadThumbnailUpdateDeleteView.as_view(), name='upload-thumbnail-detail'),


    # Registration
    path('register/', register_view, name='student-register'),

    # Shared OTP & Login
    path('verify-otp/', verify_otp_view, name='verify-otp'),
    path('resend-otp/', resend_otp_view, name='resend-otp'),
    path('login/', login_view, name='login'),
    path('google-login/', google_login_view, name='google-login'),

    # Password Reset
    path('forgot-password/', forgot_password_view, name='forgot-password'),
    path('reset-password/', reset_password_view, name='reset-password'),

    # User Profile
    path('profile/', user_profile_view, name='profile'),

    path('admin-user-list/', AdminUserList.as_view(), name='admin-user-list'),

    # Actions
    path('users/<int:id>/report/', report_user_view, name='report-user'),
    path('users/<int:id>/block/', block_user_view, name='block-user'),


    # Notification URLs
    path('notification-create/', notification_views.NotificationCreateView.as_view(), name='notification-create'),
    path('user-notification-list/', notification_views.UserNotificationListView.as_view(), name='user-notification-list'),
    path('admin-notification-list/', notification_views.AdminNotificationListView.as_view(), name='admin-notification-list'),
    path('notification-detail/<int:id>/', notification_views.NotificationDetailView.as_view(), name='notification-detail'),

    path('user-del-notification/<int:id>/', notification_views.UserDelNofications.as_view(), name='user-del-notification'),


    # Email URLs
    path('email-create/', notification_views.EmailCreateView.as_view(), name='email-create'),
    path('email-list/', notification_views.EmailListView.as_view(), name='email-list'),
    path('email-detail/<int:id>/', notification_views.EmailDetailView.as_view(), name='email-detail'),

    # Plan / Stripe URLs
    path('plan-list/', plan_views.PlanListView.as_view(), name='plan-list'),
    path('plan-detail-update/<int:pk>/', plan_views.PlanDetailUpdateView.as_view(), name='plan-detail-update'),
    path('user-current-plan/', plan_views.UserCurrentPlanView.as_view(), name='user-current-plan'),
    path('create-checkout-session/', plan_views.CreateCheckoutSessionView.as_view(), name='create-checkout-session'),
    path('stripe-webhook/', plan_views.StripeWebhookView.as_view(), name='stripe-webhook'),
    path('cancel-subscription/', plan_views.CancelSubscriptionView.as_view(), name='cancel-subscription'),
    path('run-tests/', plan_views.RunTestsView.as_view(), name='run-tests'),
]


