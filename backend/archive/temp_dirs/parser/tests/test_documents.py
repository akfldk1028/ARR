"""
Unit tests for document management endpoints.

Tests:
- POST /sources_list - Get list of document sources
- POST /upload - Upload file chunks
- POST /url/scan - Scan URLs (S3/GCS/Web/YouTube/Wikipedia)
- POST /delete_document_and_entities - Delete documents
- GET /document_status/<file_name> - Get document status
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock, mock_open
import io


class SourcesListEndpointTests(APITestCase):
    """Tests for the sources list endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('sources_list')
        self.payload = {
            'uri': 'neo4j+s://demo.neo4jlabs.com',
            'userName': 'recommendations',
            'password': 'recommendations',
            'database': 'recommendations'
        }

    @patch('src.main.get_source_list_from_graph')
    def test_sources_list_success(self, mock_get_sources):
        """Test successful retrieval of source list."""
        mock_get_sources.return_value = {
            'status': 'Success',
            'data': ['doc1.pdf', 'doc2.txt']
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        mock_get_sources.assert_called_once()

    @patch('src.main.get_source_list_from_graph')
    def test_sources_list_empty(self, mock_get_sources):
        """Test sources list when no documents exist."""
        mock_get_sources.return_value = {
            'status': 'Success',
            'data': []
        }

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)


