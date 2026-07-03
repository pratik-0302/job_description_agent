import os
import time
import uuid
import datetime
import hashlib
import queue
import logging
from typing import Set, Dict, Tuple, Optional
# pyrefly: ignore [missing-import]
from watchdog.observers import Observer
# pyrefly: ignore [missing-import]
from watchdog.events import FileSystemEventHandler, FileSystemEvent, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent, FileMovedEvent

from src.storage.sqlite_manager import SQLiteManager, DocumentRepository, Document
from src.ingestion.models import DocumentRecord, PipelineEvent

logger = logging.getLogger(__name__)

def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of a file in chunks to save memory."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class FileDebouncer:
    def __init__(self, window_seconds: float = 0.3):
        self.window = window_seconds
        self.last_events: Dict[Tuple[str, str], float] = {}

    def should_process(self, path: str, event_type: str) -> bool:
        now = time.time()
        key = (path, event_type)
        last_time = self.last_events.get(key, 0.0)
        if now - last_time < self.window:
            return False
        self.last_events[key] = now
        return True


class DiscoveryEventHandler(FileSystemEventHandler):
    def __init__(self, discovery_module: 'DocumentDiscoveryModule'):
        self.discovery = discovery_module
        self.debouncer = FileDebouncer(window_seconds=0.3)

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        path = os.path.abspath(event.src_path)
        if self.discovery.is_supported_file(path):
            if self.debouncer.should_process(path, "created"):
                logger.info(f"FileSystem Watcher: File created - {path}")
                self.discovery.handle_file_created(path)

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        path = os.path.abspath(event.src_path)
        if self.discovery.is_supported_file(path):
            if self.debouncer.should_process(path, "modified"):
                logger.info(f"FileSystem Watcher: File modified - {path}")
                self.discovery.handle_file_modified(path)

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory:
            return
        path = os.path.abspath(event.src_path)
        if self.discovery.is_supported_file(path):
            if self.debouncer.should_process(path, "deleted"):
                logger.info(f"FileSystem Watcher: File deleted - {path}")
                self.discovery.handle_file_deleted(path)

    def on_moved(self, event: FileMovedEvent):
        if event.is_directory:
            return
        src_path = os.path.abspath(event.src_path)
        dest_path = os.path.abspath(event.dest_path)
        logger.info(f"FileSystem Watcher: File moved from {src_path} to {dest_path}")
        
        # Handle source deletion if it was supported
        if self.discovery.is_supported_file(src_path):
            if self.debouncer.should_process(src_path, "deleted"):
                self.discovery.handle_file_deleted(src_path)
        
        # Handle destination creation if supported
        if self.discovery.is_supported_file(dest_path):
            if self.debouncer.should_process(dest_path, "created"):
                self.discovery.handle_file_created(dest_path)


