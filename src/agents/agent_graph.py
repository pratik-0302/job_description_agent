import logging
import uuid
import datetime
from typing import TypedDict, List, Dict, Any, Optional, Tuple

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.config import AppConfig
from src.storage.sqlite_manager import SQLiteManager, JDMetadata, JDSkill, JDLocation, JDBranch, QueryRepository
from src.embedding.embedding_pipeline import EmbeddingPipelineModule
from src.vector_db.chroma_manager import ChromaManager, VectorSearchResult
from src.retrieval.intent_detector import IntentDetector
from src.retrieval.result_fusion import ResultFusion, RetrievedDocument
from src.retrieval.hybrid_retriever import QueryFilters, QueryEntityExtractor, ContextAssembler, HybridRetrievalModule
from src.llm.prompt_builder import PromptBuilder
from src.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# Define LangGraph AgentState TypedDict
class AgentState(TypedDict, total=False):
    query_text: str
    resolved_query: str
    intent: str
    metadata_filters: dict
    retrieved_chunks: List[dict]
    source_documents: List[dict]
    response_text: str
    structured_data: Optional[dict]
    follow_up_suggestions: List[str]
    user_profile: dict  # Keys: cgpa, branch, skills, preferred_locations, preferred_job_type, min_package
    turn_history: List[dict]
    interacted_doc_ids: List[str]
    final_response: Optional[dict]
    error: Optional[str]


class AgentResponse:
    def __init__(
        self,
        response_id: str,
        agent_type: str,
        response_text: str,
        structured_data: Optional[dict],
        source_documents: List[dict],
        follow_up_suggestions: List[str],
        confidence: float,
        generation_time_ms: int
    ):
        self.response_id = response_id
        self.agent_type = agent_type
        self.response_text = response_text
        self.structured_data = structured_data
        self.source_documents = source_documents
        self.follow_up_suggestions = follow_up_suggestions
        self.confidence = confidence
        self.generation_time_ms = generation_time_ms

    def to_dict(self) -> dict:
        return {
            "response_id": self.response_id,
            "agent_type": self.agent_type,
            "response_text": self.response_text,
            "structured_data": self.structured_data,
            "source_documents": self.source_documents,
            "follow_up_suggestions": self.follow_up_suggestions,
            "confidence": self.confidence,
            "generation_time_ms": self.generation_time_ms
        }


