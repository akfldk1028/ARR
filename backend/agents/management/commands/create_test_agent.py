"""
Django management command to create test agent data
Usage: python manage.py create_test_agent
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from agents.models import Agent
from core.models import Organization, Tag

class Command(BaseCommand):
    help = 'Create test agent for endpoint testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating test data...')

        # Create test organization
        org, created = Organization.objects.get_or_create(
            name='Test Organization',
            defaults={'slug': 'test-org', 'description': 'Test organization for agents'}
        )

        # Create test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )

        # Create test tags
        tag1, created = Tag.objects.get_or_create(
            name='AI Assistant',
            organization=org,
            defaults={'color': '#0066cc'}
        )
        tag2, created = Tag.objects.get_or_create(
            name='LangGraph',
            organization=org,
            defaults={'color': '#00cc66'}
        )

        # Create test agent
        agent, created = Agent.objects.get_or_create(
            slug='test-agent',
            defaults={
                'name': 'Test Agent',
                'agent_type': 'gpt',
                'description': 'A test agent for development and testing',
                'organization': org,
                'created_by': user,
                'model_name': 'gpt-3.5-turbo',
                'system_prompt': 'You are a helpful AI assistant for testing purposes.',
                'capabilities': ['text', 'conversation'],
                'status': 'active',
                'max_concurrent_sessions': 10,
                'rate_limit_per_minute': 60,
                'config': {
                    'temperature': 0.7,
                    'max_tokens': 2048,
                    'test_mode': True
                }
            }
        )

        if created:
            agent.tags.add(tag1, tag2)
            self.stdout.write(
                self.style.SUCCESS(f'Test agent created: {agent.name} (slug: {agent.slug})')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Test agent already exists: {agent.name}')
            )

        self.stdout.write('Test data creation completed!')
        self.stdout.write(f'Agent card URL: http://localhost:8000/.well-known/agent-card/{agent.slug}.json')
        self.stdout.write(f'Agent status URL: http://localhost:8000/agents/{agent.slug}/status/')
        self.stdout.write(f'Agent list URL: http://localhost:8000/agents/')