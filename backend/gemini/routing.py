from django.urls import re_path
from .consumers.simple_consumer import SimpleChatConsumer

websocket_urlpatterns = [
    re_path(r'^ws/gemini/$', SimpleChatConsumer.as_asgi()),
]