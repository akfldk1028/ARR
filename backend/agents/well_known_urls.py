"""
URL Configuration for .well-known endpoints (A2A compatible)
"""

from django.urls import path
from . import views

app_name = 'well_known'

urlpatterns = [
    # Agent card endpoints (A2A compatible)
    path('agent-card.json', views.WellKnownAgentCardView.as_view(), name='agent_card'),
    path('agent-card/<slug:agent_slug>.json', views.WellKnownAgentCardView.as_view(), name='agent_card_detail'),
]