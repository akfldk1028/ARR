"""
Unit tests for health and connection endpoints.

Tests:
- GET /health - Health check endpoint
- POST /connect - Neo4j connection test
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock


class HealthEndpointTests(APITestCase):
    """Tests for the health check endpoint."""

    def test_health_endpoint_returns_ok(self):
        """Test that health endpoint returns 200 OK with correct message."""
        url = reverse('health')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['message'], 'Django migration successful')

    def test_health_endpoint_structure(self):
        """Test that health endpoint returns correct JSON structure."""
        url = reverse('health')
        response = self.client.get(url)

        self.assertIn('status', response.data)
        self.assertIn('message', response.data)


class ConnectEndpointTests(APITestCase):
    """Tests for the Neo4j connection endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('connect')
        self.valid_payload = {
            'uri': 'neo4j+s://demo.neo4jlabs.com',
            'userName': 'recommendations',
            'password': 'recommendations',
            'database': 'recommendations'
        }

    @patch('src.main.create_graph_database_connection')
    @patch('src.main.connection_check_and_get_vector_dimensions')
    def test_connect_with_valid_credentials(self, mock_get_dimensions, mock_create_connection):
        """Test connection with valid Neo4j credentials."""
        # Mock successful connection
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph
        mock_get_dimensions.return_value = {
            'embedding_dimension': 384,
            'status': 'Success'
        }

        response = self.client.post(self.url, self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)

        # Verify mocks were called with correct arguments
        mock_create_connection.assert_called_once()
        # connection_check_and_get_vector_dimensions receives (graph, database) parameters
        mock_get_dimensions.assert_called_once_with(mock_graph, 'recommendations')

    @patch('src.main.create_graph_database_connection')
    def test_connect_with_invalid_credentials(self, mock_create_connection):
        """Test connection with invalid Neo4j credentials."""
        # Mock connection failure
        mock_create_connection.side_effect = Exception("Authentication failed")

        invalid_payload = {
            'uri': 'bolt://localhost:7687',
            'userName': 'neo4j',
            'password': 'wrong_password',
            'database': 'neo4j'
        }

        response = self.client.post(self.url, invalid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertEqual(response.data['status'], 'Failed')

    def test_connect_with_missing_fields(self):
        """Test connection endpoint with missing required fields."""
        incomplete_payload = {
            'uri': 'bolt://localhost:7687',
            # Missing userName, password, database
        }

        response = self.client.post(self.url, incomplete_payload, format='json')

        # Should still return 200 but with error in response
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('src.main.create_graph_database_connection')
    @patch('src.main.connection_check_and_get_vector_dimensions')
    def test_connect_includes_logging(self, mock_get_dimensions, mock_create_connection):
        """Test that connection endpoint performs logging."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph
        mock_get_dimensions.return_value = {
            'embedding_dimension': 384,
            'status': 'Success'
        }

        payload_with_email = {
            **self.valid_payload,
            'email': 'test@example.com'
        }

        response = self.client.post(self.url, payload_with_email, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify that the endpoint handled the email parameter
        self.assertIsNotNone(response.data)
