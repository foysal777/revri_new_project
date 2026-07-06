import urllib.parse

from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def get_user_from_jwt_token(token: str):
    jwt_auth = JWTAuthentication()
    validated_token = jwt_auth.get_validated_token(token)
    return jwt_auth.get_user(validated_token)


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        params = urllib.parse.parse_qs(query_string)
        token_values = params.get('token') or []
        token = token_values[0] if token_values else None

        if token:
            try:
                user = await get_user_from_jwt_token(token)
            except Exception:
                user = AnonymousUser()
        else:
            user = AnonymousUser()

        scope['user'] = user
        return await self.app(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
