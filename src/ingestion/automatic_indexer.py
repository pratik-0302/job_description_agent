import os
import queue
import threading
import logging
import datetime
from typing import Dict, Any, Optional

from src.config import AppConfig
from src.storage.sqlite_manager import SQLiteManager, DocumentRepository, MetadataRepository
from src.ingestion.parser import DocumentParserModule
from src.extraction.metadata_extractor import MetadataExtractorModule
from src.chunking.semantic_chunker import SemanticChunkerModule
from src.embedding.embedding_pipeline import EmbeddingPipelineModule
from src.vector_db.chroma_manager import ChromaManager
from src.ingestion.models import PipelineEvent

logger = logging.getLogger(__name__)


class AutomaticIndexingModule:
    def __init__(
        self,
        cfg: AppConfig,
        db_manager: SQLiteManager,
        chroma_manager: ChromaManager,
        embedding_pipeline: EmbeddingPipelineModule,
        event_queue: queue.Queue,
        query_cache = None,
        analytics_cache = None
    ):
        self.cfg = cfg
        self.db_manager = db_manager
        self.chroma_manager = chroma_manager
        self.embedding_pipeline = embedding_pipeline
        self.event_queue = event_queue
        self.query_cache = query_cache
        self.analytics_cache = analytics_cache
        
        self.parser_module = DocumentParserModule()
        self.metadata_extractor = MetadataExtractorModule(cfg)
        self.chunker = SemanticChunkerModule(cfg)
        
        self.is_running = False
        self._stop_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        
        # Status metrics
        self.indexed_count = 0
        self.failed_count = 0
        self.currently_processing = None
        self.last_indexed_at = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, name="IndexingWorker", daemon=True)
        self.worker_thread.start()
        logger.info("Automatic Indexing background worker thread started.")

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        self._stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=30.0)
            logger.info("Automatic Indexing background worker thread stopped.")

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                event: PipelineEvent = self.event_queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            try:
                self._process_event(event)
            except Exception as e:
                logger.error(f"Unexpected error processing indexing event {event}: {e}", exc_info=True)
            finally:
                self.event_queue.task_done()

    def _process_event(self, event: PipelineEvent):
        logger.info(f"Processing indexing event: {event.event_type} - {event.file_path}")
        self.currently_processing = event.file_path
        
        session = self.db_manager.get_session()
        doc_repo = DocumentRepository(session)
        meta_repo = MetadataRepository(session)
        
        try:
            if event.event_type == "deleted":
                # 1. Delete Chroma DB chunks
                self.chroma_manager.delete_document_chunks(event.doc_id)
                # 2. Delete Relational database metadata
                meta_repo.delete_metadata(event.doc_id)
                # 3. Update document registry state
                doc_repo.update_document_status(event.doc_id, "deleted")
                session.commit()
                self._invalidate_caches()
                logger.info(f"Successfully deleted indexing trace data for doc_id: {event.doc_id}")
                
            elif event.event_type in ["new", "modified"]:
                # If modified, cleanup previous index entries first
                if event.event_type == "modified":
                    self.chroma_manager.delete_document_chunks(event.doc_id)
                    meta_repo.delete_metadata(event.doc_id)
                    
                # Update status to indexing
                doc_repo.update_document_status(event.doc_id, "indexing")
                session.commit()
                
                # 1. Parse document contents
                parsed_doc = self.parser_module.parse_document(event.file_path, event.doc_id)
                
                # 2. Extract structured metadata attributes
                metadata_dict, report = self.metadata_extractor.extract_metadata(parsed_doc)
                
                # 3. Save metadata variables to SQLite tables
                meta_repo.insert_metadata(event.doc_id, metadata_dict)
                
                # 4. Generate semantic paragraph text chunks
                chunks = self.chunker.chunk_document(parsed_doc, metadata_dict)
                
                # 5. Compute text block embeddings (SentenceTransformers)
                embedded_chunks = self.embedding_pipeline.embed_chunks(chunks)
                
                # 6. Upsert chunk records to ChromaDB
                self.chroma_manager.upsert_chunks(embedded_chunks)
                
                # 7. Update status to indexed
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                doc_repo.update_document_status(event.doc_id, "indexed", indexed_at=now_str)
                session.commit()
                self._invalidate_caches()
                
                self.indexed_count += 1
                self.last_indexed_at = now_str
                logger.info(f"Successfully processed {event.event_type} event for doc_id: {event.doc_id}")
                
        except Exception as e:
            logger.error(f"Failed to process indexing workflow for event {event.event_id}: {e}", exc_info=True)
            try:
                session.rollback()
                doc_repo.update_document_status(event.doc_id, "failed", failure_reason=str(e))
                session.commit()
            except Exception as se:
                logger.error(f"Failed to record indexing failure status in SQLite: {se}")
            self.failed_count += 1
            
        finally:
            session.close()
            self.currently_processing = None

    def _invalidate_caches(self):
        if self.query_cache:
            self.query_cache.clear()
        if self.analytics_cache:
            self.analytics_cache.clear()

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "queue_depth": self.event_queue.qsize(),
            "currently_processing": self.currently_processing,
            "indexed_count": self.indexed_count,
            "failed_count": self.failed_count,
            "last_indexed_at": self.last_indexed_at
        }
