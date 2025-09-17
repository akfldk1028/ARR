"""
URL Configuration for Agents App
"""

from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # Worker communication test endpoints (MUST come FIRST)
    path('worker-test/', views.WorkerTestView.as_view(), name='worker_test'),
    path('test-worker-communication/', views.WorkerCommunicationTestView.as_view(), name='test_worker_communication'),
    path('test_worker_communication/', views.WorkerCommunicationTestView.as_view(), name='test_worker_communication_alt'),

    # .well-known endpoints for A2A compatibility
    path('.well-known/agent-card.json', views.WellKnownAgentCardView.as_view(), name='well_known_agent_card'),
    path('.well-known/agent-card/<slug:agent_slug>.json', views.WellKnownAgentCardView.as_view(), name='well_known_agent_card_detail'),

    # API endpoints (with api/ prefix)
    path('api/', views.AgentListView.as_view(), name='api_agent_list'),
    path('api/<slug:agent_slug>/', views.AgentCardView.as_view(), name='api_agent_detail'),
    path('api/<slug:agent_slug>/status/', views.AgentStatusView.as_view(), name='api_agent_status'),

    # Agent list (empty path)
    path('', views.AgentListView.as_view(), name='agent_list'),

    # Agent management endpoints (slug patterns must come LAST)
    path('<slug:agent_slug>/', views.AgentCardView.as_view(), name='agent_detail'),
    path('<slug:agent_slug>/status/', views.AgentStatusView.as_view(), name='agent_status'),
    path('<slug:agent_slug>/chat/', views.AgentChatView.as_view(), name='agent_chat'),
]