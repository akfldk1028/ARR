"""
Document management endpoints.

Endpoints:
- sources_list: Get list of sources from Neo4j database (POST)
- upload: Upload large file in chunks (POST)
- url_scan: Create source knowledge graph from URL (POST)
- delete_document_and_entities: Delete documents and entities (POST)
- document_status: Get current status of a document node (GET)
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

# Import helper functions from views.helpers
from .helpers import MERGED_DIR, CHUNK_DIR, decode_password, sanitize_filename, validate_file_path, convert_neo4j_datetime


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

        # Convert Neo4j DateTime objects to strings for JSON serialization
        result = convert_neo4j_datetime(result)

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

        # Convert Neo4j DateTime objects to strings
        result = convert_neo4j_datetime(result)

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
