from django.urls import path
from . import views

app_name = 'gemini'

urlpatterns = [
    path('', views.gemini_home, name='home'),
    path('continuous-voice/', views.continuous_voice, name='continuous_voice'),
    path('health/', views.health_check, name='health'),
]