"""
Connection & Health check endpoints.

Endpoints:
- health: Health check endpoint (GET)
- connect: Neo4j database connection check (POST)
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import time
import logging
import os
from datetime import datetime, timezone

# Import business logic modules from src/
from src.api_response import create_api_response
from src.shared.common_fn import formatted_time


@api_view(['GET'])
def health(request):
    """
    Health check endpoint.
    Migrated from FastAPI score.py
    """
    return Response({'status': 'ok', 'message': 'Django migration successful'}, status=status.HTTP_200_OK)


@api_view(['POST'])
def connect(request):
    """
    Check Neo4j database connection and get vector dimensions.
    Migrated from FastAPI score.py:330-349
    Business logic: src/main.py -> create_graph_database_connection(), connection_check_and_get_vector_dimensions()
    """
    try:
        from src.main import create_graph_database_connection, connection_check_and_get_vector_dimensions

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start = time.time()

        # Extract parameters from request
        uri = request.data.get('uri')
        userName = request.data.get('userName')
        password = request.data.get('password')
        database = request.data.get('database')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        result = connection_check_and_get_vector_dimensions(graph, database)
        gcs_file_cache = os.environ.get('GCS_FILE_CACHE')

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'connect',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'count': 1,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"connect: {json_obj}")

        result['elapsed_api_time'] = f'{elapsed_time:.2f}'
        result['gcs_file_cache'] = gcs_file_cache

        return Response(create_api_response('Success', data=result))

    except Exception as e:
        job_status = "Failed"
        message = "Connection failed to connect Neo4j database"
        error_message = str(e)
        logging.exception(f'Connection failed to connect Neo4j database:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))
