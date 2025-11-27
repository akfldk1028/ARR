"""
Health Check API Views

REST API endpoint for backend health monitoring.
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from agents.law.agent_manager import AgentManager
from graph_db.services import Neo4jService

logger = logging.getLogger(__name__)

# Global AgentManager singleton
_agent_manager = None


def get_agent_manager() -> AgentManager:
    """Get or create AgentManager singleton"""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager


@method_decorator(csrf_exempt, name='dispatch')
class HealthCheckAPIView(APIView):
    """
    Health Check API

    GET /api/health

    Response:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "backend": "ok" | "error",
            "neo4j": "ok" | "error",
            "agent_manager": "ok" | "error",
            "domains": int,
            "total_nodes": int,
            "details": {
                "backend_version": str,
                "neo4j_connected": bool,
                "agent_manager_initialized": bool
            }
        }
    """

    def get(self, request):
        """Check backend health status"""
        try:
            health_data = {
                'status': 'healthy',
                'backend': 'ok',
                'neo4j': 'error',
                'agent_manager': 'error',
                'domains': 0,
                'total_nodes': 0,
                'details': {
                    'backend_version': '1.0.0',
                    'neo4j_connected': False,
                    'agent_manager_initialized': False,
                }
            }

            # Check Neo4j connection
            try:
                neo4j = Neo4jService()
                neo4j.connect()

                # Simple query to verify connection
                result = neo4j.execute_query("RETURN 1 AS test", {})
                if result and result[0].get('test') == 1:
                    health_data['neo4j'] = 'ok'
                    health_data['details']['neo4j_connected'] = True

                neo4j.disconnect()
            except Exception as e:
                logger.error(f"Neo4j health check failed: {e}")
                health_data['status'] = 'degraded'

            # Check AgentManager
            try:
                agent_manager = get_agent_manager()

                if agent_manager and agent_manager.domains:
                    health_data['agent_manager'] = 'ok'
                    health_data['domains'] = len(agent_manager.domains)
                    health_data['total_nodes'] = len(agent_manager.node_to_domain)
                    health_data['details']['agent_manager_initialized'] = True
                else:
                    health_data['status'] = 'degraded'

            except Exception as e:
                logger.error(f"AgentManager health check failed: {e}")
                health_data['status'] = 'degraded'

            # Determine overall status
            if health_data['neo4j'] == 'error' or health_data['agent_manager'] == 'error':
                if health_data['status'] == 'healthy':
                    health_data['status'] = 'degraded'

            logger.info(
                f"Health check: status={health_data['status']}, "
                f"neo4j={health_data['neo4j']}, "
                f"agent_manager={health_data['agent_manager']}, "
                f"domains={health_data['domains']}"
            )

            # Return 200 even if degraded (allows monitoring to distinguish from complete failure)
            return Response(health_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in HealthCheckAPIView: {e}", exc_info=True)
            return Response(
                {
                    'status': 'unhealthy',
                    'backend': 'error',
                    'error': str(e)
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
