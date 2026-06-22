"""URL configuration for land app."""
from django.urls import path
from . import views

app_name = 'land'

urlpatterns = [
    path('analyze/', views.analyze, name='analyze'),
    path('agent-analyze/stream', views.agent_analyze_stream, name='agent_analyze_stream'),
    path('resolve/', views.resolve, name='resolve'),
    path('reverse/', views.reverse, name='reverse'),
    path('zones/', views.zones, name='zones'),
    path('stats/', views.stats, name='stats'),
    path('map-config/', views.map_config, name='map_config'),
    path('elevation-grid/', views.elevation_grid, name='elevation_grid'),
    # Map proxy (Vworld API key hidden server-side)
    path('tiles/<int:z>/<int:y>/<int:x>.png', views.tile_proxy, name='tile_proxy'),
    path('wms', views.wms_proxy, name='wms_proxy'),
]