class GraphBuilder:
    def __init__(
        self, 
        cfg: AppConfig, 
        db_manager: SQLiteManager, 
        chroma_manager: ChromaManager, 
        hybrid_retriever: HybridRetrievalModule, 
        ollama_client: OllamaClient
    ):
        self.cfg = cfg
        self.db_manager = db_manager
        self.chroma_manager = chroma_manager
        self.hybrid_retriever = hybrid_retriever
        self.ollama_client = ollama_client

    def _get_known_companies(self) -> List[str]:
        session = self.db_manager.get_session()
        try:
            results = session.query(JDMetadata.company_name).distinct().all()
            return [r[0] for r in results if r[0]]
        except Exception:
            return []
        finally:
            session.close()

    # --- GRAPH NODES ---

    def intent_router_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: IntentRouter")
        intent = IntentDetector.detect_intent(state.get("query_text", ""))
        return {"intent": intent}

    def followup_resolver_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: FollowupResolver")
        query = state.get("query_text", "")
        resolved = query
        
        # Pull last mentioned company from history
        last_company = None
        for turn in reversed(state.get("turn_history", [])):
            doc_cits = turn.get("doc_ids_referenced", [])
            if doc_cits:
                # Retrieve company details from turn metadata context if stored
                last_company = turn.get("company_name")
                if last_company:
                    break
        
        # Expand query if it contains references
        references = ["their", "it", "them", "that", "this company", "eligibility", "deadline", "salary", "stipend"]
        if last_company and any(re_word in query.lower() for re_word in references):
            resolved = f"{query} for {last_company}"
            logger.info(f"Resolved follow-up query to: '{resolved}'")
            
        # Re-run intent detection on the expanded query
        new_intent = IntentDetector.detect_intent(resolved)
        if new_intent == "followup":
            new_intent = "search"
            
        return {"resolved_query": resolved, "intent": new_intent}

    def search_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: SearchAgent")
        query = state.get("resolved_query") or state.get("query_text", "")
        
        # Execute hybrid retrieval
        retrieval_res = self.hybrid_retriever.retrieve(query, n_results=5)
        
        sys_p, user_p = PromptBuilder.build_prompts("search", query, retrieval_res["context_text"])
        
        try:
            llm_res = self.ollama_client.generate(sys_p, user_p)
            response_text = llm_res["response_text"]
        except Exception as e:
            logger.error(f"Search LLM call failed: {e}")
            response_text = "I'm sorry, I'm unable to connect to the LLM generation service at this moment."
            
        source_docs = [d.to_dict() for d in retrieval_res["fused_documents"]]
        
        return {
            "response_text": response_text,
            "source_documents": source_docs,
            "retrieved_chunks": [c.to_dict() for d in retrieval_res["fused_documents"] for c in d.chunks]
        }

    def recommendation_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: RecommendationAgent")
        query = state.get("resolved_query") or state.get("query_text", "")
        profile = state.get("user_profile", {})
        
        # Build strict SQL filters based on student eligibility criteria
        filters = {}
        if profile.get("cgpa") is not None:
            filters["max_cgpa_cutoff"] = profile["cgpa"]
        if profile.get("branch"):
            filters["branches"] = [profile["branch"]]
        if profile.get("skills"):
            filters["skills"] = profile["skills"]
            
        session = self.db_manager.get_session()
        query_repo = QueryRepository(session)
        
        try:
            eligible_jds = query_repo.filter_jobs(filters)
            logger.info(f"Recommendation eligibility: {len(eligible_jds)} JDs pass criteria filters.")
        except Exception as e:
            logger.error(f"Recommendation pre-filter query failed: {e}")
            eligible_jds = []
        finally:
            session.close()

        # Narrow down vector search based on eligible JDs whitelists
        where_filter = None
        if eligible_jds:
            doc_ids = [j.doc_id for j in eligible_jds]
            if len(doc_ids) == 1:
                where_filter = {"doc_id": doc_ids[0]}
            else:
                where_filter = {"doc_id": {"$in": doc_ids}}
                
        # Use embed_query() so the instruction prefix is correctly applied
        query_vector = self.hybrid_retriever.embedding_pipeline.embed_query(query)
        
        vector_res = self.chroma_manager.query_similarity(query_vector, n_results=10, where_filter=where_filter)
        fused = ResultFusion.fuse(eligible_jds, vector_res.results)[:5]
        
        context_text = ContextAssembler.assemble(fused)
        sys_p, user_p = PromptBuilder.build_prompts("recommend", query, context_text)
        
        try:
            llm_res = self.ollama_client.generate(sys_p, user_p)
            response_text = llm_res["response_text"]
        except Exception as e:
            logger.error(f"Recommend LLM call failed: {e}")
            response_text = "I'm sorry, I'm unable to process recommendations at this moment."
            
        return {
            "response_text": response_text,
            "source_documents": [d.to_dict() for d in fused]
        }

    def comparison_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: ComparisonAgent")
        query = state.get("resolved_query") or state.get("query_text", "")
        
        # 1. Parse mentioned companies
        known_companies = self._get_known_companies()
        query_filters = QueryEntityExtractor.extract_entities(query, known_companies)
        
        session = self.db_manager.get_session()
        query_repo = QueryRepository(session)
        
        companies_metadata: List[JDMetadata] = []
        try:
            for comp in query_filters.company_names:
                jds = query_repo.filter_jobs({"company_name": comp})
                if jds:
                    companies_metadata.append(jds[0])
        finally:
            session.close()
            
        # If fewer than 2 companies are detected, run basic query fallback
        if len(companies_metadata) < 2:
            retrieval_res = self.hybrid_retriever.retrieve(query, n_results=5)
            sys_p, user_p = PromptBuilder.build_prompts("search", query, retrieval_res["context_text"])
            llm_res = self.ollama_client.generate(sys_p, user_p)
            return {
                "response_text": llm_res["response_text"] + "\n\n*Note: Could not identify multiple companies for explicit comparison matrix.*",
                "source_documents": [d.to_dict() for d in retrieval_res["fused_documents"]]
            }
            
        # 2. Build structured comparison matrix
        structured_comparison = {}
        context_blocks = []
        
        for jd in companies_metadata:
            structured_comparison[jd.company_name] = {
                "role_title": jd.role_title,
                "job_type": jd.job_type,
                "package_ctc": jd.package_ctc,
                "cgpa_cutoff": jd.cgpa_cutoff,
                "deadline": jd.deadline,
                "work_mode": jd.work_mode
            }
            
            # Bug fixed: was using [0.0]*384 zero-vector (meaningless similarity).
            # Use get_chunks_by_doc_id() for direct document chunk retrieval.
            doc_chunks = self.chroma_manager.get_chunks_by_doc_id(jd.doc_id, limit=5)
            chunks_text = "\n".join(c.content for c in doc_chunks)
            context_blocks.append(f"[SOURCE: {jd.company_name or 'Unknown'}]\n{chunks_text}")
            
        context_text = "\n\n---\n\n".join(context_blocks)
        sys_p, user_p = PromptBuilder.build_prompts("compare", query, context_text)
        
        try:
            llm_res = self.ollama_client.generate(sys_p, user_p)
            response_text = llm_res["response_text"]
        except Exception as e:
            logger.error(f"Compare LLM call failed: {e}")
            response_text = "Comparison details failed to generate."
            
        # 3. Post-LLM Fact Verification Check
        # Search the generated text for any numerical hallucination discrepancies
        corrections = []
        for comp, data in structured_comparison.items():
            package_val = data["package_ctc"]
            cgpa_val = data["cgpa_cutoff"]
            
            # Simple check if correct numbers exist in text
            if package_val and str(package_val) not in response_text:
                corrections.append(f"- {comp}: CTC Package is exactly {package_val} LPA")
            if cgpa_val and str(cgpa_val) not in response_text:
                corrections.append(f"- {comp}: CGPA Cutoff is exactly {cgpa_val}")
                
        if corrections:
            response_text += "\n\n### Factual Metadata Verification:\n" + "\n".join(corrections)
            
        return {
            "response_text": response_text,
            "structured_data": {"matrix": structured_comparison},
            "source_documents": [{"doc_id": j.doc_id, "company_name": j.company_name, "role_title": j.role_title} for j in companies_metadata]
        }

    def analytics_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: AnalyticsAgent")
        query = state.get("resolved_query") or state.get("query_text", "")
        
        # Calculate statistics directly from relational SQLite
        session = self.db_manager.get_session()
        try:
            from sqlalchemy import func
            avg_ctc = session.query(func.avg(JDMetadata.package_ctc)).scalar() or 0.0
            max_ctc = session.query(func.max(JDMetadata.package_ctc)).scalar() or 0.0
            count_jds = session.query(func.count(JDMetadata.metadata_id)).scalar() or 0
            
            # Location counts
            locs_raw = session.query(JDLocation.location, func.count(JDLocation.id)).group_by(JDLocation.location).all()
            loc_distribution = {loc: count for loc, count in locs_raw}
        finally:
            session.close()
            
        # Build precise narrative context for the LLM
        analytics_text = (
            f"Placement Repository Analytics Overview:\n"
            f"- Total Job Descriptions: {count_jds}\n"
            f"- Average CTC Package: {avg_ctc:.2f} LPA\n"
            f"- Maximum CTC Package: {max_ctc:.2f} LPA\n"
            f"- Geographic Distribution: " + ", ".join([f"{l} ({c} jobs)" for l, c in loc_distribution.items()])
        )
        
        sys_p, user_p = PromptBuilder.build_prompts("analytics", query, analytics_text)
        
        try:
            llm_res = self.ollama_client.generate(sys_p, user_p)
            response_text = llm_res["response_text"]
        except Exception as e:
            logger.error(f"Analytics LLM call failed: {e}")
            response_text = "Analytics interpretations failed to generate."
            
        structured_data = {
            "total_jds": count_jds,
            "avg_ctc": avg_ctc,
            "max_ctc": max_ctc,
            "location_distribution": loc_distribution
        }
        
        return {
            "response_text": response_text,
            "structured_data": structured_data
        }

    def summary_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: SummaryAgent")
        query = state.get("resolved_query") or state.get("query_text", "")
        
        # Identify the matching company name
        known_companies = self._get_known_companies()
        query_filters = QueryEntityExtractor.extract_entities(query, known_companies)
        company = query_filters.company_names[0] if query_filters.company_names else None
        
        session = self.db_manager.get_session()
        query_repo = QueryRepository(session)
        jd = None
        try:
            if company:
                jds = query_repo.filter_jobs({"company_name": company})
                if jds:
                    jd = jds[0]
        finally:
            session.close()
            
        if not jd:
            # If no target company, fallback to general search summary
            retrieval_res = self.hybrid_retriever.retrieve(query, n_results=5)
            sys_p, user_p = PromptBuilder.build_prompts("summary", query, retrieval_res["context_text"])
            llm_res = self.ollama_client.generate(sys_p, user_p)
            return {
                "response_text": llm_res["response_text"] + "\n\n*Note: Could not locate a specific matching JD record in database to summarize.*",
                "source_documents": [d.to_dict() for d in retrieval_res["fused_documents"]]
            }
            
        # Bug fixed: was using [0.0]*384 zero-vector — use direct chunk fetch instead
        doc_chunks = self.chroma_manager.get_chunks_by_doc_id(jd.doc_id, limit=10)
        chunks_text = "\n\n".join(c.content for c in doc_chunks)
        
        sys_p, user_p = PromptBuilder.build_prompts("summary", query, chunks_text)
        
        try:
            llm_res = self.ollama_client.generate(sys_p, user_p)
            response_text = llm_res["response_text"]
        except Exception as e:
            logger.error(f"Summary LLM call failed: {e}")
            response_text = f"Failed to generate summary for {jd.company_name}."
            
        return {
            "response_text": response_text,
            "source_documents": [{"doc_id": jd.doc_id, "company_name": jd.company_name, "role_title": jd.role_title}]
        }

    def preference_extractor_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: PreferenceExtractor")
        query = state.get("query_text", "")
        profile = dict(state.get("user_profile", {}))
        
        # Extract student metrics dynamically
        extracted = QueryEntityExtractor.extract_entities(query, [])
        
        if extracted.min_package is not None:
            profile["min_package"] = extracted.min_package
        if extracted.max_cgpa_cutoff is not None:
            profile["cgpa"] = extracted.max_cgpa_cutoff
        if extracted.job_type:
            profile["preferred_job_type"] = extracted.job_type
            
        if extracted.locations:
            profile.setdefault("preferred_locations", [])
            for loc in extracted.locations:
                if loc not in profile["preferred_locations"]:
                    profile["preferred_locations"].append(loc)
                    
        if extracted.skills:
            profile.setdefault("skills", [])
            for skill in extracted.skills:
                if skill not in profile["skills"]:
                    profile["skills"].append(skill)
                    
        return {"user_profile": profile}

    def response_formatter_node(self, state: AgentState) -> dict:
        logger.info("LangGraph Node: ResponseFormatter")
        
        # Build Suggestions list
        suggestions = [
            "Are there any skill requirements?",
            "What is the average package?",
            "When is the application deadline?"
        ]
        
        # Format source citations
        source_docs = state.get("source_documents", [])
        
        response = AgentResponse(
            response_id=str(uuid.uuid4()),
            agent_type=state.get("intent", "search"),
            response_text=state.get("response_text", ""),
            structured_data=state.get("structured_data"),
            source_documents=source_docs,
            follow_up_suggestions=state.get("follow_up_suggestions") or suggestions,
            confidence=0.9,
            generation_time_ms=0 # populated by invoker if needed
        )
        
        # Update session conversation history turns
        history = list(state.get("turn_history", []))
        
        # Find referenced company from sources
        company_ref = None
        if source_docs:
            company_ref = source_docs[0].get("company_name")
            
        new_turn = {
            "turn_number": len(history) + 1,
            "query_text": state.get("query_text", ""),
            "resolved_query": state.get("resolved_query"),
            "agent_type": state.get("intent", "search"),
            "doc_ids_referenced": [d.get("doc_id") for d in source_docs if d.get("doc_id")],
            "company_name": company_ref,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        history.append(new_turn)
        
        # Apply truncation if turns exceed limit
        max_turns = 10
        if len(history) > max_turns:
            history = history[-max_turns:]
            
        return {
            "turn_history": history,
            "final_response": response.to_dict()
        }

    # --- GRAPH ROUTING EDGE ---

    def route_intent(self, state: AgentState) -> str:
        intent = state.get("intent", "search")
        if intent == "followup":
            return "followup_resolver"
        return intent

    def build_graph(self, checkpointer):
        # 1. Instantiate the LangGraph stateful graph
        builder = StateGraph(AgentState)
        
        # 2. Register graph nodes
        builder.add_node("intent_router", self.intent_router_node)
        builder.add_node("followup_resolver", self.followup_resolver_node)
        builder.add_node("search", self.search_node)
        builder.add_node("recommend", self.recommendation_node)
        builder.add_node("compare", self.comparison_node)
        builder.add_node("analytics", self.analytics_node)
        builder.add_node("summary", self.summary_node)
        builder.add_node("preference_extractor", self.preference_extractor_node)
        builder.add_node("response_formatter", self.response_formatter_node)
        
        # 3. Configure edges
        builder.set_entry_point("intent_router")
        
        # Route query to agent nodes based on intent classification
        builder.add_conditional_edges(
            "intent_router",
            self.route_intent,
            {
                "followup_resolver": "followup_resolver",
                "search": "search",
                "compare": "compare",
                "recommend": "recommend",
                "analytics": "analytics",
                "summary": "summary"
            }
        )
        
        # Route followup resolver output directly to target agent nodes
        builder.add_conditional_edges(
            "followup_resolver",
            self.route_intent,
            {
                "search": "search",
                "compare": "compare",
                "recommend": "recommend",
                "analytics": "analytics",
                "summary": "summary"
            }
        )
        
        # All agent nodes transition to preference extraction
        builder.add_edge("search", "preference_extractor")
        builder.add_edge("recommend", "preference_extractor")
        builder.add_edge("compare", "preference_extractor")
        builder.add_edge("analytics", "preference_extractor")
        builder.add_edge("summary", "preference_extractor")
        
        # Preference extraction transitions to final formatting
        builder.add_edge("preference_extractor", "response_formatter")
        builder.add_edge("response_formatter", END)
        
        # 4. Compile the stateful graph
        return builder.compile(checkpointer=checkpointer)
