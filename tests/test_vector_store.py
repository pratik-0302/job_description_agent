import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from src.config import AppConfig
from src.ingestion.models import ParsedDocument, ParsedSection, ParsedTable
from src.storage.sqlite_manager import SQLiteManager
from src.chunking.semantic_chunker import SemanticChunkerModule, TokenEstimator, TextChunk
from src.embedding.embedding_pipeline import EmbeddingPipelineModule, EmbeddedChunk
from src.vector_db.chroma_manager import ChromaManager


class TestVectorStoreLayer(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for databases
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_metadata.db")
        self.chroma_path = os.path.join(self.test_dir, "chroma")
        
        # Build System Config
        self.cfg = AppConfig()
        self.cfg.paths.sqlite_db = self.db_path
        self.cfg.paths.chroma_db = self.chroma_path
        self.cfg.chunking.chunk_size = 100
        self.cfg.chunking.chunk_overlap = 10
        self.cfg.embedding.batch_size = 4
        
        self.db_manager = SQLiteManager(self.db_path)

    def tearDown(self):
        from src.storage.sqlite_manager import Base
        Base.metadata.drop_all(self.db_manager.engine)
        self.db_manager.engine.dispose()
        shutil.rmtree(self.test_dir)

    def test_token_estimator(self):
        text = "Hello world. Testing estimated sub-word token counts."
        words = text.split()
        expected = int(len(words) * 1.3)
        self.assertEqual(TokenEstimator.estimate_tokens(text), expected)
        self.assertEqual(TokenEstimator.estimate_tokens(""), 0)

    def test_semantic_chunker(self):
        chunker = SemanticChunkerModule(self.cfg)
        
        # Mock structured document with sections and a table
        sections = [
            ParsedSection(
                section_id="S1",
                heading_text="Section Title",
                heading_level=1,
                content="This is a paragraph. " * 30, # ~180 words/230 tokens (will split)
                start_page=1
            )
        ]
        
        tables = [
            ParsedTable(
                table_id="T1",
                headers=["Col1", "Col2"],
                rows=[["val1", "val2"]],
                source_page=2,
                raw_text="Col1 | Col2\nval1 | val2"
            )
        ]
        
        doc = ParsedDocument(
            doc_id="doc-123",
            file_path="/path/to/doc.pdf",
            file_type="pdf",
            full_text="...",
            sections=sections,
            tables=tables
        )
        
        metadata = {
            "company_name": "Google",
            "role_title": "SWE",
            "job_type": "fte"
        }
        
        chunks = chunker.chunk_document(doc, metadata)
        
        # Verify chunks exist
        self.assertTrue(len(chunks) > 1)
        
        # Check that metadata was denormalized into chunk fields
        for chunk in chunks:
            self.assertEqual(chunk.company_name, "Google")
            self.assertEqual(chunk.role_title, "SWE")
            
        # Verify that the table was kept as a separate chunk of type 'table'
        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        self.assertEqual(len(table_chunks), 1)
        self.assertEqual(table_chunks[0].content, "Col1 | Col2\nval1 | val2")

    @patch('src.embedding.embedding_pipeline.SentenceTransformer')
    def test_embedding_pipeline_and_cache(self, mock_transformer):
        # Mock encoding output
        mock_model = mock_transformer.return_value
        # Mock return value of encoding: numpy arrays (normalized floats)
        mock_model.encode.return_value = [
            [0.1] * 384,
            [0.2] * 384
        ]
        
        pipeline = EmbeddingPipelineModule(self.cfg, self.db_manager)
        
        # Create text chunks
        chunks = [
            TextChunk("chunk-1", "doc-123", 0, "text", "Chunk one text.", 10),
            TextChunk("chunk-2", "doc-123", 1, "text", "Chunk two text.", 10)
        ]
        
        # First call (should be cache misses, calls model.encode)
        embedded_chunks_1 = pipeline.embed_chunks(chunks)
        self.assertEqual(len(embedded_chunks_1), 2)
        self.assertEqual(embedded_chunks_1[0].embedding[0], 0.1)
        mock_model.encode.assert_called_once()
        
        # Reset mock call tracker
        mock_model.encode.reset_mock()
        
        # Second call with same chunks (should be cache hits, no model.encode call)
        embedded_chunks_2 = pipeline.embed_chunks(chunks)
        self.assertEqual(len(embedded_chunks_2), 2)
        self.assertEqual(embedded_chunks_2[0].embedding[0], 0.1)
        mock_model.encode.assert_not_called()

    def test_chroma_manager_lifecycle(self):
        # Initialize chroma manager
        manager = ChromaManager(self.cfg)
        
        # Prepare embedded chunks
        doc_id = "doc-nvidia-456"
        vec1 = [0.1] * 384
        vec1[0] = 0.9
        vec2 = [0.1] * 384
        vec2[1] = 0.9
        
        chunks = [
            EmbeddedChunk(
                chunk_id="chunk-n1",
                doc_id=doc_id,
                chunk_index=0,
                chunk_type="text",
                content="NVIDIA leads graphics and GPU tech.",
                embedding=vec1,
                content_hash="hash1",
                company_name="NVIDIA",
                role_title="Hardware Intern",
                job_type="internship",
                page_number=1
            ),
            EmbeddedChunk(
                chunk_id="chunk-n2",
                doc_id=doc_id,
                chunk_index=1,
                chunk_type="text",
                content="Requirements include Verilog and SystemVerilog.",
                embedding=vec2,
                content_hash="hash2",
                company_name="NVIDIA",
                role_title="Hardware Intern",
                job_type="internship",
                page_number=1
            )
        ]
        
        # 1. Test Upsert
        success = manager.upsert_chunks(chunks)
        self.assertTrue(success)
        
        # Verify collection count
        stats = manager.get_collection_stats()
        self.assertEqual(stats["total_chunks"], 2)
        
        # 2. Test Similarity Query
        query_vec = [0.1] * 384
        query_vec[0] = 0.9
        # query closest match
        q_results = manager.query_similarity(query_vec, n_results=1)
        self.assertEqual(q_results.total_found, 1)
        self.assertEqual(q_results.results[0].chunk_id, "chunk-n1")
        self.assertEqual(q_results.results[0].metadata["company_name"], "NVIDIA")
        self.assertAlmostEqual(q_results.results[0].similarity_score, 1.0, places=5) # Cosine distance identical is 1.0 similarity
        
        # Test Query with metadata filter
        where_filter = {"company_name": "NVIDIA"}
        filtered_results = manager.query_similarity(query_vec, n_results=5, where_filter=where_filter)
        self.assertEqual(filtered_results.total_found, 2)
        
        # Test query matching different company (should return empty hits)
        other_filter = {"company_name": "Google"}
        empty_results = manager.query_similarity(query_vec, n_results=5, where_filter=other_filter)
        self.assertEqual(empty_results.total_found, 0)
        
        # 3. Test Delete Chunks
        del_success = manager.delete_document_chunks(doc_id)
        self.assertTrue(del_success)
        
        # Verify cleanup
        post_del_stats = manager.get_collection_stats()
        self.assertEqual(post_del_stats["total_chunks"], 0)


if __name__ == "__main__":
    unittest.main()
