import os
import time
import hashlib
import shutil
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from src.config import load_config, AppConfig
from src.storage.sqlite_manager import SQLiteManager, Document, JDMetadata, JDLocation, JDBranch, JDSkill, QueryRepository
from src.embedding.embedding_pipeline import EmbeddingPipelineModule
from src.vector_db.chroma_manager import ChromaManager
from src.retrieval.hybrid_retriever import HybridRetrievalModule
from src.llm.ollama_client import OllamaClient
from src.agents.agent_graph import GraphBuilder, AgentState
# pyrefly: ignore [missing-import]
from langgraph.checkpoint.sqlite import SqliteSaver
import queue
from src.ingestion.discovery import DocumentDiscoveryModule
from src.ingestion.automatic_indexer import AutomaticIndexingModule
from src.retrieval.query_cache import QueryResultCache

logger = logging.getLogger(__name__)

# Lifespan Context Manager to handle startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FastAPI Placement Intelligence Service...")
    
    # Load configuration
    cfg = load_config("config.yaml")
    app.state.cfg = cfg
    
    # Initialize databases
    db_manager = SQLiteManager(cfg.paths.sqlite_db)
    app.state.db_manager = db_manager
    
    chroma_manager = ChromaManager(cfg)
    app.state.chroma_manager = chroma_manager
    
    # Initialize pipelines
    embedding_pipeline = EmbeddingPipelineModule(cfg, db_manager)
    app.state.embedding_pipeline = embedding_pipeline
    
    hybrid_retriever = HybridRetrievalModule(cfg, db_manager, chroma_manager, embedding_pipeline)
    app.state.hybrid_retriever = hybrid_retriever
    
    ollama_client = OllamaClient(cfg)
    app.state.ollama_client = ollama_client
    
    # Compile Agent graph with persistent checkpointer
    memory_db_path = os.path.join(os.path.dirname(cfg.paths.sqlite_db), "checkpoints.db")
    os.makedirs(os.path.dirname(memory_db_path), exist_ok=True)
    
    with SqliteSaver.from_conn_string(memory_db_path) as checkpointer:
        builder = GraphBuilder(cfg, db_manager, chroma_manager, hybrid_retriever, ollama_client)
        compiled_graph = builder.build_graph(checkpointer=checkpointer)
        app.state.graph = compiled_graph
        app.state.checkpointer = checkpointer
        
        # Initialize caching structures
        query_cache = QueryResultCache(max_size=100, ttl_seconds=300.0)
        analytics_cache = QueryResultCache(max_size=10, ttl_seconds=86400.0)
        app.state.query_cache = query_cache
        app.state.analytics_cache = analytics_cache

        # Initialize background discovery and indexing workers
        event_queue = queue.Queue()
        discovery_module = DocumentDiscoveryModule(cfg.paths.jd_files, db_manager, event_queue)
        indexing_module = AutomaticIndexingModule(
            cfg, db_manager, chroma_manager, embedding_pipeline, event_queue,
            query_cache=query_cache, analytics_cache=analytics_cache
        )
        
        app.state.discovery_module = discovery_module
        app.state.indexing_module = indexing_module
        
        # Start background execution
        discovery_module.start()
        indexing_module.start()
        
        logger.info("Placement Intelligence backend startup sequence completed successfully.")
        yield
        
        logger.info("Shutting down backend service layers...")
        discovery_module.stop()
        indexing_module.stop()
        db_manager.engine.dispose()

app = FastAPI(
    title="AI Placement Intelligence backend",
    description="REST API backend exposing placement semantic search, recommendations, comparisons, and analytics.",
    lifespan=lifespan
)

# Register CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local Streamlit connectivity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- REQUEST / RESPONSE DTOS (Pydantic Models) ---

class QueryRequestDTO(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=2000)
    session_id: str

class QueryResponseDTO(BaseModel):
    response_id: str
    agent_type: str
    response_text: str
    structured_data: Optional[Dict[str, Any]] = None
    source_documents: List[Dict[str, Any]] = []
    follow_up_suggestions: List[str] = []
    confidence: float
    generation_time_ms: int

