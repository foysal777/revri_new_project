"""
ASGI config for project_root project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_root.settings')

django_asgi_app = get_asgi_application()

import notifiation.routing
import chatsystem.routing
from .jwt_auth import TokenAuthMiddlewareStack

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": TokenAuthMiddlewareStack(
            URLRouter(
                notifiation.routing.websocket_urlpatterns +
                chatsystem.routing.websocket_urlpatterns
            )
        ),
    }
)
