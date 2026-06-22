"""
URL configuration for law app.

Proxy endpoints to law-domain-agents (port 8011).
"""
from django.urls import path
from . import views

app_name = 'law'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('search/stream', views.search_stream, name='search_stream'),
    path('domain/<str:domain_id>/search/', views.search_domain, name='search_domain'),
    path('domains/', views.domains, name='domains'),
    path('health/', views.health, name='health'),
    path('article/', views.article, name='article'),
    path('stats/', views.stats, name='stats'),
]
