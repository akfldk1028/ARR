"""
Graph-related API endpoints.

This module contains endpoints for graph operations, including:
- get_neighbours: Get neighbour nodes for a given element ID
- chunk_entities: Get entities from chunk IDs
- graph_query: Get graph query results
- fetch_chunktext: Fetch chunk text results from Neo4j database
- get_unconnected_nodes_list: Get list of unconnected nodes
- delete_unconnected_nodes: Delete unconnected nodes from Neo4j database
- get_duplicate_nodes: Get list of duplicate nodes
- merge_duplicate_nodes: Merge duplicate nodes in Neo4j database

Migrated from FastAPI score.py
Business logic remains in src/ folder - unchanged!
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import time
import logging
from datetime import datetime, timezone

# Import business logic modules from src/
from src.api_response import create_api_response
from src.shared.common_fn import formatted_time

# Import helper functions
from .helpers import convert_neo4j_datetime


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

        # Convert Neo4j DateTime objects to strings
        result = convert_neo4j_datetime(result)

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

        # Convert Neo4j DateTime objects to strings
        result = convert_neo4j_datetime(result)

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

        # Convert Neo4j DateTime objects to strings
        result = convert_neo4j_datetime(result)

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

        # Convert Neo4j DateTime objects to strings
        result = convert_neo4j_datetime(result)

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

        # Convert Neo4j DateTime objects to strings
        nodes_list = convert_neo4j_datetime(nodes_list)

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

        # Convert Neo4j DateTime objects to strings
        result = convert_neo4j_datetime(result)

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

        # Convert Neo4j DateTime objects to strings
        nodes_list = convert_neo4j_datetime(nodes_list)

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

        # Convert Neo4j DateTime objects to strings
        result = convert_neo4j_datetime(result)

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
