from django.urls import path
from . import views

app_name = 'gemini'

urlpatterns = [
    path('', views.gemini_home, name='home'),
    path('continuous-voice/', views.continuous_voice, name='continuous_voice'),
    path('live-voice/', views.live_voice_a2a, name='live_voice_a2a'),
    path('test-simple/', views.test_simple, name='test_simple'),
    path('health/', views.health_check, name='health'),
]