import unittest
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock
import httpx

from src.config import AppConfig
from src.storage.sqlite_manager import SQLiteManager, Document, JDMetadata, JDSkill, JDLocation, JDBranch, QueryRepository
from src.retrieval.intent_detector import IntentDetector
from src.retrieval.result_fusion import ResultFusion, RetrievedDocument
from src.retrieval.hybrid_retriever import QueryFilters, QueryEntityExtractor, ContextAssembler, HybridRetrievalModule
from src.llm.prompt_builder import PromptBuilder
from src.llm.ollama_client import OllamaClient
from src.vector_db.chroma_manager import VectorSearchResult


class TestRetrievalLLMLayer(unittest.TestCase):
    def setUp(self):
        # Temp dir for SQLite database
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_query.db")
        self.db_manager = SQLiteManager(self.db_path)
        
        self.cfg = AppConfig()
        self.cfg.paths.sqlite_db = self.db_path
        self.cfg.llm.base_url = "http://localhost:11434"
        self.cfg.llm.model = "qwen3:8b"
        self.cfg.llm.temperature = 0.0

    def tearDown(self):
        from src.storage.sqlite_manager import Base
        Base.metadata.drop_all(self.db_manager.engine)
        self.db_manager.engine.dispose()
        shutil.rmtree(self.test_dir)

    def test_intent_detector(self):
        self.assertEqual(IntentDetector.detect_intent("Compare Google and Microsoft"), "compare")
        self.assertEqual(IntentDetector.detect_intent("What is the average package for CSE?"), "analytics")
        self.assertEqual(IntentDetector.detect_intent("Can you suggest some jobs for me?"), "recommend")
        self.assertEqual(IntentDetector.detect_intent("Summarize the JD for NVIDIA"), "summary")
        self.assertEqual(IntentDetector.detect_intent("Show me python jobs in Bangalore"), "search")

    def test_result_fusion(self):
        # Mock SQLite matching docs
        sql_docs = [
            JDMetadata(metadata_id="m1", doc_id="doc1", company_name="Co1"),
            JDMetadata(metadata_id="m2", doc_id="doc2", company_name="Co2")
        ]
        
        # Mock vector chunks
        vec_chunks = [
            VectorSearchResult("c1", "doc2", "chunk-doc2", 0.1, 0.95, {}),
            VectorSearchResult("c2", "doc3", "chunk-doc3", 0.2, 0.90, {})
        ]
        
        fused = ResultFusion.fuse(sql_docs, vec_chunks)
        
        # Check fusion outputs
        self.assertEqual(len(fused), 3)
        
        # RRF logic:
        # doc2 appears in SQL (rank 2) and Vec (rank 1) -> score: 1/(60+2) + 1/(60+1) = 0.016129 + 0.016393 = 0.032522
        # doc1 appears in SQL only (rank 1) -> score: 1/(60+1) = 0.016393
        # doc3 appears in Vec only (rank 2) -> score: 1/(60+2) = 0.016129
        # Fused order: doc2, doc1, doc3
        self.assertEqual(fused[0].doc_id, "doc2")
        self.assertEqual(fused[0].retrieval_source, "both")
        self.assertEqual(fused[1].doc_id, "doc1")
        self.assertEqual(fused[1].retrieval_source, "metadata_only")
        self.assertEqual(fused[2].doc_id, "doc3")
        self.assertEqual(fused[2].retrieval_source, "semantic_only")

    def test_query_entity_extractor(self):
        known = ["Google", "NVIDIA", "Microsoft"]
        
        # Package, CGPA, job type, skills, and locations
        q1 = "Looking for a python internship at NVIDIA with package of 12 LPA and CGPA cutoff 8.0 in Pune"
        filters = QueryEntityExtractor.extract_entities(q1, known)
        
        self.assertEqual(filters.company_names, ["NVIDIA"])
        self.assertEqual(filters.min_package, 12.0)
        self.assertEqual(filters.max_cgpa_cutoff, 8.0)
        self.assertEqual(filters.job_type, "internship")
        self.assertEqual(filters.locations, ["pune"])
        self.assertIn("python", filters.skills)

    def test_sqlite_query_repository(self):
        session = self.db_manager.get_session()
        
        # Populate test data
        import uuid
        parent1 = Document(
            doc_id="d1",
            file_path="/path/to/d1.pdf",
            file_name="d1.pdf",
            file_extension="pdf",
            content_hash="hash_d1",
            discovered_at="2026-06-28T00:00:00",
            status="indexed"
        )
        parent2 = Document(
            doc_id="d2",
            file_path="/path/to/d2.pdf",
            file_name="d2.pdf",
            file_extension="pdf",
            content_hash="hash_d2",
            discovered_at="2026-06-28T00:00:00",
            status="indexed"
        )
        session.add_all([parent1, parent2])
        
        doc1 = JDMetadata(
            metadata_id=str(uuid.uuid4()),
            doc_id="d1", company_name="Google", role_title="SWE", 
            job_type="fte", package_ctc=25.0, cgpa_cutoff=8.5, deadline="2026-10-10"
        )
        doc2 = JDMetadata(
            metadata_id=str(uuid.uuid4()),
            doc_id="d2", company_name="NVIDIA", role_title="HW Engineer", 
            job_type="internship", package_ctc=12.0, cgpa_cutoff=7.5, deadline="2026-10-10"
        )
        session.add_all([doc1, doc2])
        
        s1 = JDSkill(doc_id="d1", skill="python", skill_normalized="python")
        s2 = JDSkill(doc_id="d2", skill="verilog", skill_normalized="verilog")
        l1 = JDLocation(doc_id="d1", location="bangalore")
        l2 = JDLocation(doc_id="d2", location="pune")
        b1 = JDBranch(doc_id="d1", branch_code="cse")
        b2 = JDBranch(doc_id="d2", branch_code="ece")
        session.add_all([s1, s2, l1, l2, b1, b2])
        session.commit()
        
        repo = QueryRepository(session)
        
        # Test 1: filter by package & cgpa
        f1 = {"min_package": 15.0, "max_cgpa_cutoff": 9.0}
        res1 = repo.filter_jobs(f1)
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0].company_name, "Google")
        
        # Test 2: filter by skill & location
        f2 = {"skills": ["verilog"], "locations": ["pune"]}
        res2 = repo.filter_jobs(f2)
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0].company_name, "NVIDIA")
        
        session.close()

    def test_prompt_builder(self):
        sys_p, user_p = PromptBuilder.build_prompts(
            agent_type="search",
            query_text="What are the details of SWE job?",
            context_text="[SOURCE: Google]\nContent: SWE fte with 25 LPA package."
        )
        
        self.assertIn("placement advisor", sys_p)
        self.assertIn("Google", user_p)
        self.assertIn("SWE job?", user_p)

    @patch('src.llm.ollama_client.httpx.Client')
    def test_ollama_client_sync(self, mock_client_class):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "Mock generated response from local Ollama model."
            }
        }
        
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.post.return_value = mock_response
        
        client = OllamaClient(self.cfg)
        res = client.generate("sys", "user", stream=False)
        
        self.assertEqual(res["response_text"], "Mock generated response from local Ollama model.")
        self.assertEqual(res["model_used"], "qwen3:8b")


if __name__ == "__main__":
    unittest.main()
