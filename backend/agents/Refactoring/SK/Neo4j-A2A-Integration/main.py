"""
Neo4j + A2A Integration Main Application
FastAPI server with enhanced conversation tracking
"""

import asyncio
import logging
import os
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from graph.neo4j_connection import Neo4jConnection, initialize_database, shutdown_database
from agents.neo4j_enhanced_agent import Neo4jEnhancedTravelAgent

# Load environment variables
load_dotenv()

# Create logs directory
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Enhanced logging setup with file output
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = logs_dir / f"neo4j_conversation_{current_time}.log"
json_log_filename = logs_dir / f"neo4j_conversation_{current_time}.json"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)

# Create conversation logger for clean logs
conversation_logger = logging.getLogger('conversation')
conversation_logger.setLevel(logging.INFO)
conversation_handler = logging.FileHandler(logs_dir / f"conversation_{current_time}.log", encoding='utf-8')
conversation_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
conversation_logger.addHandler(conversation_handler)

# Create JSON logger
json_logger = logging.getLogger('json')
json_logger.setLevel(logging.INFO)
json_handler = logging.FileHandler(json_log_filename, encoding='utf-8')
json_handler.setFormatter(logging.Formatter('%(message)s'))
json_logger.addHandler(json_handler)

logger = logging.getLogger(__name__)

