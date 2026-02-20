"""
Neo4j Real-time Event Listener
Listens to Neo4j CDC events from Kafka and broadcasts to WebSocket clients
"""
import asyncio
import json
import logging
from typing import Optional, List

try:
    from aiokafka import AIOKafkaConsumer
except ImportError:
    AIOKafkaConsumer = None

from channels.layers import get_channel_layer
from django.conf import settings

from .handlers import EventHandlerRegistry

logger = logging.getLogger(__name__)


class Neo4jEventListener:
    """
    Listen to Neo4j CDC events from Kafka and broadcast to Django Channels

    Events are published by Neo4j APOC triggers to Kafka, then this listener
    picks them up and broadcasts to WebSocket clients via Django Channels.
    """

    def __init__(self, kafka_brokers: List[str] = None, group_id: str = 'neo4j-listener-group'):
        """
        Initialize the listener

        Args:
            kafka_brokers: List of Kafka broker URLs (e.g., ['localhost:9092'])
            group_id: Kafka consumer group ID
        """
        if AIOKafkaConsumer is None:
            raise ImportError(
                "aiokafka is required for Neo4j real-time events. "
                "Install it with: pip install aiokafka"
            )

        self.kafka_brokers = kafka_brokers or ['localhost:9092']
        self.group_id = group_id
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.channel_layer = get_channel_layer()
        self.handler_registry = EventHandlerRegistry()
        self.running = False

        # Kafka topics to subscribe to
        self.topics = [
            'neo4j.conversation.created',
            'neo4j.conversation.updated',
            'neo4j.message.created',
            'neo4j.turn.created',
            'neo4j.agent_execution.created',
            'neo4j.agent_execution.completed',
        ]

    async def connect(self):
        """Connect to Kafka and subscribe to Neo4j event topics"""
        try:
            self.consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.kafka_brokers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',  # Start from latest messages
                enable_auto_commit=True,
            )

            # Start the consumer
            await self.consumer.start()

            logger.info("[OK] Connected to Kafka at %s", ','.join(self.kafka_brokers))
            logger.info("[SUBSCRIBED] Subscribed to topics: %s", ', '.join(self.topics))

        except Exception as e:
            logger.error("[ERROR] Failed to connect to Kafka: %s", str(e))
            raise

    async def listen(self):
        """Listen for events and broadcast to WebSocket clients"""
        if not self.consumer:
            raise RuntimeError("Not connected to Kafka. Call connect() first.")

        logger.info("[LISTENING] Listening for Neo4j events...")
        self.running = True

        try:
            async for msg in self.consumer:
                if not self.running:
                    break

                try:
                    topic = msg.topic
                    data = msg.value

                    logger.debug("[RECEIVED] Received event from %s: %s", topic, data.get('type', 'unknown'))

                    # Convert Kafka topic to channel format for handler routing
                    # e.g., 'neo4j.conversation.created' → 'neo4j:conversation:created'
                    channel = topic.replace('.', ':')

                    # Route to appropriate handler via registry
                    await self.handler_registry.route_event(channel, data)

                except json.JSONDecodeError as e:
                    logger.error("[ERROR] Invalid JSON in event: %s", str(e))
                except Exception as e:
                    logger.error("[ERROR] Error processing event: %s", str(e), exc_info=True)

        except asyncio.CancelledError:
            logger.info("[STOP] Event listener cancelled")
            raise
        except Exception as e:
            logger.error("[ERROR] Error in event listener: %s", str(e), exc_info=True)
            raise
        finally:
            self.running = False


    async def close(self):
        """Close connections gracefully"""
        self.running = False

        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("[DISCONNECTED] Disconnected from Kafka")
            except Exception as e:
                logger.warning("[WARNING] Error closing Kafka consumer: %s", str(e))

    async def __aenter__(self):
        """Async context manager support"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager support"""
        await self.close()


async def start_listener(kafka_brokers: List[str] = None, group_id: str = 'neo4j-listener-group'):
    """
    Start the Neo4j event listener

    Args:
        kafka_brokers: List of Kafka broker URLs
        group_id: Kafka consumer group ID
    """
    logger.info("[START] Starting Neo4j event listener...")

    async with Neo4jEventListener(kafka_brokers=kafka_brokers, group_id=group_id) as listener:
        try:
            await listener.listen()
        except KeyboardInterrupt:
            logger.info("[STOP] Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error("[ERROR] Listener crashed: %s", str(e), exc_info=True)
            raise

    logger.info("[STOPPED] Neo4j event listener stopped")
