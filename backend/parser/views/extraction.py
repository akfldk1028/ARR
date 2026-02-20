"""
Extraction-related API endpoints.

This module contains endpoints for graph extraction and processing:
- extract: Extract knowledge graph from file (local, S3, GCS, web-url, YouTube, Wikipedia)
- post_processing: Post-processing tasks for graph database
- retry_processing: Retry processing for a failed document
- cancelled_job: Cancel running job for file processing
- update_extract_status: Server-Sent Events (SSE) endpoint for real-time file processing status updates

Migrated from FastAPI score.py
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

# Import helper functions from views.helpers
from .helpers import MERGED_DIR, CHUNK_DIR, decode_password, sanitize_filename, validate_file_path


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


def update_extract_status(request, file_name):
    """
    Server-Sent Events (SSE) endpoint for real-time file processing status updates.
    Migrated from FastAPI score.py:147-194 (@app.get)
    Business logic: graphDBdataAccess.get_current_status_document_node()

    This endpoint streams status updates to the client using SSE.
    NOTE: Does NOT use @api_view decorator to avoid DRF content negotiation conflicts with SSE.
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
        from .helpers import convert_neo4j_datetime

        try:
            graph = create_graph_database_connection(url, userName, decoded_password, database)
            graphDb_data_Access = graphDBdataAccess(graph)

            while True:
                try:
                    # Get current status of document node
                    result = graphDb_data_Access.get_current_status_document_node(file_name)

                    if len(result) > 0:
                        # Convert Neo4j DateTime objects before JSON serialization
                        converted_result = convert_neo4j_datetime(result[0])

                        status = json.dumps({
                            'fileName': file_name,
                            'status': converted_result['Status'],
                            'processingTime': converted_result['processingTime'],
                            'nodeCount': converted_result['nodeCount'],
                            'relationshipCount': converted_result['relationshipCount'],
                            'model': converted_result['model'],
                            'total_chunks': converted_result['total_chunks'],
                            'fileSize': converted_result['fileSize'],
                            'processed_chunk': converted_result['processed_chunk'],
                            'fileSource': converted_result['fileSource'],
                            'chunkNodeCount': converted_result['chunkNodeCount'],
                            'chunkRelCount': converted_result['chunkRelCount'],
                            'entityNodeCount': converted_result['entityNodeCount'],
                            'entityEntityRelCount': converted_result['entityEntityRelCount'],
                            'communityNodeCount': converted_result['communityNodeCount'],
                            'communityRelCount': converted_result['communityRelCount']
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
    # Add CORS headers for frontend access
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    return response
