import os
import logging
import time
from typing import List, Dict, Optional, Any
import chromadb
import uuid

from src.embedding.embedding_pipeline import EmbeddedChunk
from src.config import AppConfig

logger = logging.getLogger(__name__)

class VectorSearchResult:
    def __init__(
        self,
        chunk_id: str,
        doc_id: str,
        content: str,
        distance: float,
        similarity_score: float,
        metadata: Dict[str, Any]
    ):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.content = content
        self.distance = distance
        self.similarity_score = similarity_score
        self.metadata = metadata

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "content": self.content,
            "distance": self.distance,
            "similarity_score": self.similarity_score,
            "metadata": self.metadata
        }


class VectorQueryResult:
    def __init__(self, results: List[VectorSearchResult], query_time_ms: int, total_found: int):
        self.results = results
        self.query_time_ms = query_time_ms
        self.total_found = total_found

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "query_time_ms": self.query_time_ms,
            "total_found": self.total_found
        }


class ChromaManager:
    def __init__(self, cfg: AppConfig):
        self.chroma_path = os.path.abspath(cfg.paths.chroma_db)
        os.makedirs(self.chroma_path, exist_ok=True)
        
        logger.info(f"Initializing ChromaDB Client at: {self.chroma_path}")
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        
        # Initialize or fetch target collection with Cosine distance metric
        self.collection_name = "jd_chunks"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Connected to ChromaDB collection: '{self.collection_name}'")

    def upsert_chunks(self, embedded_chunks: List[EmbeddedChunk]) -> bool:
        if not embedded_chunks:
            return True
            
        start_time = time.time()
        logger.info(f"ChromaDB: Upserting {len(embedded_chunks)} chunks to vector index...")
        
        # Batch size for upserts (ChromaDB recommends up to 500 elements)
        batch_size = 200
        
        try:
            for i in range(0, len(embedded_chunks), batch_size):
                batch = embedded_chunks[i:i + batch_size]
                
                ids = [c.chunk_id for c in batch]
                embeddings = [c.embedding for c in batch]
                documents = [c.content for c in batch]
                
                # Metadata dictionary creation
                metadatas = []
                for c in batch:
                    meta = {
                        "doc_id": c.doc_id,
                        "chunk_index": c.chunk_index,
                        "chunk_type": c.chunk_type,
                        "content_hash": c.content_hash
                    }
                    if c.section_heading:
                        meta["section_heading"] = c.section_heading
                    if c.page_number is not None:
                        meta["page_number"] = c.page_number
                    if c.company_name:
                        meta["company_name"] = c.company_name
                    if c.role_title:
                        meta["role_title"] = c.role_title
                    if c.job_type:
                        meta["job_type"] = c.job_type
                    metadatas.append(meta)

                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
                
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Upserted {len(embedded_chunks)} vectors in {duration_ms} ms.")
            return True
        except Exception as e:
            logger.error(f"ChromaDB upsert failed: {e}")
            return False

    def query_similarity(self, query_embedding: List[float], n_results: int = 5, where_filter: Optional[Dict[str, Any]] = None) -> VectorQueryResult:
        start_time = time.time()
        
        # Run query
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["metadatas", "documents", "distances"]
            )
            
            search_results: List[VectorSearchResult] = []
            
            # Format outputs
            if results and results.get("ids") and len(results["ids"][0]) > 0:
                ids = results["ids"][0]
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]
                
                for idx, c_id in enumerate(ids):
                    dist = float(distances[idx])
                    # Cosine distance ranges [0.0, 2.0] where 0.0 is identical
                    similarity = 1.0 - (dist / 2.0)
                    
                    search_results.append(VectorSearchResult(
                        chunk_id=c_id,
                        doc_id=metadatas[idx].get("doc_id", ""),
                        content=documents[idx],
                        distance=dist,
                        similarity_score=similarity,
                        metadata=metadatas[idx]
                    ))
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Vector search returned {len(search_results)} hits in {duration_ms} ms.")
            return VectorQueryResult(
                results=search_results,
                query_time_ms=duration_ms,
                total_found=len(search_results)
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return VectorQueryResult(results=[], query_time_ms=0, total_found=0)

    def get_chunks_by_doc_id(self, doc_id: str, limit: int = 10) -> List[VectorSearchResult]:
        """Fetch stored chunks for a document directly — no similarity search needed."""
        try:
            res = self.collection.get(
                where={"doc_id": doc_id},
                limit=limit,
                include=["metadatas", "documents"],
            )
            results: List[VectorSearchResult] = []
            if res and res.get("ids"):
                for i, cid in enumerate(res["ids"]):
                    results.append(VectorSearchResult(
                        chunk_id=cid,
                        doc_id=doc_id,
                        content=res["documents"][i],
                        distance=0.0,
                        similarity_score=1.0,
                        metadata=res["metadatas"][i],
                    ))
            return results
        except Exception as e:
            logger.error(f"get_chunks_by_doc_id failed for {doc_id}: {e}")
            return []

    def delete_document_chunks(self, doc_id: str) -> bool:
        logger.info(f"ChromaDB: Deleting all vector chunks for doc_id: {doc_id}")
        try:
            self.collection.delete(where={"doc_id": doc_id})
            return True
        except Exception as e:
            logger.error(f"ChromaDB chunk deletion failed for doc_id {doc_id}: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_chunks": count,
                "distance_space": self.collection.metadata.get("hnsw:space", "cosine") if self.collection.metadata else "cosine"
            }
        except Exception as e:
            logger.error(f"Failed to fetch collection stats: {e}")
            return {"total_chunks": 0}
