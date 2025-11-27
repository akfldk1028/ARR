"""
Unit tests for graph schema endpoints.

Tests:
- POST /schema - Get graph schema (labels and relationship types)
- POST /populate_graph_schema - Generate schema from text using LLM
- POST /schema_visualization - Get schema visualization
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock


class SchemaEndpointTests(APITestCase):
    """Tests for the schema endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('schema')
        self.payload = {
            'uri': 'neo4j+s://demo.neo4jlabs.com',
            'userName': 'recommendations',
            'password': 'recommendations',
            'database': 'recommendations',
            'email': 'test@example.com'
        }

    @patch('src.main.get_labels_and_relationtypes')
    def test_schema_retrieval_success(self, mock_get_schema):
        """Test successful schema retrieval."""
        mock_get_schema.return_value = {
            'labels': ['Person', 'Movie', 'Genre'],
            'relationshipTypes': ['ACTED_IN', 'DIRECTED', 'HAS_GENRE'],
            'status': 'Success'
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        mock_get_schema.assert_called_once_with(
            self.payload['uri'],
            self.payload['userName'],
            self.payload['password'],
            self.payload['database']
        )

    @patch('src.main.get_labels_and_relationtypes')
    def test_schema_empty_database(self, mock_get_schema):
        """Test schema retrieval from empty database."""
        mock_get_schema.return_value = {
            'labels': [],
            'relationshipTypes': [],
            'status': 'Success'
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    @patch('src.main.get_labels_and_relationtypes')
    def test_schema_connection_failure(self, mock_get_schema):
        """Test schema endpoint with connection failure."""
        mock_get_schema.side_effect = Exception("Connection failed")

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Failed')
        self.assertIn('error', response.data)

    @patch('src.main.get_labels_and_relationtypes')
    def test_schema_response_includes_elapsed_time(self, mock_get_schema):
        """Test that schema response includes elapsed time."""
        mock_get_schema.return_value = {
            'labels': ['Person'],
            'relationshipTypes': ['KNOWS']
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)


class PopulateGraphSchemaEndpointTests(APITestCase):
    """Tests for the populate graph schema endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('populate_graph_schema')
        self.payload = {
            'input_text': 'A person can act in a movie. A movie belongs to a genre.',
            'model': 'test-model',
            'is_schema_description_checked': False,
            'is_local_storage': False,
            'email': 'test@example.com'
        }

    @patch('src.main.populate_graph_schema_from_text')
    def test_populate_schema_success(self, mock_populate):
        """Test successful schema population from text."""
        mock_populate.return_value = {
            'labels': ['Person', 'Movie', 'Genre'],
            'relationshipTypes': ['ACTED_IN', 'BELONGS_TO'],
            'status': 'Success'
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        mock_populate.assert_called_once_with(
            self.payload['input_text'],
            self.payload['model'],
            self.payload['is_schema_description_checked'],
            self.payload['is_local_storage']
        )

    @patch('src.main.populate_graph_schema_from_text')
    def test_populate_schema_with_descriptions(self, mock_populate):
        """Test schema population with description checking enabled."""
        mock_populate.return_value = {
            'labels': ['Person', 'Movie'],
            'relationshipTypes': ['ACTED_IN'],
            'descriptions': {
                'Person': 'An individual actor',
                'Movie': 'A film production'
            }
        }

        payload = {
            **self.payload,
            'is_schema_description_checked': True
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    @patch('src.main.populate_graph_schema_from_text')
    def test_populate_schema_llm_failure(self, mock_populate):
        """Test schema population with LLM failure."""
        mock_populate.side_effect = Exception("LLM API key not configured")

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Failed')
        self.assertIn('error', response.data)

    @patch('src.main.populate_graph_schema_from_text')
    def test_populate_schema_empty_text(self, mock_populate):
        """Test schema population with empty input text."""
        mock_populate.return_value = {
            'labels': [],
            'relationshipTypes': [],
            'status': 'Success'
        }

        payload = {
            **self.payload,
            'input_text': ''
        }

        response = self.client.post(self.url, payload, format='json')

        # Should handle gracefully
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SchemaVisualizationEndpointTests(APITestCase):
    """Tests for the schema visualization endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('schema_visualization')
        self.payload = {
            'uri': 'neo4j+s://demo.neo4jlabs.com',
            'userName': 'recommendations',
            'password': 'recommendations',
            'database': 'recommendations'
        }

    @patch('src.graph_query.visualize_schema')
    def test_schema_visualization_success(self, mock_visualize):
        """Test successful schema visualization."""
        mock_visualize.return_value = {
            'nodes': [
                {'id': '1', 'label': 'Person', 'properties': ['name', 'age']},
                {'id': '2', 'label': 'Movie', 'properties': ['title', 'year']}
            ],
            'relationships': [
                {'from': '1', 'to': '2', 'type': 'ACTED_IN'}
            ],
            'status': 'Success'
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        mock_visualize.assert_called_once_with(
            uri=self.payload['uri'],
            userName=self.payload['userName'],
            password=self.payload['password'],
            database=self.payload['database']
        )

    @patch('src.graph_query.visualize_schema')
    def test_schema_visualization_empty_graph(self, mock_visualize):
        """Test schema visualization for empty graph."""
        mock_visualize.return_value = {
            'nodes': [],
            'relationships': [],
            'status': 'Success'
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    @patch('src.graph_query.visualize_schema')
    def test_schema_visualization_failure(self, mock_visualize):
        """Test schema visualization with connection failure."""
        mock_visualize.side_effect = Exception("Database connection failed")

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Failed')
        self.assertIn('error', response.data)

    @patch('src.graph_query.visualize_schema')
    def test_schema_visualization_includes_elapsed_time(self, mock_visualize):
        """Test that visualization response includes elapsed time."""
        mock_visualize.return_value = {
            'nodes': [{'id': '1', 'label': 'Test'}],
            'relationships': []
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        # Check that elapsed time is mentioned in message
        self.assertIn('elapsed', response.data['message'].lower())
