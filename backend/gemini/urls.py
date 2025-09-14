from django.urls import path
from . import views

app_name = 'gemini'

urlpatterns = [
    path('', views.gemini_home, name='home'),
    path('health/', views.health_check, name='health'),
]