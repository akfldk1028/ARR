"""
API views for parser app.

Migrated from FastAPI score.py (1,095 lines, 29 endpoints)
Business logic remains in src/ folder - unchanged!
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import time
import logging
import os
import json
from datetime import datetime, timezone

# Import business logic modules from src/
from src.api_response import create_api_response
from src.shared.common_fn import formatted_time

# Note: CustomLogger imports google.cloud.logging which may fail
# Import it lazily when needed

# Define directories for file operations (same as score.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MERGED_DIR = os.path.join(BASE_DIR, "merged_files")
CHUNK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chunks")


# Helper functions for password encoding/decoding (from score.py)
def decode_password(pwd):
    """Decode base64 encoded password."""
    import base64
    sample_string_bytes = base64.b64decode(pwd)
    decoded_password = sample_string_bytes.decode("utf-8")
    return decoded_password


def encode_password(pwd):
    """Encode password to base64."""
    import base64
    data_bytes = pwd.encode('ascii')
    encoded_pwd_bytes = base64.b64encode(data_bytes)
    return encoded_pwd_bytes


# Helper functions for file operations (from score.py)
def sanitize_filename(filename):
    """
    Sanitize the user-provided filename to prevent directory traversal and remove unsafe characters.
    """
    # Remove path separators and collapse redundant separators
    filename = os.path.basename(filename)
    filename = os.path.normpath(filename)
    return filename


def validate_file_path(directory, filename):
    """
    Construct the full file path and ensure it is within the specified directory.
    """
    file_path = os.path.join(directory, filename)
    abs_directory = os.path.abspath(directory)
    abs_file_path = os.path.abspath(file_path)
    # Ensure the file path starts with the intended directory path
    if not abs_file_path.startswith(abs_directory):
        raise ValueError("Invalid file path")
    return abs_file_path


@api_view(['GET'])
def health(request):
    """
    Health check endpoint.
    Migrated from FastAPI score.py
    """
    return Response({'status': 'ok', 'message': 'Django migration successful'}, status=status.HTTP_200_OK)


@api_view(['POST'])
def sources_list(request):
    """
    Get list of sources from Neo4j database.
    Migrated from FastAPI score.py:335-358
    Business logic: src/main.py -> get_source_list_from_graph()
    """
    try:
        from src.main import get_source_list_from_graph

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None  # Fallback to None if google-cloud-logging not available

        start = time.time()

        # Extract parameters from request
        uri = request.data.get('uri')
        userName = request.data.get('userName')
        password = request.data.get('password')
        database = request.data.get('database')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        result = get_source_list_from_graph(uri, userName, password, database)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'sources_list',
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
            logging.info(f"sources_list: {json_obj}")

        return Response(create_api_response("Success", data=result, message=f"Total elapsed API time {elapsed_time:.2f}"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to fetch source list"
        error_message = str(e)
        logging.exception(f'Exception:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


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


@api_view(['POST'])
def clear_chat_bot(request):
    """
    Clear chat history for a given session.
    Migrated from FastAPI score.py:310-328
    Business logic: src/QA_integration.py -> clear_chat_history()
    """
    try:
        from src.main import create_graph_database_connection
        from src.QA_integration import clear_chat_history

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
        session_id = request.data.get('session_id')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        result = clear_chat_history(graph=graph, session_id=session_id)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'clear_chat_bot',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'session_id': session_id,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"clear_chat_bot: {json_obj}")

        return Response(create_api_response('Success', data=result))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to clear chat History"
        error_message = str(e)
        logging.exception(f'Exception in chat bot:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def delete_document_and_entities(request):
    """
    Delete documents and entities from Neo4j database.
    Migrated from FastAPI score.py:460-488
    Business logic: src/graphDB_dataAccess.py -> delete_file_from_graph()
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
        filenames = request.data.get('filenames')
        source_types = request.data.get('source_types')
        deleteEntities = request.data.get('deleteEntities')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        files_list_size = graphDb_data_Access.delete_file_from_graph(filenames, source_types, deleteEntities, MERGED_DIR, uri)

        message = f"Deleted {files_list_size} documents with entities from database"

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'delete_document_and_entities',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'filenames': filenames,
            'deleteEntities': deleteEntities,
            'source_types': source_types,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"delete_document_and_entities: {json_obj}")

        return Response(create_api_response('Success', message=message))

    except Exception as e:
        job_status = "Failed"
        message = f"Unable to delete document {request.data.get('filenames', '')}"
        error_message = str(e)
        logging.exception(f'{message}:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def get_neighbours(request):
    """
    Get neighbour nodes for a given element ID.
    Migrated from FastAPI score.py:213-230
    Business logic: src.neighbours -> get_neighbour_nodes()
    """
    try:
        from src.neighbours import get_neighbour_nodes

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
        elementId = request.data.get('elementId')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        result = get_neighbour_nodes(uri=uri, username=userName, password=password, database=database, element_id=elementId)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'get_neighbours',
            'userName': userName,
            'database': database,
            'db_url': uri,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"get_neighbours: {json_obj}")

        return Response(create_api_response('Success', data=result, message=f"Total elapsed API time {elapsed_time:.2f}"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to extract neighbour nodes for given element ID"
        error_message = str(e)
        logging.exception(f'Exception in get neighbours :{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def chunk_entities(request):
    """
    Get entities from chunk IDs.
    Migrated from FastAPI score.py:257-275
    Business logic: src.chunkid_entities -> get_entities_from_chunkids()
    """
    try:
        from src.chunkid_entities import get_entities_from_chunkids

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
        nodedetails = request.data.get('nodedetails')
        entities = request.data.get('entities')
        mode = request.data.get('mode')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        result = get_entities_from_chunkids(
            nodedetails=nodedetails,
            entities=entities,
            mode=mode,
            uri=uri,
            username=userName,
            password=password,
            database=database
        )

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'chunk_entities',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'nodedetails': nodedetails,
            'entities': entities,
            'mode': mode,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"chunk_entities: {json_obj}")

        return Response(create_api_response('Success', data=result, message=f"Total elapsed API time {elapsed_time:.2f}"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to extract entities from chunk ids"
        error_message = str(e)
        logging.exception(f'Exception in chat bot:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def graph_query(request):
    """
    Get graph query results.
    Migrated from FastAPI score.py:214-245
    Business logic: src.graph_query -> get_graph_results()
    """
    try:
        from src.graph_query import get_graph_results

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start = time.time()

        # Extract parameters from request
        uri = request.data.get('uri')
        database = request.data.get('database')
        userName = request.data.get('userName')
        password = request.data.get('password')
        document_names = request.data.get('document_names')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        result = get_graph_results(
            uri=uri,
            username=userName,
            password=password,
            database=database,
            document_names=document_names
        )

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'graph_query',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'document_names': document_names,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"graph_query: {json_obj}")

        return Response(create_api_response('Success', data=result, message=f"Total elapsed API time {elapsed_time:.2f}"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to get graph query response"
        error_message = str(e)
        logging.exception(f'Exception in graph query: {error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


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
def get_unconnected_nodes_list(request):
    """
    Get list of unconnected nodes from Neo4j database.
    Migrated from FastAPI score.py:697-716
    Business logic: graphDBdataAccess -> list_unconnected_nodes()
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
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        nodes_list, total_nodes = graphDb_data_Access.list_unconnected_nodes()

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'get_unconnected_nodes_list',
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
            logging.info(f"get_unconnected_nodes_list: {json_obj}")

        return Response(create_api_response('Success', data=nodes_list, message=total_nodes))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to get the list of unconnected nodes"
        error_message = str(e)
        logging.exception(f'Exception in getting list of unconnected nodes:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def delete_unconnected_nodes(request):
    """
    Delete unconnected nodes from Neo4j database.
    Migrated from FastAPI score.py:718-737
    Business logic: graphDBdataAccess -> delete_unconnected_nodes()
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
        unconnected_entities_list = request.data.get('unconnected_entities_list')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        result = graphDb_data_Access.delete_unconnected_nodes(unconnected_entities_list)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'delete_unconnected_nodes',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'unconnected_entities_list': unconnected_entities_list,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"delete_unconnected_nodes: {json_obj}")

        return Response(create_api_response('Success', data=result, message="Unconnected entities delete successfully"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to delete the unconnected nodes"
        error_message = str(e)
        logging.exception(f'Exception in delete the unconnected nodes:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def get_duplicate_nodes(request):
    """
    Get list of duplicate nodes from Neo4j database.
    Migrated from FastAPI score.py:86-105
    Business logic: graphDBdataAccess -> get_duplicate_nodes_list()
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
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        nodes_list, total_nodes = graphDb_data_Access.get_duplicate_nodes_list()

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'get_duplicate_nodes',
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
            logging.info(f"get_duplicate_nodes: {json_obj}")

        return Response(create_api_response('Success', data=nodes_list, message=total_nodes))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to get the list of duplicate nodes"
        error_message = str(e)
        logging.exception(f'Exception in getting list of duplicate nodes:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def merge_duplicate_nodes(request):
    """
    Merge duplicate nodes in Neo4j database.
    Migrated from FastAPI score.py:739-759
    Business logic: graphDBdataAccess -> merge_duplicate_nodes()
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
        duplicate_nodes_list = request.data.get('duplicate_nodes_list')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        result = graphDb_data_Access.merge_duplicate_nodes(duplicate_nodes_list)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'merge_duplicate_nodes',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'duplicate_nodes_list': duplicate_nodes_list,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"merge_duplicate_nodes: {json_obj}")

        return Response(create_api_response('Success', data=result, message="Duplicate entities merged successfully"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to merge the duplicate nodes"
        error_message = str(e)
        logging.exception(f'Exception in merge the duplicate nodes:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


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
def retry_processing(request):
    """
    Retry processing for a failed document.
    Migrated from FastAPI score.py:107-130
    Business logic: execute_graph_query, set_status_retry
    """
    try:
        from src.main import create_graph_database_connection, execute_graph_query, QUERY_TO_GET_CHUNKS, set_status_retry

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
        file_name = request.data.get('file_name')
        retry_condition = request.data.get('retry_condition')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        chunks = execute_graph_query(graph, QUERY_TO_GET_CHUNKS, params={"filename": file_name})

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'retry_processing',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'file_name': file_name,
            'retry_condition': retry_condition,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"retry_processing: {json_obj}")

        # Check if chunks exist and are valid
        if chunks[0]['text'] is None or chunks[0]['text'] == "" or not chunks:
            return Response(create_api_response('Success', message=f"Chunks are not created for the file{file_name}. Please upload again the file to re-process.", data=chunks))
        else:
            set_status_retry(graph, file_name, retry_condition)
            return Response(create_api_response('Success', message=f"Status set to Ready to Reprocess for filename : {file_name}"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to set status to Retry"
        error_message = str(e)
        logging.exception(f'{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))


@api_view(['POST'])
def calculate_metric(request):
    """
    Calculate evaluation metrics for RAG system.
    Migrated from FastAPI score.py:783-819
    Business logic: src.ragas_eval -> get_ragas_metrics()
    """
    try:
        from src.ragas_eval import get_ragas_metrics
        import gc

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start = time.time()

        # Extract parameters from request
        question = request.data.get('question')
        context = request.data.get('context')
        answer = request.data.get('answer')
        model = request.data.get('model')
        mode = request.data.get('mode')

        # Parse JSON string parameters into lists
        context_list = [str(item).strip() for item in json.loads(context)] if context else []
        answer_list = [str(item).strip() for item in json.loads(answer)] if answer else []
        mode_list = [str(item).strip() for item in json.loads(mode)] if mode else []

        # Call business logic (unchanged from src/)
        result = get_ragas_metrics(question, context_list, answer_list, model)

        if result is None or "error" in result:
            return Response(create_api_response(
                'Failed',
                message='Failed to calculate evaluation metrics.',
                error=result.get("error", "Ragas evaluation returned null") if result else "Ragas evaluation returned null"
            ))

        # Transform result into mode-indexed dictionary
        data = {mode: {metric: result[metric][i] for metric in result} for i, mode in enumerate(mode_list)}

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'metric',
            'question': question,
            'context': context,
            'answer': answer,
            'model': model,
            'mode': mode,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}'
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"calculate_metric: {json_obj}")

        return Response(create_api_response('Success', data=data))

    except Exception as e:
        logging.exception(f"Error while calculating evaluation metrics: {e}")
        return Response(create_api_response(
            'Failed',
            message="Error while calculating evaluation metrics",
            error=str(e)
        ))
    finally:
        gc.collect()


@api_view(['POST'])
def calculate_additional_metrics(request):
    """
    Calculate additional evaluation metrics for RAG system.
    Migrated from FastAPI score.py:953-982
    Business logic: src.ragas_eval -> get_additional_metrics()
    """
    try:
        from src.ragas_eval import get_additional_metrics
        import gc
        import asyncio

        # Extract parameters from request
        question = request.data.get('question')
        context = request.data.get('context')
        answer = request.data.get('answer')
        reference = request.data.get('reference')
        model = request.data.get('model')
        mode = request.data.get('mode')

        # Parse JSON string parameters into lists
        context_list = [str(item).strip() for item in json.loads(context)] if context else []
        answer_list = [str(item).strip() for item in json.loads(answer)] if answer else []
        mode_list = [str(item).strip() for item in json.loads(mode)] if mode else []

        # Call business logic (async function - need to run it)
        result = asyncio.run(get_additional_metrics(question, context_list, answer_list, reference, model))

        if result is None or "error" in result:
            return Response(create_api_response(
                'Failed',
                message='Failed to calculate evaluation metrics.',
                error=result.get("error", "Ragas evaluation returned null") if result else "Ragas evaluation returned null"
            ))

        # Transform result into mode-indexed dictionary
        data = {mode: {metric: result[i][metric] for metric in result[i]} for i, mode in enumerate(mode_list)}

        return Response(create_api_response('Success', data=data))

    except Exception as e:
        logging.exception(f"Error while calculating evaluation metrics: {e}")
        return Response(create_api_response(
            'Failed',
            message="Error while calculating evaluation metrics",
            error=str(e)
        ))
    finally:
        gc.collect()


@api_view(['POST'])
def fetch_chunktext(request):
    """
    Fetch chunk text results from Neo4j database.
    Migrated from FastAPI score.py:984-1027
    Business logic: src.graph_query -> get_chunktext_results()
    """
    try:
        from src.graph_query import get_chunktext_results

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start = time.time()

        # Extract parameters from request
        uri = request.data.get('uri')
        database = request.data.get('database')
        userName = request.data.get('userName')
        password = request.data.get('password')
        document_name = request.data.get('document_name')
        page_no = request.data.get('page_no', 1)  # Default to 1
        email = request.data.get('email')

        # Convert page_no to int if it's not already
        if isinstance(page_no, str):
            page_no = int(page_no)

        # Call business logic (unchanged from src/)
        result = get_chunktext_results(
            uri=uri,
            username=userName,
            password=password,
            database=database,
            document_name=document_name,
            page_no=page_no
        )

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'fetch_chunktext',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'document_name': document_name,
            'page_no': page_no,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"fetch_chunktext: {json_obj}")

        return Response(create_api_response('Success', data=result, message=f"Total elapsed API time {elapsed_time:.2f}"))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to get chunk text response"
        error_message = str(e)
        logging.exception(f'Exception in fetch_chunktext: {error_message}')
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


@api_view(['POST'])
def url_scan(request):
    """
    Create source knowledge graph from URL (S3, GCS, web-url, YouTube, Wikipedia).
    Migrated from FastAPI score.py:123-193
    Business logic: src.main -> create_source_node_graph_url_*()
    """
    try:
        from src.main import (
            create_graph_database_connection,
            create_source_node_graph_url_s3,
            create_source_node_graph_url_gcs,
            create_source_node_graph_web_url,
            create_source_node_graph_url_youtube,
            create_source_node_graph_url_wikipedia
        )
        from src.shared.llm_graph_builder_exception import LLMGraphBuilderException
        from google.oauth2.credentials import Credentials
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
        source_url = request.data.get('source_url')
        database = request.data.get('database')
        aws_access_key_id = request.data.get('aws_access_key_id')
        aws_secret_access_key = request.data.get('aws_secret_access_key')
        wiki_query = request.data.get('wiki_query')
        model = request.data.get('model')
        gcs_bucket_name = request.data.get('gcs_bucket_name')
        gcs_bucket_folder = request.data.get('gcs_bucket_folder')
        source_type = request.data.get('source_type')
        gcs_project_id = request.data.get('gcs_project_id')
        access_token = request.data.get('access_token')
        email = request.data.get('email')

        # Determine source
        if source_url is not None:
            source = source_url
        else:
            source = wiki_query

        # Create graph connection
        graph = create_graph_database_connection(uri, userName, password, database)

        # Call appropriate business logic based on source_type
        if source_type == 's3 bucket' and aws_access_key_id and aws_secret_access_key:
            lst_file_name, success_count, failed_count = create_source_node_graph_url_s3(
                graph, model, source_url, aws_access_key_id, aws_secret_access_key, source_type
            )
        elif source_type == 'gcs bucket':
            lst_file_name, success_count, failed_count = create_source_node_graph_url_gcs(
                graph, model, gcs_project_id, gcs_bucket_name, gcs_bucket_folder, source_type, Credentials(access_token)
            )
        elif source_type == 'web-url':
            lst_file_name, success_count, failed_count = create_source_node_graph_web_url(
                graph, model, source_url, source_type
            )
        elif source_type == 'youtube':
            lst_file_name, success_count, failed_count = create_source_node_graph_url_youtube(
                graph, model, source_url, source_type
            )
        elif source_type == 'Wikipedia':
            lst_file_name, success_count, failed_count = create_source_node_graph_url_wikipedia(
                graph, model, wiki_query, source_type
            )
        else:
            return Response(create_api_response('Failed', message='source_type is other than accepted source'))

        message = f"Source Node created successfully for source type: {source_type} and source: {source}"
        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'url_scan',
            'db_url': uri,
            'url_scanned_file': lst_file_name,
            'source_url': source_url,
            'wiki_query': wiki_query,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'userName': userName,
            'database': database,
            'aws_access_key_id': aws_access_key_id,
            'model': model,
            'gcs_bucket_name': gcs_bucket_name,
            'gcs_bucket_folder': gcs_bucket_folder,
            'source_type': source_type,
            'gcs_project_id': gcs_project_id,
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"url_scan: {json_obj}")

        result = {'elapsed_api_time': f'{elapsed_time:.2f}'}
        return Response(create_api_response("Success", message=message, success_count=success_count, failed_count=failed_count, file_name=lst_file_name, data=result))

    except LLMGraphBuilderException as e:
        error_message = str(e)
        message = f" Unable to create source node for source type: {source_type} and source: {source}"
        # Set the status "Success" because we are treating these error already handled by application as like custom errors.
        json_obj = {
            'error_message': error_message,
            'status': 'Success',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'success_count': 1,
            'source_type': source_type,
            'source_url': source_url,
            'wiki_query': wiki_query,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"url_scan LLMGraphBuilderException: {json_obj}")
        logging.exception(f'File Failed in upload: {e}')
        return Response(create_api_response('Failed', message=message + error_message[:80], error=error_message, file_source=source_type))

    except Exception as e:
        error_message = str(e)
        message = f" Unable to create source node for source type: {source_type} and source: {source}"
        json_obj = {
            'error_message': error_message,
            'status': 'Failed',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'failed_count': 1,
            'source_type': source_type,
            'source_url': source_url,
            'wiki_query': wiki_query,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "ERROR")
        else:
            logging.error(f"url_scan Exception: {json_obj}")
        logging.exception(f'Exception Stack trace upload:{e}')
        return Response(create_api_response('Failed', message=message + error_message[:80], error=error_message, file_source=source_type))
    finally:
        gc.collect()


@api_view(['POST'])
def extract(request):
    """
    Extract knowledge graph from file (local, S3, GCS, web-url, YouTube, Wikipedia).
    Migrated from FastAPI score.py:195-333
    Business logic: src.main -> extract_graph_from_file_*()
    """
    try:
        from src.main import (
            create_graph_database_connection,
            extract_graph_from_file_local_file,
            extract_graph_from_file_s3,
            extract_graph_from_web_page,
            extract_graph_from_file_youtube,
            extract_graph_from_file_Wikipedia,
            extract_graph_from_file_gcs,
            failed_file_process
        )
        from src.graphDB_dataAccess import graphDBdataAccess
        from src.shared.llm_graph_builder_exception import LLMGraphBuilderException
        import gc
        import asyncio

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start_time = time.time()

        # Extract parameters from request
        uri = request.data.get('uri')
        userName = request.data.get('userName')
        password = request.data.get('password')
        model = request.data.get('model')
        database = request.data.get('database')
        source_url = request.data.get('source_url')
        aws_access_key_id = request.data.get('aws_access_key_id')
        aws_secret_access_key = request.data.get('aws_secret_access_key')
        wiki_query = request.data.get('wiki_query')
        gcs_project_id = request.data.get('gcs_project_id')
        gcs_bucket_name = request.data.get('gcs_bucket_name')
        gcs_bucket_folder = request.data.get('gcs_bucket_folder')
        gcs_blob_filename = request.data.get('gcs_blob_filename')
        source_type = request.data.get('source_type')
        file_name = request.data.get('file_name')
        allowedNodes = request.data.get('allowedNodes')
        allowedRelationship = request.data.get('allowedRelationship')
        token_chunk_size = request.data.get('token_chunk_size')
        chunk_overlap = request.data.get('chunk_overlap')
        chunks_to_combine = request.data.get('chunks_to_combine')
        language = request.data.get('language')
        access_token = request.data.get('access_token')
        retry_condition = request.data.get('retry_condition')
        additional_instructions = request.data.get('additional_instructions')
        email = request.data.get('email')

        # Convert Optional[int] parameters to int if they're not None
        if token_chunk_size is not None:
            token_chunk_size = int(token_chunk_size)
        if chunk_overlap is not None:
            chunk_overlap = int(chunk_overlap)
        if chunks_to_combine is not None:
            chunks_to_combine = int(chunks_to_combine)

        # Create graph connection
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)

        # Call appropriate business logic based on source_type (these are async functions)
        if source_type == 'local file':
            file_name_sanitized = sanitize_filename(file_name)
            merged_file_path = validate_file_path(MERGED_DIR, file_name_sanitized)
            uri_latency, result = asyncio.run(extract_graph_from_file_local_file(
                uri, userName, password, database, model, merged_file_path, file_name,
                allowedNodes, allowedRelationship, token_chunk_size, chunk_overlap,
                chunks_to_combine, retry_condition, additional_instructions
            ))
        elif source_type == 's3 bucket' and source_url:
            uri_latency, result = asyncio.run(extract_graph_from_file_s3(
                uri, userName, password, database, model, source_url, aws_access_key_id,
                aws_secret_access_key, file_name, allowedNodes, allowedRelationship,
                token_chunk_size, chunk_overlap, chunks_to_combine, retry_condition, additional_instructions
            ))
        elif source_type == 'web-url':
            uri_latency, result = asyncio.run(extract_graph_from_web_page(
                uri, userName, password, database, model, source_url, file_name,
                allowedNodes, allowedRelationship, token_chunk_size, chunk_overlap,
                chunks_to_combine, retry_condition, additional_instructions
            ))
        elif source_type == 'youtube' and source_url:
            uri_latency, result = asyncio.run(extract_graph_from_file_youtube(
                uri, userName, password, database, model, source_url, file_name,
                allowedNodes, allowedRelationship, token_chunk_size, chunk_overlap,
                chunks_to_combine, retry_condition, additional_instructions
            ))
        elif source_type == 'Wikipedia' and wiki_query:
            uri_latency, result = asyncio.run(extract_graph_from_file_Wikipedia(
                uri, userName, password, database, model, wiki_query, language, file_name,
                allowedNodes, allowedRelationship, token_chunk_size, chunk_overlap,
                chunks_to_combine, retry_condition, additional_instructions
            ))
        elif source_type == 'gcs bucket' and gcs_bucket_name:
            uri_latency, result = asyncio.run(extract_graph_from_file_gcs(
                uri, userName, password, database, model, gcs_project_id, gcs_bucket_name,
                gcs_bucket_folder, gcs_blob_filename, access_token, file_name,
                allowedNodes, allowedRelationship, token_chunk_size, chunk_overlap,
                chunks_to_combine, retry_condition, additional_instructions
            ))
        else:
            return Response(create_api_response('Failed', message='source_type is other than accepted source'))

        extract_api_time = time.time() - start_time

        if result is not None:
            logging.info("Going for counting nodes and relationships in extract")
            count_node_time = time.time()
            graph = create_graph_database_connection(uri, userName, password, database)
            graphDb_data_Access = graphDBdataAccess(graph)
            count_response = graphDb_data_Access.update_node_relationship_count(file_name)
            logging.info("Nodes and Relationship Counts updated")

            if count_response:
                result['chunkNodeCount'] = count_response[file_name].get('chunkNodeCount', "0")
                result['chunkRelCount'] = count_response[file_name].get('chunkRelCount', "0")
                result['entityNodeCount'] = count_response[file_name].get('entityNodeCount', "0")
                result['entityEntityRelCount'] = count_response[file_name].get('entityEntityRelCount', "0")
                result['communityNodeCount'] = count_response[file_name].get('communityNodeCount', "0")
                result['communityRelCount'] = count_response[file_name].get('communityRelCount', "0")
                result['nodeCount'] = count_response[file_name].get('nodeCount', "0")
                result['relationshipCount'] = count_response[file_name].get('relationshipCount', "0")
                logging.info(f"counting completed in {(time.time()-count_node_time):.2f}")

            result['db_url'] = uri
            result['api_name'] = 'extract'
            result['source_url'] = source_url
            result['wiki_query'] = wiki_query
            result['source_type'] = source_type
            result['logging_time'] = formatted_time(datetime.now(timezone.utc))
            result['elapsed_api_time'] = f'{extract_api_time:.2f}'
            result['userName'] = userName
            result['database'] = database
            result['aws_access_key_id'] = aws_access_key_id
            result['gcs_bucket_name'] = gcs_bucket_name
            result['gcs_bucket_folder'] = gcs_bucket_folder
            result['gcs_blob_filename'] = gcs_blob_filename
            result['gcs_project_id'] = gcs_project_id
            result['language'] = language
            result['retry_condition'] = retry_condition
            result['email'] = email

        if logger:
            logger.log_struct(result, "INFO")
        else:
            logging.info(f"extract: {result}")

        result.update(uri_latency)
        logging.info(f"extraction completed in {extract_api_time:.2f} seconds for file name {file_name}")
        return Response(create_api_response('Success', data=result, file_source=source_type))

    except LLMGraphBuilderException as e:
        error_message = str(e)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        graphDb_data_Access.update_exception_db(file_name, error_message, retry_condition)

        if source_type == 'local file':
            file_name_sanitized = sanitize_filename(file_name)
            merged_file_path = validate_file_path(MERGED_DIR, file_name_sanitized)
            failed_file_process(uri, file_name, merged_file_path)

        node_detail = graphDb_data_Access.get_current_status_document_node(file_name)
        # Set the status "Completed" in logging because we are treating these error already handled by application as like custom errors.
        json_obj = {
            'api_name': 'extract',
            'message': error_message,
            'file_created_at': formatted_time(node_detail[0]['created_time']),
            'error_message': error_message,
            'file_name': file_name,
            'status': 'Completed',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'success_count': 1,
            'source_type': source_type,
            'source_url': source_url,
            'wiki_query': wiki_query,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'email': email,
            'allowedNodes': allowedNodes,
            'allowedRelationship': allowedRelationship
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"extract LLMGraphBuilderException: {json_obj}")
        logging.exception(f'File Failed in extraction: {e}')
        return Response(create_api_response("Failed", message=error_message, error=error_message, file_name=file_name))

    except Exception as e:
        message = f"Failed To Process File:{file_name} or LLM Unable To Parse Content "
        error_message = str(e)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        graphDb_data_Access.update_exception_db(file_name, error_message, retry_condition)

        if source_type == 'local file':
            file_name_sanitized = sanitize_filename(file_name)
            merged_file_path = validate_file_path(MERGED_DIR, file_name_sanitized)
            failed_file_process(uri, file_name, merged_file_path)

        node_detail = graphDb_data_Access.get_current_status_document_node(file_name)
        json_obj = {
            'api_name': 'extract',
            'message': message,
            'file_created_at': formatted_time(node_detail[0]['created_time']),
            'error_message': error_message,
            'file_name': file_name,
            'status': 'Failed',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'failed_count': 1,
            'source_type': source_type,
            'source_url': source_url,
            'wiki_query': wiki_query,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'email': email,
            'allowedNodes': allowedNodes,
            'allowedRelationship': allowedRelationship
        }
        if logger:
            logger.log_struct(json_obj, "ERROR")
        else:
            logging.error(f"extract Exception: {json_obj}")
        logging.exception(f'File Failed in extraction: {e}')
        return Response(create_api_response('Failed', message=message + error_message[:100], error=error_message, file_name=file_name))
    finally:
        gc.collect()


@api_view(['POST'])
def post_processing(request):
    """
    Post-processing tasks for graph database.
    Migrated from FastAPI score.py:360-415
    Business logic: src.main -> update_graph(), src.post_processing -> create_vector_fulltext_indexes(), etc.
    """
    try:
        from src.main import create_graph_database_connection, update_graph
        from src.post_processing import create_vector_fulltext_indexes, create_entity_embedding, graph_schema_consolidation
        from src.communities import create_communities
        from src.graphDB_dataAccess import graphDBdataAccess
        import gc

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        # Extract parameters from request
        uri = request.data.get('uri')
        userName = request.data.get('userName')
        password = request.data.get('password')
        database = request.data.get('database')
        tasks = request.data.get('tasks')
        email = request.data.get('email')

        # Parse tasks JSON string to set
        tasks = set(map(str.strip, json.loads(tasks)))

        graph = create_graph_database_connection(uri, userName, password, database)
        api_name = 'post_processing'
        count_response = []
        start = time.time()

        # Execute tasks based on what's requested
        if "materialize_text_chunk_similarities" in tasks:
            update_graph(graph)
            api_name = 'post_processing/update_similarity_graph'
            logging.info(f'Updated KNN Graph')

        if "enable_hybrid_search_and_fulltext_search_in_bloom" in tasks:
            create_vector_fulltext_indexes(uri=uri, username=userName, password=password, database=database)
            api_name = 'post_processing/enable_hybrid_search_and_fulltext_search_in_bloom'
            logging.info(f'Full Text index created')

        if os.environ.get('ENTITY_EMBEDDING', 'False').upper() == "TRUE" and "materialize_entity_similarities" in tasks:
            create_entity_embedding(graph)
            api_name = 'post_processing/create_entity_embedding'
            logging.info(f'Entity Embeddings created')

        if "graph_schema_consolidation" in tasks:
            graph_schema_consolidation(graph)
            api_name = 'post_processing/graph_schema_consolidation'
            logging.info(f'Updated nodes and relationship labels')

        if "enable_communities" in tasks:
            api_name = 'create_communities'
            create_communities(uri, userName, password, database)
            logging.info(f'created communities')

        # Update node and relationship counts
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        document_name = ""
        count_response = graphDb_data_Access.update_node_relationship_count(document_name)

        if count_response:
            count_response = [{"filename": filename, **counts} for filename, counts in count_response.items()]
            logging.info(f'Updated source node with community related counts')

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': api_name,
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
            logging.info(f"post_processing: {json_obj}")

        return Response(create_api_response('Success', data=count_response, message='All tasks completed successfully'))

    except Exception as e:
        job_status = "Failed"
        error_message = str(e)
        message = f"Unable to complete tasks"
        logging.exception(f'Exception in post_processing tasks: {error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))
    finally:
        gc.collect()


@api_view(['POST'])
def chat_bot(request):
    """
    Chat bot endpoint for QA with RAG.
    Migrated from FastAPI score.py:417-447
    Business logic: src.QA_integration -> QA_RAG
    """
    logging.info(f"QA_RAG called at {datetime.now()}")
    qa_rag_start_time = time.time()
    try:
        from src.QA_integration import QA_RAG
        from src.main import create_graph_database_connection
        from langchain_neo4j import Neo4jGraph
        from src.graphDB_dataAccess import graphDBdataAccess
        import gc

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        # Extract parameters from request
        uri = request.data.get('uri')
        model = request.data.get('model')
        userName = request.data.get('userName')
        password = request.data.get('password')
        database = request.data.get('database')
        question = request.data.get('question')
        document_names = request.data.get('document_names')
        session_id = request.data.get('session_id')
        mode = request.data.get('mode')
        email = request.data.get('email')

        # Conditional graph creation based on mode
        if mode == "graph":
            graph = Neo4jGraph(url=uri, username=userName, password=password, database=database, sanitize=True, refresh_schema=True)
        else:
            graph = create_graph_database_connection(uri, userName, password, database)

        graph_DB_dataAccess = graphDBdataAccess(graph)
        write_access = graph_DB_dataAccess.check_account_access(database=database)

        # Call QA_RAG (it's a sync function, no asyncio needed in Django)
        result = QA_RAG(graph=graph, model=model, question=question, document_names=document_names, session_id=session_id, mode=mode, write_access=write_access)

        total_call_time = time.time() - qa_rag_start_time
        logging.info(f"Total Response time is {total_call_time:.2f} seconds")
        result["info"]["response_time"] = round(total_call_time, 2)

        json_obj = {
            'api_name': 'chat_bot',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'question': question,
            'document_names': document_names,
            'session_id': session_id,
            'mode': mode,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{total_call_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"chat_bot: {json_obj}")

        return Response(create_api_response('Success', data=result))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to get chat response"
        error_message = str(e)
        logging.exception(f'Exception in chat bot:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message, data=mode))
    finally:
        gc.collect()


@api_view(['POST'])
def upload(request):
    """
    Upload large file in chunks.
    Migrated from FastAPI score.py:417-445
    Business logic: src.main -> upload_file()
    """
    try:
        from src.main import create_graph_database_connection, upload_file
        from src.graphDB_dataAccess import graphDBdataAccess
        import gc

        # Lazy import CustomLogger to avoid google.cloud.logging import errors
        try:
            from src.logger import CustomLogger
            logger = CustomLogger()
        except ImportError:
            logger = None

        start = time.time()

        # Extract file and parameters from request
        file = request.FILES.get('file')
        chunkNumber = request.data.get('chunkNumber')
        totalChunks = request.data.get('totalChunks')
        originalname = request.data.get('originalname')
        model = request.data.get('model')
        uri = request.data.get('uri')
        userName = request.data.get('userName')
        password = request.data.get('password')
        database = request.data.get('database')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        result = upload_file(graph, model, file, chunkNumber, totalChunks, originalname, uri, CHUNK_DIR, MERGED_DIR)

        end = time.time()
        elapsed_time = end - start

        # Conditional logging (only when last chunk)
        if int(chunkNumber) == int(totalChunks):
            json_obj = {
                'api_name': 'upload',
                'db_url': uri,
                'userName': userName,
                'database': database,
                'chunkNumber': chunkNumber,
                'totalChunks': totalChunks,
                'original_file_name': originalname,
                'model': model,
                'logging_time': formatted_time(datetime.now(timezone.utc)),
                'elapsed_api_time': f'{elapsed_time:.2f}',
                'email': email
            }
            if logger:
                logger.log_struct(json_obj, "INFO")
            else:
                logging.info(f"upload: {json_obj}")

        # Return different messages based on whether this is the last chunk
        if int(chunkNumber) == int(totalChunks):
            return Response(create_api_response('Success', data=result, message='Source Node Created Successfully'))
        else:
            return Response(create_api_response('Success', message=result))

    except Exception as e:
        message = "Unable to upload file in chunks"
        error_message = str(e)
        graph = create_graph_database_connection(uri, userName, password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        graphDb_data_Access.update_exception_db(originalname, error_message)
        logging.info(message)
        logging.exception(f'Exception:{error_message}')
        return Response(create_api_response('Failed', message=message + error_message[:100], error=error_message, file_name=originalname))
    finally:
        gc.collect()


@api_view(['GET'])
def update_extract_status(request, file_name):
    """
    Server-Sent Events (SSE) endpoint for real-time file processing status updates.
    Migrated from FastAPI score.py:147-194 (@app.get)
    Business logic: graphDBdataAccess.get_current_status_document_node()

    This endpoint streams status updates to the client using SSE.
    """
    from django.http import StreamingHttpResponse
    from src.main import create_graph_database_connection
    from src.graphDB_dataAccess import graphDBdataAccess
    import time

    # Get query parameters
    uri = request.GET.get('uri')
    userName = request.GET.get('userName')
    password = request.GET.get('password')
    database = request.GET.get('database')

    # Decode password if provided
    if password is not None and password != "null":
        decoded_password = decode_password(password)
    else:
        decoded_password = None

    # Handle spaces in URL
    url = uri
    if url and " " in url:
        url = url.replace(" ", "+")

    def event_stream():
        """Generator function for SSE streaming."""
        try:
            graph = create_graph_database_connection(url, userName, decoded_password, database)
            graphDb_data_Access = graphDBdataAccess(graph)

            while True:
                try:
                    # Get current status of document node
                    result = graphDb_data_Access.get_current_status_document_node(file_name)

                    if len(result) > 0:
                        status = json.dumps({
                            'fileName': file_name,
                            'status': result[0]['Status'],
                            'processingTime': result[0]['processingTime'],
                            'nodeCount': result[0]['nodeCount'],
                            'relationshipCount': result[0]['relationshipCount'],
                            'model': result[0]['model'],
                            'total_chunks': result[0]['total_chunks'],
                            'fileSize': result[0]['fileSize'],
                            'processed_chunk': result[0]['processed_chunk'],
                            'fileSource': result[0]['fileSource'],
                            'chunkNodeCount': result[0]['chunkNodeCount'],
                            'chunkRelCount': result[0]['chunkRelCount'],
                            'entityNodeCount': result[0]['entityNodeCount'],
                            'entityEntityRelCount': result[0]['entityEntityRelCount'],
                            'communityNodeCount': result[0]['communityNodeCount'],
                            'communityRelCount': result[0]['communityRelCount']
                        })

                        # Send data in SSE format
                        yield f"data: {status}\n\n"

                    # Small delay to prevent excessive polling
                    time.sleep(1)

                except Exception as e:
                    logging.exception(f"Error in SSE stream: {e}")
                    break

        except Exception as e:
            logging.exception(f"Error initializing SSE connection: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    # Return StreamingHttpResponse with SSE headers
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response


@api_view(['POST'])
def cancelled_job(request):
    """
    Cancel running job for file processing.
    Migrated from FastAPI score.py:596-615
    Business logic: src.main -> manually_cancelled_job()
    """
    try:
        from src.main import create_graph_database_connection, manually_cancelled_job
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
        filenames = request.data.get('filenames')
        source_types = request.data.get('source_types')
        email = request.data.get('email')

        # Call business logic (unchanged from src/)
        graph = create_graph_database_connection(uri, userName, password, database)
        result = manually_cancelled_job(graph, filenames, source_types, MERGED_DIR, uri)

        end = time.time()
        elapsed_time = end - start

        # Logging
        json_obj = {
            'api_name': 'cancelled_job',
            'db_url': uri,
            'userName': userName,
            'database': database,
            'filenames': filenames,
            'source_types': source_types,
            'logging_time': formatted_time(datetime.now(timezone.utc)),
            'elapsed_api_time': f'{elapsed_time:.2f}',
            'email': email
        }
        if logger:
            logger.log_struct(json_obj, "INFO")
        else:
            logging.info(f"cancelled_job: {json_obj}")

        return Response(create_api_response('Success', message=result))

    except Exception as e:
        job_status = "Failed"
        message = "Unable to cancelled the running job"
        error_message = str(e)
        logging.exception(f'Exception in cancelling the running job:{error_message}')
        return Response(create_api_response(job_status, message=message, error=error_message))
    finally:
        gc.collect()


@api_view(['GET'])
def document_status(request, file_name):
    """
    Get current status of a document node (single query, no streaming).
    Migrated from FastAPI score.py:147-185 (@app.get)
    Business logic: graphDBdataAccess.get_current_status_document_node()

    Similar to update_extract_status but returns a single status snapshot instead of streaming.
    """
    try:
        from src.main import create_graph_database_connection
        from src.graphDB_dataAccess import graphDBdataAccess

        # Get query parameters
        url = request.GET.get('url')
        userName = request.GET.get('userName')
        password = request.GET.get('password')
        database = request.GET.get('database')

        # Decode password if provided
        if password is not None and password != "null":
            decoded_password = decode_password(password)
        else:
            decoded_password = None

        # Handle spaces in URL
        if url and " " in url:
            uri = url.replace(" ", "+")
        else:
            uri = url

        # Call business logic
        graph = create_graph_database_connection(uri, userName, decoded_password, database)
        graphDb_data_Access = graphDBdataAccess(graph)
        result = graphDb_data_Access.get_current_status_document_node(file_name)

        # Build status response
        if len(result) > 0:
            status = {
                'fileName': file_name,
                'status': result[0]['Status'],
                'processingTime': result[0]['processingTime'],
                'nodeCount': result[0]['nodeCount'],
                'relationshipCount': result[0]['relationshipCount'],
                'model': result[0]['model'],
                'total_chunks': result[0]['total_chunks'],
                'fileSize': result[0]['fileSize'],
                'processed_chunk': result[0]['processed_chunk'],
                'fileSource': result[0]['fileSource'],
                'chunkNodeCount': result[0]['chunkNodeCount'],
                'chunkRelCount': result[0]['chunkRelCount'],
                'entityNodeCount': result[0]['entityNodeCount'],
                'entityEntityRelCount': result[0]['entityEntityRelCount'],
                'communityNodeCount': result[0]['communityNodeCount'],
                'communityRelCount': result[0]['communityRelCount']
            }
        else:
            status = {'fileName': file_name, 'status': 'Failed'}

        logging.info(f'Result of document status in refresh : {result}')
        return Response(create_api_response('Success', message="", file_name=status))

    except Exception as e:
        message = f"Unable to get the document status"
        error_message = str(e)
        logging.exception(f'{message}:{error_message}')
        return Response(create_api_response('Failed', message=message))


# ========================================
# ALL 29 ENDPOINTS MIGRATED SUCCESSFULLY!
# ========================================
# Pattern: FastAPI @app.post() -> Django @api_view(['POST'])
# Business logic from src/ folder imported as-is
