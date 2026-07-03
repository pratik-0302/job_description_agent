import re
import logging
from typing import List, Dict, Any, Optional

from src.config import AppConfig
from src.storage.sqlite_manager import SQLiteManager, QueryRepository, JDMetadata
from src.embedding.embedding_pipeline import EmbeddingPipelineModule
from src.vector_db.chroma_manager import ChromaManager, VectorSearchResult
from src.retrieval.intent_detector import IntentDetector
from src.retrieval.result_fusion import ResultFusion, RetrievedDocument

logger = logging.getLogger(__name__)

class QueryFilters:
    def __init__(self):
        self.company_names: List[str] = []
        self.skills: List[str] = []
        self.min_package: Optional[float] = None
        self.max_cgpa_cutoff: Optional[float] = None
        self.locations: List[str] = []
        self.job_type: Optional[str] = None
        self.work_mode: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "company_name": self.company_names[0] if self.company_names else None,
            "skills": self.skills if self.skills else None,
            "min_package": self.min_package,
            "max_cgpa_cutoff": self.max_cgpa_cutoff,
            "locations": self.locations if self.locations else None,
            "job_type": self.job_type,
            "work_mode": self.work_mode
        }


class QueryEntityExtractor:
    @staticmethod
    def extract_entities(query_text: str, known_companies: List[str]) -> QueryFilters:
        filters = QueryFilters()
        q = query_text.lower()
        
        # 1. Company matching (case-insensitive check against known companies in DB)
        for comp in known_companies:
            if re.search(r'\b' + re.escape(comp.lower()) + r'\b', q):
                filters.company_names.append(comp)
                
        # 2. Package extraction (e.g. 10 lpa, 15lakhs, ctc > 8)
        pkg_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lp)', q)
        if pkg_matches:
            filters.min_package = float(pkg_matches[0])
        else:
            # Fallback pattern check for numbers near "package", "ctc" or "salary"
            ctc_near = re.findall(r'(?:package|ctc|salary)\s*(?:of|is|>=|>)?\s*(\d+(?:\.\d+)?)', q)
            if ctc_near:
                filters.min_package = float(ctc_near[0])

        # 3. CGPA cutoff extraction (e.g. cgpa >= 8.0, 7.5 cgpa, cgpa cutoff 6)
        cgpa_matches = re.findall(r'(\d+(?:\.\d+)?)\s*cgpa', q)
        if cgpa_matches:
            filters.max_cgpa_cutoff = float(cgpa_matches[0])
        else:
            cgpa_near = re.findall(r'cgpa\s*(?:cutoff|>=|>|<=|<|:|=)?\s*(\d+(?:\.\d+)?)', q)
            if cgpa_near:
                filters.max_cgpa_cutoff = float(cgpa_near[0])
                
        # 4. Job type extraction
        if "intern" in q:
            filters.job_type = "internship"
        elif "fte" in q or "fulltime" in q or "full-time" in q or "full time" in q:
            filters.job_type = "fte"
            
        # 5. Work mode
        if "remote" in q:
            filters.work_mode = "remote"
        elif "onsite" in q or "on-site" in q or "office" in q:
            filters.work_mode = "on-site"
        elif "hybrid" in q:
            filters.work_mode = "hybrid"

        # 6. Common Tech Skills matching
        common_skills = [
            "python", "java", "c++", "c#", "rust", "javascript", "typescript", "golang",
            "react", "angular", "vue", "django", "flask", "fastapi", "spring", "sql", "nosql",
            "mysql", "postgres", "mongodb", "redis", "aws", "azure", "gcp", "docker", "kubernetes",
            "pytorch", "tensorflow", "opencv", "machine learning", "deep learning", "nlp"
        ]
        for skill in common_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', q):
                filters.skills.append(skill)
                
        # 7. Common Indian Locations matching
        common_locations = [
            "mumbai", "pune", "bangalore", "bengaluru", "hyderabad", "delhi", "noida", 
            "gurgaon", "gurugram", "chennai", "kolkata", "ahmedabad", "bhopal"
        ]
        for loc in common_locations:
            if re.search(r'\b' + re.escape(loc) + r'\b', q):
                # Standardize Bengaluru/Bangalore
                if loc == "bengaluru":
                    filters.locations.append("bangalore")
                else:
                    filters.locations.append(loc)
                    
        return filters


