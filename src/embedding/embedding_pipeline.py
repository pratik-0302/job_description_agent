import hashlib
import time
import logging
from typing import List, Optional
# pyrefly: ignore [missing-import]
import numpy as np

# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer

from src.chunking.semantic_chunker import TextChunk
from src.storage.sqlite_manager import SQLiteManager, EmbeddingCacheRepository
from src.config import AppConfig

logger = logging.getLogger(__name__)

def compute_string_sha256(text: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddedChunk:
    def __init__(
        self,
        chunk_id: str,
        doc_id: str,
        chunk_index: int,
        chunk_type: str,
        content: str,
        embedding: List[float],
        content_hash: str,
        section_heading: Optional[str] = None,
        company_name: Optional[str] = None,
        role_title: Optional[str] = None,
        job_type: Optional[str] = None,
        page_number: Optional[int] = None
    ):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.chunk_index = chunk_index
        self.chunk_type = chunk_type
        self.content = content
        self.embedding = embedding
        self.content_hash = content_hash
        self.section_heading = section_heading
        self.company_name = company_name
        self.role_title = role_title
        self.job_type = job_type
        self.page_number = page_number


class EmbeddingPipelineModule:
    def __init__(self, cfg: AppConfig, db_manager: SQLiteManager):
        self.cfg = cfg
        self.db_manager = db_manager
        
        self.model_name = cfg.embedding.model  # "BAAI/bge-small-en-v1.5"
        self.batch_size = cfg.embedding.batch_size  # default: 32
        self.instruction = cfg.embedding.instruction  # prefix instruction
        
        # Load local model (SentenceTransformer handles local cache lookup automatically)
        logger.info(f"Loading SentenceTransformer embedding model: {self.model_name}")
        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info("SentenceTransformer loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}")
            raise

    def embed_query(self, query_text: str) -> List[float]:
        """Encode a search query with the instruction prefix (asymmetric retrieval)."""
        prefixed = f"{self.instruction}{query_text}"
        raw = self.model.encode(prefixed, normalize_embeddings=True)
        return raw.tolist() if hasattr(raw, "tolist") else list(raw)

    def embed_chunks(self, chunks: List[TextChunk]) -> List[EmbeddedChunk]:
        start_time = time.time()
        embedded_chunks: List[EmbeddedChunk] = []
        
        session = self.db_manager.get_session()
        cache_repo = EmbeddingCacheRepository(session)
        
        try:
            # 1. Split chunks into cache hits and misses
            miss_chunks: List[TextChunk] = []
            miss_hashes: List[str] = []
            
            for chunk in chunks:
                content_hash = compute_string_sha256(chunk.content)
                cached_vec = cache_repo.get_cached_embedding(content_hash, self.model_name)
                
                if cached_vec is not None:
                    # Cache Hit
                    embedded_chunks.append(EmbeddedChunk(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        chunk_index=chunk.chunk_index,
                        chunk_type=chunk.chunk_type,
                        content=chunk.content,
                        embedding=cached_vec,
                        content_hash=content_hash,
                        section_heading=chunk.section_heading,
                        company_name=chunk.company_name,
                        role_title=chunk.role_title,
                        job_type=chunk.job_type,
                        page_number=chunk.page_number
                    ))
                else:
                    # Cache Miss
                    miss_chunks.append(chunk)
                    miss_hashes.append(content_hash)
            
            logger.info(f"Embedding pipeline: Chunks={len(chunks)} | Hits={len(chunks) - len(miss_chunks)} | Misses={len(miss_chunks)}")
            
            # 2. Run model encoding for cache misses in batches
            if miss_chunks:
                for i in range(0, len(miss_chunks), self.batch_size):
                    batch_chunks = miss_chunks[i:i + self.batch_size]
                    batch_hashes = miss_hashes[i:i + self.batch_size]
                    
                    # Bug fixed: instruction prefix must be applied to QUERIES only, not documents.
                    # For BGE models, documents are encoded as plain text.
                    batch_texts = [c.content for c in batch_chunks]
                    
                    # Encode with L2 normalization
                    embeddings = self.model.encode(batch_texts, normalize_embeddings=True)
                    
                    # Store embeddings in SQLite cache & reconstruct EmbeddedChunk list
                    for idx, chunk in enumerate(batch_chunks):
                        emb_val = embeddings[idx]
                        vector = emb_val.tolist() if hasattr(emb_val, 'tolist') else list(emb_val)
                        content_hash = batch_hashes[idx]
                        
                        # Save in DB cache
                        cache_repo.cache_embedding(content_hash, self.model_name, vector)
                        
                        embedded_chunks.append(EmbeddedChunk(
                            chunk_id=chunk.chunk_id,
                            doc_id=chunk.doc_id,
                            chunk_index=chunk.chunk_index,
                            chunk_type=chunk.chunk_type,
                            content=chunk.content,
                            embedding=vector,
                            content_hash=content_hash,
                            section_heading=chunk.section_heading,
                            company_name=chunk.company_name,
                            role_title=chunk.role_title,
                            job_type=chunk.job_type,
                            page_number=chunk.page_number
                        ))
            
            # Re-sort chunks by chunk_index to maintain logical document order
            embedded_chunks.sort(key=lambda c: c.chunk_index)
            
        finally:
            session.close()

        duration = time.time() - start_time
        logger.info(f"Finished embedding document chunks in {duration:.2f} seconds.")
        return embedded_chunks
