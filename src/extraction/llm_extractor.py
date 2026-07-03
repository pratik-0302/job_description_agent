import json
import logging
import re
from typing import Dict, List, Optional, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from src.ingestion.models import ParsedDocument
from src.extraction.models import PartialMetadata
from src.config import load_config, AppConfig

logger = logging.getLogger(__name__)

class LLMExtractor:
    def __init__(self, cfg: AppConfig):
        self.model_name = cfg.llm.model
        self.base_url = cfg.llm.base_url
        self.temperature = cfg.llm.temperature
        self.timeout = cfg.llm.timeout_seconds
        
        # Initialize ChatOllama client
        try:
            self.llm = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=self.temperature,
                timeout=self.timeout
            )
            logger.info(f"Initialized ChatOllama extractor with model={self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize ChatOllama: {e}")
            self.llm = None

    def extract(self, doc: ParsedDocument, partial: PartialMetadata, missing_fields: List[str]) -> PartialMetadata:
        if not self.llm:
            logger.warning("Ollama LLM client not initialized; skipping LLM extraction step.")
            return partial
            
        if not missing_fields:
            return partial

        logger.info(f"Invoking local LLM to extract fields: {missing_fields}")
        
        # Truncate text to avoid model context overflows (e.g. max 4000 characters)
        doc_snippet = doc.full_text[:4000]
        
        system_prompt = (
            "You are an expert AI extraction assistant for college placement portals.\n"
            "Analyze the job description provided and extract the requested fields.\n"
            "You must return your output ONLY as a valid JSON object matching the following structure:\n"
            "{\n"
            '  "company_name": "Hiring Company Name" (string or null),\n'
            '  "role_title": "Designation/Role Title" (string or null),\n'
            '  "stipend_monthly": Monthly stipend in INR (number or null),\n'
            '  "package_ctc": Annual package CTC in LPA/Lakhs per Annum (number or null),\n'
            '  "bond_clause": true if a bond or service agreement is mentioned, false if not, or null,\n'
            '  "selection_process": ["Round 1 details", "Round 2 details", ...] (list of strings or empty list),\n'
            '  "perks": ["Benefit 1", "Benefit 2", ...] (list of strings or empty list)\n'
            "}\n\n"
            "STRICT RULES:\n"
            "1. Output ONLY the raw JSON object. Do NOT wrap it in markdown code blocks like ```json ... ```.\n"
            "2. Do NOT write any conversational intros, explanations, or notes.\n"
            "3. If a value is not explicitly mentioned or cannot be inferred, set it to null."
        )
        
        human_prompt = (
            f"Please extract the following specific missing fields: {missing_fields}\n\n"
            f"--- START JOB DESCRIPTION ---\n"
            f"{doc_snippet}\n"
            f"--- END JOB DESCRIPTION ---"
        )
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            response = self.llm.invoke(messages)
            
            # Parse response
            raw_content = response.content.strip()
            extracted_data = self._clean_and_parse_json(raw_content)
            
            if extracted_data:
                self._merge_llm_data(partial, extracted_data, missing_fields)
            else:
                logger.warning("LLM response could not be parsed as valid JSON.")
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            
        return partial

    def _clean_and_parse_json(self, raw_content: str) -> Optional[Dict[str, Any]]:
        # Strip markdown wrapping if model ignored instructions
        json_str = raw_content
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            json_str = "\n".join(lines).strip()
            
        # Clean any leading/trailing extra text
        match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if match:
            json_str = match.group(0)
            
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError: {e} | Raw input: {raw_content}")
            return None

    def _merge_llm_data(self, partial: PartialMetadata, data: Dict[str, Any], missing_fields: List[str]):
        # LLM confidence is set lower than rule-based/NLP due to hallucination risks
        confidence_score = 0.65
        
        if "company_name" in missing_fields and data.get("company_name"):
            partial.company_name = data["company_name"].strip()
            partial.confidences["company_name"] = confidence_score
            
        if "role_title" in missing_fields and data.get("role_title"):
            partial.role_title = data["role_title"].strip()
            partial.confidences["role_title"] = confidence_score
            
        if "stipend_monthly" in missing_fields and data.get("stipend_monthly") is not None:
            try:
                partial.stipend_monthly = float(data["stipend_monthly"])
                partial.confidences["stipend_monthly"] = confidence_score
            except (ValueError, TypeError):
                pass
                
        if "package_ctc" in missing_fields and data.get("package_ctc") is not None:
            try:
                partial.package_ctc = float(data["package_ctc"])
                partial.confidences["package_ctc"] = confidence_score
            except (ValueError, TypeError):
                pass
                
        if "bond_clause" in missing_fields and data.get("bond_clause") is not None:
            partial.bond_clause = bool(data["bond_clause"])
            partial.confidences["bond_clause"] = confidence_score
            
        if "selection_process" in missing_fields and data.get("selection_process"):
            partial.selection_process = [str(r).strip() for r in data["selection_process"] if str(r).strip()]
            partial.confidences["selection_process"] = confidence_score
            
        if "perks" in missing_fields and data.get("perks"):
            partial.perks = [str(p).strip() for p in data["perks"] if str(p).strip()]
            partial.confidences["perks"] = confidence_score
