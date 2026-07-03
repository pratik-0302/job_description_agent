import unittest
from unittest.mock import MagicMock, patch
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

from src.api.app import app
from src.config import AppConfig
from src.storage.sqlite_manager import SQLiteManager, JDMetadata, JDLocation, JDBranch


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        # Build mock state dependencies
        self.db_manager = MagicMock(spec=SQLiteManager)
        self.chroma_manager = MagicMock()
        self.ollama_client = MagicMock()
        self.graph = MagicMock()
        self.indexing_module = MagicMock()
        self.discovery_module = MagicMock()
        self.cfg = AppConfig()
        from src.retrieval.query_cache import QueryResultCache
        self.query_cache = QueryResultCache()
        self.analytics_cache = QueryResultCache()
        
        # Inject mocks into app.state
        app.state.db_manager = self.db_manager
        app.state.chroma_manager = self.chroma_manager
        app.state.ollama_client = self.ollama_client
        app.state.graph = self.graph
        app.state.indexing_module = self.indexing_module
        app.state.discovery_module = self.discovery_module
        app.state.query_cache = self.query_cache
        app.state.analytics_cache = self.analytics_cache
        app.state.cfg = self.cfg
        
        self.client = TestClient(app)

    def test_health_endpoint(self):
        # Setup mocks
        db_session = MagicMock()
        self.db_manager.get_session.return_value = db_session
        db_session.query.return_value.count.return_value = 5
        
        self.ollama_client.health_check.return_value = True
        
        response = self.client.get("/api/index/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["sqlite_status"], "up")
        self.assertEqual(data["chroma_status"], "up")
        self.assertEqual(data["ollama_status"], "up")
        self.assertEqual(data["indexed_document_count"], 5)

    def test_query_endpoint(self):
        # Setup mock graph invoke response
        self.graph.invoke.return_value = {
            "final_response": {
                "response_id": "r1",
                "agent_type": "search",
                "response_text": "Mock LLM output text",
                "structured_data": None,
                "source_documents": [{"doc_id": "d1", "company_name": "Google"}],
                "follow_up_suggestions": ["What is average pack?"],
                "confidence": 0.9,
                "generation_time_ms": 100
            }
        }
        
        payload = {
            "query_text": "Jobs at Google",
            "session_id": "test_session_id"
        }
        
        response = self.client.post("/api/query", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["response_text"], "Mock LLM output text")
        self.assertEqual(data["agent_type"], "search")
        self.assertEqual(len(data["source_documents"]), 1)

    def test_list_documents_endpoint(self):
        db_session = MagicMock()
        self.db_manager.get_session.return_value = db_session
        
        mock_jd = MagicMock()
        mock_jd.doc_id = "d1"
        mock_jd.company_name = "Google"
        mock_jd.role_title = "SWE"
        mock_jd.job_type = "fte"
        mock_jd.package_ctc = 25.0
        mock_jd.cgpa_cutoff = 8.0
        mock_jd.deadline = "2026-10-10"
        
        db_session.query.return_value.all.return_value = [mock_jd]
        
        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["company_name"], "Google")
        self.assertEqual(data[0]["package_ctc"], 25.0)

    def test_get_document_details(self):
        db_session = MagicMock()
        self.db_manager.get_session.return_value = db_session
        
        mock_jd = MagicMock()
        mock_jd.doc_id = "d1"
        mock_jd.company_name = "Google"
        mock_jd.role_title = "SWE"
        mock_jd.job_type = "fte"
        mock_jd.package_ctc = 25.0
        mock_jd.cgpa_cutoff = 8.0
        mock_jd.deadline = "2026-10-10"
        mock_jd.work_mode = "hybrid"
        
        db_session.query.return_value.filter.return_value.first.return_value = mock_jd
        
        # Mock related tables query results (locs, skills, branches)
        db_session.query.return_value.filter.return_value.all.side_effect = [
            [MagicMock(location="Bangalore")],
            [MagicMock(skill="Python")],
            [MagicMock(branch_code="CS")]
        ]
        
        response = self.client.get("/api/documents/d1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["company_name"], "Google")
        self.assertEqual(data["locations"], ["Bangalore"])
        self.assertEqual(data["skills"], ["Python"])
        self.assertEqual(data["branches"], ["CS"])

    def test_get_indexing_status(self):
        self.indexing_module.get_status.return_value = {"is_running": True}
        response = self.client.get("/api/index/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"is_running": True})

    def test_trigger_manual_scan(self):
        response = self.client.post("/api/index/scan")
        self.assertEqual(response.status_code, 200)
        self.discovery_module.force_rescan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
