"""
Django management command to test the reorganized worker agent structure
Usage: python manage.py test_worker_structure
"""

import asyncio
from django.core.management.base import BaseCommand
from agents.worker_agents import get_worker_for_slug, worker_manager, WorkerAgentFactory
from agents.database.neo4j import initialize_neo4j

class Command(BaseCommand):
    help = 'Test the reorganized worker agent structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-type',
            type=str,
            default='all',
            choices=['all', 'factory', 'manager', 'communication'],
            help='Type of test to run (default: all)'
        )

    def handle(self, *args, **options):
        test_type = options['test_type']

        self.stdout.write('Testing reorganized worker agent structure...')
        self.stdout.write(f'Test type: {test_type}')

        # Initialize Neo4j
        if initialize_neo4j():
            self.stdout.write(
                self.style.SUCCESS('Neo4j connection established')
            )

        # Run async tests
        asyncio.run(self._run_tests(test_type))

    async def _run_tests(self, test_type: str):
        """Run worker structure tests"""
        try:
            if test_type in ['all', 'factory']:
                await self._test_worker_factory()

            if test_type in ['all', 'manager']:
                await self._test_worker_manager()

            if test_type in ['all', 'communication']:
                await self._test_worker_communication()

            self.stdout.write(
                self.style.SUCCESS('All worker structure tests completed successfully!')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Worker structure tests failed: {str(e)}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())

    async def _test_worker_factory(self):
        """Test WorkerAgentFactory"""
        self.stdout.write('\\n=== Testing Worker Factory ===')

        # Test available worker types
        worker_types = WorkerAgentFactory.get_available_worker_types()
        self.stdout.write(f'Available worker types: {worker_types}')

        # Test creating different worker types
        test_configs = [
            {
                'agent_slug': 'test-general',
                'config': {
                    'name': 'Test General Worker',
                    'agent_type': 'general',
                    'description': 'Test general worker agent',
                    'model_name': 'gpt-3.5-turbo',
                    'system_prompt': 'You are a test general worker.',
                    'capabilities': ['text', 'conversation']
                }
            },
            {
                'agent_slug': 'test-flight',
                'config': {
                    'name': 'Test Flight Worker',
                    'agent_type': 'flight-specialist',
                    'description': 'Test flight specialist worker',
                    'model_name': 'gpt-3.5-turbo',
                    'system_prompt': 'You are a test flight specialist.',
                    'capabilities': ['text', 'flight_booking']
                }
            }
        ]

        for test_config in test_configs:
            worker = WorkerAgentFactory.create_worker(
                test_config['agent_slug'],
                test_config['config']
            )

            if worker:
                self.stdout.write(
                    self.style.SUCCESS(f'SUCCESS: Created {worker.__class__.__name__} for {test_config["agent_slug"]}')
                )

                # Test worker properties
                self.stdout.write(f'  Name: {worker.agent_name}')
                self.stdout.write(f'  Description: {worker.agent_description}')
                self.stdout.write(f'  Capabilities: {worker.capabilities}')

                # Test agent card generation
                card = worker.generate_agent_card()
                self.stdout.write(f'  Agent Card: {card["name"]} - {len(card["endpoints"])} endpoints')
            else:
                self.stdout.write(
                    self.style.ERROR(f'ERROR: Failed to create worker for {test_config["agent_slug"]}')
                )

        self.stdout.write(
            self.style.SUCCESS('Worker Factory tests completed')
        )

    async def _test_worker_manager(self):
        """Test WorkerAgentManager"""
        self.stdout.write('\\n=== Testing Worker Manager ===')

        # Test getting existing agents
        test_agents = ['test-agent', 'flight-specialist']

        for agent_slug in test_agents:
            self.stdout.write(f'Testing worker manager for: {agent_slug}')

            worker = await get_worker_for_slug(agent_slug)

            if worker:
                self.stdout.write(
                    self.style.SUCCESS(f'SUCCESS: Retrieved {worker.agent_name}')
                )

                # Test agent card through manager
                from agents.worker_agents import get_worker_card_for_slug
                card = await get_worker_card_for_slug(agent_slug)

                if card:
                    self.stdout.write(f'  Agent card retrieved: {card["name"]}')
                    self.stdout.write(f'  Endpoints: {list(card["endpoints"].keys())}')
                else:
                    self.stdout.write(
                        self.style.WARNING('WARNING: No agent card retrieved')
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(f'ERROR: Could not retrieve worker for {agent_slug}')
                )

        # Test manager functions
        active_workers = worker_manager.list_active_workers()
        self.stdout.write(f'Active workers: {active_workers}')

        self.stdout.write(
            self.style.SUCCESS('Worker Manager tests completed')
        )

    async def _test_worker_communication(self):
        """Test worker-to-worker communication"""
        self.stdout.write('\\n=== Testing Worker Communication ===')

        # Get workers
        general_worker = await get_worker_for_slug('test-agent')
        flight_worker = await get_worker_for_slug('flight-specialist')

        if not general_worker or not flight_worker:
            self.stdout.write(
                self.style.ERROR('ERROR: Could not get required workers for communication test')
            )
            return

        # Test direct chat
        self.stdout.write('Testing direct worker chat...')

        general_response = await general_worker.chat(
            user_input="Hello, I'm testing the new worker structure!",
            context_id="worker_structure_test",
            session_id="structure_test_session",
            user_name="structure_tester"
        )

        if general_response:
            self.stdout.write(
                self.style.SUCCESS(f'General Worker Response: {general_response[:100]}...')
            )
        else:
            self.stdout.write(
                self.style.ERROR('ERROR: No response from general worker')
            )

        flight_response = await flight_worker.chat(
            user_input="I need flight information from Seoul to Tokyo",
            context_id="flight_structure_test",
            session_id="flight_test_session",
            user_name="flight_tester"
        )

        if flight_response:
            self.stdout.write(
                self.style.SUCCESS(f'Flight Worker Response: {flight_response[:100]}...')
            )
        else:
            self.stdout.write(
                self.style.ERROR('ERROR: No response from flight worker')
            )

        # Test worker-to-worker communication
        self.stdout.write('Testing worker-to-worker communication...')

        inter_worker_response = await general_worker.communicate_with_agent(
            target_agent_slug='flight-specialist',
            message="A user is asking about flights. Can you help?",
            context_id="inter_worker_test"
        )

        if inter_worker_response:
            self.stdout.write(
                self.style.SUCCESS(f'Inter-worker Communication Success: {inter_worker_response[:100]}...')
            )
        else:
            self.stdout.write(
                self.style.WARNING('WARNING: Inter-worker communication failed')
            )

        self.stdout.write(
            self.style.SUCCESS('Worker Communication tests completed')
        )