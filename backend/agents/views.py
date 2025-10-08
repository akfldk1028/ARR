"""
Django Views for Agents App
Includes Agent Card functionality adapted from SK system
"""

import asyncio
import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from asgiref.sync import sync_to_async

from django.conf import settings

from .models import Agent
from .worker_agents import get_worker_for_slug

class AgentCardView(View):
    """
    Agent Card endpoint - compatible with A2A standard
    Returns agent information in standard format
    """

    def get(self, request, agent_slug=None):
        if agent_slug:
            # Get specific agent
            agent = get_object_or_404(Agent, slug=agent_slug, status='active')

            # A2A Protocol compliant agent card
            card_data = {
                "name": agent.name,
                "description": agent.description,
                "version": "1.0.0",
                "agent_type": agent.agent_type,
                "capabilities": agent.capabilities,
                "protocols": ["a2a", "json-rpc-2.0"],
                "transport": ["http", "https"],
                "skills": [
                    {
                        "name": "chat",
                        "description": "General conversation and task assistance",
                        "type": "chat_completion",
                        "input_types": ["text"],
                        "output_types": ["text"]
                    },
                    {
                        "name": "task_assistance",
                        "description": "Help with various tasks",
                        "type": "task_completion",
                        "input_types": ["text"],
                        "output_types": ["text"]
                    }
                ],
                "endpoints": {
                    "chat": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/chat/",
                    "status": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/status/",
                    "a2a": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/a2a/",
                    "jsonrpc": f"{settings.A2A_BASE_URL}/agents/{agent.slug}/chat/",  # A2A compatible endpoint
                },
                "authentication": {
                    "type": "none",  # Could be "bearer", "api_key", etc.
                    "description": "No authentication required for demo"
                },
                "rate_limits": {
                    "requests_per_minute": agent.rate_limit_per_minute,
                    "concurrent_sessions": agent.max_concurrent_sessions
                },
                "metadata": {
                    "organization": agent.organization.name if agent.organization else None,
                    "created_by": agent.created_by.username if agent.created_by else None,
                    "tags": [tag.name for tag in agent.tags.all()],
                    "model": agent.model_name,
                    "framework": "langgraph",
                    "created_at": agent.created_at.isoformat(),
                    "updated_at": agent.updated_at.isoformat()
                }
            }

            return JsonResponse(card_data)
        else:
            # List all active agents
            agents = Agent.objects.filter(status='active')
            agents_list = []

            for agent in agents:
                agents_list.append({
                    "slug": agent.slug,
                    "name": agent.name,
                    "description": agent.description,
                    "agent_type": agent.agent_type,
                    "capabilities": agent.capabilities,
                    "card_url": f"/.well-known/agent-card/{agent.slug}.json"
                })

            return JsonResponse({"agents": agents_list})

class WellKnownAgentCardView(View):
    """
    Standard A2A agent card endpoint
    /.well-known/agent-card.json or /.well-known/agent-card/{slug}.json
    """

    def get(self, request, agent_slug=None):
        # Delegate to AgentCardView
        card_view = AgentCardView()
        return card_view.get(request, agent_slug)

class AgentStatusView(View):
    """
    Agent status endpoint
    """

    def get(self, request, agent_slug):
        agent = get_object_or_404(Agent, slug=agent_slug)

        status_data = {
            "agent_slug": agent.slug,
            "status": agent.status,
            "active_sessions": 0,  # TODO: implement session tracking
            "max_concurrent_sessions": agent.max_concurrent_sessions,
            "rate_limit_per_minute": agent.rate_limit_per_minute,
            "last_activity": None,  # TODO: implement activity tracking
            "health": "healthy" if agent.status == 'active' else "inactive"
        }

        return JsonResponse(status_data)

class AgentListView(View):
    """
    List all agents with filtering
    """

    def get(self, request):
        agents = Agent.objects.all()

        # Filter by status
        status = request.GET.get('status')
        if status:
            agents = agents.filter(status=status)

        # Filter by agent_type
        agent_type = request.GET.get('type')
        if agent_type:
            agents = agents.filter(agent_type=agent_type)

        # Filter by organization
        org = request.GET.get('organization')
        if org:
            agents = agents.filter(organization__slug=org)

        agents_data = []
        for agent in agents:
            agents_data.append({
                "id": agent.id,
                "slug": agent.slug,
                "name": agent.name,
                "description": agent.description,
                "agent_type": agent.agent_type,
                "model_name": agent.model_name,
                "status": agent.status,
                "capabilities": agent.capabilities,
                "card_url": f"/.well-known/agent-card/{agent.slug}.json",
                "created_at": agent.created_at.isoformat(),
                "updated_at": agent.updated_at.isoformat()
            })

        return JsonResponse({"agents": agents_data, "count": len(agents_data)})

