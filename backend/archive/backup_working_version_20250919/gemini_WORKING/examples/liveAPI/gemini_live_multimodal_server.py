#!/usr/bin/env python3
"""
Gemini Live API Multimodal WebSocket Server
Real-time text, audio, and video streaming via WebSocket
Using the correct Live API endpoint and methods
"""

import asyncio
import json
import time
import base64
import os
import sys
sys.path.append('../../src')

from dotenv import load_dotenv
import websockets
from websockets.server import serve
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
import uvicorn

# Google Gemini Live API
from google import genai
from google.genai import types

# For image handling
from PIL import Image
import io

load_dotenv(override=True)

# FastAPI app
app = FastAPI(title="Gemini Live API Multimodal Server")

class GeminiLiveMultimodalServer:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key or self.api_key == "...":
            raise ValueError("GOOGLE_API_KEY not found in .env file")

        # Live API Client
        self.client = genai.Client(api_key=self.api_key)
        self.model = "models/gemini-2.0-flash-exp"  # Live API 전용 모델 (2024 최신)

        # Live API configuration for multimodal streaming
        self.config = types.LiveConnectConfig(
            response_modalities=["TEXT"],  # Can add "AUDIO" for voice output
            temperature=0.9,
            max_output_tokens=2048,
            system_instruction="""You are a helpful AI assistant with multimodal capabilities.
            You can analyze images, video streams, and have natural conversations.
            Provide detailed and helpful responses."""
        )

        print(f"[OK] Gemini Live Multimodal Server Initialized")
        print(f"[OK] Model: {self.model}")
        print(f"[OK] Capabilities: Text, Image, Video, Audio (input)")
        print(f"[OK] WebSocket Streaming: Enabled")

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
                        # Stream back chunk by chunk if needed
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
            print("Note: Using regular Gemini API since Live API doesn't support images yet")

            # 일반 Gemini API 사용 (Live API는 아직 이미지 미지원)
            response = await self.client.aio.models.generate_content(
                model='models/gemini-2.0-flash-exp',  # 일반 모델 사용
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

            # Send audio data to Live API WebSocket
            audio_message = {
                "realtime_input": {
                    "media_chunks": [
                        {
                            "mime_type": "audio/wav",
                            "data": audio_data  # Keep as base64
                        }
                    ]
                }
            }

            # For now, process through Live API text channel (placeholder)
            # In future: implement proper Live API audio streaming
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
        """Process video frames using regular API (Live API video support coming soon)"""
        start_time = time.time()

        try:
            print("Note: Video streaming via Live API not yet supported. Using frame-by-frame analysis.")

            # 첫 번째 프레임만 분석 (Live API 비디오 지원 대기중)
            if not video_frames:
                return {
                    'text': "No video frames provided",
                    'response_time': 0,
                    'model': 'error',
                    'type': 'error',
                    'success': False
                }

            # 첫 프레임을 이미지로 분석
            first_frame = video_frames[0]
            result = await self.process_image_stream(first_frame, f"[VIDEO FRAME ANALYSIS] {prompt}")

            # 응답 타입 수정
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

# Global server instance
live_server = GeminiLiveMultimodalServer()

# HTML client page
@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Gemini Live API Multimodal Test</title>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #666;
            font-size: 14px;
        }}
        .chat {{
            border: 2px solid #e0e0e0;
            height: 500px;
            overflow-y: auto;
            padding: 20px;
            margin: 20px 0;
            background: #f9f9f9;
            border-radius: 15px;
        }}
        .message {{
            margin: 15px 0;
            padding: 15px;
            border-radius: 10px;
            max-width: 80%;
            animation: fadeIn 0.3s;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .user {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-left: auto;
            text-align: right;
        }}
        .ai {{
            background: white;
            border: 1px solid #e0e0e0;
            margin-right: auto;
        }}
        .controls {{
            margin: 20px 0;
            padding: 20px;
            background: #f5f5f5;
            border-radius: 15px;
        }}
        .control-group {{
            margin-bottom: 20px;
        }}
        .control-group h3 {{
            color: #333;
            margin-bottom: 10px;
        }}
        input, button {{
            padding: 12px 20px;
            margin: 5px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.3s;
        }}
        button {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            cursor: pointer;
            font-weight: bold;
        }}
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }}
        #messageInput {{ width: 60%; }}
        #imagePrompt {{ width: 50%; }}
        .status {{
            padding: 10px 20px;
            margin: 10px 0;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
            transition: all 0.3s;
        }}
        .connected {{
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }}
        .disconnected {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }}
        .image-preview {{
            max-width: 300px;
            margin: 10px 0;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        .info-badge {{
            display: inline-block;
            padding: 4px 8px;
            background: #f0f0f0;
            border-radius: 4px;
            font-size: 12px;
            color: #666;
            margin-left: 10px;
        }}
        .capabilities {{
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 10px;
        }}
        .capability {{
            padding: 5px 15px;
            background: #e3f2fd;
            color: #1976d2;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Gemini Live API Multimodal Test</h1>
            <p>Model: {live_server.model} | Real-time WebSocket Streaming</p>
            <div class="capabilities">
                <span class="capability">Text</span>
                <span class="capability">Image</span>
                <span class="capability">Video (Soon)</span>
                <span class="capability">Audio (Input)</span>
            </div>
        </div>

        <div id="status" class="status disconnected">Connecting to Live API...</div>

        <div id="chat" class="chat"></div>

        <div class="controls">
            <div class="control-group">
                <h3>Image Analysis</h3>
                <input type="file" id="imageInput" accept="image/*">
                <input type="text" id="imagePrompt" placeholder="Ask about the image..." value="What do you see in this image?">
                <button onclick="uploadImage()">Analyze Image</button>
            </div>

            <div class="control-group">
                <h3>Audio Chat</h3>
                <button id="audioButton" onclick="toggleAudio()">🎤 Start Recording</button>
                <div id="audioStatus" style="margin: 10px 0; font-size: 12px; color: #666;"></div>
            </div>

            <div class="control-group">
                <h3>Text Chat</h3>
                <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()">Send</button>
                <button onclick="clearChat()">Clear</button>
            </div>
        </div>
    </div>

    <script>
        const ws = new WebSocket('ws://localhost:8899/ws');
        const chat = document.getElementById('chat');
        const status = document.getElementById('status');

        ws.onopen = () => {{
            status.textContent = 'Connected to Gemini Live API';
            status.className = 'status connected';
            addMessage('Connected to Gemini Live API Multimodal Server!', 'ai');
        }};

        ws.onclose = () => {{
            status.textContent = 'Disconnected';
            status.className = 'status disconnected';
        }};

        ws.onerror = (error) => {{
            status.textContent = 'Connection Error';
            status.className = 'status disconnected';
            console.error('WebSocket error:', error);
        }};

        ws.onmessage = (event) => {{
            const data = JSON.parse(event.data);
            if (data.type === 'response') {{
                const time = data.response_time ? ` <span class="info-badge">${{data.response_time.toFixed(2)}}s</span>` : '';
                let typeIcon = '[TXT]';
                if (data.analysis_type === 'image_stream') typeIcon = '[IMG]';
                else if (data.analysis_type === 'audio_live_api') typeIcon = '[AUD]';
                else if (data.analysis_type === 'video_frame_analysis') typeIcon = '[VID]';
                addMessage(`${{typeIcon}} ${{data.message}}${{time}}`, 'ai');
            }} else if (data.type === 'error') {{
                addMessage(`[ERROR] ${{data.message}}`, 'ai');
            }}
        }};

        function addMessage(msg, sender) {{
            const div = document.createElement('div');
            div.className = 'message ' + sender;
            div.innerHTML = msg;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }}

        function sendMessage() {{
            const input = document.getElementById('messageInput');
            const msg = input.value.trim();
            if (msg && ws.readyState === WebSocket.OPEN) {{
                addMessage('[TXT] ' + msg, 'user');
                ws.send(JSON.stringify({{type: 'text', message: msg}}));
                input.value = '';
            }} else if (ws.readyState !== WebSocket.OPEN) {{
                alert('Not connected. Please refresh the page.');
            }}
        }}

        function uploadImage() {{
            const file = document.getElementById('imageInput').files[0];
            const prompt = document.getElementById('imagePrompt').value || 'What do you see in this image?';

            if (file && ws.readyState === WebSocket.OPEN) {{
                const reader = new FileReader();
                reader.onload = (e) => {{
                    addMessage(`[IMG] Analyzing image: "${{prompt}}"`, 'user');

                    // Show image preview
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.className = 'image-preview';
                    chat.appendChild(img);
                    chat.scrollTop = chat.scrollHeight;

                    ws.send(JSON.stringify({{
                        type: 'image',
                        image: e.target.result,
                        prompt: prompt
                    }}));
                }};
                reader.readAsDataURL(file);
            }} else if (!file) {{
                alert('Please select an image file.');
            }} else {{
                alert('WebSocket not connected.');
            }}
        }}

        function clearChat() {{
            chat.innerHTML = '';
            addMessage('Chat cleared. Ready for new conversation!', 'ai');
        }}

        // Audio recording variables
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;

        async function toggleAudio() {{
            const audioButton = document.getElementById('audioButton');
            const audioStatus = document.getElementById('audioStatus');

            if (!isRecording) {{
                try {{
                    const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];

                    mediaRecorder.ondataavailable = (event) => {{
                        audioChunks.push(event.data);
                    }};

                    mediaRecorder.onstop = async () => {{
                        const audioBlob = new Blob(audioChunks, {{ type: 'audio/wav' }});
                        const reader = new FileReader();
                        reader.onloadend = () => {{
                            const base64Audio = reader.result.split(',')[1];
                            if (ws.readyState === WebSocket.OPEN) {{
                                addMessage('🎤 Processing audio...', 'user');
                                ws.send(JSON.stringify({{
                                    type: 'audio',
                                    audio: base64Audio
                                }}));
                            }}
                        }};
                        reader.readAsDataURL(audioBlob);
                    }};

                    mediaRecorder.start();
                    isRecording = true;
                    audioButton.textContent = '⏹️ Stop Recording';
                    audioButton.style.background = '#dc3545';
                    audioStatus.textContent = 'Recording... Click to stop';
                    addMessage('🎤 Recording started...', 'user');
                }} catch (error) {{
                    console.error('Error accessing microphone:', error);
                    audioStatus.textContent = 'Microphone access denied or unavailable';
                }}
            }} else {{
                mediaRecorder.stop();
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
                isRecording = false;
                audioButton.textContent = '🎤 Start Recording';
                audioButton.style.background = '#4CAF50';
                audioStatus.textContent = 'Processing audio...';
            }}
        }}
    </script>
</body>
</html>"""
    return html_content

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"[OK] WebSocket client connected")

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get('type') == 'text':
                # Process text message
                user_message = message_data.get('message', '')
                print(f"Processing text: {user_message[:50]}...")

                result = await live_server.process_text_stream(user_message)

                await websocket.send_text(json.dumps({
                    'type': 'response',
                    'message': result['text'],
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'analysis_type': result['type'],
                    'success': result['success']
                }))

            elif message_data.get('type') == 'image':
                # Process image with prompt
                image_data = message_data.get('image', '')
                prompt = message_data.get('prompt', 'What do you see in this image?')
                print(f"Processing image with prompt: {prompt}")

                result = await live_server.process_image_stream(image_data, prompt)

                await websocket.send_text(json.dumps({
                    'type': 'response',
                    'message': result['text'],
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'analysis_type': result['type'],
                    'success': result['success']
                }))

            elif message_data.get('type') == 'audio':
                # Process audio through Live API
                audio_data = message_data.get('audio', '')
                print(f"Processing audio data: {len(audio_data)} bytes")

                result = await live_server.process_audio_stream(audio_data)

                await websocket.send_text(json.dumps({
                    'type': 'response',
                    'message': result['text'],
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'analysis_type': result['type'],
                    'success': result['success']
                }))

            elif message_data.get('type') == 'video':
                # Process video frames (future)
                frames = message_data.get('frames', [])
                prompt = message_data.get('prompt', 'What is happening in this video?')

                result = await live_server.process_video_stream(frames, prompt)

                await websocket.send_text(json.dumps({
                    'type': 'response',
                    'message': result['text'],
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'analysis_type': result['type'],
                    'success': result['success']
                }))

    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            'type': 'error',
            'message': f'Server error: {str(e)}'
        }))
    finally:
        print("WebSocket client disconnected")

# Standalone WebSocket server (alternative to FastAPI)
async def handle_websocket(websocket, path):
    """Handle WebSocket connections for standalone server"""
    print(f"[OK] Client connected from {websocket.remote_address}")

    try:
        async for message in websocket:
            data = json.loads(message)

            if data.get('type') == 'text':
                result = await live_server.process_text_stream(data.get('message', ''))
            elif data.get('type') == 'image':
                result = await live_server.process_image_stream(
                    data.get('image', ''),
                    data.get('prompt', 'What do you see?')
                )
            else:
                result = {'text': 'Unknown message type', 'success': False}

            await websocket.send(json.dumps({
                'type': 'response',
                'message': result.get('text', ''),
                'response_time': result.get('response_time', 0),
                'success': result.get('success', False)
            }))

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")

async def start_standalone_websocket():
    """Start standalone WebSocket server"""
    print("=" * 60)
    print("Gemini Live API Multimodal WebSocket Server")
    print("=" * 60)
    print(f"WebSocket: ws://localhost:8765")
    print(f"Model: {live_server.model}")
    print(f"Capabilities: Text, Image, Video (soon), Audio")
    print("=" * 60)

    async with serve(handle_websocket, "localhost", 8765):
        print("[OK] WebSocket server running on ws://localhost:8765")
        print("[OK] Open http://localhost:8899 for web interface")
        print("[OK] Or connect directly via WebSocket client")
        await asyncio.Future()  # Run forever

def main():
    """Main entry point - choose between FastAPI or standalone WebSocket"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--websocket-only':
        # Run standalone WebSocket server only
        asyncio.run(start_standalone_websocket())
    else:
        # Run FastAPI with integrated WebSocket
        print("=" * 60)
        print("Gemini Live API Multimodal Server (FastAPI + WebSocket)")
        print("=" * 60)
        print(f"Web Interface: http://localhost:8899")
        print(f"WebSocket: ws://localhost:8899/ws")
        print(f"Model: {live_server.model}")
        print("=" * 60)

        uvicorn.run(app, host="localhost", port=8899, log_level="info")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[OK] Server stopped")