class DocumentDiscoveryModule:
    def __init__(self, watched_dir: str, db_manager: SQLiteManager, event_queue: queue.Queue):
        self.watched_dir = os.path.abspath(watched_dir)
        self.db_manager = db_manager
        self.event_queue = event_queue
        self.supported_extensions: Set[str] = {".pdf", ".docx"}
        
        # Ensure watched directory exists
        os.makedirs(self.watched_dir, exist_ok=True)
        
        self.observer: Optional[Observer] = None

    def is_supported_file(self, file_path: str) -> bool:
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.supported_extensions

    def start(self):
        """Start document discovery (Full Scan followed by real-time Watcher)."""
        logger.info(f"Starting Document Discovery Module. Watched directory: {self.watched_dir}")
        
        # 1. Perform full startup scan
        self.force_rescan()
        
        # 2. Setup Watchdog Observer for continuous monitoring
        self.observer = Observer()
        handler = DiscoveryEventHandler(self)
        self.observer.schedule(handler, path=self.watched_dir, recursive=True)
        self.observer.start()
        logger.info("Real-time filesystem observer started.")

    def stop(self):
        """Stop the filesystem observer."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Real-time filesystem observer stopped.")

    def force_rescan(self):
        """Scan watched directory, sync with SQLite registry, and emit events."""
        logger.info("Executing full filesystem rescan...")
        
        session = self.db_manager.get_session()
        repo = DocumentRepository(session)
        
        try:
            # Step A: Get all documents currently in the SQLite registry
            registered_docs = repo.list_documents()
            registered_paths_map = {doc.file_path: doc for doc in registered_docs}
            
            seen_paths = set()
            
            # Step B: Walk watched directory
            for root, _, files in os.walk(self.watched_dir):
                for file in files:
                    file_path = os.path.abspath(os.path.join(root, file))
                    if not self.is_supported_file(file_path):
                        continue
                    
                    seen_paths.add(file_path)
                    
                    # Check file size
                    try:
                        file_size = os.path.getsize(file_path)
                    except OSError:
                        logger.warning(f"Unable to read size for file: {file_path}")
                        continue
                        
                    if file_size == 0:
                        logger.debug(f"Skipping zero-byte file: {file_path}")
                        continue
                    
                    # Compute content hash
                    try:
                        content_hash = compute_sha256(file_path)
                    except (PermissionError, IOError) as e:
                        logger.error(f"Failed to hash file {file_path}: {e}")
                        continue
                    
                    # Check if already registered
                    if file_path in registered_paths_map:
                        registered_doc = registered_paths_map[file_path]
                        hash_changed = registered_doc.content_hash != content_hash
                        # Re-queue if content changed OR if status is stuck/bad
                        stuck_statuses = {"deleted", "indexing", "failed", "pending"}
                        prior_status = registered_doc.status
                        if hash_changed or prior_status in stuck_statuses:
                            logger.info(f"Re-queuing file (hash_changed={hash_changed}, status={prior_status}): {file_path}")
                            registered_doc.content_hash = content_hash
                            registered_doc.file_size_bytes = file_size
                            registered_doc.status = "pending"
                            registered_doc.failure_reason = None
                            session.commit()
                            # Treat previously-deleted docs as new; others as modified re-index
                            event_type = "new" if prior_status == "deleted" else "modified"
                            self._emit_event(event_type, registered_doc.doc_id, file_path)
                    else:
                        # New path, check duplicate detection by content hash
                        existing_hash_doc = repo.get_document_by_hash(content_hash)
                        if existing_hash_doc:
                            # Hash duplicate but different file path, skip ingestion to prevent duplicates
                            logger.warning(f"Skipped duplicate document by hash. Content hash matches: {existing_hash_doc.file_path} for file {file_path}")
                        else:
                            # New file
                            logger.info(f"New file discovered: {file_path}")
                            doc_id = str(uuid.uuid4())
                            doc_record = {
                                'doc_id': doc_id,
                                'file_path': file_path,
                                'file_name': os.path.basename(file_path),
                                'file_extension': os.path.splitext(file_path)[1].lower(),
                                'file_size_bytes': file_size,
                                'content_hash': content_hash,
                                'status': 'pending'
                            }
                            repo.insert_document(doc_record)
                            self._emit_event("new", doc_id, file_path)
            
            # Step C: Detect deleted files (registered but not seen in os.walk)
            for path, registered_doc in registered_paths_map.items():
                if path not in seen_paths and registered_doc.status != 'deleted':
                    logger.info(f"File deleted: {path}")
                    repo.update_document_status(registered_doc.doc_id, "deleted")
                    self._emit_event("deleted", registered_doc.doc_id, path)
                    
        finally:
            session.close()
            logger.info("Filesystem rescan complete.")

    def handle_file_created(self, file_path: str):
        session = self.db_manager.get_session()
        repo = DocumentRepository(session)
        try:
            if not os.path.exists(file_path):
                return
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return
            
            content_hash = compute_sha256(file_path)
            
            # Check if path already in database
            existing_doc = repo.get_document_by_path(file_path)
            if existing_doc:
                if existing_doc.content_hash != content_hash:
                    # Treat as modified if path exists
                    self.handle_file_modified(file_path)
                return
                
            # Duplicate check
            existing_hash_doc = repo.get_document_by_hash(content_hash)
            if existing_hash_doc:
                logger.warning(f"File created duplicate of {existing_hash_doc.file_path} - skipped: {file_path}")
                return
                
            # Insert document
            doc_id = str(uuid.uuid4())
            repo.insert_document({
                'doc_id': doc_id,
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_extension': os.path.splitext(file_path)[1].lower(),
                'file_size_bytes': file_size,
                'content_hash': content_hash,
                'status': 'pending'
            })
            self._emit_event("new", doc_id, file_path)
        except Exception as e:
            logger.error(f"Error handling file creation for {file_path}: {e}")
        finally:
            session.close()

    def handle_file_modified(self, file_path: str):
        session = self.db_manager.get_session()
        repo = DocumentRepository(session)
        try:
            if not os.path.exists(file_path):
                return
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return
            
            content_hash = compute_sha256(file_path)
            existing_doc = repo.get_document_by_path(file_path)
            
            if existing_doc:
                if existing_doc.content_hash != content_hash:
                    logger.info(f"File modified on disk: {file_path}")
                    existing_doc.content_hash = content_hash
                    existing_doc.file_size_bytes = file_size
                    existing_doc.status = "pending"
                    existing_doc.failure_reason = None
                    session.commit()
                    self._emit_event("modified", existing_doc.doc_id, file_path)
            else:
                # If not registered yet, handle as creation
                self.handle_file_created(file_path)
        except Exception as e:
            logger.error(f"Error handling file modification for {file_path}: {e}")
        finally:
            session.close()

    def handle_file_deleted(self, file_path: str):
        session = self.db_manager.get_session()
        repo = DocumentRepository(session)
        try:
            existing_doc = repo.get_document_by_path(file_path)
            if existing_doc and existing_doc.status != 'deleted':
                logger.info(f"File deleted on disk: {file_path}")
                repo.update_document_status(existing_doc.doc_id, "deleted")
                self._emit_event("deleted", existing_doc.doc_id, file_path)
        except Exception as e:
            logger.error(f"Error handling file deletion for {file_path}: {e}")
        finally:
            session.close()

    def _emit_event(self, event_type: str, doc_id: str, file_path: str):
        _, ext = os.path.splitext(file_path.lower())
        event = PipelineEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            doc_id=doc_id,
            file_path=file_path,
            file_extension=ext,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        self.event_queue.put(event)
        logger.info(f"PipelineEvent queued: {event_type} - {file_path}")
