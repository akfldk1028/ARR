# Worker Agent Cards

This directory contains agent card definitions for different worker agent types. These cards define the specifications, capabilities, and configuration templates for each worker agent class.

## Card Structure

Each worker agent card contains:

### Basic Information
- `name`: Display name of the worker agent type
- `description`: Brief description of the agent's purpose
- `version`: Version of the worker agent specification
- `agent_type`: Type classification (always "worker" for worker agents)
- `worker_class`: Python class name implementing this worker type

### Capabilities
- `capabilities`: List of capabilities this worker provides
- `protocols`: Communication protocols supported (A2A, JSON-RPC 2.0)
- `skills`: Detailed skill definitions with input/output types

### Specialization
- `primary`: Primary specialization area
- `expertise_areas`: Specific areas of expertise
- `delegation_keywords`: Keywords that trigger delegation to this worker
- `collaboration_offers`: How this worker collaborates with others

### Configuration
- `default_temperature`: Default LLM temperature setting
- `max_tokens`: Maximum tokens for responses
- `model`: Preferred LLM model
- Additional worker-specific configuration

## Available Workers

### GeneralWorkerAgent
- **File**: `general_worker_card.json`
- **Purpose**: General-purpose assistance and coordination
- **Specialization**: Delegates specialized tasks to appropriate workers
- **Use Case**: First point of contact for diverse user requests

### FlightSpecialistWorkerAgent
- **File**: `flight_specialist_card.json`
- **Purpose**: Flight booking and travel information specialist
- **Specialization**: Flight searches, airline information, route planning
- **Use Case**: Handles all flight-related queries and bookings

## Usage

These cards are used by:

1. **WorkerAgentFactory**: To understand worker capabilities and configuration
2. **A2A Protocol**: To generate runtime agent cards for discovery
3. **Documentation**: To understand what each worker type provides
4. **Testing**: To validate worker implementations against specifications

## Adding New Worker Types

To add a new worker type:

1. Create a new card JSON file in this directory
2. Follow the existing card structure and schema
3. Update the WorkerAgentFactory to register the new worker class
4. Implement the worker class in the implementations directory
5. Add appropriate tests for the new worker type

The card system ensures consistent worker behavior and enables proper A2A protocol compliance for inter-agent communication.