"""
URL configuration for chat app
"""

from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.index, name='index'),
    path('law/', views.law_chat, name='law_chat'),
]
