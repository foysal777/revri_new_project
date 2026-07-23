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

        # Check monthly question limit based on subscription plan
        from plan.models import UserSubscription, Plans
        from django.utils import timezone
        import datetime

        user = request.user
        limit = None
        plantype = getattr(user, 'plantype', 'free')

        # 1. Look for active UserSubscription
        active_sub = UserSubscription.objects.filter(user=user, status='active').order_by('-start_date').first()
        if active_sub and active_sub.plan:
            limit = active_sub.plan.questions_per_month
        else:
            # 2. Fall back to Plans in DB for user's plantype
            db_plan = Plans.objects.filter(plantype=plantype, is_active=True).order_by('-updated_at').first()
            if db_plan:
                limit = db_plan.questions_per_month
            else:
                # 3. Fall back to hardcoded defaults
                LIMIT_MAPPING = {
                    'free': 5,
                    'core': 30,
                    'builder': 75,
                    'anchor': -1,
                    'premium': 1000,
                }
                limit = LIMIT_MAPPING.get(plantype, 5)

        if limit != -1:
            now = timezone.now()
            start_of_month = datetime.datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
            sent_count = models.Message.objects.filter(
                sender=user,
                is_deleted=False,
                created_at__gte=start_of_month
            ).count()

            if sent_count >= limit:
                return Response(
                    {"detail": f"You have reached your monthly question limit of {limit} questions. Please upgrade your plan to continue."},
                    status=status.HTTP_403_FORBIDDEN
                )

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

        # Build conversation history from recent room messages for multi-turn AI context
        conversation_history = []
        if room:
            recent_msgs = models.Message.objects.filter(room=room, is_deleted=False).order_by('-created_at')[:6]
            for m in reversed(list(recent_msgs)):
                if m.message:
                    conversation_history.append({"role": "user", "content": m.message})
                if m.ai_response:
                    try:
                        ai_data = json.loads(m.ai_response)
                        ans = ai_data.get('answer')
                        if ans:
                            conversation_history.append({"role": "assistant", "content": ans})
                    except Exception:
                        pass

        result = ai_module.handle_message(message_text, conversation_history=conversation_history)

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

        try:
            channel_layer = get_channel_layer()
            if channel_layer and room:
                async_to_sync(channel_layer.group_send)(
                    f"chat_{room.id}",
                    {
                        "type": "chat_message",
                        "message": response_data["message"]
                    }
                )
        except Exception:
            pass  # Gracefully proceed if channel layer / Redis is unavailable

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


class FrequentQuestionsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Max

        try:
            limit = int(request.query_params.get('limit', 5))
            if limit <= 0:
                limit = 5
        except ValueError:
            limit = 5
        limit = min(limit, 5)

        # Query frequency from UserQueryLog
        qs = (
            models.UserQueryLog.objects.filter(is_blocked=False)
            .exclude(query_text__isnull=True)
            .exclude(query_text__exact='')
            .values('query_text')
            .annotate(count=Count('id'), last_asked=Max('created_at'))
            .order_by('-count', '-last_asked')[:limit]
        )

        results = []
        for item in qs:
            query = (item['query_text'] or '').strip()
            if query:
                results.append({
                    'question': query,
                    'count': item['count'],
                    'last_asked': item['last_asked'].strftime('%Y-%m-%d %H:%M:%S') if item['last_asked'] else None
                })

        # Fallback to Message model if no query logs
        if not results:
            msg_qs = (
                models.Message.objects.filter(is_deleted=False)
                .exclude(message='')
                .values('message')
                .annotate(count=Count('id'), last_asked=Max('created_at'))
                .order_by('-count', '-last_asked')[:limit]
            )
            for item in msg_qs:
                query = (item['message'] or '').strip()
                if query:
                    results.append({
                        'question': query,
                        'count': item['count'],
                        'last_asked': item['last_asked'].strftime('%Y-%m-%d %H:%M:%S') if item['last_asked'] else None
                    })

        # Default curated FAQs for BMC if catalog database logs are empty
        if not results:
            default_faqs = [
                "What church health assessments are available?",
                "Where can I find research reports on Black Millennials & Faith?",
                "How do I subscribe to leadership coaching programs?",
                "What digital downloads and curriculum resources are provided?",
                "How can I purchase books and research materials?"
            ]
            results = [
                {'question': q, 'count': 1, 'last_asked': None}
                for q in default_faqs[:limit]
            ]

        results = results[:limit]

        try:
            from common.responses import success_response
            return success_response(data=results, message="Frequently asked AI questions retrieved successfully.")
        except Exception:
            return Response({"data": results, "message": "Frequently asked AI questions retrieved successfully."}, status=status.HTTP_200_OK)



