"""
Domain Management API Views

REST API endpoints for managing and listing law domains.
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from agents.law.agent_manager import AgentManager

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
class DomainsListAPIView(APIView):
    """
    Domains List API

    GET /api/law/domains

    Response:
        {
            "domains": [
                {
                    "domain_id": str,
                    "domain_name": str,
                    "agent_slug": str,
                    "node_count": int,
                    "neighbor_count": int,
                    "created_at": str (ISO),
                    "last_updated": str (ISO)
                },
                ...
            ],
            "total": int
        }
    """

    def get(self, request):
        """Get list of all domains"""
        try:
            # Get AgentManager
            agent_manager = get_agent_manager()

            # Get all domains
            domains = []
            for domain_info in agent_manager.domains.values():
                domains.append(domain_info.to_dict())

            # Sort by node_count descending
            domains.sort(key=lambda d: d['node_count'], reverse=True)

            response_data = {
                'domains': domains,
                'total': len(domains),
            }

            logger.info(f"Domains list retrieved: {len(domains)} domains")

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in DomainsListAPIView: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class DomainDetailAPIView(APIView):
    """
    Domain Detail API

    GET /api/law/domain/<domain_id>

    Response:
        {
            "domain_id": str,
            "domain_name": str,
            "agent_slug": str,
            "node_count": int,
            "neighbor_count": int,
            "created_at": str (ISO),
            "last_updated": str (ISO),
            "neighbors": [
                {
                    "domain_id": str,
                    "domain_name": str
                },
                ...
            ]
        }
    """

    def get(self, request, domain_id):
        """Get details for specific domain"""
        try:
            # Get AgentManager
            agent_manager = get_agent_manager()

            # Get specified domain
            domain_info = agent_manager.domains.get(domain_id)

            if not domain_info:
                return Response(
                    {'error': f'Domain {domain_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Build response
            response_data = domain_info.to_dict()

            # Add neighbor details
            neighbors = []
            for neighbor_id in domain_info.neighbor_domains:
                neighbor_info = agent_manager.domains.get(neighbor_id)
                if neighbor_info:
                    neighbors.append({
                        'domain_id': neighbor_id,
                        'domain_name': neighbor_info.domain_name,
                    })

            response_data['neighbors'] = neighbors

            logger.info(f"Domain detail retrieved: {domain_info.domain_name}")

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in DomainDetailAPIView: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