class StudentProfileDTO(BaseModel):
    cgpa: Optional[float] = None
    branch: Optional[str] = None
    skills: Optional[List[str]] = []
    preferred_locations: Optional[List[str]] = []
    preferred_job_type: Optional[str] = None

class DocumentSummaryDTO(BaseModel):
    doc_id: str
    company_name: str
    role_title: str
    job_type: str
    package_ctc: Optional[float] = None
    cgpa_cutoff: Optional[float] = None
    deadline: Optional[str] = None

class SystemHealthDTO(BaseModel):
    status: str
    ollama_status: str
    chroma_status: str
    sqlite_status: str
    indexed_document_count: int
    embedding_model: str


# --- API ENDPOINTS ---

@app.get("/api/index/health", response_model=SystemHealthDTO)
def get_system_health(request: Request):
    db_manager = request.app.state.db_manager
    chroma_manager = request.app.state.chroma_manager
    ollama_client = request.app.state.ollama_client
    
    # 1. Check SQLite
    sqlite_status = "down"
    indexed_count = 0
    try:
        session = db_manager.get_session()
        indexed_count = session.query(JDMetadata).count()
        sqlite_status = "up"
        session.close()
    except Exception:
        pass
        
    # 2. Check Chroma
    chroma_status = "down"
    try:
        chroma_manager.get_collection_stats()
        chroma_status = "up"
    except Exception:
        pass
        
    # 3. Check Ollama
    ollama_status = "down"
    try:
        if ollama_client.health_check():
            ollama_status = "up"
    except Exception:
        pass
        
    overall_status = "healthy"
    if sqlite_status == "down" or chroma_status == "down":
        overall_status = "unhealthy"
    elif ollama_status == "down":
        overall_status = "degraded"
        
    return SystemHealthDTO(
        status=overall_status,
        ollama_status=ollama_status,
        chroma_status=chroma_status,
        sqlite_status=sqlite_status,
        indexed_document_count=indexed_count,
        embedding_model=request.app.state.cfg.embedding.model
    )


@app.get("/api/index/status")
def get_indexing_status(request: Request):
    return request.app.state.indexing_module.get_status()


@app.post("/api/index/scan")
def trigger_manual_scan(request: Request):
    request.app.state.discovery_module.force_rescan()
    return {"status": "success", "message": "Manual filesystem rescan initiated successfully."}


@app.post("/api/query", response_model=QueryResponseDTO)
def submit_query(request: Request, payload: QueryRequestDTO):
    # Construct distinct session key
    cache_key = f"{payload.session_id}:{payload.query_text}"
    cached_val = request.app.state.query_cache.get(cache_key)
    if cached_val:
        logger.info("Serving query response from Query Cache.")
        return QueryResponseDTO(**cached_val)

    graph = request.app.state.graph
    start_time = time.time()
    
    initial_state = {
        "query_text": payload.query_text,
        "resolved_query": "",
        "intent": ""
    }
    
    config = {"configurable": {"thread_id": payload.session_id}}
    
    try:
        final_state = graph.invoke(initial_state, config=config)
        duration_ms = int((time.time() - start_time) * 1000)
        
        resp_data = final_state.get("final_response")
        if not resp_data:
            raise HTTPException(status_code=500, detail="Graph response format failed to compile.")
            
        resp_data["generation_time_ms"] = duration_ms
        request.app.state.query_cache.set(cache_key, resp_data)
        return QueryResponseDTO(**resp_data)
        
    except Exception as e:
        logger.error(f"Graph execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")


