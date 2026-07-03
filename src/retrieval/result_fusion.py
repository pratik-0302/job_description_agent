import uuid
from typing import List, Dict, Any, Optional
from src.storage.sqlite_manager import JDMetadata
from src.vector_db.chroma_manager import VectorSearchResult

class RetrievedDocument:
    def __init__(
        self,
        doc_id: str,
        metadata: Optional[JDMetadata],
        chunks: List[VectorSearchResult],
        rrf_score: float,
        retrieval_source: str  # "metadata_only", "semantic_only", "both"
    ):
        self.doc_id = doc_id
        self.metadata = metadata
        self.chunks = chunks
        self.rrf_score = rrf_score
        self.retrieval_source = retrieval_source

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            # Bug fixed: was "ctc_pkg" — renamed to "package_ctc" for consistency
            "metadata": {
                "company_name": self.metadata.company_name,
                "role_title":   self.metadata.role_title,
                "job_type":     self.metadata.job_type,
                "package_ctc":  self.metadata.package_ctc,
                "cgpa_cutoff":  self.metadata.cgpa_cutoff,
                "deadline":     self.metadata.deadline,
            } if self.metadata else None,
            "chunks": [c.to_dict() for c in self.chunks],
            "rrf_score": self.rrf_score,
            "retrieval_source": self.retrieval_source,
        }


class ResultFusion:
    @staticmethod
    def fuse(metadata_results: List[JDMetadata], vector_results: List[VectorSearchResult]) -> List[RetrievedDocument]:
        # Maps doc_id to its rank in SQL metadata search (1-based)
        sql_ranks: Dict[str, int] = {}
        for idx, item in enumerate(metadata_results):
            sql_ranks[item.doc_id] = idx + 1
            
        # Maps doc_id to its highest rank in vector search (1-based)
        vec_ranks: Dict[str, int] = {}
        for idx, item in enumerate(vector_results):
            if item.doc_id not in vec_ranks:
                vec_ranks[item.doc_id] = idx + 1

        # Combine all unique doc_ids
        all_doc_ids = set(sql_ranks.keys()).union(set(vec_ranks.keys()))
        
        fused_docs: List[RetrievedDocument] = []
        
        # SQL Map for lookup
        sql_map = {m.doc_id: m for m in metadata_results}
        
        # Group chunks by doc_id
        chunks_by_doc: Dict[str, List[VectorSearchResult]] = {}
        for chunk in vector_results:
            chunks_by_doc.setdefault(chunk.doc_id, []).append(chunk)
            
        for doc_id in all_doc_ids:
            score_sql = 0.0
            score_vec = 0.0
            
            in_sql = doc_id in sql_ranks
            in_vec = doc_id in vec_ranks
            
            if in_sql:
                score_sql = 1.0 / (60.0 + sql_ranks[doc_id])
            if in_vec:
                score_vec = 1.0 / (60.0 + vec_ranks[doc_id])
                
            rrf_score = score_sql + score_vec
            
            # Determine source
            if in_sql and in_vec:
                source = "both"
            elif in_sql:
                source = "metadata_only"
            else:
                source = "semantic_only"
                
            # Get metadata: lookup in sql_map first, otherwise fallback to the metadata in the vector chunk
            metadata = None
            if in_sql:
                metadata = sql_map[doc_id]
            elif in_vec and chunks_by_doc[doc_id]:
                # Construct a mock JDMetadata from vector chunk metadata fields
                chunk_meta = chunks_by_doc[doc_id][0].metadata
                # Bug fixed: 0.0 defaults for numeric fields caused false data; use None instead
                metadata = JDMetadata(
                    metadata_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    company_name=chunk_meta.get("company_name"),
                    role_title=chunk_meta.get("role_title"),
                    job_type=chunk_meta.get("job_type"),
                    package_ctc=chunk_meta.get("package_ctc"),
                    cgpa_cutoff=chunk_meta.get("cgpa_cutoff"),
                    deadline=chunk_meta.get("deadline"),
                )
                
            doc_chunks = chunks_by_doc.get(doc_id, [])
            
            fused_docs.append(RetrievedDocument(
                doc_id=doc_id,
                metadata=metadata,
                chunks=doc_chunks,
                rrf_score=rrf_score,
                retrieval_source=source
            ))
            
        # Sort by RRF score descending
        fused_docs.sort(key=lambda d: d.rrf_score, reverse=True)
        return fused_docs
