import unittest
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver

from src.config import AppConfig
from src.storage.sqlite_manager import SQLiteManager, JDMetadata, Document
from src.agents.agent_graph import GraphBuilder, AgentState
from src.retrieval.hybrid_retriever import HybridRetrievalModule
from src.llm.ollama_client import OllamaClient


class TestAgentGraph(unittest.TestCase):
    def setUp(self):
        # Build mock config & managers
        self.cfg = AppConfig()
        self.db_manager = MagicMock(spec=SQLiteManager)
        self.chroma_manager = MagicMock()
        self.hybrid_retriever = MagicMock(spec=HybridRetrievalModule)
        self.hybrid_retriever.embedding_pipeline = MagicMock()
        self.hybrid_retriever.embedding_pipeline.instruction = "Represent: "
        self.hybrid_retriever.embedding_pipeline.model = MagicMock()
        self.hybrid_retriever.embedding_pipeline.model.encode.return_value = [0.1] * 384
        
        self.ollama_client = MagicMock(spec=OllamaClient)

        # Mock known companies query
        self.db_session = MagicMock()
        self.db_manager.get_session.return_value = self.db_session
        self.db_session.query.return_value.distinct.return_value.all.return_value = [
            ("Google",),
            ("NVIDIA",)
        ]

        # Instantiate graph builder
        self.builder = GraphBuilder(
            cfg=self.cfg,
            db_manager=self.db_manager,
            chroma_manager=self.chroma_manager,
            hybrid_retriever=self.hybrid_retriever,
            ollama_client=self.ollama_client
        )

        # Compile with in-memory checkpointer
        self.checkpointer = MemorySaver()
        self.graph = self.builder.build_graph(checkpointer=self.checkpointer)

    def test_intent_routing_and_execution_flow(self):
        # 1. Setup mock search retriever and client responses
        mock_fused_doc = MagicMock()
        mock_fused_doc.doc_id = "d1"
        mock_fused_doc.chunks = []
        mock_fused_doc.to_dict.return_value = {"doc_id": "d1", "company_name": "Google"}
        
        self.hybrid_retriever.retrieve.return_value = {
            "context_text": "[SOURCE: Google] SW engineer roles.",
            "fused_documents": [mock_fused_doc]
        }
        
        self.ollama_client.generate.return_value = {
            "response_text": "Here are python developer positions."
        }

        # 2. Invoke Search intent
        initial_state = {
            "query_text": "python jobs at Google",
            "resolved_query": "",
            "intent": "",
            "user_profile": {},
            "turn_history": [],
            "interacted_doc_ids": []
        }
        
        config = {"configurable": {"thread_id": "session-1"}}
        final_state = self.graph.invoke(initial_state, config=config)

        # Assert correct intent classification and final response population
        self.assertEqual(final_state["intent"], "search")
        self.assertEqual(final_state["resolved_query"], "")
        self.assertIn("Here are python developer positions", final_state["response_text"])
        
        # Check preference extraction (Google is extracted as company but not locations/packages)
        self.assertEqual(final_state["user_profile"].get("skills"), ["python"])

        # Check turn history has been populated
        self.assertEqual(len(final_state["turn_history"]), 1)
        self.assertEqual(final_state["turn_history"][0]["query_text"], "python jobs at Google")

    def test_followup_resolution(self):
        # 1. Run first turn to establish history in state checkpointer
        mock_fused_doc = MagicMock()
        mock_fused_doc.doc_id = "d1"
        mock_fused_doc.chunks = []
        mock_fused_doc.to_dict.return_value = {"doc_id": "d1", "company_name": "Google"}
        
        self.hybrid_retriever.retrieve.return_value = {
            "context_text": "[SOURCE: Google] SW engineer roles.",
            "fused_documents": [mock_fused_doc]
        }
        self.ollama_client.generate.return_value = {
            "response_text": "Google information."
        }

        config = {"configurable": {"thread_id": "session-2"}}
        
        # First turn query
        self.graph.invoke({
            "query_text": "tell me about Google",
            "turn_history": [],
            "user_profile": {}
        }, config=config)

        # 2. Run follow-up query (references last company "Google" in turn_history)
        self.ollama_client.generate.return_value = {
            "response_text": "Google eligibility is 8.0 CGPA."
        }
        
        followup_state = {
            "query_text": "What is their eligibility?"
        }
        
        result_state = self.graph.invoke(followup_state, config=config)
        
        # Verify resolution
        self.assertEqual(result_state["resolved_query"], "What is their eligibility? for Google")
        self.assertEqual(result_state["intent"], "search")
        self.assertEqual(len(result_state["turn_history"]), 2)


if __name__ == "__main__":
    unittest.main()
