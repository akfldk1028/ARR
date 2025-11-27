# Quick Start Guide - Law Domain Agents

Get started with Domain 1 Agent in 5 minutes.

## Prerequisites

1. **Neo4j Database** running on `localhost:7687`
   - Must have law data loaded (run backend pipeline first)
   - See: `D:\Data\11_Backend\01_ARR\backend\law\STEP\README.md`

2. **Python 3.11+** installed

3. **OpenAI API Key** ready

## Step 1: Setup (2 minutes)

```bash
cd D:\Data\11_Backend\01_ARR\agent\law-domain-agents

# Run interactive setup
python setup.py
```

The setup wizard will:
- Create `.env` file from template
- Guide you through configuration
- Test Neo4j connection
- Verify OpenAI API key

## Step 2: Configure Environment (1 minute)

Edit `.env` file:

```bash
# Required settings
NEO4J_PASSWORD=your_neo4j_password
OPENAI_API_KEY=your_openai_api_key

# Optional (defaults are fine)
DOMAIN_1_PORT=8011
LLM_MODEL=gpt-4o
```

## Step 3: Install Dependencies (2 minutes)

```bash
# Using pip
pip install -r requirements.txt

# OR using uv (faster)
uv pip install -r requirements.txt
```

## Step 4: Run Domain 1 Agent (1 second)

```bash
python run_domain_1.py
```

You should see:

```
╔══════════════════════════════════════════════════════════════╗
║ Law Domain Agent - Domain 1                                  ║
║ 도시계획 및 이용                                               ║
╚══════════════════════════════════════════════════════════════╝

Domain ID:    domain_1
Port:         8011
Description:  국토계획법 도시계획 및 이용 관련 법률 조항 검색 전문 에이전트

Endpoints:
  - Agent Card:  http://localhost:8011/.well-known/agent-card.json
  - Messages:    http://localhost:8011/messages
  - Health:      http://localhost:8011/health
  - API Docs:    http://localhost:8011/docs

Starting server...
INFO:     Uvicorn running on http://0.0.0.0:8011 (Press CTRL+C to quit)
```

## Step 5: Test Agent (30 seconds)

Open a NEW terminal:

```bash
cd D:\Data\11_Backend\01_ARR\agent\law-domain-agents
python test_domain_1.py
```

Expected output:

```
╔══════════════════════════════════════════════════════════════╗
║ Testing Domain 1 Agent                                       ║
║ 도시계획 및 이용                                               ║
╚══════════════════════════════════════════════════════════════╝

============================================================
TEST 1: Agent Card Endpoint
============================================================
✓ Test PASSED

============================================================
TEST 2: Health Endpoint
============================================================
✓ Test PASSED

============================================================
TEST 3: Message Endpoint (A2A Protocol)
============================================================
✓ Test PASSED

============================================================
TEST SUMMARY
============================================================
✓ PASS - Agent Card
✓ PASS - Health
✓ PASS - Message

Total: 3/3 tests passed
```

## Step 6: Explore API (1 minute)

### Browser Interface

Open in browser:
```
http://localhost:8011/docs
```

Explore the interactive Swagger UI.

### Command Line Tests

**Test 1: Agent Card**
```bash
curl http://localhost:8011/.well-known/agent-card.json
```

**Test 2: Health Check**
```bash
curl http://localhost:8011/health
```

**Test 3: Send Message (A2A Protocol)**
```bash
curl -X POST http://localhost:8011/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "test-001",
        "contextId": "test-context",
        "role": "user",
        "parts": [
          {"kind": "text", "text": "17조에 대해 알려주세요"}
        ]
      }
    },
    "id": "req-001"
  }'
```

## Common Issues

### Issue 1: Neo4j Connection Failed

**Error**: `Neo4j connection failed`

**Solution**:
1. Check Neo4j is running: Open `http://localhost:7474`
2. Verify credentials in `.env`
3. Test connection manually:
   ```bash
   python -c "from shared.neo4j_client import get_neo4j_client; get_neo4j_client()"
   ```

### Issue 2: OpenAI API Error

**Error**: `OpenAI API test failed`

**Solution**:
1. Verify API key in `.env`
2. Check API key is valid at https://platform.openai.com/api-keys
3. Test manually:
   ```bash
   python -c "from shared.openai_client import get_openai_client; get_openai_client()"
   ```

### Issue 3: Import Errors

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
pip install -r requirements.txt
```

### Issue 4: Port Already in Use

**Error**: `Address already in use`

**Solution**:
1. Change port in `.env`:
   ```bash
   DOMAIN_1_PORT=8012
   ```
2. Or kill existing process:
   ```bash
   # Windows
   netstat -ano | findstr :8011
   taskkill /PID <PID> /F
   ```

## Project Structure

```
law-domain-agents/
├── .env                    # Your configuration (created by setup)
├── run_domain_1.py         # Start agent
├── test_domain_1.py        # Test agent
├── setup.py                # Setup wizard
│
├── domain-1-agent/         # Domain 1 implementation
│   ├── server.py           # FastAPI server
│   ├── graph.py            # LangGraph workflow
│   ├── domain_logic.py     # Search logic
│   └── config.py           # Configuration
│
└── shared/                 # Shared utilities
    ├── neo4j_client.py     # Neo4j connection
    └── openai_client.py    # OpenAI connection
```

## Next Steps

### 1. Enhance Search Logic

Port advanced search from backend:
- KR-SBERT semantic search
- RNE graph expansion
- Cross-law references

See: `domain-1-agent/domain_logic.py`

### 2. Add More Domain Agents

Copy Domain 1 structure:
```bash
cp -r domain-1-agent/ domain-2-agent/
# Update config.py with Domain 2 settings
```

### 3. Implement QueryCoordinator

See: `coordinator/README.md`

### 4. Deploy to Production

Consider:
- Docker containerization
- Load balancing
- Monitoring
- Logging aggregation

## Resources

### Documentation
- `README.md` - Full project documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `coordinator/README.md` - Coordinator design

### Backend Integration
- `D:\Data\11_Backend\01_ARR\backend\START_HERE.md`
- `D:\Data\11_Backend\01_ARR\backend\LAW_SEARCH_SYSTEM_ARCHITECTURE.md`
- `D:\Data\11_Backend\01_ARR\backend\law\STEP\README.md`

### A2A Protocol
- Official Spec: https://a2a.dev
- Reference Implementation: `D:\Data\11_Backend\01_ARR\agent\a2a\`

## Support

For issues or questions:
1. Check `IMPLEMENTATION_SUMMARY.md` for technical details
2. Review backend documentation
3. Test with `test_domain_1.py`
4. Check logs in terminal output

---

**Total Time**: ~5 minutes from zero to running agent

**Status**: Ready for testing and enhancement
