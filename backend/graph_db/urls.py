"""
Graph DB URL Configuration
Neo4j CDC event endpoints
"""
from django.urls import path
from . import views

urlpatterns = [
    path('neo4j-events/', views.neo4j_event, name='neo4j_event'),
]
