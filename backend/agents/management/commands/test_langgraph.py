"""
Django management command to test LangGraph agent
Usage: python manage.py test_langgraph
"""

import asyncio
from django.core.management.base import BaseCommand
from agents.langgraph_agent import get_agent_for_slug
from agents.services import initialize_neo4j

class Command(BaseCommand):
    help = 'Test LangGraph agent functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--agent-slug',
            type=str,
            default='test-agent',
            help='Agent slug to test (default: test-agent)'
        )
        parser.add_argument(
            '--message',
            type=str,
            default='Hello! Can you help me?',
            help='Test message to send'
        )

    def handle(self, *args, **options):
        agent_slug = options['agent_slug']
        test_message = options['message']

        self.stdout.write(f'Testing LangGraph agent: {agent_slug}')
        self.stdout.write(f'Test message: {test_message}')

        # Initialize Neo4j connection
        if initialize_neo4j():
            self.stdout.write(
                self.style.SUCCESS('Neo4j connection established')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Neo4j connection failed - continuing without it')
            )

        # Run async test
        asyncio.run(self._test_agent(agent_slug, test_message))

    async def _test_agent(self, agent_slug: str, test_message: str):
        """Async test method"""
        try:
            # Get agent
            self.stdout.write('Loading LangGraph agent...')
            agent = await get_agent_for_slug(agent_slug)

            if not agent:
                self.stdout.write(
                    self.style.ERROR(f'Failed to load agent: {agent_slug}')
                )
                self.stdout.write('Make sure the agent exists and is active')
                return

            self.stdout.write(
                self.style.SUCCESS(f'Agent loaded: {agent.name}')
            )

            # Test chat
            self.stdout.write('Testing chat functionality...')

            response = await agent.chat(
                user_input=test_message,
                context_id='test_context_123',
                session_id='test_session',
                user_name='test_user'
            )

            self.stdout.write(
                self.style.SUCCESS('Chat test successful!')
            )
            self.stdout.write(f'User: {test_message}')
            self.stdout.write(f'Agent: {response}')

            # Test conversation memory
            self.stdout.write('Testing conversation memory...')

            follow_up_response = await agent.chat(
                user_input='What did I just ask you?',
                context_id='test_context_123',
                session_id='test_session',
                user_name='test_user'
            )

            self.stdout.write(
                self.style.SUCCESS('Memory test successful!')
            )
            self.stdout.write(f'Follow-up: What did I just ask you?')
            self.stdout.write(f'Agent: {follow_up_response}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during agent test: {str(e)}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())