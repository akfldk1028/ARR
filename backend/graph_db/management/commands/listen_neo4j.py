"""
Django Management Command: listen_neo4j
Starts the Neo4j event listener for real-time updates
"""
import asyncio
import sys
from django.core.management.base import BaseCommand
from django.conf import settings

from graph_db.realtime import start_listener


class Command(BaseCommand):
    help = 'Listen to Neo4j CDC events from Kafka and broadcast to WebSocket'

    def add_arguments(self, parser):
        """Add command-line arguments"""
        parser.add_argument(
            '--kafka-brokers',
            type=str,
            default='localhost:9092',
            help='Comma-separated list of Kafka broker URLs (default: localhost:9092)'
        )
        parser.add_argument(
            '--group-id',
            type=str,
            default='neo4j-listener-group',
            help='Kafka consumer group ID (default: neo4j-listener-group)'
        )

    def handle(self, *args, **options):
        """Execute the command"""
        kafka_brokers_str = options.get('kafka_brokers')
        kafka_brokers = [b.strip() for b in kafka_brokers_str.split(',')]
        group_id = options.get('group_id')

        self.stdout.write(
            self.style.SUCCESS('[START] Starting Neo4j event listener...')
        )
        self.stdout.write(
            f"   Kafka Brokers: {', '.join(kafka_brokers)}"
        )
        self.stdout.write(
            f"   Consumer Group: {group_id}"
        )
        self.stdout.write(
            "   Press Ctrl+C to stop"
        )
        self.stdout.write("")

        try:
            # Run the async listener
            asyncio.run(start_listener(kafka_brokers=kafka_brokers, group_id=group_id))

        except KeyboardInterrupt:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING('[STOP] Received keyboard interrupt')
            )
            self.stdout.write(
                self.style.SUCCESS('[OK] Neo4j event listener stopped gracefully')
            )
            sys.exit(0)

        except Exception as e:
            self.stdout.write("")
            self.stderr.write(
                self.style.ERROR(f'[ERROR] Listener crashed: {str(e)}')
            )
            sys.exit(1)
