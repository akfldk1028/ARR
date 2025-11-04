"""
Graph DB Views
API endpoints for Neo4j CDC events
"""
import json
import logging
import asyncio
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from asgiref.sync import async_to_sync

from .kafka_producer import get_kafka_producer

logger = logging.getLogger(__name__)


@csrf_exempt
async def neo4j_event(request):
    """
    Receive Neo4j CDC events from APOC triggers and publish to Kafka

    Expected JSON payload:
    {
        "type": "conversation_created",
        "data": {...}
    }
    """
    try:
        # Parse JSON payload
        body = await request.body() if hasattr(request.body, '__call__') else request.body
        logger.info(f"Raw body received: {body}")
        logger.info(f"Body type: {type(body)}")
        payload = json.loads(body)
        event_type = payload.get('type')
        data = payload.get('data', {})

        if not event_type:
            return JsonResponse({'error': 'Missing event type'}, status=400)

        # Publish to Kafka asynchronously
        producer = await get_kafka_producer()
        try:
            await producer.publish_event(event_type, data)
            logger.info(f"Received and published Neo4j event: {event_type}")
        finally:
            # Clean up producer
            await producer.stop()

        return JsonResponse({'status': 'success', 'event_type': event_type})

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    except Exception as e:
        logger.error(f"Error processing Neo4j event: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
