import json
from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from . import ai as ai_module
from . import models, serializers
from common.pagination import StandardResultsSetPagination

# Create your views here.


class ChatRoomList(generics.ListAPIView):
    serializer_class = serializers.ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return models.ChatRoom.objects.filter(is_deleted=False, human=self.request.user)


class ChatDetails(generics.ListAPIView):
    serializer_class = serializers.MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs.get('room_id')
        return models.Message.objects.filter(room_id=room_id, room__human=self.request.user, is_deleted=False)



class MessageDelete(generics.CreateAPIView):
    queryset = models.Message.objects.filter(is_deleted=False)
    serializer_class = serializers.MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def create(self, request, *args, **kwargs):
        message_id = self.kwargs.get('id')
        try:
            message = models.Message.objects.get(id=message_id, is_deleted=False)
            message.is_deleted = True
            message.save()
            return Response({"detail": "Message deleted successfully."}, status=status.HTTP_200_OK)
        except models.Message.DoesNotExist:
            return Response({"detail": "Message not found."}, status=status.HTTP_404_NOT_FOUND)


class MessageCreate(generics.CreateAPIView):
    queryset = models.Message.objects.all()
    serializer_class = serializers.MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        room_id = request.data.get('room')
        message_text = str(request.data.get('message', '')).strip()
        # print("user Message", message_text )
        if not message_text:
            return Response({"detail": "Message text is required."}, status=status.HTTP_400_BAD_REQUEST)

        room = None
        if room_id:
            try:
                room = models.ChatRoom.objects.get(id=room_id, is_deleted=False)
            except models.ChatRoom.DoesNotExist:
                return Response({"detail": "Chat room not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            room = models.ChatRoom.objects.create(
                human=request.user,
                name=f"Chat room for {request.user.email}",
            )

        result = ai_module.handle_message(message_text)

        # print("ai response",result)
        if isinstance(result, dict) and isinstance(result.get('results'), list):
            for item in result['results']:
                image = item.get('image')
                if image and isinstance(image, str) and image.startswith('/'):
                    try:
                        item['image'] = request.build_absolute_uri(image)
                    except Exception:
                        pass
                url = item.get('url')
                if url and isinstance(url, str) and url.startswith('/'):
                    try:
                        item['url'] = request.build_absolute_uri(url)
                    except Exception:
                        pass

        stored_ai_response = json.dumps(result)

        message = models.Message.objects.create(
            room=room,
            sender=request.user,
            message=message_text,
            ai_response=stored_ai_response,
        )

        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        
        response_data = {
            "message": serializers.MessageSerializer(message, context={"request": request}).data,
        }

        channel_layer = get_channel_layer()
        if channel_layer and room:
            async_to_sync(channel_layer.group_send)(
                f"chat_{room.id}",
                {
                    "type": "chat_message",
                    "message": response_data["message"]
                }
            )

        return Response(response_data, status=status.HTTP_201_CREATED)


class RoomDeleteView(generics.CreateAPIView):
    queryset = models.ChatRoom.objects.filter(is_deleted=False)
    serializer_class = serializers.ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def create(self, request, *args, **kwargs):
        room_id = self.kwargs.get('id')
        try:
            room = models.ChatRoom.objects.get(id=room_id, is_deleted=False)
            room.is_deleted = True
            room.save()
            return Response({"detail": "Chat room deleted successfully."}, status=status.HTTP_200_OK)
        except models.ChatRoom.DoesNotExist:
            return Response({"detail": "Chat room not found."}, status=status.HTTP_404_NOT_FOUND)



class AiSettingsView(generics.RetrieveUpdateAPIView):
    queryset = models.AISetting.objects.all()
    serializer_class = serializers.AiSettingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj, created = models.AISetting.objects.get_or_create(id=1)
        return obj
    

class KnowledgePDFListView(generics.ListAPIView):
    queryset = models.KnowledgePDF.objects.filter(is_active=True)
    serializer_class = serializers.KnowledgePDFSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination


class KnowledgePDFCreateView(generics.CreateAPIView):
    queryset = models.KnowledgePDF.objects.all()
    serializer_class = serializers.KnowledgePDFSerializer
    permission_classes = [permissions.IsAuthenticated]


class KnowledgePDFDeleteView(generics.DestroyAPIView):
    queryset = models.KnowledgePDF.objects.all()
    serializer_class = serializers.KnowledgePDFSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'



class BlockedKeywordListView(generics.ListAPIView):
    queryset = models.BlockedKeyword.objects.all()
    serializer_class = serializers.BlockedKeywordSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination



class BlockedKeywordCreateView(generics.CreateAPIView):
    queryset = models.BlockedKeyword.objects.all()
    serializer_class = serializers.BlockedKeywordSerializer
    permission_classes = [permissions.IsAuthenticated]


class BlockedKeywordDeleteView(generics.DestroyAPIView):
    queryset = models.BlockedKeyword.objects.all()
    serializer_class = serializers.BlockedKeywordSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'



class UserQueryLogListView(generics.ListAPIView):
    queryset = models.UserQueryLog.objects.all()
    serializer_class = serializers.UserQueryLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination


class UserQueryLogDeleteView(generics.DestroyAPIView):
    queryset = models.UserQueryLog.objects.all()
    serializer_class = serializers.UserQueryLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'


