"""
URL configuration for law app.
"""
from django.urls import path
from . import views

app_name = 'law'

urlpatterns = [
    path('', views.index, name='index'),
    path('search/rne/', views.search_rne, name='search_rne'),
    path('search/ine/', views.search_ine, name='search_ine'),
    path('stats/', views.stats, name='stats'),
]
