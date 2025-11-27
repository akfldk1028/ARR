"""
LangGraph workflow for Domain 1: 도시계획 및 이용

Based on: agent/a2a/langraph_agent/graph.py
Integrated with: backend/agents/law/domain_agent.py search logic
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from domain_logic import Domain1SearchLogic
from config import config
import logging

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize LLM
llm = init_chat_model(f"openai:{config.LLM_MODEL}", temperature=config.LLM_TEMPERATURE)

# Initialize search logic
search_logic = Domain1SearchLogic()


class Domain1State(MessagesState):
    """
    State for Domain 1 agent

    Extends MessagesState to maintain conversation history
    plus domain-specific metadata
    """
    domain_id: str = config.DOMAIN_ID
    domain_name: str = config.DOMAIN_NAME
    search_results: list = []


def search_domain_1(state: Domain1State) -> dict:
    """
    Main search logic for Domain 1

    Steps:
    1. Extract query from last message
    2. Search Neo4j for relevant articles
    3. Format results for LLM
    4. Generate response with LLM

    Args:
        state: Current graph state

    Returns:
        Updated state with new messages and search results
    """
    logger.info(f"Executing search_domain_1 node")

    # Get latest user message
    messages = state.get("messages", [])
    if not messages:
        return {"messages": [AIMessage(content="메시지가 없습니다.")]}

    last_message = messages[-1]
    query = last_message.content if hasattr(last_message, 'content') else str(last_message)

    logger.info(f"Query: {query}")

    # Execute search
    try:
        search_results = search_logic.search_by_query(query, top_k=5)
        logger.info(f"Found {len(search_results)} results")

        # Format results
        formatted_results = search_logic.format_search_results(search_results)

        # Build system prompt with search context
        system_prompt = f"""당신은 {state['domain_name']} 법률 전문 AI 어시스턴트입니다.

사용자의 질문에 대해 다음 검색 결과를 바탕으로 정확하고 유용한 답변을 제공하세요.

검색 결과:
{formatted_results}

답변 지침:
1. 검색된 법률 조항을 명확히 인용하세요
2. 조항의 의미를 쉽게 설명하세요
3. 관련 법조문이 여러 개인 경우 체계적으로 정리하세요
4. 검색 결과가 없는 경우, 솔직하게 밝히고 일반적인 정보를 제공하세요

사용자 질문: {query}
"""

        # Call LLM with search context
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ])

        logger.info(f"Generated response: {response.content[:100]}...")

        # Return updated state
        return {
            "messages": [AIMessage(content=response.content)],
            "search_results": search_results
        }

    except Exception as e:
        logger.error(f"Error in search_domain_1: {e}", exc_info=True)
        error_message = f"죄송합니다. 검색 중 오류가 발생했습니다: {str(e)}"
        return {"messages": [AIMessage(content=error_message)]}


# Build LangGraph
graph_builder = StateGraph(Domain1State)

# Add nodes
graph_builder.add_node("search", search_domain_1)

# Add edges
graph_builder.add_edge(START, "search")
graph_builder.add_edge("search", END)

# Compile graph
domain_1_graph = graph_builder.compile()

logger.info("Domain 1 LangGraph compiled successfully")
