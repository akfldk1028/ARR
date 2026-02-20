"""
Kafka Producer for Neo4j Events
Publishes Neo4j CDC events to Kafka topics
"""
import json
import logging
from typing import Dict, Any
from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)


class Neo4jKafkaProducer:
    """Kafka producer for Neo4j events"""

    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None

    async def start(self):
        """Start the Kafka producer"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info(f"Kafka producer started: {self.bootstrap_servers}")

    async def stop(self):
        """Stop the Kafka producer"""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_event(self, event_type: str, data: Dict[str, Any]):
        """
        Publish an event to the appropriate Kafka topic

        Args:
            event_type: Type of event (e.g., 'conversation_created')
            data: Event data
        """
        if not self.producer:
            raise RuntimeError("Producer not started. Call start() first.")

        # Map event type to Kafka topic
        topic_map = {
            'conversation_created': 'neo4j.conversation.created',
            'conversation_updated': 'neo4j.conversation.updated',
            'message_created': 'neo4j.message.created',
            'turn_created': 'neo4j.turn.created',
            'agent_execution_created': 'neo4j.agent_execution.created',
            'agent_execution_completed': 'neo4j.agent_execution.completed',
        }

        topic = topic_map.get(event_type)
        if not topic:
            logger.warning(f"Unknown event type: {event_type}")
            return

        # Prepare message
        message = {
            'type': event_type,
            **data
        }

        # Send to Kafka
        try:
            await self.producer.send_and_wait(topic, message)
            logger.info(f"Published {event_type} to {topic}")
        except Exception as e:
            logger.error(f"Failed to publish {event_type}: {e}")
            raise


async def get_kafka_producer() -> Neo4jKafkaProducer:
    """Create a new Kafka producer for each request to avoid event loop conflicts"""
    producer = Neo4jKafkaProducer()
    await producer.start()
    return producer
