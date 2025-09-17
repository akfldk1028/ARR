"""
Django management command to test Neo4j connection
Usage: python manage.py test_neo4j
"""

from django.core.management.base import BaseCommand
from agents.database.neo4j import initialize_neo4j, get_neo4j_service

class Command(BaseCommand):
    help = 'Test Neo4j connection and basic operations'

    def handle(self, *args, **options):
        self.stdout.write('Testing Neo4j connection...')

        # Test connection
        if initialize_neo4j():
            self.stdout.write(
                self.style.SUCCESS('Neo4j connection successful!')
            )

            # Test basic query
            neo4j_service = get_neo4j_service()
            try:
                from agents.database.neo4j import get_database_stats
                stats = get_database_stats(neo4j_service)
                self.stdout.write(f'Database Stats: {stats}')

                # Test write operation
                test_query = """
                CREATE (n:TestNode {name: 'Django Test', timestamp: datetime()})
                RETURN n
                """
                result = neo4j_service.execute_write_query(test_query)
                self.stdout.write(f'Test write result: {result}')

                # Clean up test node
                cleanup_query = "MATCH (n:TestNode {name: 'Django Test'}) DELETE n"
                neo4j_service.execute_write_query(cleanup_query)
                self.stdout.write('Cleaned up test node')

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error during operations: {str(e)}')
                )
            finally:
                neo4j_service.disconnect()

        else:
            self.stdout.write(
                self.style.ERROR('Neo4j connection failed!')
            )
            self.stdout.write('Make sure Neo4j is running on bolt://localhost:7687')
            self.stdout.write('Check NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD environment variables')