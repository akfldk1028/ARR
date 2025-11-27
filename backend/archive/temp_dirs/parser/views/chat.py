"""
Chat-related API endpoints.

This module contains endpoints for chat bot functionality:
- chat_bot: Chat bot endpoint for QA with RAG
- clear_chat_bot: Clear chat history for a given session

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
def clear_chat_bot(request):
    """
    Clear chat history for a given session.
    Migrated from FastAPI score.py:310-328
    Business logic: src.QA_integration.py -> clear_chat_history()
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
