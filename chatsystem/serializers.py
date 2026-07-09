import json
from rest_framework import serializers
from . import models

class ChatRoomSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = models.ChatRoom
        fields = ['id', 'name', 'human', 'ai_response']

    def get_name(self, obj):
        first_msg = obj.messages.filter(is_deleted=False).order_by('created_at').first()
        if first_msg:
            return first_msg.message
        return obj.name


class MessageSerializer(serializers.ModelSerializer):
    ai_response = serializers.SerializerMethodField()

    class Meta:
        model = models.Message
        fields = ['id', 'room', 'sender', 'message', 'ai_response', 'created_at']
        read_only_fields = ['id', 'sender', 'ai_response', 'created_at']

    def get_ai_response(self, obj):
        if obj.ai_response is None:
            return None
        result = obj.ai_response
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                return result

        if isinstance(result, dict) and isinstance(result.get('results'), list):
            request = self.context.get('request')
            for item in result['results']:
                image = item.get('image')
                if image and isinstance(image, str) and image.startswith('/') and request is not None:
                    try:
                        item['image'] = request.build_absolute_uri(image)
                    except Exception:
                        pass
                url = item.get('url')
                if url and isinstance(url, str) and url.startswith('/') and request is not None:
                    try:
                        item['url'] = request.build_absolute_uri(url)
                    except Exception:
                        pass
        return result
    





class AiSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AISetting
        fields = ['id', 'ai_restriction', 'response_style', 'total_query_count', 'today_query_count', 'today_date', 'is_active']





class KnowledgePDFSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.KnowledgePDF
        fields = ['id', 'file', 'is_active']



class BlockedKeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BlockedKeyword
        fields = ['id', 'word']


class UserQueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserQueryLog
        fields = ['id', 'query_text', 'response_text', 'is_blocked', 'created_at']
