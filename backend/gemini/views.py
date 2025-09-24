import asyncio
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .services.service_manager import get_gemini_service

def gemini_home(request):
    """Main Gemini Live API interface"""
    try:
        # Get service instance
        service = get_gemini_service()
        model_name = service.client.config.model
    except Exception as e:
        model_name = f"Error: {str(e)}"

    # Get current host and port from request
    host = request.get_host().split(':')[0]  # Get hostname only
    websocket_url = f'ws://{host}:8000/ws/gemini/'  # WebSocket server on port 8000

    context = {
        'model_name': model_name,
        'websocket_url': websocket_url,
        'page_title': 'Gemini Live API - Django Integration (Optimized)'
    }

    return render(request, 'gemini/index.html', context)

async def health_check_async(request):
    """Async health check endpoint"""
    try:
        service = get_gemini_service()
        health_result = await service.health_check()

        if health_result.get('success'):
            return JsonResponse({
                'status': 'healthy',
                'model': health_result.get('model'),
                'response_time': health_result.get('response_time'),
                'active_sessions': health_result.get('active_sessions', 0)
            })
        else:
            return JsonResponse({
                'status': 'unhealthy',
                'error': health_result.get('error')
            }, status=500)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)

def health_check(request):
    """Sync wrapper for health check"""
    try:
        return asyncio.run(health_check_async(request))
    except Exception as e:
        return HttpResponse(f"Service error: {str(e)}", status=500)

def continuous_voice(request):
    """Continuous Voice Conversation interface using Gemini Live API"""
    # Get current host and port from request
    host = request.get_host().split(':')[0]  # Get hostname only
    websocket_url = f'ws://{host}:8000/ws/gemini/'  # WebSocket server on port 8000

    context = {
        'websocket_url': websocket_url,
        'page_title': 'Gemini Live API - Real-time Voice Conversation'
    }

    return render(request, 'gemini/voice_conversation.html', context)
