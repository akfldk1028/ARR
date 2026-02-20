"""
URL configuration for parser app.
"""
from django.urls import path
from . import views

app_name = 'parser'

urlpatterns = [
    # Health check endpoint (for testing)
    path('health', views.health, name='health'),

    # Document sources
    path('sources_list', views.sources_list, name='sources_list'),

    # Graph schema
    path('schema', views.schema, name='schema'),

    # Connection
    path('connect', views.connect, name='connect'),

    # Chat
    path('clear_chat_bot', views.clear_chat_bot, name='clear_chat_bot'),

    # Document operations
    path('delete_document_and_entities', views.delete_document_and_entities, name='delete_document_and_entities'),

    # Graph operations
    path('get_neighbours', views.get_neighbours, name='get_neighbours'),
    path('chunk_entities', views.chunk_entities, name='chunk_entities'),
    path('graph_query', views.graph_query, name='graph_query'),
    path('populate_graph_schema', views.populate_graph_schema, name='populate_graph_schema'),
    path('get_unconnected_nodes_list', views.get_unconnected_nodes_list, name='get_unconnected_nodes_list'),
    path('delete_unconnected_nodes', views.delete_unconnected_nodes, name='delete_unconnected_nodes'),
    path('get_duplicate_nodes', views.get_duplicate_nodes, name='get_duplicate_nodes'),
    path('merge_duplicate_nodes', views.merge_duplicate_nodes, name='merge_duplicate_nodes'),
    path('drop_create_vector_index', views.drop_create_vector_index, name='drop_create_vector_index'),
    path('retry_processing', views.retry_processing, name='retry_processing'),
    path('metric', views.calculate_metric, name='calculate_metric'),
    path('additional_metrics', views.calculate_additional_metrics, name='calculate_additional_metrics'),
    path('fetch_chunktext', views.fetch_chunktext, name='fetch_chunktext'),
    path('backend_connection_configuration', views.backend_connection_configuration, name='backend_connection_configuration'),
    path('schema_visualization', views.schema_visualization, name='schema_visualization'),
    path('url/scan', views.url_scan, name='url_scan'),
    path('extract', views.extract, name='extract'),
    path('post_processing', views.post_processing, name='post_processing'),
    path('chat_bot', views.chat_bot, name='chat_bot'),
    path('upload', views.upload, name='upload'),
    path('cancelled_job', views.cancelled_job, name='cancelled_job'),
    path('update_extract_status/<str:file_name>', views.update_extract_status, name='update_extract_status'),
    path('document_status/<str:file_name>', views.document_status, name='document_status'),

    # ========================================
    # ALL 29 ENDPOINTS MIGRATED SUCCESSFULLY!
    # ========================================
]
