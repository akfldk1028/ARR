"""
Neo4j Task Manager - Phase 2
Blackboard Pattern + Contract Net Protocol + Tool Routing
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
import json

from graph_db.services import Neo4jService

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages Tasks, Tools, Capabilities for Multi-Agent Orchestration"""

    def __init__(self, service: Neo4jService):
        self.service = service

    # ===== Task Management (Blackboard Pattern) =====

    def create_task(
        self,
        turn_id: str,
        description: str,
        priority: int = 5,
        deadline: datetime = None,
        status: str = 'TODO',
        decision_id: str = None
    ) -> str:
        """Create a new task from a conversation turn

        Args:
            turn_id: ID of the turn this task belongs to
            description: Task description
            priority: Task priority (1-10)
            deadline: Optional deadline
            status: Task status ('TODO', 'DOING', 'DONE')
            decision_id: Optional Decision ID that created this task

        Returns:
            task_id: UUID of the created task
        """
        task_id = str(uuid4())

        # If decision_id provided, link Task to Decision
        if decision_id:
            query = """
            MATCH (t:Turn {id: $turn_id})
            MATCH (d:Decision {id: $decision_id})
            CREATE (task:Task {
                id: $task_id,
                turn_id: $turn_id,
                description: $description,
                status: $status,
                priority: $priority,
                deadline: $deadline,
                created_at: datetime($created_at)
            })
            CREATE (t)-[:GENERATED_TASK]->(task)
            CREATE (d)-[:CREATES_TASK]->(task)
            RETURN task.id as task_id
            """
            params = {
                'task_id': task_id,
                'turn_id': turn_id,
                'decision_id': decision_id,
                'description': description,
                'status': status,
                'priority': priority,
                'deadline': deadline.isoformat() if deadline else None,
                'created_at': datetime.utcnow().isoformat()
            }
        else:
            # Legacy mode: no decision_id provided
            query = """
            MATCH (t:Turn {id: $turn_id})
            CREATE (task:Task {
                id: $task_id,
                turn_id: $turn_id,
                description: $description,
                status: $status,
                priority: $priority,
                deadline: $deadline,
                created_at: datetime($created_at)
            })
            CREATE (t)-[:GENERATED_TASK]->(task)
            RETURN task.id as task_id
            """
            params = {
                'task_id': task_id,
                'turn_id': turn_id,
                'description': description,
                'status': status,
                'priority': priority,
                'deadline': deadline.isoformat() if deadline else None,
                'created_at': datetime.utcnow().isoformat()
            }

        self.service.execute_write_query(query, params)
        logger.info(f"Created task {task_id}: {description[:50]}..." +
                   (f" (decision: {decision_id})" if decision_id else ""))
        return task_id

    def assign_task_to_agent(self, task_id: str, agent_slug: str, execution_id: str = None):
        """Assign a task to an agent

        Args:
            task_id: ID of the task to assign
            agent_slug: Slug of the agent to assign to
            execution_id: Optional AgentExecution ID that will execute this task
        """
        if execution_id:
            # Create EXECUTED_BY relationship to AgentExecution
            query = """
            MATCH (task:Task {id: $task_id})
            MATCH (ae:AgentExecution {id: $execution_id})
            SET task.assigned_to = $agent_slug,
                task.status = 'DOING',
                task.started_at = datetime($started_at)
            CREATE (task)-[:EXECUTED_BY]->(ae)
            RETURN task
            """
            params = {
                'task_id': task_id,
                'agent_slug': agent_slug,
                'execution_id': execution_id,
                'started_at': datetime.utcnow().isoformat()
            }
        else:
            # Legacy mode: just set properties
            query = """
            MATCH (task:Task {id: $task_id})
            SET task.assigned_to = $agent_slug,
                task.status = 'DOING',
                task.started_at = datetime($started_at)
            RETURN task
            """
            params = {
                'task_id': task_id,
                'agent_slug': agent_slug,
                'started_at': datetime.utcnow().isoformat()
            }

        self.service.execute_write_query(query, params)
        logger.info(f"Assigned task {task_id} to {agent_slug}" +
                   (f" (execution: {execution_id})" if execution_id else ""))

    def complete_task(self, task_id: str):
        """Mark a task as completed"""
        query = """
        MATCH (task:Task {id: $task_id})
        SET task.status = 'DONE',
            task.completed_at = datetime($completed_at)
        RETURN task
        """

        params = {
            'task_id': task_id,
            'completed_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Completed task {task_id}")

    def link_subtasks(self, parent_task_id: str, child_task_id: str):
        """Create NEXT relationship between tasks (subtask sequence)"""
        query = """
        MATCH (parent:Task {id: $parent_task_id})
        MATCH (child:Task {id: $child_task_id})
        CREATE (parent)-[:NEXT]->(child)
        RETURN parent, child
        """

        params = {
            'parent_task_id': parent_task_id,
            'child_task_id': child_task_id
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Linked task {parent_task_id} -> {child_task_id}")

    # ===== Tool Management (Tool Routing) =====

    def create_tool(
        self,
        name: str,
        tool_type: str,
        endpoint: str = None,
        cost: float = 0.0,
        description: str = ""
    ) -> str:
        """Register a new tool"""
        tool_id = str(uuid4())
        query = """
        CREATE (tool:Tool {
            id: $tool_id,
            name: $name,
            type: $tool_type,
            endpoint: $endpoint,
            cost: $cost,
            availability: true,
            description: $description,
            created_at: datetime($created_at)
        })
        RETURN tool.id as tool_id
        """

        params = {
            'tool_id': tool_id,
            'name': name,
            'tool_type': tool_type,
            'endpoint': endpoint,
            'cost': cost,
            'description': description,
            'created_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Created tool {tool_id}: {name}")
        return tool_id

    def register_agent_tool(self, agent_slug: str, tool_name: str):
        """Register that an agent can use a tool"""
        query = """
        MATCH (agent:Agent {slug: $agent_slug})
        MATCH (tool:Tool {name: $tool_name})
        MERGE (agent)-[:CAN_USE]->(tool)
        RETURN agent, tool
        """

        params = {
            'agent_slug': agent_slug,
            'tool_name': tool_name
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Registered {agent_slug} can use {tool_name}")

    def require_tool_for_task(self, task_id: str, tool_name: str):
        """Mark that a task requires a specific tool"""
        query = """
        MATCH (task:Task {id: $task_id})
        MATCH (tool:Tool {name: $tool_name})
        MERGE (task)-[:REQUIRES_TOOL]->(tool)
        RETURN task, tool
        """

        params = {
            'task_id': task_id,
            'tool_name': tool_name
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Task {task_id} requires tool {tool_name}")

    # ===== Capability Management (Contract Net) =====

    def create_capability(
        self,
        name: str,
        category: str,
        description: str = ""
    ) -> str:
        """Create a new capability"""
        capability_id = str(uuid4())
        query = """
        CREATE (cap:Capability {
            id: $capability_id,
            name: $name,
            category: $category,
            description: $description,
            created_at: datetime($created_at)
        })
        RETURN cap.id as capability_id
        """

        params = {
            'capability_id': capability_id,
            'name': name,
            'category': category,
            'description': description,
            'created_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Created capability {capability_id}: {name}")
        return capability_id

    def assign_capability_to_agent(
        self,
        agent_slug: str,
        capability_name: str,
        proficiency: float = 0.8,
        cost: float = 0.1
    ):
        """Assign a capability to an agent with proficiency and cost"""
        query = """
        MATCH (agent:Agent {slug: $agent_slug})
        MATCH (cap:Capability {name: $capability_name})
        MERGE (agent)-[has:HAS_CAPABILITY]->(cap)
        SET has.proficiency = $proficiency,
            has.cost = $cost
        RETURN agent, cap
        """

        params = {
            'agent_slug': agent_slug,
            'capability_name': capability_name,
            'proficiency': proficiency,
            'cost': cost
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Assigned {capability_name} to {agent_slug} (proficiency: {proficiency})")

    def require_capability_for_task(self, task_id: str, capability_name: str):
        """Mark that a task requires a specific capability"""
        query = """
        MATCH (task:Task {id: $task_id})
        MATCH (cap:Capability {name: $capability_name})
        MERGE (task)-[:REQUIRES_CAPABILITY]->(cap)
        RETURN task, cap
        """

        params = {
            'task_id': task_id,
            'capability_name': capability_name
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Task {task_id} requires capability {capability_name}")

    # ===== Contract Net Protocol: FIT Score Calculation =====

    def find_best_agent_for_task(self, task_id: str) -> Optional[str]:
        """Find the best agent for a task using FIT score (Contract Net Protocol)"""
        query = """
        MATCH (task:Task {id: $task_id})-[:REQUIRES_CAPABILITY]->(cap:Capability)
        MATCH (agent:Agent)-[has:HAS_CAPABILITY]->(cap)
        WITH agent, task,
             avg(has.proficiency) as avg_proficiency,
             avg(has.cost) as avg_cost,
             count(cap) as matched_capabilities
        WITH agent, task,
             (avg_proficiency * 0.4 +
              matched_capabilities * 0.3 +
              agent.performance_score * 0.2 -
              agent.cost * 0.1) as fit_score
        ORDER BY fit_score DESC
        LIMIT 1
        RETURN agent.slug as best_agent, fit_score
        """

        params = {'task_id': task_id}
        result = self.service.execute_query(query, params)

        if result:
            best_agent = result[0]['best_agent']
            fit_score = result[0]['fit_score']
            logger.info(f"Best agent for task {task_id}: {best_agent} (FIT: {fit_score:.3f})")
            return best_agent
        return None

    def find_agents_with_tool(self, tool_name: str) -> List[str]:
        """Find all agents that can use a specific tool"""
        query = """
        MATCH (agent:Agent)-[:CAN_USE]->(tool:Tool {name: $tool_name})
        RETURN agent.slug, agent.cost, tool.cost as tool_cost
        ORDER BY (agent.cost + tool.cost) ASC
        """

        params = {'tool_name': tool_name}
        result = self.service.execute_query(query, params)

        agents = [r['agent.slug'] for r in result]
        logger.info(f"Found {len(agents)} agents for tool {tool_name}: {agents}")
        return agents

    def get_pending_tasks(self, limit: int = 10) -> List[Dict]:
        """Get pending tasks ordered by priority and deadline"""
        query = """
        MATCH (task:Task {status: 'TODO'})
        WHERE task.deadline IS NOT NULL
          AND task.deadline > datetime()
        OPTIONAL MATCH (task)-[:REQUIRES_CAPABILITY]->(cap:Capability)
        WITH task, collect(cap.name) as required_capabilities,
             duration.between(datetime(), task.deadline).hours as hours_until_deadline
        RETURN task.id, task.description, task.priority,
               required_capabilities, hours_until_deadline
        ORDER BY
          task.priority DESC,
          hours_until_deadline ASC
        LIMIT $limit
        """

        params = {'limit': limit}
        result = self.service.execute_query(query, params)

        logger.info(f"Retrieved {len(result)} pending tasks")
        return result
