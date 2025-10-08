"""
Neo4j Governance Manager - Phase 2-3
Role-Based Access Control (RBAC) + Policy Management for Multi-Agent System
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
import json

from .service import Neo4jService

logger = logging.getLogger(__name__)


class GovernanceManager:
    """Manages policies, roles, and access control for the multi-agent system"""

    def __init__(self, service: Neo4jService):
        self.service = service

    # ===== Role Management =====

    def create_role(
        self,
        name: str,
        permission_level: int,
        description: str = "",
        permissions: List[str] = None
    ) -> str:
        """Create a role with specific permissions"""
        role_id = str(uuid4())
        query = """
        CREATE (r:Role {
            id: $role_id,
            name: $name,
            permission_level: $permission_level,
            description: $description,
            permissions: $permissions,
            created_at: datetime($created_at)
        })
        RETURN r.id as role_id
        """

        params = {
            'role_id': role_id,
            'name': name,
            'permission_level': permission_level,
            'description': description,
            'permissions': json.dumps(permissions or []),
            'created_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Created role {role_id}: {name} (level {permission_level})")
        return role_id

    def assign_role_to_agent(
        self,
        agent_slug: str,
        role_name: str,
        granted_by: str = "system",
        expires_at: datetime = None
    ):
        """Assign a role to an agent"""
        if expires_at:
            query = """
            MATCH (agent:Agent {slug: $agent_slug})
            MATCH (role:Role {name: $role_name})
            MERGE (agent)-[has:HAS_ROLE]->(role)
            SET has.granted_by = $granted_by,
                has.granted_at = datetime($granted_at),
                has.expires_at = datetime($expires_at)
            RETURN agent, role
            """
            params = {
                'agent_slug': agent_slug,
                'role_name': role_name,
                'granted_by': granted_by,
                'granted_at': datetime.utcnow().isoformat(),
                'expires_at': expires_at.isoformat()
            }
        else:
            query = """
            MATCH (agent:Agent {slug: $agent_slug})
            MATCH (role:Role {name: $role_name})
            MERGE (agent)-[has:HAS_ROLE]->(role)
            SET has.granted_by = $granted_by,
                has.granted_at = datetime($granted_at)
            RETURN agent, role
            """
            params = {
                'agent_slug': agent_slug,
                'role_name': role_name,
                'granted_by': granted_by,
                'granted_at': datetime.utcnow().isoformat()
            }

        self.service.execute_write_query(query, params)
        logger.info(f"Assigned role {role_name} to agent {agent_slug}")

    # ===== Policy Management =====

    def create_policy(
        self,
        policy_type: str,
        name: str,
        scope: str,
        rules: Dict[str, Any],
        enforcement_level: str = "mandatory",
        description: str = ""
    ) -> str:
        """Create a policy for the system"""
        policy_id = str(uuid4())
        query = """
        CREATE (p:Policy {
            id: $policy_id,
            policy_type: $policy_type,
            name: $name,
            scope: $scope,
            rules: $rules,
            enforcement_level: $enforcement_level,
            description: $description,
            is_active: true,
            created_at: datetime($created_at)
        })
        RETURN p.id as policy_id
        """

        params = {
            'policy_id': policy_id,
            'policy_type': policy_type,
            'name': name,
            'scope': scope,
            'rules': json.dumps(rules),
            'enforcement_level': enforcement_level,
            'description': description,
            'created_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Created policy {policy_id}: {name} ({policy_type})")
        return policy_id

    def attach_policy_to_role(
        self,
        role_name: str,
        policy_id: str
    ):
        """Attach a policy to a role"""
        query = """
        MATCH (role:Role {name: $role_name})
        MATCH (policy:Policy {id: $policy_id})
        MERGE (role)-[:GOVERNED_BY]->(policy)
        RETURN role, policy
        """

        params = {
            'role_name': role_name,
            'policy_id': policy_id
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Attached policy {policy_id} to role {role_name}")

    def attach_policy_to_agent(
        self,
        agent_slug: str,
        policy_id: str
    ):
        """Attach a policy directly to an agent"""
        query = """
        MATCH (agent:Agent {slug: $agent_slug})
        MATCH (policy:Policy {id: $policy_id})
        MERGE (agent)-[:SUBJECT_TO]->(policy)
        RETURN agent, policy
        """

        params = {
            'agent_slug': agent_slug,
            'policy_id': policy_id
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Attached policy {policy_id} to agent {agent_slug}")

    # ===== Access Control Checks =====

    def check_agent_permission(
        self,
        agent_slug: str,
        required_permission: str
    ) -> bool:
        """Check if an agent has a specific permission"""
        query = """
        MATCH (agent:Agent {slug: $agent_slug})-[:HAS_ROLE]->(role:Role)
        WHERE role.permissions CONTAINS $required_permission
        RETURN count(role) > 0 as has_permission
        """

        params = {
            'agent_slug': agent_slug,
            'required_permission': required_permission
        }

        result = self.service.execute_query(query, params)

        if result and result[0]['has_permission']:
            logger.info(f"Agent {agent_slug} has permission: {required_permission}")
            return True

        logger.warning(f"Agent {agent_slug} lacks permission: {required_permission}")
        return False

    def get_agent_effective_policies(
        self,
        agent_slug: str
    ) -> List[Dict]:
        """Get all effective policies for an agent (direct + role-based)"""
        query = """
        MATCH (agent:Agent {slug: $agent_slug})
        OPTIONAL MATCH (agent)-[:SUBJECT_TO]->(direct_policy:Policy)
        OPTIONAL MATCH (agent)-[:HAS_ROLE]->(role:Role)-[:GOVERNED_BY]->(role_policy:Policy)
        WITH agent,
             collect(DISTINCT direct_policy) + collect(DISTINCT role_policy) as all_policies
        UNWIND all_policies as policy
        WITH policy
        WHERE policy IS NOT NULL AND policy.is_active = true
        RETURN policy.id as policy_id,
               policy.name as name,
               policy.policy_type as type,
               policy.scope as scope,
               policy.enforcement_level as enforcement,
               policy.rules as rules
        """

        params = {'agent_slug': agent_slug}
        result = self.service.execute_query(query, params)

        logger.info(f"Found {len(result)} effective policies for agent {agent_slug}")
        return result

    def check_policy_violation(
        self,
        agent_slug: str,
        action: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Check if an action would violate any policies"""
        policies = self.get_agent_effective_policies(agent_slug)

        violations = []
        for policy in policies:
            rules = json.loads(policy['rules'])

            # Check if action matches policy scope
            if 'allowed_actions' in rules:
                if action not in rules['allowed_actions']:
                    violations.append({
                        'policy_id': policy['policy_id'],
                        'policy_name': policy['name'],
                        'enforcement': policy['enforcement'],
                        'reason': f'Action {action} not in allowed_actions',
                        'rule': 'allowed_actions'
                    })

            # Check resource limits
            if 'max_cost' in rules and context and 'cost' in context:
                if context['cost'] > rules['max_cost']:
                    violations.append({
                        'policy_id': policy['policy_id'],
                        'policy_name': policy['name'],
                        'enforcement': policy['enforcement'],
                        'reason': f"Cost {context['cost']} exceeds max {rules['max_cost']}",
                        'rule': 'max_cost'
                    })

        if violations:
            mandatory = [v for v in violations if v['enforcement'] == 'mandatory']
            if mandatory:
                logger.error(f"Mandatory policy violations for {agent_slug}: {len(mandatory)}")
                return {
                    'allowed': False,
                    'violations': violations,
                    'action': action,
                    'agent': agent_slug
                }

        return {
            'allowed': True,
            'violations': violations,
            'action': action,
            'agent': agent_slug
        }

    # ===== Audit & Compliance =====

    def get_role_hierarchy(self) -> List[Dict]:
        """Get the role hierarchy by permission level"""
        query = """
        MATCH (r:Role)
        OPTIONAL MATCH (r)-[:GOVERNED_BY]->(p:Policy)
        WITH r, count(p) as policy_count
        RETURN r.id as role_id,
               r.name as name,
               r.permission_level as level,
               r.description as description,
               policy_count
        ORDER BY r.permission_level DESC
        """

        result = self.service.execute_query(query)
        logger.info(f"Retrieved {len(result)} roles in hierarchy")
        return result

    def get_agents_by_role(self, role_name: str) -> List[str]:
        """Get all agents with a specific role"""
        query = """
        MATCH (agent:Agent)-[:HAS_ROLE]->(role:Role {name: $role_name})
        RETURN agent.slug as agent_slug,
               agent.name as agent_name
        ORDER BY agent.slug
        """

        params = {'role_name': role_name}
        result = self.service.execute_query(query, params)

        agents = [r['agent_slug'] for r in result]
        logger.info(f"Found {len(agents)} agents with role {role_name}")
        return agents

    def get_policy_coverage(self) -> Dict[str, Any]:
        """Get statistics on policy coverage across agents"""
        query = """
        MATCH (agent:Agent)
        OPTIONAL MATCH (agent)-[:SUBJECT_TO|HAS_ROLE*1..2]-(policy:Policy)
        WITH agent,
             count(DISTINCT policy) as policy_count,
             collect(DISTINCT policy.policy_type) as policy_types
        RETURN
            count(agent) as total_agents,
            sum(CASE WHEN policy_count > 0 THEN 1 ELSE 0 END) as agents_with_policies,
            avg(policy_count) as avg_policies_per_agent,
            collect({agent: agent.slug, count: policy_count, types: policy_types}) as details
        """

        result = self.service.execute_query(query)

        if result:
            coverage = result[0]
            logger.info(f"Policy coverage: {coverage['agents_with_policies']}/{coverage['total_agents']} agents")
            return coverage

        return {}

    def audit_policy_compliance(
        self,
        time_window_hours: int = 24
    ) -> List[Dict]:
        """Audit recent agent executions for policy compliance"""
        query = """
        MATCH (ae:AgentExecution)
        WHERE ae.started_at > datetime() - duration({hours: $hours})
        MATCH (ae)-[:USED_AGENT]->(agent:Agent)
        OPTIONAL MATCH (agent)-[:SUBJECT_TO|HAS_ROLE*1..2]-(policy:Policy)
        WITH ae, agent, count(DISTINCT policy) as applicable_policies
        RETURN agent.slug as agent,
               count(ae) as executions,
               applicable_policies,
               CASE WHEN applicable_policies > 0 THEN 'compliant' ELSE 'uncovered' END as status
        ORDER BY executions DESC
        """

        params = {'hours': time_window_hours}
        result = self.service.execute_query(query, params)

        logger.info(f"Audited {len(result)} agents for compliance")
        return result
