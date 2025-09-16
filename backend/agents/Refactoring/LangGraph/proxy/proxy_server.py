#!/usr/bin/env python3
"""
CORS Proxy Server for A2A Agent Monitoring
This server acts as a proxy to bypass CORS issues when accessing agents from the browser
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import requests
import json
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Agent configurations
AGENTS = {
    "currency": {"name": "Currency Agent", "url": "http://localhost:10000"},
    "hello": {"name": "Hello World Agent", "url": "http://localhost:9999"}
}

@app.route('/')
def index():
    """Serve the monitoring page"""
    monitor_file = os.path.join(os.path.dirname(__file__), 'web_monitor_cors.html')
    if os.path.exists(monitor_file):
        return send_file(monitor_file)
    return "Monitor page not found", 404

@app.route('/docs/<path:filename>')
def serve_docs(filename):
    """Serve files from docs directory"""
    file_path = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return f"File {filename} not found", 404

@app.route('/api/agents')
def get_agents():
    """Get list of configured agents"""
    return jsonify(AGENTS)

@app.route('/api/agent/<agent_id>/card')
def get_agent_card(agent_id):
    """Get agent card for a specific agent"""
    if agent_id not in AGENTS:
        return jsonify({"error": "Agent not found"}), 404

    agent = AGENTS[agent_id]
    try:
        response = requests.get(f"{agent['url']}/.well-known/agent-card.json", timeout=5)
        if response.status_code == 200:
            return jsonify({
                "status": "active",
                "card": response.json(),
                "agent": agent
            })
        else:
            return jsonify({
                "status": "inactive",
                "error": f"HTTP {response.status_code}",
                "agent": agent
            })
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "inactive",
            "error": str(e),
            "agent": agent
        })

@app.route('/api/agent/<agent_id>/message', methods=['POST'])
def send_message(agent_id):
    """Send a message to an agent"""
    if agent_id not in AGENTS:
        return jsonify({"error": "Agent not found"}), 404

    agent = AGENTS[agent_id]
    message_text = request.json.get('message', 'Hello')

    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": f"web-{request.json.get('id', 'test')}",
                "parts": [
                    {
                        "kind": "text",
                        "text": message_text
                    }
                ],
                "role": "user"
            }
        },
        "id": request.json.get('id', 'test')
    }

    try:
        response = requests.post(
            agent['url'],
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return jsonify({
            "status": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text
        })
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/test')
def test_all_agents():
    """Test all configured agents"""
    results = {}
    for agent_id, agent in AGENTS.items():
        try:
            # Test agent card
            response = requests.get(f"{agent['url']}/.well-known/agent-card.json", timeout=5)
            if response.status_code == 200:
                card = response.json()
                results[agent_id] = {
                    "name": agent['name'],
                    "status": "active",
                    "card": {
                        "name": card.get('name'),
                        "description": card.get('description'),
                        "version": card.get('version'),
                        "skills": len(card.get('skills', []))
                    }
                }
            else:
                results[agent_id] = {
                    "name": agent['name'],
                    "status": "inactive",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            results[agent_id] = {
                "name": agent['name'],
                "status": "inactive",
                "error": str(e)
            }

    return jsonify(results)

if __name__ == '__main__':
    print("Starting A2A CORS Proxy Server...")
    print("Server URL: http://localhost:5000")
    print("API Endpoints:")
    print("  - GET  /api/agents - List all agents")
    print("  - GET  /api/agent/<id>/card - Get agent card")
    print("  - POST /api/agent/<id>/message - Send message to agent")
    print("  - GET  /api/test - Test all agents")
    print("\nPress Ctrl+C to stop")

    app.run(host='0.0.0.0', port=5000, debug=True)