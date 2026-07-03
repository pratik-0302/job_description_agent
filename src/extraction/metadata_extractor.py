import datetime
import logging
import re
import time
from typing import Dict, List, Optional, Tuple, Any

from src.ingestion.models import ParsedDocument
from src.extraction.models import PartialMetadata, ExtractionReport
from src.extraction.rule_extractor import RuleBasedExtractor
from src.extraction.nlp_extractor import NLPExtractor
from src.extraction.llm_extractor import LLMExtractor
from src.config import AppConfig

logger = logging.getLogger(__name__)

class MetadataExtractorModule:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.rule_extractor = RuleBasedExtractor()
        self.nlp_extractor = NLPExtractor()
        self.llm_extractor = LLMExtractor(cfg)

    def extract_metadata(self, doc: ParsedDocument) -> Tuple[dict, ExtractionReport]:
        start_time = time.time()
        logger.info(f"Starting metadata extraction for document: {doc.file_path}")

        # Step 1: Rule-Based Extraction
        partial = self.rule_extractor.extract(doc)
        fields_from_rules = [f for f, conf in partial.confidences.items() if conf >= 0.85]

        # Step 2: NLP-Based Extraction
        partial = self.nlp_extractor.extract(doc, partial)
        fields_from_nlp = [
            f for f, conf in partial.confidences.items() 
            if conf >= 0.75 and f not in fields_from_rules
        ]

        # Step 3: Identify Missing or Low Confidence Fields
        # We consider fields missing or low-confidence if not set, or score < 0.70
        core_fields = [
            "company_name", "role_title", "stipend_monthly", 
            "package_ctc", "bond_clause", "selection_process", "perks"
        ]
        
        missing_fields = []
        for field in core_fields:
            val = getattr(partial, field)
            conf = partial.confidences.get(field, 0.0)
            
            # Context-specific filters (don't ask for stipend if FTE, don't ask for package if internship)
            if field == "stipend_monthly" and partial.job_type == "fte":
                continue
            if field == "package_ctc" and partial.job_type == "internship":
                continue
                
            if val is None or conf < 0.70:
                missing_fields.append(field)

        # Step 4: LLM-Assisted Extraction
        llm_called = False
        if missing_fields:
            llm_called = True
            partial = self.llm_extractor.extract(doc, partial, missing_fields)
            
        fields_from_llm = [
            f for f, conf in partial.confidences.items() 
            if conf == 0.65 and f not in fields_from_rules and f not in fields_from_nlp
        ]

        # Step 5: Normalize and Validate metadata values
        normalized_data = self._normalize_and_validate(partial)

        # Calculate missing fields at end of pipeline
        fields_missing = []
        for field in core_fields:
            if normalized_data.get(field) is None and not (
                field == "stipend_monthly" and normalized_data.get("job_type") == "fte"
            ) and not (
                field == "package_ctc" and normalized_data.get("job_type") == "internship"
            ):
                fields_missing.append(field)

        duration_ms = int((time.time() - start_time) * 1000)
        
        report = ExtractionReport(
            doc_id=doc.doc_id,
            field_confidences=partial.confidences,
            fields_from_rules=fields_from_rules,
            fields_from_nlp=fields_from_nlp,
            fields_from_llm=fields_from_llm,
            fields_missing=fields_missing,
            llm_called=llm_called,
            total_duration_ms=duration_ms
        )

        logger.info(f"Completed extraction in {duration_ms} ms. Missing fields: {fields_missing}")
        return normalized_data, report

    def _normalize_and_validate(self, partial: PartialMetadata) -> dict:
        data = {}

        # Bug fixed: was defaulting to "Unknown Company", "Software Engineer", "fte", "onsite"
        # which polluted the DB and caused false filter matches. Keep None when unknown.
        data['company_name'] = partial.company_name or None
        data['role_title']   = partial.role_title   or None
        data['job_type']     = partial.job_type      or None

        data['package_ctc']     = partial.package_ctc
        data['stipend_monthly'] = partial.stipend_monthly

        if partial.cgpa_cutoff is not None and 0.0 <= partial.cgpa_cutoff <= 10.0:
            data['cgpa_cutoff'] = partial.cgpa_cutoff
        else:
            data['cgpa_cutoff'] = None

        data['eligible_branches']  = partial.eligible_branches
        data['required_skills']    = partial.required_skills
        data['experience_required']= partial.experience_required
        data['deadline']           = self._normalize_deadline(partial.deadline)
        data['location']           = partial.location
        data['work_mode']          = partial.work_mode or None
        data['duration_months']    = partial.duration_months
        data['selection_process']  = partial.selection_process
        # bond_clause stays None if LLM didn't detect it (avoids false "no bond" assumption)
        data['bond_clause']        = partial.bond_clause
        data['perks']              = partial.perks
        data['extraction_confidence'] = (
            sum(partial.confidences.values()) / len(partial.confidences)
            if partial.confidences else 0.5
        )
        data['extracted_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return data

    def _normalize_deadline(self, deadline_str: Optional[str]) -> Optional[str]:
        if not deadline_str:
            return None
            
        cleaned = deadline_str.strip()
        
        # Strip ordinal suffixes like 15th -> 15, 2nd -> 2
        cleaned = re.sub(r'\b([0-9]+)(?:st|nd|rd|th)\b', r'\1', cleaned, flags=re.IGNORECASE)
        
        # List of common patterns to test
        formats = [
            "%d %B %Y",  # "30 June 2026"
            "%B %d %Y",  # "June 30 2026"
            "%d/%m/%Y",  # "30/06/2026"
            "%d-%m-%Y",  # "30-06-2026"
            "%Y-%m-%d",  # "2026-06-30"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(cleaned, fmt)
                # Keep deadline normalized as standard YYYY-MM-DD string
                return dt.date().isoformat()
            except ValueError:
                continue
                
        # If unable to parse, return raw string or default fallback
        logger.warning(f"Could not parse date string: {deadline_str}")
        return None
