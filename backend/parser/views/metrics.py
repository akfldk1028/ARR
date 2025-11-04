"""
Metrics and evaluation API endpoints.

This module contains endpoints for RAG evaluation metrics:
- calculate_metric: Calculate evaluation metrics for RAG system
- calculate_additional_metrics: Calculate additional evaluation metrics for RAG system

Migrated from FastAPI score.py
Business logic remains in src/ folder - unchanged!
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import time
import logging
import json
from datetime import datetime, timezone

# Import business logic modules from src/
from src.api_response import create_api_response
from src.shared.common_fn import formatted_time


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
