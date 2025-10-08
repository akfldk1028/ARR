"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from gemini.routing import websocket_urlpatterns as gemini_ws_patterns
from chat.routing import websocket_urlpatterns as chat_ws_patterns

# Combine WebSocket URL patterns
all_websocket_patterns = gemini_ws_patterns + chat_ws_patterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(all_websocket_patterns),
})