@app.get("/api/documents")
def list_documents(request: Request):
    """Return all indexed JDs in a format the React UI (JDCard) can consume directly."""
    db_manager = request.app.state.db_manager
    session = db_manager.get_session()
    try:
        # JOIN Document → JDMetadata so we get status + file_name alongside metadata
        rows = (
            session.query(Document, JDMetadata)
            .outerjoin(JDMetadata, Document.doc_id == JDMetadata.doc_id)
            .filter(Document.status == "indexed")
            .all()
        )

        result = []
        for doc, jd in rows:
            # Fetch skills, locations, branches for this doc
            skills   = [s.skill for s in session.query(JDSkill).filter(JDSkill.doc_id == doc.doc_id).all()]
            locs     = [l.location for l in session.query(JDLocation).filter(JDLocation.doc_id == doc.doc_id).all()]
            branches = [b.branch_code for b in session.query(JDBranch).filter(JDBranch.doc_id == doc.doc_id).all()]

            result.append({
                "doc_id":    doc.doc_id,
                "file_name": doc.file_name,
                "status":    doc.status,
                "metadata": {
                    "company_name":        jd.company_name        if jd else None,
                    "job_title":           jd.role_title          if jd else None,
                    "job_type":            jd.job_type            if jd else None,
                    "package_ctc":         jd.package_ctc         if jd else None,
                    "min_cgpa":            jd.cgpa_cutoff         if jd else None,
                    "application_deadline":jd.deadline            if jd else None,
                    "work_mode":           jd.work_mode           if jd else None,
                    "skills_required":     skills,
                    "location":            locs,
                    "eligible_branches":   branches,
                } if jd else {},
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.get("/api/documents/{doc_id}")
def get_document_details(request: Request, doc_id: str):
    db_manager = request.app.state.db_manager
    session = db_manager.get_session()
    try:
        jd = session.query(JDMetadata).filter(JDMetadata.doc_id == doc_id).first()
        if not jd:
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Extract related locations, skills, branches
        locs = [l.location for l in session.query(JDLocation).filter(JDLocation.doc_id == doc_id).all()]
        skills = [s.skill for s in session.query(JDSkill).filter(JDSkill.doc_id == doc_id).all()]
        branches = [b.branch_code for b in session.query(JDBranch).filter(JDBranch.doc_id == doc_id).all()]
        
        return {
            "doc_id": jd.doc_id,
            "company_name": jd.company_name,
            "role_title": jd.role_title,
            "job_type": jd.job_type,
            "package_ctc": jd.package_ctc,
            "cgpa_cutoff": jd.cgpa_cutoff,
            "deadline": jd.deadline,
            "work_mode": jd.work_mode,
            "locations": locs,
            "skills": skills,
            "branches": branches
        }
    finally:
        session.close()


@app.get("/api/analytics/summary")
def get_analytics_summary(request: Request):
    cached_val = request.app.state.analytics_cache.get("summary")
    if cached_val:
        logger.info("Serving analytics from Analytics Cache.")
        return cached_val

    db_manager = request.app.state.db_manager
    session = db_manager.get_session()
    try:
        from sqlalchemy import func  # pyrefly: ignore [missing-import]

        total_docs    = session.query(func.count(Document.doc_id)).scalar() or 0
        indexed_count = session.query(func.count(Document.doc_id)).filter(Document.status == "indexed").scalar() or 0
        company_count = session.query(func.count(func.distinct(JDMetadata.company_name))).scalar() or 0
        avg_ctc       = session.query(func.avg(JDMetadata.package_ctc)).scalar()
        avg_ctc       = round(float(avg_ctc), 2) if avg_ctc else None

        # Job type breakdown
        jtype_raw = (
            session.query(JDMetadata.job_type, func.count(JDMetadata.metadata_id))
            .filter(JDMetadata.job_type != None)  # noqa: E711
            .group_by(JDMetadata.job_type)
            .all()
        )
        job_type_breakdown = {jt.upper() if jt else "Unknown": c for jt, c in jtype_raw}

        # Skill frequency (all skills, not just top-10, so React can sort/filter)
        skills_raw = (
            session.query(JDSkill.skill, func.count(JDSkill.id))
            .group_by(JDSkill.skill)
            .order_by(func.count(JDSkill.id).desc())
            .limit(30)
            .all()
        )
        skills_frequency = {s: c for s, c in skills_raw}

        # Location distribution
        locs_raw = (
            session.query(JDLocation.location, func.count(JDLocation.id))
            .group_by(JDLocation.location)
            .all()
        )
        location_distribution = {l: c for l, c in locs_raw}

        # Recently indexed documents
        recent_docs_raw = (
            session.query(Document, JDMetadata)
            .outerjoin(JDMetadata, Document.doc_id == JDMetadata.doc_id)
            .filter(Document.status == "indexed")
            .order_by(Document.indexed_at.desc())
            .limit(8)
            .all()
        )
        recent_documents = [
            {
                "doc_id":    doc.doc_id,
                "file_name": doc.file_name,
                "company":   jd.company_name if jd else None,
                "title":     jd.role_title   if jd else None,
            }
            for doc, jd in recent_docs_raw
        ]

        res = {
            "total_documents":     total_docs,
            "indexed_count":       indexed_count,
            "company_count":       company_count,
            "avg_ctc":             avg_ctc,
            "job_type_breakdown":  job_type_breakdown,
            "skills_frequency":    skills_frequency,
            "location_distribution": location_distribution,
            "recent_documents":    recent_documents,
        }
        request.app.state.analytics_cache.set("summary", res)
        return res
    finally:
        session.close()


@app.put("/api/profile/{session_id}")
def update_profile(request: Request, session_id: str, payload: StudentProfileDTO):
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": session_id}}
    
    # Convert DTO to dict profile representation
    profile = {
        "cgpa": payload.cgpa,
        "branch": payload.branch,
        "skills": payload.skills,
        "preferred_locations": payload.preferred_locations,
        "preferred_job_type": payload.preferred_job_type
    }
    
    try:
        # Update the profile in the persisted checkpoint state without triggering a full graph run
        graph.update_state(config, {"user_profile": profile})
        return {"status": "success", "message": "Profile preferences updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile memory state: {str(e)}")


@app.post("/api/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """
    Upload a JD (PDF or DOCX).
    - If the file is new → save it to jd_files/ and queue it for full indexing.
    - If it already exists in the database → return its existing metadata without re-indexing.
    """
    allowed = {".pdf", ".docx"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Upload PDF or DOCX only.")

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    db_manager = request.app.state.db_manager
    session = db_manager.get_session()
    try:
        # Check by filename
        existing_by_name = session.query(Document).filter(Document.file_name == file.filename).first()
        if existing_by_name:
            jd = session.query(JDMetadata).filter(JDMetadata.doc_id == existing_by_name.doc_id).first()
            return {
                "status": "already_exists",
                "doc_id": existing_by_name.doc_id,
                "file_name": file.filename,
                "indexed_status": existing_by_name.status,
                "company": jd.company_name if jd else None,
                "role":    jd.role_title   if jd else None,
                "message": f"'{file.filename}' is already in your database as '{jd.company_name or 'Unknown'} — {jd.role_title or 'Unknown role'}'. No duplicate created.",
            }

        # Check by content hash (same file with different name)
        existing_by_hash = session.query(Document).filter(Document.content_hash == content_hash).first()
        if existing_by_hash:
            jd = session.query(JDMetadata).filter(JDMetadata.doc_id == existing_by_hash.doc_id).first()
            return {
                "status": "already_exists",
                "doc_id": existing_by_hash.doc_id,
                "file_name": existing_by_hash.file_name,
                "indexed_status": existing_by_hash.status,
                "company": jd.company_name if jd else None,
                "role":    jd.role_title   if jd else None,
                "message": f"This file already exists as '{existing_by_hash.file_name}' ({jd.company_name or 'Unknown'}). No duplicate created.",
            }
    finally:
        session.close()

    # New file — save to jd_files/ and trigger rescan
    cfg = request.app.state.cfg
    save_dir = cfg.paths.jd_files
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, file.filename)
    with open(save_path, "wb") as f:
        f.write(content)

    request.app.state.discovery_module.force_rescan()
    request.app.state.analytics_cache.clear()

    logger.info(f"Uploaded new document '{file.filename}' to {save_path}, rescan triggered.")
    return {
        "status": "queued",
        "file_name": file.filename,
        "message": f"'{file.filename}' uploaded successfully and queued for indexing. It will appear in Browse JDs once processing is complete (usually 30–60 seconds).",
    }
