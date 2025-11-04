"""
Graph schema endpoints.

Endpoints:
- schema: Get graph schema (labels and relationship types) (POST)
- populate_graph_schema: Get graph schema from text using LLM (POST)
- schema_visualization: Get graph schema visualization from Neo4j (POST)
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
import time
import logging
from datetime import datetime, timezone

# Import business logic modules from src/
from src.api_response import create_api_response
from src.shared.common_fn import formatted_time


@api_view(['POST'])
def schema(request):
    """
    Get graph schema (labels and relationship types).
    Migrated from FastAPI score.py:264-282
    Business logic: src/main.py -> get_labels_and_relationtypes()
    """
    try:
        from src.main import get_labels_and_relationtypes

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
        result = get_labels_and_relationtypes(uri, userName, password, database)

        end = time.time()
        elapsed_time = end - start

        logging.info(f'Schema result from DB: {result}')

        # Logging
        json_obj = {
            'api_name': 'schema',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"schema: {json_obj}")

        return Response(create_api_response('Success', data=result, message=f"Total elapsed API time {elapsed_time:.2f}"))

    except Exception as e:
        message = "Unable to get the labels and relationtypes from neo4j database"
        error_message = str(e)
        logging.info(message)
        logging.exception(f'Exception:{error_message}')
        return Response(create_api_response("Failed", message=message, error=error_message))


@api_view(['POST'])
def populate_graph_schema(request):
    """
    Get graph schema from text using LLM.
    Migrated from FastAPI score.py:678-695
    Business logic: src.main -> populate_graph_schema_from_text()
    """
    try:
        from src.main import populate_graph_schema_from_text

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start = time.time()

        # Extract parameters from request
        input_text = request.data.get('input_text')
        model = request.data.get('model')
        is_schema_description_checked = request.data.get('is_schema_description_checked')
        is_local_storage = request.data.get('is_local_storage')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        result = populate_graph_schema_from_text(input_text, model, is_schema_description_checked, is_local_storage)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'populate_graph_schema',
            'model': model,
            'is_schema_description_checked': is_schema_description_checked,
            'input_text': input_text,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"populate_graph_schema: {json_obj}")

        return Response(create_api_response('Success', data=result))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to get the schema from text"
        error_message = str(e)
        logging.exception(f'Exception in getting the schema from text:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def schema_visualization(request):
    """
    Get graph schema visualization from Neo4j database.
    Migrated from FastAPI score.py:1069-1093
    Business logic: src.graph_query -> visualize_schema()
    """
    try:
        from src.graph_query import visualize_schema
        import gc

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

        # Call business logic (unchanged from src/)
        result = visualize_schema(
            uri=uri,
            userName=userName,
            password=password,
            database=database
        )

        if result:
            logging.info("Graph schema visualization query successful")

        end = time.time()
        elapsed_time = end - start

        logging.info(f'Schema result from DB: {result}')

        # Logging
        json_obj = {
            'api_name': 'schema_visualization',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}'
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"schema_visualization: {json_obj}")

        return Response(create_api_response('Success', data=result, message=f"Total elapsed API time {elapsed_time:.2f}"))

    except Exception as e:
        message = "Unable to get schema visualization from neo4j database"
        error_message = str(e)
        logging.info(message)
        logging.exception(f'Exception:{error_message}')
        return Response(create_api_response("Failed", message=message, error=error_message))
    finally:
        gc.collect()
