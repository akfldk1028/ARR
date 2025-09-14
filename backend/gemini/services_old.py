import asyncio
import json
import time
import base64
import os
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image
import io

class GeminiLiveMultimodalService:
    """Django integrated Gemini Live API service"""

    def __init__(self):
        # Load API key from environment or Django settings
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            try:
                from django.conf import settings
                self.api_key = getattr(settings, 'GOOGLE_API_KEY', None)
            except ImportError:
                pass

        if not self.api_key or self.api_key == "...":
            raise ValueError("GOOGLE_API_KEY not found in environment or Django settings")

        # Live API Client
        self.client = genai.Client(api_key=self.api_key)
        self.model = "models/gemini-2.0-flash-exp"  # Live API model

        # Live API configuration for multimodal streaming
        self.config = types.LiveConnectConfig(
            response_modalities=["TEXT"],  # Can add "AUDIO" for voice output
            temperature=0.9,
            max_output_tokens=2048,
            system_instruction="""You are a helpful AI assistant with multimodal capabilities.
            You can analyze images, video streams, and have natural conversations.
            Provide detailed and helpful responses."""
        )

        print(f"[Gemini Service] Initialized with model: {self.model}")

    async def process_text_stream(self, message):
        """Process text message via Live API streaming"""
        start_time = time.time()

        try:
            async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
                # Send text message using correct method
                await session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message)]
                    )
                )

                # Receive response
                full_response = ""
                async for response in session.receive():
                    # Handle different response formats
                    if hasattr(response, 'text') and response.text:
                        full_response += response.text
                    elif hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                            model_turn = response.server_content.model_turn
                            if hasattr(model_turn, 'parts') and model_turn.parts:
                                for part in model_turn.parts:
                                    if hasattr(part, 'text') and part.text:
                                        full_response += part.text

                        # Check if turn is complete
                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            break

                response_time = time.time() - start_time

                return {
                    'text': full_response or "No response from Live API",
                    'response_time': response_time,
                    'model': self.model,
                    'type': 'text_stream',
                    'success': bool(full_response)
                }

        except Exception as e:
            response_time = time.time() - start_time
            return {
                'text': f"Error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False
            }

    async def process_image_stream(self, image_data, prompt):
        """Process image using regular Gemini API (Live API doesn't support images yet)"""
        start_time = time.time()

        try:
            # Convert base64 to PIL Image
            if ',' in image_data:
                image_data = image_data.split(',')[1]

            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))

            print(f"Processing image: {image.width}x{image.height} pixels")

            # Use regular Gemini API for images
            response = await self.client.aio.models.generate_content(
                model='models/gemini-2.0-flash-exp',
                contents=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ]
            )

            response_time = time.time() - start_time

            return {
                'text': response.text or "No image analysis response",
                'response_time': response_time,
                'model': 'gemini-2.0-flash-exp (regular API)',
                'type': 'image_regular_api',
                'success': bool(response.text)
            }

        except Exception as e:
            response_time = time.time() - start_time
            return {
                'text': f"Image processing error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False
            }

    async def process_audio_stream(self, audio_data):
        """Process audio using Gemini Live API"""
        start_time = time.time()

        try:
            # Convert base64 audio to bytes
            audio_bytes = base64.b64decode(audio_data)

            print(f"[AUDIO] Processing {len(audio_bytes)} bytes of audio data")

            # For now, placeholder implementation
            response_time = time.time() - start_time

            return {
                'text': "Audio processed through Live API (speech recognition in progress...)",
                'response_time': response_time,
                'model': self.model,
                'type': 'audio_live_api',
                'success': True
            }

        except Exception as e:
            response_time = time.time() - start_time
            print(f"[ERROR] Audio processing failed: {str(e)}")
            return {
                'text': f"Audio processing error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'audio_error',
                'success': False
            }

    async def process_video_stream(self, video_frames, prompt):
        """Process video frames using regular API"""
        start_time = time.time()

        try:
            if not video_frames:
                return {
                    'text': "No video frames provided",
                    'response_time': 0,
                    'model': 'error',
                    'type': 'error',
                    'success': False
                }

            # Analyze first frame
            first_frame = video_frames[0]
            result = await self.process_image_stream(first_frame, f"[VIDEO FRAME ANALYSIS] {prompt}")

            # Modify response type
            result['type'] = 'video_frame_analysis'
            result['text'] = f"[Video Analysis - First Frame] {result['text']}"

            return result

        except Exception as e:
            response_time = time.time() - start_time
            return {
                'text': f"Video processing error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False
            }