# Global variables
enhanced_agent: Optional[Neo4jEnhancedTravelAgent] = None
neo4j_db: Optional[Neo4jConnection] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    global enhanced_agent, neo4j_db
    
    logger.info("Starting Neo4j + A2A Integration Server")
    
    try:
        # Initialize Neo4j connection
        logger.info("Connecting to Neo4j...")
        success = await initialize_database()
        
        if not success:
            logger.error("Failed to connect to Neo4j")
            raise RuntimeError("Neo4j connection failed")
        
        neo4j_db = Neo4jConnection()
        if not neo4j_db.connect():
            raise RuntimeError("Failed to establish Neo4j connection")
        
        # Initialize enhanced agent
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            logger.error("OpenAI API key not found")
            raise RuntimeError("OpenAI API key required")
        
        logger.info("Initializing Enhanced Travel Agent...")
        enhanced_agent = Neo4jEnhancedTravelAgent(
            openai_api_key=openai_api_key,
            neo4j_connection=neo4j_db,
            flight_agent_url=os.getenv("A2A_BASE_URL", "http://localhost:9999")
        )
        
        logger.info("Server initialization complete!")
        
        yield  # Server runs here
        
    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down...")
        if neo4j_db:
            neo4j_db.disconnect()
        await shutdown_database()
        logger.info("Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Neo4j + A2A Integration",
    description="Enhanced A2A agent communication with graph database tracking",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes

@app.get("/", response_class=HTMLResponse)
async def index():
    """Main interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Neo4j + A2A Enhanced Travel Agent</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                max-width: 1200px; 
                margin: 0 auto; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
            }
            .container {
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                color: #4a5568;
            }
            .chat-container {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                height: 500px;
                overflow-y: auto;
                padding: 20px;
                margin-bottom: 20px;
                background: #f7fafc;
            }
            .input-container {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }
            #user-input {
                flex: 1;
                padding: 12px;
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                font-size: 16px;
            }
            button {
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
            }
            button:hover { opacity: 0.9; }
            .message {
                margin: 15px 0;
                padding: 15px;
                border-radius: 8px;
                max-width: 80%;
            }
            .user-message {
                background: #bee3f8;
                margin-left: auto;
                text-align: right;
            }
            .agent-message {
                background: #c6f6d5;
                margin-right: auto;
            }
            .system-message {
                background: #fed7d7;
                text-align: center;
                font-style: italic;
            }
            .analytics-panel {
                margin-top: 30px;
                padding: 20px;
                background: #edf2f7;
                border-radius: 8px;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            .stat-card {
                background: white;
                padding: 15px;
                border-radius: 6px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .loading {
                opacity: 0.6;
                pointer-events: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Neo4j + A2A Enhanced Travel Agent</h1>
                <p>Experience intelligent travel planning with graph-based conversation tracking</p>
            </div>
            
            <div class="chat-container" id="chat-container">
                <div class="message system-message">
                    Welcome! I'm an enhanced travel agent powered by Neo4j graph database tracking. 
                    Ask me about flights, hotels, or trip planning. All our conversations are tracked 
                    for continuous improvement!
                </div>
            </div>
            
            <div class="input-container">
                <input type="text" id="user-input" placeholder="Ask me about your travel needs..." maxlength="500">
                <button onclick="sendMessage()">Send</button>
                <button onclick="endConversation()">End Chat</button>
            </div>
            
            <div class="input-container">
                <input type="text" id="session-id" placeholder="Your name (optional)" value="guest_user">
                <input type="text" id="context-id" placeholder="Conversation ID" value="">
                <button onclick="loadAnalytics()">Show Analytics</button>
                <button onclick="viewGraph()">View Graph</button>
            </div>
            
            <div class="analytics-panel" id="analytics-panel" style="display: none;">
                <h3>Conversation Analytics</h3>
                <div class="stats-grid" id="stats-grid">
                    <!-- Analytics will be loaded here -->
                </div>
            </div>
        </div>

        <script>
            let conversationId = 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            document.getElementById('context-id').value = conversationId;
            
            function addMessage(content, type = 'agent') {
                const chatContainer = document.getElementById('chat-container');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}-message`;
                messageDiv.innerHTML = content.replace(/\\n/g, '<br>');
                chatContainer.appendChild(messageDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            async function sendMessage() {
                const input = document.getElementById('user-input');
                const sessionId = document.getElementById('session-id').value || 'guest_user';
                const contextId = document.getElementById('context-id').value || conversationId;
                const message = input.value.trim();
                
                if (!message) return;
                
                addMessage(`You: ${message}`, 'user');
                input.value = '';
                
                // Show loading
                document.body.classList.add('loading');
                addMessage('🤔 Thinking...', 'system');
                
                try {
                    const formData = new FormData();
                    formData.append('user_input', message);
                    formData.append('context_id', contextId);
                    formData.append('session_id', sessionId);
                    
                    const response = await fetch('/chat', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    // Remove loading message
                    const messages = document.querySelectorAll('.system-message');
                    if (messages.length > 1) {
                        messages[messages.length - 1].remove();
                    }
                    
                    addMessage(`Agent: ${data.response}`, 'agent');
                    
                } catch (error) {
                    addMessage(`Error: ${error.message}`, 'system');
                } finally {
                    document.body.classList.remove('loading');
                }
            }
            
            async function endConversation() {
                const contextId = document.getElementById('context-id').value || conversationId;
                
                try {
                    const response = await fetch(`/end_conversation/${contextId}`, {
                        method: 'POST'
                    });
                    
                    if (response.ok) {
                        addMessage('Conversation ended and saved to graph database. Thank you!', 'system');
                        // Generate new conversation ID
                        conversationId = 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                        document.getElementById('context-id').value = conversationId;
                    }
                } catch (error) {
                    addMessage(`Error ending conversation: ${error.message}`, 'system');
                }
            }
            
            async function loadAnalytics() {
                const contextId = document.getElementById('context-id').value;
                const analyticsPanel = document.getElementById('analytics-panel');
                const statsGrid = document.getElementById('stats-grid');
                
                try {
                    let url = '/analytics';
                    if (contextId) {
                        url += `?context_id=${contextId}`;
                    }
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    let statsHtml = '';
                    
                    if (data.conversation_analytics) {
                        const conv = data.conversation_analytics;
                        statsHtml += `
                            <div class="stat-card">
                                <h4>Messages</h4>
                                <p>${conv.message_count || 0}</p>
                            </div>
                            <div class="stat-card">
                                <h4>Agents Involved</h4>
                                <p>${conv.agents ? conv.agents.length : 0}</p>
                            </div>
                        `;
                    }
                    
                    if (data.overall_analytics) {
                        const overall = data.overall_analytics;
                        statsHtml += `
                            <div class="stat-card">
                                <h4>Total Conversations</h4>
                                <p>${overall.total_conversations || 0}</p>
                            </div>
                            <div class="stat-card">
                                <h4>Total Messages</h4>
                                <p>${overall.total_messages || 0}</p>
                            </div>
                            <div class="stat-card">
                                <h4>Avg Duration</h4>
                                <p>${Math.round(overall.avg_duration || 0)}s</p>
                            </div>
                        `;
                    }
                    
                    statsGrid.innerHTML = statsHtml;
                    analyticsPanel.style.display = 'block';
                    
                } catch (error) {
                    addMessage(`Error loading analytics: ${error.message}`, 'system');
                }
            }
            
            function viewGraph() {
                // This would open Neo4j browser or custom graph visualization
                addMessage('🔗 Graph visualization would open here. Check your Neo4j Browser at http://localhost:7474', 'system');
            }
            
            // Allow Enter key to send message
            document.getElementById('user-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            // Load initial analytics
            setTimeout(loadAnalytics, 1000);
        </script>
    </body>
    </html>
    """
    return html_content

@app.post("/chat")
async def chat_endpoint(
    user_input: str = Form(...),
    context_id: str = Form("default"),
    session_id: str = Form("default_session"),
    user_name: str = Form(None)
):
    """Enhanced chat endpoint with Neo4j tracking"""
    global enhanced_agent
    
    if not enhanced_agent:
        raise HTTPException(status_code=503, detail="Enhanced agent not available")
    
    try:
        # Log user input to conversation log
        conversation_logger.info(f"USER [{session_id}]: {user_input}")
        
        response = await enhanced_agent.chat(
            user_input=user_input,
            context_id=context_id,
            session_id=session_id,
            user_name=user_name
        )
        
        # Log agent response to conversation log
        conversation_logger.info(f"AGENT [{session_id}]: {response}")
        
        # Log to JSON file
        chat_data = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "context_id": context_id,
            "user_input": user_input,
            "agent_response": response,
            "type": "chat_exchange"
        }
        json_logger.info(json.dumps(chat_data, ensure_ascii=False))
        
        return {"response": response, "context_id": context_id}
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/end_conversation/{context_id}")
async def end_conversation_endpoint(context_id: str):
    """End conversation tracking"""
    global enhanced_agent
    
    if not enhanced_agent:
        raise HTTPException(status_code=503, detail="Enhanced agent not available")
    
    try:
        success = await enhanced_agent.end_conversation(context_id, success=True)
        return {"success": success, "context_id": context_id}
        
    except Exception as e:
        logger.error(f"End conversation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics")
