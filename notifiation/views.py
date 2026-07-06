from django.shortcuts import render
from rest_framework import generics, permissions,status
from rest_framework.response import Response
from . import models, serializers
from common.pagination import StandardResultsSetPagination
# Create your views here.


class NotificationCreateView(generics.CreateAPIView):
    queryset = models.Notification.objects.all()
    serializer_class = serializers.NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    

class UserNotificationListView(generics.ListAPIView):
    queryset = models.Notification.objects.filter(is_deleted=False)
    serializer_class = serializers.NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination  


class UserDelNofications(generics.RetrieveAPIView):
    queryset = models.Notification.objects.all()
    serializer_class = serializers.UserDelNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'


class AdminNotificationListView(generics.ListAPIView):
    queryset = models.Notification.objects.all()
    serializer_class = serializers.NotificationSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = StandardResultsSetPagination


class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Notification.objects.filter(is_deleted=False)
    serializer_class = serializers.NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def delete(self, request, *args, **kwargs):
        notification = self.get_object()
        notification.is_deleted = True
        notification.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    


class EmailCreateView(generics.CreateAPIView):
    queryset = models.Email.objects.all()
    serializer_class = serializers.EmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    

class EmailListView(generics.ListAPIView):
    serializer_class = serializers.EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):

        return models.Email.objects.filter(user=self.request.user).order_by('-created_at')


class EmailDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Email.objects.all()
    serializer_class = serializers.EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def delete(self, request, *args, **kwargs):
        email = self.get_object()
        email.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
