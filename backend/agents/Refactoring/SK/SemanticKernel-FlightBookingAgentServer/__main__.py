import logging
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import SemanticKernelFlightBookingAgentExecutor  # type: ignore[import-untyped]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("Starting Semantic Kernel Flight Booking Agent Server.")

    # Define the flight booking skill
    flight_booking_skill = AgentSkill(
        id='flight_booking',
        name='Flight Booking',
        description='Assists users in booking flights based on their requests.',
        tags=['flight', 'booking', 'travel'],
        examples=[
            'Book a flight from New York to London next Monday.',
            'I need a flight to Paris tomorrow morning.',
        ],
    )

    # Public-facing agent card for the flight booking agent
    flight_booking_agent_card = AgentCard(
        name='Semantic Kernel Flight Booking Agent',
        description='An agent that helps users book flights using semantic kernel capabilities.',
        capabilities=AgentCapabilities(streaming=True),
        url='http://localhost:9999/',
        version='1.0.0',
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        skills=[flight_booking_skill],
        supportsAuthenticatedExtendedCard=False,

    )

    # Initialize request handler with the flight booking agent executor
    request_handler = DefaultRequestHandler(
        agent_executor=SemanticKernelFlightBookingAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    # Create and run the server application
    server = A2AStarletteApplication(
        agent_card=flight_booking_agent_card,
        http_handler=request_handler,
    )

    logger.info("Starting Semantic Kernel Flight Booking Agent server on port 9999.")
    uvicorn.run(server.build(), host='0.0.0.0', port=9999)