class ContextAssembler:
    @staticmethod
    def assemble(fused_docs: List[RetrievedDocument], max_tokens: int = 6000) -> str:
        blocks = []
        current_estimated_tokens = 0

        for doc in fused_docs:
            meta = doc.metadata
            meta_label = "Unknown"
            if meta:
                # Bug fixed: job_type / company_name / role_title can be None — guard before calling .upper()
                company  = meta.company_name or "Unknown Company"
                role     = meta.role_title   or "Unknown Role"
                jt       = (meta.job_type or "").upper() or "N/A"
                meta_label = f"{company} | {role} | {jt}"
                if meta.package_ctc:
                    meta_label += f" | CTC: {meta.package_ctc} LPA"
                if meta.cgpa_cutoff:
                    meta_label += f" | CGPA: {meta.cgpa_cutoff}"
                if meta.deadline:
                    meta_label += f" | Deadline: {meta.deadline}"
            
            # Combine chunk texts
            chunk_texts = [c.content for c in doc.chunks]
            doc_content = "\n\n".join(chunk_texts)
            
            # Estimate tokens: (label + content) * 1.3 approx
            doc_block = f"[SOURCE: {meta_label}]\nContent:\n{doc_content}\n---"
            est_tokens = int(len(doc_block.split()) * 1.3)
            
            if current_estimated_tokens + est_tokens > max_tokens:
                # If we have at least one block, break to avoid exceeding context limit
                if blocks:
                    break
            
            blocks.append(doc_block)
            current_estimated_tokens += est_tokens
            
        return "\n\n".join(blocks)


class HybridRetrievalModule:
    def __init__(self, cfg: AppConfig, db_manager: SQLiteManager, chroma_manager: ChromaManager, embedding_pipeline: EmbeddingPipelineModule):
        self.cfg = cfg
        self.db_manager = db_manager
        self.chroma_manager = chroma_manager
        self.embedding_pipeline = embedding_pipeline

    def _get_known_companies(self) -> List[str]:
        session = self.db_manager.get_session()
        try:
            results = session.query(JDMetadata.company_name).distinct().all()
            return [r[0] for r in results if r[0]]
        except Exception:
            return []
        finally:
            session.close()

    def retrieve(self, query_text: str, n_results: int = 5) -> Dict[str, Any]:
        logger.info(f"Initiating hybrid retrieval for: '{query_text}'")
        
        # 1. Detect query intent
        intent = IntentDetector.detect_intent(query_text)
        
        # 2. Extract query filters
        known_companies = self._get_known_companies()
        query_filters = QueryEntityExtractor.extract_entities(query_text, known_companies)
        filters_dict = query_filters.to_dict()
        
        # 3. Query SQLite Database
        session = self.db_manager.get_session()
        query_repo = QueryRepository(session)
        sql_docs: List[JDMetadata] = []
        try:
            # If any database filters are extracted, perform SQL query
            has_db_filters = any(v is not None for v in filters_dict.values())
            if has_db_filters:
                sql_docs = query_repo.filter_jobs(filters_dict)
                logger.info(f"SQLite filter returned {len(sql_docs)} matches.")
                
                # Progressive filter relaxation if strict filters return nothing
                if not sql_docs:
                    # Relax skills
                    if filters_dict.get("skills"):
                        logger.info("Relaxing skills filter...")
                        filters_dict["skills"] = None
                        sql_docs = query_repo.filter_jobs(filters_dict)
                    # Relax locations
                    if not sql_docs and filters_dict.get("locations"):
                        logger.info("Relaxing locations filter...")
                        filters_dict["locations"] = None
                        sql_docs = query_repo.filter_jobs(filters_dict)
        except Exception as e:
            logger.error(f"SQL retrieval failed: {e}")
        finally:
            session.close()
            
        # 4. Query Vector DB (ChromaDB)
        vector_results: List[VectorSearchResult] = []
        try:
            # Use embed_query() which correctly prepends the BGE instruction prefix for queries
            query_vector = self.embedding_pipeline.embed_query(query_text)
            
            # Construct Chroma whitelist filter if SQLite returned documents
            where_filter = None
            if sql_docs:
                doc_ids = [d.doc_id for d in sql_docs]
                if len(doc_ids) == 1:
                    where_filter = {"doc_id": doc_ids[0]}
                else:
                    where_filter = {"doc_id": {"$in": doc_ids}}
                    
            v_query_res = self.chroma_manager.query_similarity(
                query_embedding=query_vector,
                n_results=20,  # retrieve a larger pool to support rank fusion
                where_filter=where_filter
            )
            vector_results = v_query_res.results
        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}")
            
        # 5. Result Fusion
        fused_docs = ResultFusion.fuse(sql_docs, vector_results)
        
        # If any fused doc has no vector chunks retrieved (e.g. metadata-only matches),
        # query ChromaDB for chunks of that document to populate text context
        for doc in fused_docs:
            if not doc.chunks:
                try:
                    doc.chunks = self.chroma_manager.get_chunks_by_doc_id(doc.doc_id, limit=5)
                except Exception as e:
                    logger.error(f"Failed to fetch fallback chunks for {doc.doc_id}: {e}")
                    
        # Apply result limit
        fused_docs = fused_docs[:n_results]
        
        # 6. Context Assembly
        context_text = ContextAssembler.assemble(fused_docs)
        
        return {
            "query_text": query_text,
            "intent": intent,
            "filters": filters_dict,
            "fused_documents": fused_docs,
            "context_text": context_text
        }
