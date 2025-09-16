from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from agent import SemanticKernelFlightBookingAgent
import logging
from a2a.utils import (
    new_agent_text_message,
    new_task,
    new_text_artifact,
)

logger = logging.getLogger(__name__)

class SemanticKernelFlightBookingAgentExecutor(AgentExecutor):
    """Executor for SemanticKernelFlightBookingAgent."""

    def __init__(self):
        logger.info("Initializing SemanticKernelFlightBookingAgentExecutor.")
        self.agent = SemanticKernelFlightBookingAgent()
        logger.info("SemanticKernelFlightBookingAgentExecutor initialized successfully.")

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = context.get_user_input()
        task = context.current_task
        context_id = context.context_id
        
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        logger.info(f"Executing flight booking with user input: {user_input} with task: {task.id} and context ID: {context_id}")
        try:
            result = await self.agent.book_flight(user_input, context_id)
            await event_queue.enqueue_event(new_agent_text_message(result))
            logger.info("Flight booking executed successfully.")
        except Exception as e:
            logger.error(f"Error during flight booking execution: {e}")
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {str(e)}"))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        logger.warning("Cancel operation requested but not supported.")
        raise Exception('Cancel operation not supported.')