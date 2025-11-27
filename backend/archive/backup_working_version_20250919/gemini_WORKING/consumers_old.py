import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .services import GeminiLiveMultimodalService

class GeminiLiveConsumer(AsyncWebsocketConsumer):
    """Django Channels WebSocket consumer for Gemini Live API"""

    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Initialize Gemini service
            self.gemini_service = GeminiLiveMultimodalService()
            await self.accept()

            # Send welcome message
            await self.send(text_data=json.dumps({
                'type': 'connection',
                'message': 'Connected to Gemini Live API',
                'model': self.gemini_service.model,
                'capabilities': ['text', 'image', 'audio', 'video'],
                'success': True
            }))

            print("[Django WebSocket] Client connected to Gemini Live API")

        except Exception as e:
            print(f"[Django WebSocket] Connection error: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        print(f"[Django WebSocket] Client disconnected: {close_code}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            message_data = json.loads(text_data)
            message_type = message_data.get('type')

            if message_type == 'text':
                await self.handle_text_message(message_data)
            elif message_type == 'image':
                await self.handle_image_message(message_data)
            elif message_type == 'audio':
                await self.handle_audio_message(message_data)
            elif message_type == 'video':
                await self.handle_video_message(message_data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            await self.send_error(f"Message processing error: {str(e)}")

    async def handle_text_message(self, message_data):
        """Handle text message processing"""
        user_message = message_data.get('message', '')

        if not user_message.strip():
            await self.send_error("Empty message")
            return

        print(f"[Text] Processing: {user_message[:50]}...")

        # Process with Gemini Live API
        result = await self.gemini_service.process_text_stream(user_message)

        # Send response
        await self.send(text_data=json.dumps({
            'type': 'response',
            'message': result['text'],
            'response_time': result['response_time'],
            'model': result['model'],
            'analysis_type': result['type'],
            'success': result['success']
        }))

    async def handle_image_message(self, message_data):
        """Handle image message processing"""
        image_data = message_data.get('image', '')
        prompt = message_data.get('prompt', 'What do you see in this image?')

        if not image_data:
            await self.send_error("No image data provided")
            return

        print(f"[Image] Processing with prompt: {prompt}")

        # Process with Gemini API
        result = await self.gemini_service.process_image_stream(image_data, prompt)

        # Send response
        await self.send(text_data=json.dumps({
            'type': 'response',
            'message': result['text'],
            'response_time': result['response_time'],
            'model': result['model'],
            'analysis_type': result['type'],
            'success': result['success']
        }))

    async def handle_audio_message(self, message_data):
        """Handle audio message processing"""
        audio_data = message_data.get('audio', '')

        if not audio_data:
            await self.send_error("No audio data provided")
            return

        print(f"[Audio] Processing {len(audio_data)} bytes")

        # Process with Gemini Live API
        result = await self.gemini_service.process_audio_stream(audio_data)

        # Send response
        await self.send(text_data=json.dumps({
            'type': 'response',
            'message': result['text'],
            'response_time': result['response_time'],
            'model': result['model'],
            'analysis_type': result['type'],
            'success': result['success']
        }))

    async def handle_video_message(self, message_data):
        """Handle video message processing"""
        frames = message_data.get('frames', [])
        prompt = message_data.get('prompt', 'What is happening in this video?')

        if not frames:
            await self.send_error("No video frames provided")
            return

        print(f"[Video] Processing {len(frames)} frames with prompt: {prompt}")

        # Process with Gemini API
        result = await self.gemini_service.process_video_stream(frames, prompt)

        # Send response
        await self.send(text_data=json.dumps({
            'type': 'response',
            'message': result['text'],
            'response_time': result['response_time'],
            'model': result['model'],
            'analysis_type': result['type'],
            'success': result['success']
        }))

    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
            'success': False
        }))
        print(f"[Django WebSocket] Error: {error_message}")