class UploadEndpointTests(APITestCase):
    """Tests for the file upload endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('upload')

    @patch('src.main.create_graph_database_connection')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_upload_first_chunk(self, mock_makedirs, mock_exists, mock_file, mock_create_connection):
        """Test uploading the first chunk of a file."""
        mock_exists.return_value = False
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph

        # Create a simple file
        file_content = b"Test file content"
        file = io.BytesIO(file_content)
        file.name = 'test.txt'

        payload = {
            'uri': 'bolt://localhost:7687',
            'userName': 'neo4j',
            'password': 'password',
            'database': 'neo4j',
            'chunkNumber': '0',
            'totalChunks': '1',
            'originalname': 'test.txt',
            'model': 'test-model'
        }

        response = self.client.post(
            self.url,
            {**payload, 'file': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('src.main.create_graph_database_connection')
    def test_upload_missing_file(self, mock_create_connection):
        """Test upload endpoint with missing file."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph

        payload = {
            'uri': 'bolt://localhost:7687',
            'userName': 'neo4j',
            'password': 'password',
            'database': 'neo4j',
            'chunkNumber': '0',
            'totalChunks': '1',
            'originalname': 'test.txt'
        }

        response = self.client.post(self.url, payload, format='multipart')

        # Should handle missing file gracefully
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class URLScanEndpointTests(APITestCase):
    """Tests for the URL scan endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('url_scan')
        self.base_payload = {
            'uri': 'bolt://localhost:7687',
            'userName': 'neo4j',
            'password': 'password',
            'database': 'neo4j',
            'model': 'test-model'
        }

    @patch('src.main.create_graph_database_connection')
    @patch('src.main.create_source_node_graph_web_url')
    def test_url_scan_web_url(self, mock_create_source, mock_create_connection):
        """Test scanning a regular web URL."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph
        # Return value: (lst_file_name, success_count, failed_count)
        mock_create_source.return_value = ([{'fileName': 'test.html', 'status': 'Success'}], 1, 0)

        payload = {
            **self.base_payload,
            'source_url': 'https://example.com',
            'source_type': 'web-url'
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify create_source_node_graph_web_url was called with correct args
        mock_create_source.assert_called_once_with(mock_graph, 'test-model', 'https://example.com', 'web-url')

    @patch('src.main.create_graph_database_connection')
    @patch('src.main.create_source_node_graph_url_youtube')
    def test_url_scan_youtube(self, mock_create_source, mock_create_connection):
        """Test scanning a YouTube URL."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph
        # Return value: (lst_file_name, success_count, failed_count)
        mock_create_source.return_value = ([{'fileName': 'test_video', 'status': 'Success'}], 1, 0)

        payload = {
            **self.base_payload,
            'source_url': 'https://youtube.com/watch?v=test',
            'source_type': 'youtube'
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify create_source_node_graph_url_youtube was called with correct args
        mock_create_source.assert_called_once_with(mock_graph, 'test-model', 'https://youtube.com/watch?v=test', 'youtube')

    @patch('src.main.create_graph_database_connection')
    @patch('src.main.create_source_node_graph_url_wikipedia')
    def test_url_scan_wikipedia(self, mock_create_source, mock_create_connection):
        """Test scanning Wikipedia with query."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph
        # Return value: (lst_file_name, success_count, failed_count)
        mock_create_source.return_value = ([{'fileName': 'Python_programming', 'status': 'Success'}], 1, 0)

        payload = {
            **self.base_payload,
            'wiki_query': 'Python programming',
            'source_type': 'Wikipedia'
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify create_source_node_graph_url_wikipedia was called with correct args
        mock_create_source.assert_called_once_with(mock_graph, 'test-model', 'Python programming', 'Wikipedia')


class DeleteDocumentEndpointTests(APITestCase):
    """Tests for the delete document endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.url = reverse('delete_document_and_entities')
        self.payload = {
            'uri': 'bolt://localhost:7687',
            'userName': 'neo4j',
            'password': 'password',
            'database': 'neo4j',
            'filenames': '["test.pdf"]',
            'source_types': '["local file"]',
            'deleteEntities': 'true'
        }

    @patch('src.graphDB_dataAccess.graphDBdataAccess')
    @patch('src.main.create_graph_database_connection')
    def test_delete_document_success(self, mock_create_connection, mock_graphdb_class):
        """Test successful document deletion."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph

        # Mock the graphDBdataAccess instance
        mock_graphdb_instance = MagicMock()
        mock_graphdb_instance.delete_file_from_graph.return_value = 1
        mock_graphdb_class.return_value = mock_graphdb_instance

        response = self.client.post(self.url, self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify graphDBdataAccess was instantiated with graph
        mock_graphdb_class.assert_called_once_with(mock_graph)
        # Verify delete_file_from_graph was called
        self.assertTrue(mock_graphdb_instance.delete_file_from_graph.called)

    @patch('src.graphDB_dataAccess.graphDBdataAccess')
    @patch('src.main.create_graph_database_connection')
    def test_delete_multiple_documents(self, mock_create_connection, mock_graphdb_class):
        """Test deletion of multiple documents."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph

        # Mock the graphDBdataAccess instance
        mock_graphdb_instance = MagicMock()
        mock_graphdb_instance.delete_file_from_graph.return_value = 3
        mock_graphdb_class.return_value = mock_graphdb_instance

        payload = {
            **self.payload,
            'filenames': '["doc1.pdf", "doc2.txt", "doc3.docx"]',
            'source_types': '["local file", "local file", "local file"]'
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DocumentStatusEndpointTests(APITestCase):
    """Tests for the document status endpoint."""

    @patch('src.graphDB_dataAccess.graphDBdataAccess')
    @patch('src.main.create_graph_database_connection')
    def test_document_status_exists(self, mock_create_connection, mock_graphdb_class):
        """Test status check for existing document."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph

        # Mock the graphDBdataAccess instance
        mock_graphdb_instance = MagicMock()
        mock_graphdb_instance.get_current_status_document_node.return_value = [{
            'Status': 'Completed',
            'processingTime': 10.5,
            'nodeCount': 100,
            'relationshipCount': 150,
            'model': 'test-model',
            'total_chunks': 5,
            'fileSize': 1024,
            'processed_chunk': 5,
            'fileSource': 'local file',
            'chunkNodeCount': 5,
            'chunkRelCount': 4,
            'entityNodeCount': 95,
            'entityEntityRelCount': 146,
            'communityNodeCount': 0,
            'communityRelCount': 0
        }]
        mock_graphdb_class.return_value = mock_graphdb_instance

        url = reverse('document_status', kwargs={'file_name': 'test.pdf'})
        response = self.client.get(url, {
            'url': 'bolt://localhost:7687',
            'userName': 'neo4j',
            'password': 'password',
            'database': 'neo4j'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('file_name', response.data)

    @patch('src.graphDB_dataAccess.graphDBdataAccess')
    @patch('src.main.create_graph_database_connection')
    def test_document_status_not_found(self, mock_create_connection, mock_graphdb_class):
        """Test status check for non-existent document."""
        mock_graph = MagicMock()
        mock_create_connection.return_value = mock_graph

        # Mock the graphDBdataAccess instance with empty result
        mock_graphdb_instance = MagicMock()
        mock_graphdb_instance.get_current_status_document_node.return_value = []
        mock_graphdb_class.return_value = mock_graphdb_instance

        url = reverse('document_status', kwargs={'file_name': 'nonexistent.pdf'})
        response = self.client.get(url, {
            'url': 'bolt://localhost:7687',
            'userName': 'neo4j',
            'password': 'password',
            'database': 'neo4j'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