@method_decorator(csrf_exempt, name='dispatch')
class AgentChatView(View):
    """
    LangGraph Agent Chat endpoint
    """

    def post(self, request, agent_slug):
        """Handle chat requests with LangGraph agent"""

        # Make the view async-compatible
        async def _handle_async():
            try:
                # Parse request data - handle both JSON-RPC 2.0 and regular JSON
                if request.content_type == 'application/json':
                    try:
                        # Try UTF-8 first, then other encodings
                        body_text = request.body.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            # Try with error handling
                            body_text = request.body.decode('utf-8', errors='replace')
                        except:
                            # Fallback to latin-1
                            body_text = request.body.decode('latin-1')

                    data = json.loads(body_text)

                    # Check if this is a JSON-RPC 2.0 request (A2A format)
                    if 'jsonrpc' in data and 'method' in data:
                        # A2A JSON-RPC 2.0 format
                        if data.get('method') == 'message/send':
                            message_data = data.get('params', {}).get('message', {})
                            parts = message_data.get('parts', [])
                            user_input = parts[0].get('text', '') if parts else ''
                            context_id = message_data.get('contextId', f'a2a_chat_{agent_slug}')
                            session_id = f"a2a_session_{data.get('id', 'default')}"
                            user_name = 'a2a_agent'
                            request_id = data.get('id')
                            is_a2a_request = True
                        else:
                            return JsonResponse({
                                "jsonrpc": "2.0",
                                "error": {"code": -32601, "message": "Method not found"},
                                "id": data.get('id')
                            }, status=400)
                    else:
                        # Regular JSON format
                        user_input = data.get('message', '').strip()
                        context_id = data.get('context_id', f'web_chat_{agent_slug}')
                        session_id = data.get('session_id', 'web_session')
                        user_name = data.get('user_name', 'anonymous')
                        is_a2a_request = False
                else:
                    # Handle form data
                    data = dict(request.POST.items())
                    user_input = data.get('message', '').strip()
                    context_id = data.get('context_id', f'web_chat_{agent_slug}')
                    session_id = data.get('session_id', 'web_session')
                    user_name = data.get('user_name', 'anonymous')
                    is_a2a_request = False

                if not user_input:
                    return JsonResponse({
                        'error': 'Message is required',
                        'success': False
                    }, status=400)

                # Get Worker agent
                agent = await get_worker_for_slug(agent_slug)
                if not agent:
                    return JsonResponse({
                        'error': f'Agent {agent_slug} not found or inactive',
                        'success': False
                    }, status=404)

                # Get response from agent
                response = await agent.chat(
                    user_input=user_input,
                    context_id=context_id,
                    session_id=session_id,
                    user_name=user_name
                )

                # Check for delegation marker and clean it up
                delegation_info = None
                specialist_response = None

                if response.startswith('[DELEGATION_OCCURRED:'):
                    # Parse delegation marker
                    first_end = response.find(']')
                    if first_end != -1:
                        delegation_part = response[:first_end+1]
                        specialist_agent = delegation_part.split(':')[1].split(']')[0]
                        delegation_info = specialist_agent

                        # Check for specialist response marker
                        remaining = response[first_end+1:]
                        if remaining.startswith('[SPECIALIST_RESPONSE:'):
                            second_end = remaining.find('] ')
                            if second_end != -1:
                                specialist_part = remaining[:second_end+1]
                                specialist_response = specialist_part.split(':', 1)[1].split(']')[0]
                                response = remaining[second_end+2:]  # Remove both markers
                            else:
                                response = remaining[2:] if remaining.startswith(' ') else remaining
                        else:
                            response = remaining[2:] if remaining.startswith(' ') else remaining

                # Return A2A JSON-RPC format if it's an A2A request
                if is_a2a_request:
                    return JsonResponse({
                        "jsonrpc": "2.0",
                        "result": {
                            "parts": [{"text": response}],
                            "messageId": str(uuid4()),
                            "role": "assistant"
                        },
                        "id": request_id
                    })
                else:
                    json_response = {
                        'response': response,
                        'context_id': context_id,
                        'session_id': session_id,
                        'agent': agent_slug,
                        'success': True
                    }

                    # Add delegation info if present
                    if delegation_info:
                        json_response['delegation'] = {
                            'occurred': True,
                            'specialist_agent': delegation_info
                        }
                        if specialist_response:
                            json_response['delegation']['specialist_response'] = specialist_response

                    return JsonResponse(json_response)

            except json.JSONDecodeError:
                return JsonResponse({
                    'error': 'Invalid JSON data',
                    'success': False
                }, status=400)

            except Exception as e:
                return JsonResponse({
                    'error': f'Internal server error: {str(e)}',
                    'success': False
                }, status=500)

        # Use Django's async_to_sync for proper async handling
        try:
            from asgiref.sync import async_to_sync
            result = async_to_sync(_handle_async)()
            return result
        except Exception as e:
            return JsonResponse({
                'error': f'Processing error: {str(e)}',
                'success': False
            }, status=500)

    def get(self, request, agent_slug):
        """Show chat interface"""
        try:
            # Check if agent exists
            agent = get_object_or_404(Agent, slug=agent_slug, status='active')

            # Return simple chat interface
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Chat with {agent.name}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .chat-container {{ border: 1px solid #ddd; height: 400px; overflow-y: auto; padding: 10px; margin: 20px 0; background: #f9f9f9; }}
                    .message {{ margin: 10px 0; padding: 10px; border-radius: 8px; }}
                    .user-message {{ background: #e3f2fd; text-align: right; }}
                    .agent-message {{ background: #e8f5e8; }}
                    .input-area {{ display: flex; gap: 10px; }}
                    input {{ flex: 1; padding: 10px; }}
                    button {{ padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }}
                    button:hover {{ background: #0056b3; }}
                </style>
            </head>
            <body>
                <h1>Chat with {agent.name}</h1>
                <p>{agent.description}</p>

                <div class="chat-container" id="chat-container">
                    <div class="message agent-message">
                        Hello! I'm {agent.name}. How can I help you today?
                    </div>
                </div>

                <div class="input-area">
                    <input type="text" id="message-input" placeholder="Type your message..." maxlength="500">
                    <button onclick="sendMessage()">Send</button>
                </div>

                <script>
                    const contextId = 'web_chat_' + Date.now();

                    function addMessage(content, isUser) {{
                        const chatContainer = document.getElementById('chat-container');
                        const messageDiv = document.createElement('div');
                        messageDiv.className = 'message ' + (isUser ? 'user-message' : 'agent-message');
                        messageDiv.textContent = (isUser ? 'You: ' : '{agent.name}: ') + content;
                        chatContainer.appendChild(messageDiv);
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }}

                    async function sendMessage() {{
                        const input = document.getElementById('message-input');
                        const message = input.value.trim();

                        if (!message) return;

                        addMessage(message, true);
                        input.value = '';

                        try {{
                            const response = await fetch('/agents/{agent_slug}/chat/', {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json',
                                }},
                                body: JSON.stringify({{
                                    message: message,
                                    context_id: contextId,
                                    session_id: 'web_session',
                                    user_name: 'web_user'
                                }})
                            }});

                            const data = await response.json();

                            if (data.success) {{
                                addMessage(data.response, false);
                            }} else {{
                                addMessage('Error: ' + data.error, false);
                            }}
                        }} catch (error) {{
                            addMessage('Connection error: ' + error.message, false);
                        }}
                    }}

                    // Allow Enter key to send message
                    document.getElementById('message-input').addEventListener('keypress', function(e) {{
                        if (e.key === 'Enter') {{
                            sendMessage();
                        }}
                    }});
                </script>
            </body>
            </html>
            """

            from django.http import HttpResponse
            return HttpResponse(html_content)

        except Exception as e:
            return JsonResponse({
                'error': f'Error loading chat interface: {str(e)}',
                'success': False
            }, status=500)

class WorkerTestView(View):
    """Worker-to-Worker Communication Test Interface"""

    def get(self, request):
        """Show worker communication test interface"""
        try:
            # Check if we have active agents
            agents = Agent.objects.filter(status='active').count()
            if agents < 2:
                return HttpResponse("""
                    <h1>Worker Test Not Available</h1>
                    <p>You need at least 2 active agents to test worker communication.</p>
                    <p>Run: <code>python manage.py create_test_agent</code> and <code>python manage.py create_second_agent</code></p>
                """, status=503)

            # Render the worker test template
            return render(request, 'agents/worker_test.html')

        except Exception as e:
            return HttpResponse(f"Error loading worker test: {str(e)}", status=500)

@method_decorator(csrf_exempt, name='dispatch')
class WorkerCommunicationTestView(View):
    """Test direct worker-to-worker communication"""

    def post(self, request):
        """Test A2A communication between workers"""
        try:
            data = json.loads(request.body.decode('utf-8'))
            message = data.get('message', 'Test worker communication')
            source_agent = data.get('source_agent', 'test-agent')
            target_agent = data.get('target_agent', 'flight-specialist')

            # Get source worker
            from .worker_agents import get_worker_for_slug

            async def _test_communication():
                source_worker = await get_worker_for_slug(source_agent)
                if not source_worker:
                    return {'success': False, 'error': f'Source agent {source_agent} not found'}

                # Test communication
                response = await source_worker.communicate_with_agent(
                    target_agent_slug=target_agent,
                    message=message,
                    context_id=f"direct_test_{uuid4()}"
                )

                if response:
                    return {'success': True, 'response': response}
                else:
                    return {'success': False, 'error': 'No response from target agent'}

            # Use Django's async_to_sync for proper async handling
            try:
                from asgiref.sync import async_to_sync
                result = async_to_sync(_test_communication)()
                return JsonResponse(result)
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Communication test error: {str(e)}'
                }, status=500)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)