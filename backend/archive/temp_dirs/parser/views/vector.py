"""
Vector index and backend configuration API endpoints.

This module contains endpoints for vector operations and backend configuration:
- drop_create_vector_index: Drop and recreate vector index in Neo4j database
- backend_connection_configuration: Check backend Neo4j connection configuration from environment variables

Migrated from FastAPI score.py
Business logic remains in src/ folder - unchanged!
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


@api_view(['POST'])
def drop_create_vector_index(request):
    """
    Drop and recreate vector index in Neo4j database.
    Migrated from FastAPI score.py:761-781
    Business logic: graphDBdataAccess -> drop_create_vector_index()
    """
    try:
        from src.main import create_graph_database_connection
        from src.graphDB_dataAccess import graphDBdataAccess

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
        isVectorIndexExist = request.data.get('isVectorIndexExist')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        result = graphDb_data_Access.drop_create_vector_index(isVectorIndexExist)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'drop_create_vector_index',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'isVectorIndexExist': isVectorIndexExist,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"drop_create_vector_index: {json_obj}")

        return Response(create_api_response('Success', message=result))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to drop and re-create vector index with correct dimesion as per application configuration"
        error_message = str(e)
        logging.exception(f'Exception into drop and re-create vector index with correct dimesion as per application configuration:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def backend_connection_configuration(request):
    """
    Check backend Neo4j connection configuration from environment variables.
    Migrated from FastAPI score.py:1030-1067
    Business logic: graphDBdataAccess -> connection_check_and_get_vector_dimensions()
    """
    try:
        from langchain_neo4j import Neo4jGraph
        from src.graphDB_dataAccess import graphDBdataAccess
        import gc

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start = time.time()

        # Read Neo4j configuration from environment variables
        uri = os.getenv('NEO4J_URI')
        username = os.getenv('NEO4J_USERNAME')
        database = os.getenv('NEO4J_DATABASE')
        password = os.getenv('NEO4J_PASSWORD')
        gcs_file_cache = os.environ.get('GCS_FILE_CACHE')

        # Check if all required environment variables are set
        if all([uri, username, database, password]):
            graph = Neo4jGraph()
            logging.info(f'login connection status of object: {graph}')

            if graph is not None:
                graph_connection = True
                graphDb_data_Access = graphDBdataAccess(graph)
                result = graphDb_data_Access.connection_check_and_get_vector_dimensions(database)
                result['gcs_file_cache'] = gcs_file_cache
                result['uri'] = uri

                end = time.time()
                elapsed_time = end - start

                result['api_name'] = 'backend_connection_configuration'
                result['elapsed_api_time'] = f'{elapsed_time:.2f}'
                result['graph_connection'] = f'{graph_connection}'
                result['connection_from'] = 'backendAPI'

                if logger:
                    logger.log_struct(result, "INFO")
                else:
                    logging.info(f"backend_connection_configuration: {result}")

                return Response(create_api_response('Success', message=f"Backend connection successful", data=result))
        else:
            graph_connection = False
            return Response(create_api_response('Success', message=f"Backend connection is not successful", data=graph_connection))

    except Exception as e:
        graph_connection = False
        job_status = "Failed"
        message = "Unable to connect backend DB"
        error_message = str(e)
        logging.exception(f'{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message.rstrip('.') + ', or fill from the login dialog.', data=graph_connection))
    finally:
        gc.collect()
