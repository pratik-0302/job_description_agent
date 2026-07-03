import unittest
import queue
import time
from unittest.mock import MagicMock, patch

from src.config import AppConfig
from src.storage.sqlite_manager import SQLiteManager
from src.ingestion.models import PipelineEvent
from src.ingestion.automatic_indexer import AutomaticIndexingModule


class TestIndexingWorker(unittest.TestCase):
    def setUp(self):
        self.cfg = AppConfig()
        self.db_manager = MagicMock(spec=SQLiteManager)
        self.chroma_manager = MagicMock()
        self.embedding_pipeline = MagicMock()
        self.event_queue = queue.Queue()

        self.db_session = MagicMock()
        self.db_manager.get_session.return_value = self.db_session

        self.indexer = AutomaticIndexingModule(
            cfg=self.cfg,
            db_manager=self.db_manager,
            chroma_manager=self.chroma_manager,
            embedding_pipeline=self.embedding_pipeline,
            event_queue=self.event_queue
        )

    def test_deleted_document_event(self):
        # 1. Enqueue a deleted event
        event = PipelineEvent(
            event_id="e1",
            event_type="deleted",
            doc_id="d1",
            file_path="jd_files/google.pdf",
            file_extension=".pdf",
            timestamp=None
        )
        self.event_queue.put(event)

        # 2. Mock repository instances
        mock_doc_repo = MagicMock()
        mock_meta_repo = MagicMock()

        with patch("src.ingestion.automatic_indexer.DocumentRepository", return_value=mock_doc_repo), \
             patch("src.ingestion.automatic_indexer.MetadataRepository", return_value=mock_meta_repo):
             
            # Process single event manually
            self.indexer._process_event(event)

        # 3. Assert cascade deletions were invoked
        self.chroma_manager.delete_document_chunks.assert_called_once_with("d1")
        mock_meta_repo.delete_metadata.assert_called_once_with("d1")
        mock_doc_repo.update_document_status.assert_called_once_with("d1", "deleted")
        self.db_session.commit.assert_called_once()

    def test_new_document_event_processing(self):
        # 1. Enqueue new event
        event = PipelineEvent(
            event_id="e2",
            event_type="new",
            doc_id="d2",
            file_path="jd_files/google.pdf",
            file_extension=".pdf",
            timestamp=None
        )
        self.event_queue.put(event)

        # 2. Mock all pipeline layers
        self.indexer.parser_module.parse_document = MagicMock()
        self.indexer.metadata_extractor.extract_metadata = MagicMock(return_value=({"company_name": "Google"}, None))
        self.indexer.chunker.chunk_document = MagicMock(return_value=[])
        self.embedding_pipeline.embed_chunks.return_value = []

        mock_doc_repo = MagicMock()
        mock_meta_repo = MagicMock()

        with patch("src.ingestion.automatic_indexer.DocumentRepository", return_value=mock_doc_repo), \
             patch("src.ingestion.automatic_indexer.MetadataRepository", return_value=mock_meta_repo):
             
            self.indexer._process_event(event)

        # 3. Assert all stages executed in sequence
        self.indexer.parser_module.parse_document.assert_called_once_with("jd_files/google.pdf", "d2")
        self.indexer.metadata_extractor.extract_metadata.assert_called_once()
        mock_meta_repo.insert_metadata.assert_called_once_with("d2", {"company_name": "Google"})
        self.indexer.chunker.chunk_document.assert_called_once()
        self.embedding_pipeline.embed_chunks.assert_called_once()
        self.chroma_manager.upsert_chunks.assert_called_once()
        
        # Verify status transitions to indexing and then indexed
        mock_doc_repo.update_document_status.assert_any_call("d2", "indexing")
        mock_doc_repo.update_document_status.assert_any_call("d2", "indexed", indexed_at=unittest.mock.ANY)


if __name__ == "__main__":
    unittest.main()