async def analytics_endpoint(context_id: Optional[str] = None):
    """Get conversation analytics"""
    global enhanced_agent
    
    if not enhanced_agent:
        raise HTTPException(status_code=503, detail="Enhanced agent not available")
    
    try:
        analytics = {}
        
        if context_id:
            analytics["conversation_analytics"] = await enhanced_agent.get_conversation_analytics(context_id)
        else:
            analytics["overall_analytics"] = await enhanced_agent.get_conversation_analytics()
        
        analytics["agent_performance"] = await enhanced_agent.get_agent_performance()
        analytics["popular_intents"] = await enhanced_agent.get_popular_intents()
        
        return analytics
        
    except Exception as e:
        logger.error(f"Analytics endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global neo4j_db, enhanced_agent
    
    status = {
        "timestamp": datetime.now().isoformat(),
        "neo4j_connected": neo4j_db is not None and neo4j_db._driver is not None,
        "enhanced_agent_available": enhanced_agent is not None,
        "status": "healthy"
    }
    
    if neo4j_db:
        try:
            stats = neo4j_db.get_database_stats()
            status["neo4j_stats"] = stats
        except:
            status["neo4j_connected"] = False
            status["status"] = "degraded"
    
    return status

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8001))
    debug = os.getenv("DEBUG", "true").lower() == "true"
    
    print("Starting Neo4j + A2A Integration Server")
    print(f"Server will be available at: http://{host}:{port}")
    print("Neo4j Browser: http://localhost:7474")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )