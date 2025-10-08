"""
A2A Voice WebSocket Server - Real-time voice communication with A2A agents
Integrates Gemini Live API with A2A agent system for voice conversations
"""

import asyncio
import json
import logging
import base64
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from .a2a_voice_service import get_voice_service
from ..worker_agents.worker_manager import WorkerAgentManager

logger = logging.getLogger(__name__)

app = FastAPI(title="A2A Voice WebSocket Server")

class VoiceConnectionManager:
    """Manages WebSocket connections for voice conversations"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.voice_sessions: Dict[str, Dict[str, Any]] = {}
        self.voice_service = get_voice_service()
        self.worker_manager = WorkerAgentManager()

    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f"Voice connection established: {connection_id}")

    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.voice_sessions:
            del self.voice_sessions[connection_id]
        logger.info(f"Voice connection closed: {connection_id}")

    async def send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                self.disconnect(connection_id)

    async def process_voice_message(self, connection_id: str, data: Dict[str, Any]):
        """Process incoming voice message"""
        try:
            message_type = data.get('type')

            if message_type == 'start_session':
                # Start new voice session with specified agent
                agent_slug = data.get('agent_slug', 'general-worker')
                context_id = data.get('context_id', f"voice_{connection_id}")

                # Create Live API session
                session_info = await self.voice_service.create_live_session(agent_slug, context_id)
                self.voice_sessions[connection_id] = session_info

                # Send session started confirmation
                await self.send_message(connection_id, {
                    'type': 'session_started',
                    'agent_slug': agent_slug,
                    'agent_name': session_info['agent_name'],
                    'voice_description': session_info['voice_config']['voice_description'],
                    'audio_config': session_info['audio_config']
                })

            elif message_type == 'voice_input':
                # Process voice input
                if connection_id not in self.voice_sessions:
                    await self.send_message(connection_id, {
                        'type': 'error',
                        'message': 'No active voice session. Start session first.'
                    })
                    return

                # Decode audio data
                audio_data_b64 = data.get('audio_data', '')
                if not audio_data_b64:
                    await self.send_message(connection_id, {
                        'type': 'error',
                        'message': 'No audio data provided'
                    })
                    return

                audio_data = base64.b64decode(audio_data_b64)
                session_info = self.voice_sessions[connection_id]

                # Process through Live API
                result = await self.voice_service.process_voice_with_live_api(
                    session_info=session_info,
                    audio_data=audio_data,
                    session_id=f"voice_session_{connection_id}"
                )

                if result['success']:
                    # Send voice response
                    response_message = {
                        'type': 'voice_response',
                        'text_response': result['text_response'],
                        'agent_slug': result['agent_slug'],
                        'agent_name': result.get('agent_name', ''),
                        'response_time': result['response_time']
                    }

                    # Include audio response if available
                    if result.get('audio_response'):
                        response_message['audio_response'] = base64.b64encode(result['audio_response']).decode('utf-8')

                    # Handle delegation
                    if result.get('delegation_occurred'):
                        response_message.update({
                            'delegation_occurred': True,
                            'delegated_to': result['delegated_to'],
                            'specialist_response': result['specialist_response']
                        })

                        # Auto-switch to delegated agent
                        new_agent_slug = result['delegated_to']
                        new_session_info = await self.voice_service.create_live_session(
                            new_agent_slug, session_info['context_id']
                        )
                        self.voice_sessions[connection_id] = new_session_info

                        response_message['new_agent_slug'] = new_agent_slug
                        response_message['new_agent_name'] = new_session_info['agent_name']

                    await self.send_message(connection_id, response_message)
                else:
                    await self.send_message(connection_id, {
                        'type': 'error',
                        'message': result.get('error', 'Voice processing failed')
                    })

            elif message_type == 'text_input':
                # Process text input (alternative to voice)
                if connection_id not in self.voice_sessions:
                    await self.send_message(connection_id, {
                        'type': 'error',
                        'message': 'No active voice session. Start session first.'
                    })
                    return

                text_message = data.get('text', '')
                if not text_message:
                    await self.send_message(connection_id, {
                        'type': 'error',
                        'message': 'No text provided'
                    })
                    return

                session_info = self.voice_sessions[connection_id]

                # Process text through voice system (will generate voice response)
                text_audio = text_message.encode('utf-8')  # Simple conversion for demo
                result = await self.voice_service.process_voice_with_live_api(
                    session_info=session_info,
                    audio_data=text_audio,
                    session_id=f"voice_session_{connection_id}"
                )

                # Send response similar to voice input
                if result['success']:
                    await self.send_message(connection_id, {
                        'type': 'text_response',
                        'text_response': result['text_response'],
                        'agent_slug': result['agent_slug'],
                        'delegation_occurred': result.get('delegation_occurred', False)
                    })

            elif message_type == 'switch_agent':
                # Switch to different agent
                new_agent_slug = data.get('agent_slug')
                if not new_agent_slug:
                    await self.send_message(connection_id, {
                        'type': 'error',
                        'message': 'Agent slug required for switching'
                    })
                    return

                context_id = self.voice_sessions.get(connection_id, {}).get('context_id', f"voice_{connection_id}")
                new_session_info = await self.voice_service.create_live_session(new_agent_slug, context_id)
                self.voice_sessions[connection_id] = new_session_info

                await self.send_message(connection_id, {
                    'type': 'agent_switched',
                    'agent_slug': new_agent_slug,
                    'agent_name': new_session_info['agent_name'],
                    'voice_description': new_session_info['voice_config']['voice_description']
                })

            elif message_type == 'list_agents':
                # Send list of available agents
                voices = self.voice_service.list_available_voices()

                # Create agent list from voice configurations
                agent_list = []
                for agent_slug, voice_info in voices.items():
                    agent_list.append({
                        'slug': agent_slug,
                        'name': voice_info.get('agent_name', agent_slug.replace('-', ' ').title()),
                        'description': f"Agent with {voice_info['voice_config']['voice_description']}",
                        'voice_description': voice_info['voice_config']['voice_description'],
                        'capabilities': voice_info.get('capabilities', ['voice', 'text'])
                    })

                await self.send_message(connection_id, {
                    'type': 'agents_list',
                    'agents': agent_list
                })

        except Exception as e:
            logger.error(f"Error processing voice message for {connection_id}: {e}")
            await self.send_message(connection_id, {
                'type': 'error',
                'message': f'Processing error: {str(e)}'
            })

# Global connection manager
voice_manager = VoiceConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_voice_interface():
    """Voice interface HTML page"""
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>A2A Voice Chat</title>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', sans-serif;
            max-width: 1000px;
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
        .chat {{
            border: 2px solid #e0e0e0;
            height: 400px;
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
        }}
        .user {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin-left: auto;
            text-align: right;
        }}
        .agent {{
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
        button {{
            padding: 12px 20px;
            margin: 5px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
            font-weight: bold;
        }}
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }}
        input {{
            padding: 12px 20px;
            margin: 5px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            width: 60%;
        }}
        .status {{
            padding: 10px 20px;
            margin: 10px 0;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
        }}
        .connected {{
            background: #d4edda;
            color: #155724;
        }}
        .disconnected {{
            background: #f8d7da;
            color: #721c24;
        }}
        .agent-selector {{
            margin: 10px 0;
        }}
        select {{
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #ccc;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>A2A Voice Chat with Gemini Live API</h1>
            <p>Real-time voice conversations with different AI agents</p>
        </div>

        <div id="status" class="status disconnected">Connecting...</div>

        <div class="agent-selector">
            <label>Current Agent: </label>
            <select id="agentSelect">
                <option value="general-worker">General Assistant</option>
                <option value="flight-specialist">Flight Specialist</option>
                <option value="hotel-specialist">Hotel Specialist</option>
                <option value="travel-assistant">Travel Assistant</option>
            </select>
            <button onclick="switchAgent()">Switch Agent</button>
            <button onclick="startSession()">Start Session</button>
        </div>

        <div id="chat" class="chat"></div>

        <div class="controls">
            <div>
                <button id="recordButton" onclick="toggleRecording()">🎤 Start Recording</button>
                <button onclick="listAgents()">List Agents</button>
                <button onclick="clearChat()">Clear Chat</button>
            </div>
            <div style="margin-top: 10px;">
                <input type="text" id="textInput" placeholder="Type message..." onkeypress="if(event.key==='Enter') sendText()">
                <button onclick="sendText()">Send Text</button>
            </div>
        </div>
    </div>

    <script>
        const ws = new WebSocket('ws://localhost:8004/voice');
        const chat = document.getElementById('chat');
        const status = document.getElementById('status');
        let isRecording = false;
        let mediaRecorder;
        let audioChunks = [];

        ws.onopen = () => {{
            status.textContent = 'Connected to A2A Voice Server';
            status.className = 'status connected';
            addMessage('Connected to A2A Voice Server!', 'agent');
        }};

        ws.onclose = () => {{
            status.textContent = 'Disconnected';
            status.className = 'status disconnected';
        }};

        ws.onmessage = (event) => {{
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        }};

        function handleServerMessage(data) {{
            if (data.type === 'session_started') {{
                addMessage(`Session started with ${{data.agent_name}} (${{data.voice_description}})`, 'agent');
            }} else if (data.type === 'voice_response') {{
                let msg = `${{data.agent_name}}: ${{data.text_response}}`;
                if (data.delegation_occurred) {{
                    msg += ` [Delegated to ${{data.delegated_to}}]`;
                }}
                addMessage(msg, 'agent');

                // Play audio response if available
                if (data.audio_response) {{
                    playAudioResponse(data.audio_response);
                }}
            }} else if (data.type === 'agent_switched') {{
                addMessage(`Switched to ${{data.agent_name}} (${{data.voice_description}})`, 'agent');
            }} else if (data.type === 'agents_list') {{
                displayAgentsList(data.agents);
            }} else if (data.type === 'error') {{
                addMessage(`Error: ${{data.message}}`, 'agent');
            }}
        }}

        function addMessage(msg, sender) {{
            const div = document.createElement('div');
            div.className = 'message ' + sender;
            div.textContent = msg;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }}

        function startSession() {{
            const agentSlug = document.getElementById('agentSelect').value;
            ws.send(JSON.stringify({{
                type: 'start_session',
                agent_slug: agentSlug,
                context_id: 'voice_' + Date.now()
            }}));
        }}

        function switchAgent() {{
            const agentSlug = document.getElementById('agentSelect').value;
            ws.send(JSON.stringify({{
                type: 'switch_agent',
                agent_slug: agentSlug
            }}));
        }}

        async function toggleRecording() {{
            const button = document.getElementById('recordButton');

            if (!isRecording) {{
                try {{
                    const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];

                    mediaRecorder.ondataavailable = (event) => {{
                        audioChunks.push(event.data);
                    }};

                    mediaRecorder.onstop = () => {{
                        const audioBlob = new Blob(audioChunks, {{ type: 'audio/wav' }});
                        const reader = new FileReader();
                        reader.onloadend = () => {{
                            const base64Audio = reader.result.split(',')[1];
                            ws.send(JSON.stringify({{
                                type: 'voice_input',
                                audio_data: base64Audio
                            }}));
                        }};
                        reader.readAsDataURL(audioBlob);
                    }};

                    mediaRecorder.start();
                    isRecording = true;
                    button.textContent = '⏹️ Stop Recording';
                    addMessage('🎤 Recording...', 'user');
                }} catch (error) {{
                    alert('Microphone access denied or unavailable');
                }}
            }} else {{
                mediaRecorder.stop();
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
                isRecording = false;
                button.textContent = '🎤 Start Recording';
            }}
        }}

        function sendText() {{
            const input = document.getElementById('textInput');
            const text = input.value.trim();
            if (text) {{
                addMessage(text, 'user');
                ws.send(JSON.stringify({{
                    type: 'text_input',
                    text: text
                }}));
                input.value = '';
            }}
        }}

        function listAgents() {{
            ws.send(JSON.stringify({{ type: 'list_agents' }}));
        }}

        function clearChat() {{
            chat.innerHTML = '';
            addMessage('Chat cleared. Ready for voice conversation!', 'agent');
        }}

        function playAudioResponse(base64Audio) {{
            const audio = new Audio('data:audio/wav;base64,' + base64Audio);
            audio.play();
        }}

        function displayAgentsList(agents) {{
            let msg = 'Available Agents:\\n';
            agents.forEach(agent => {{
                msg += `- ${{agent.name}}: ${{agent.voice_description}}\\n`;
            }});
            addMessage(msg, 'agent');
        }}
    </script>
</body>
</html>"""
    return html_content

@app.websocket("/voice")
async def voice_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for voice communication"""
    connection_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(websocket)}"

    await voice_manager.connect(websocket, connection_id)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            await voice_manager.process_voice_message(connection_id, message_data)

    except WebSocketDisconnect:
        voice_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        voice_manager.disconnect(connection_id)

def run_voice_server(host: str = "localhost", port: int = 8004):
    """Run the A2A Voice WebSocket server"""
    logger.info("=" * 60)
    logger.info("A2A Voice WebSocket Server with Gemini Live API")
    logger.info("=" * 60)
    logger.info(f"Web Interface: http://{host}:{port}")
    logger.info(f"WebSocket: ws://{host}:{port}/voice")
    logger.info("Supported agents: general-worker, flight-specialist, hotel-specialist, travel-assistant")
    logger.info("=" * 60)

    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_voice_server()